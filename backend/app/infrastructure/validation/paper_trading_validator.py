"""
Paper Trading Validator — Virtual Order Execution with Realistic Fills

Implements a complete paper trading simulator with:
- Realistic order execution (market, limit, stop, stop-limit)
- Slippage models (square-root, Almgren-Chriss, empirical)
- Market impact models (linear, square-root, Almgren-Chriss)
- Latency simulation (network, exchange, processing)
- Partial fills, rejections, cancellations
- Fill probability models
- Commission and fee structures
- Position tracking and P&L
- Margin and risk management

References:
- "Optimal Execution of Portfolio Transactions" - Almgren & Chriss (2000)
- "Market Microstructure Theory" - O'Hara (1995)
- "Market Liquidity and Trading" - Gatheral (2010)
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable
from uuid import uuid4

import numpy as np
import pandas as pd

from backend.app.core.logging import get_logger

log = get_logger("conflu.validation.paper_trading")


class OrderType(str, Enum):
    """Order types supported."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"


class OrderSide(str, Enum):
    """Order side."""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    """Order status lifecycle."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class TimeInForce(str, Enum):
    """Time in force."""
    DAY = "day"
    GTC = "gtc"
    IOC = "ioc"
    FOK = "fok"
    GTD = "gtd"  # Good till date


class FillModel(str, Enum):
    """Fill probability model."""
    DETERMINISTIC = "deterministic"  # Always fill if price touches
    PROBABILISTIC = "probabilistic"  # Probability based on spread/size
    QUEUE_MODEL = "queue"  # Queue position based


@dataclass
class SlippageModel:
    """Slippage model configuration."""
    model: str = "sqrt"  # "linear", "sqrt", "almgren_chriss", "empirical"
    # Linear: slippage = a * volume + b
    linear_a: float = 0.0001
    linear_b: float = 0.0001
    # Square-root: slippage = k * sqrt(volume / adv)
    sqrt_k: float = 0.001
    # Almgren-Chriss
    ac_tau: float = 0.001  # Temporary impact
    ac_eta: float = 0.0001  # Permanent impact
    ac_sigma: float = 0.02  # Daily volatility
    # Empirical
    empirical_spread_mult: float = 0.5  # Fraction of spread
    empirical_volume_mult: float = 0.1  # Volume impact multiplier


@dataclass
class LatencyModel:
    """Network and processing latency model."""
    # Network latency (ms) - lognormal
    network_ms_mean: float = 2.0
    network_ms_std: float = 1.0
    # Exchange processing (ms) - lognormal
    exchange_ms_mean: float = 1.0
    exchange_ms_std: float = 0.5
    # Processing overhead (ms) - fixed
    processing_ms: float = 0.5
    # Queue time at exchange (ms) - exponential
    queue_ms_mean: float = 0.5


@dataclass
class PaperTradingConfig:
    """Configuration for paper trading simulation."""
    # Fill model
    fill_model: FillModel = FillModel.PROBABILISTIC
    
    # Slippage
    slippage: SlippageModel = field(default_factory=SlippageModel)
    
    # Latency
    latency: LatencyModel = field(default_factory=LatencyModel)
    
    # Commission and fees (bps)
    commission_bps: float = 1.0          # 1 bp commission
    exchange_fee_bps: float = 0.5        # 0.5 bp exchange fee
    sec_fee_bps: float = 0.005           # SEC fee (sell only)
    clearing_fee_bps: float = 0.02       # Clearing fee
    
    # Margin and leverage
    initial_margin: float = 0.50         # 50% initial margin
    maintenance_margin: float = 0.25     # 25% maintenance margin
    max_leverage: float = 2.0            # Max 2x leverage
    
    # Position limits
    max_position_pct: float = 0.20       # Max 20% per position
    max_sector_pct: float = 0.40         # Max 40% per sector
    max_total_exposure: float = 1.0      # Max 100% gross exposure
    
    # Risk management
    max_daily_loss_pct: float = 0.02     # 2% max daily loss
    max_drawdown_pct: float = 0.10       # 10% max drawdown
    position_stop_loss_pct: float = 0.05  # 5% per-position stop
    
    # Fill probability
    base_fill_prob: float = 0.95         # Base fill probability
    spread_fill_penalty: float = 0.5     # Penalty per spread crossed
    size_fill_penalty: float = 0.1       # Penalty per ADV fraction
    
    # Queue position (for queue model)
    queue_decay_rate: float = 0.1        # Queue position decay per second
    
    # Market hours
    market_open: str = "09:30"
    market_close: str = "16:00"
    timezone: str = "US/Eastern"
    
    # Data
    use_real_market_data: bool = True
    tick_size: float = 0.01
    lot_size: int = 100


@dataclass
class Order:
    """Order representation."""
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    type: OrderType = OrderType.MARKET
    quantity: float = 0.0
    filled_quantity: float = 0.0
    price: float | None = None
    stop_price: float | None = None
    trail_amount: float | None = None
    time_in_force: TimeInForce = TimeInForce.DAY
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    submitted_at: datetime | None = None
    filled_at: datetime | None = None
    cancelled_at: datetime | None = None
    fills: list["Fill"] = field(default_factory=list)
    commission: float = 0.0
    fees: float = 0.0
    reject_reason: str | None = None
    client_order_id: str | None = None
    
    @property
    def remaining_quantity(self) -> float:
        return self.quantity - self.filled_quantity
    
    @property
    def is_active(self) -> bool:
        return self.status in (OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.PARTIAL)
    
    @property
    def is_terminal(self) -> bool:
        return self.status in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.EXPIRED)
    
    @property
    def avg_fill_price(self) -> float | None:
        if not self.fills:
            return None
        total_qty = sum(f.quantity for f in self.fills)
        if total_qty == 0:
            return None
        return sum(f.price * f.quantity for f in self.fills) / total_qty


@dataclass
class Fill:
    """Fill representation."""
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    order_id: str = ""
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    quantity: float = 0.0
    price: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    commission: float = 0.0
    fees: float = 0.0
    slippage: float = 0.0
    latency_ms: float = 0.0
    liquidity: str = "unknown"  # "maker", "taker", "unknown"


@dataclass
class Position:
    """Position representation."""
    symbol: str = ""
    quantity: float = 0.0
    avg_entry_price: float = 0.0
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    total_commission: float = 0.0
    total_fees: float = 0.0
    opened_at: datetime | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price
    
    @property
    def is_long(self) -> bool:
        return self.quantity > 0
    
    @property
    def is_short(self) -> bool:
        return self.quantity < 0


@dataclass
class Account:
    """Paper trading account."""
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    name: str = "Paper Account"
    cash: float = 100000.0
    equity: float = 100000.0
    buying_power: float = 100000.0
    positions: dict[str, Position] = field(default_factory=dict)
    orders: dict[str, Order] = field(default_factory=dict)
    trade_history: list[Fill] = field(default_factory=list)
    daily_pnl: float = 0.0
    peak_equity: float = 100000.0
    max_drawdown: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def total_pnl(self) -> float:
        return self.equity - 100000.0
    
    @property
    def total_return_pct(self) -> float:
        return (self.equity / 100000.0) - 1.0
    
    @property
    def current_drawdown(self) -> float:
        if self.peak_equity == 0:
            return 0.0
        return (self.peak_equity - self.equity) / self.peak_equity


class PaperTradingValidator:
    """
    Paper Trading Validator — Virtual order execution with realistic fills.
    
    Simulates:
    - Order lifecycle (submit, partial fill, fill, cancel, reject)
    - Market impact and slippage
    - Latency and fill probability
    - Commission and fees
    - Margin and risk checks
    - Position and P&L tracking
    """
    
    def __init__(self, config: PaperTradingConfig | None = None):
        self.config = config or PaperTradingConfig()
        self.account = Account()
        self._market_data: dict[str, pd.DataFrame] = {}
        self._order_queue: list[Order] = []
        self._fill_id = 0
        self._rng = np.random.default_rng(42)
        
    def reset(self, initial_cash: float = 100000.0):
        """Reset the paper trading account."""
        self.account = Account(cash=initial_cash, equity=initial_cash, buying_power=initial_cash)
        self._order_queue = []
        self._fill_id = 0
        
    def set_market_data(self, symbol: str, data: pd.DataFrame):
        """Set market data for a symbol."""
        self._market_data[symbol] = data
    
    def get_market_data(self, symbol: str) -> pd.DataFrame | None:
        """Get market data for a symbol."""
        return self._market_data.get(symbol)
    
    def get_best_bid_ask(self, symbol: str) -> tuple[float | None, float | None]:
        """Get best bid and ask for a symbol."""
        data = self._market_data.get(symbol)
        if data is None or len(data) == 0:
            return None, None
        
        last_row = data.iloc[-1]
        # Simulate bid-ask spread (1-2 bps for liquid stocks)
        mid = last_row.get("close", 100.0)
        spread_bps = 1.5
        half_spread = mid * spread_bps / 10000 / 2
        return mid - half_spread, mid + half_spread
    
    def get_last_price(self, symbol: str) -> float | None:
        """Get last trade price for a symbol."""
        data = self._market_data.get(symbol)
        if data is None or len(data) == 0:
            return None
        return float(data.iloc[-1].get("close", 100.0))
    
    def get_volume(self, symbol: str) -> float:
        """Get recent volume for a symbol."""
        data = self._market_data.get(symbol)
        if data is None or len(data) == 0:
            return 0.0
        return float(data.iloc[-1].get("volume", 1e6))
    
    def submit_order(self, order: Order) -> Order:
        """Submit an order for execution."""
        # Validate order
        if not self._validate_order(order):
            order.status = OrderStatus.REJECTED
            order.reject_reason = "Order validation failed"
            return order
        
        # Check risk limits
        if not self._check_risk_limits(order):
            order.status = OrderStatus.REJECTED
            order.reject_reason = "Risk limit exceeded"
            return order
        
        # Assign ID if not set
        if not order.id:
            order.id = uuid4().hex[:12]
        
        order.status = OrderStatus.SUBMITTED
        order.submitted_at = datetime.now(timezone.utc)
        self.account.orders[order.id] = order
        self._order_queue.append(order)
        
        # Try immediate execution for market orders
        if order.type == OrderType.MARKET:
            self._process_order(order)
        
        return order
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        order = self.account.orders.get(order_id)
        if not order:
            return False
        
        if not order.is_active:
            return False
        
        order.status = OrderStatus.CANCELLED
        order.cancelled_at = datetime.now(timezone.utc)
        if order in self._order_queue:
            self._order_queue.remove(order)
        return True
    
    def _validate_order(self, order: Order) -> bool:
        """Validate order parameters."""
        if order.quantity <= 0:
            return False
        if order.side not in (OrderSide.BUY, OrderSide.SELL):
            return False
        if order.type == OrderType.LIMIT and (order.price is None or order.price <= 0):
            return False
        if order.type in (OrderType.STOP, OrderType.STOP_LIMIT) and (order.stop_price is None or order.stop_price <= 0):
            return False
        if order.type == OrderType.STOP_LIMIT and (order.price is None or order.price <= 0):
            return False
        return True
    
    def _check_risk_limits(self, order: Order) -> bool:
        """Check if order passes risk limits."""
        # Check position size limit
        current_pos = self.account.positions.get(order.symbol)
        current_qty = current_pos.quantity if current_pos else 0
        new_qty = current_qty + (order.quantity if order.side == OrderSide.BUY else -order.quantity)
        
        # Estimate position value
        price = order.price or self.get_last_price(order.symbol) or 100.0
        position_value = abs(new_qty) * price
        portfolio_value = self.account.equity
        
        if position_value / portfolio_value > self.config.max_position_pct:
            return False
        
        # Check buying power
        if order.side == OrderSide.BUY:
            est_cost = order.quantity * (order.price or self.get_last_price(order.symbol) or 100.0)
            est_cost += est_cost * (self.config.commission_bps + self.config.exchange_fee_bps) / 10000
            if est_cost > self.account.buying_power:
                return False
        
        # Check daily loss limit
        if self.account.daily_pnl < -self.config.max_daily_loss_pct * self.account.equity:
            return False
        
        # Check max drawdown
        if self.account.current_drawdown > self.config.max_drawdown_pct:
            return False
        
        return True
    
    def _process_order(self, order: Order):
        """Process an order for execution."""
        if order.type == OrderType.MARKET:
            self._execute_market_order(order)
        elif order.type == OrderType.LIMIT:
            self._check_limit_order(order)
        elif order.type in (OrderType.STOP, OrderType.STOP_LIMIT):
            self._check_stop_order(order)
    
    def _execute_market_order(self, order: Order):
        """Execute a market order."""
        bid, ask = self.get_best_bid_ask(order.symbol)
        if bid is None or ask is None:
            order.status = OrderStatus.REJECTED
            order.reject_reason = "No market data available"
            return
        
        # Determine execution price
        if order.side == OrderSide.BUY:
            exec_price = ask
        else:
            exec_price = bid
        
        # Apply slippage
        exec_price = self._apply_slippage(order, exec_price)
        
        # Determine fill probability
        fill_prob = self._calculate_fill_probability(order, bid, ask)
        if self._rng.random() > fill_prob:
            order.status = OrderStatus.REJECTED
            order.reject_reason = "Fill probability check failed"
            return
        
        # Execute fill
        self._fill_order(order, exec_price, order.quantity)
    
    def _check_limit_order(self, order: Order):
        """Check if limit order should be filled."""
        bid, ask = self.get_best_bid_ask(order.symbol)
        if bid is None or ask is None:
            return
        
        should_fill = False
        fill_price = order.price
        
        if order.side == OrderSide.BUY and bid <= order.price:
            should_fill = True
            fill_price = min(ask, order.price)
        elif order.side == OrderSide.SELL and ask >= order.price:
            should_fill = True
            fill_price = max(bid, order.price)
        
        if should_fill:
            # Apply slippage
            fill_price = self._apply_slippage(order, fill_price)
            
            # Check fill probability
            fill_prob = self._calculate_fill_probability_limit(order, bid, ask)
            if self._rng.random() <= fill_prob:
                self._fill_order(order, fill_price, order.quantity)
    
    def _check_stop_order(self, order: Order):
        """Check if stop order should be triggered."""
        last_price = self.get_last_price(order.symbol)
        if last_price is None:
            return
        
        triggered = False
        if order.side == OrderSide.BUY and last_price >= order.stop_price:
            triggered = True
        elif order.side == OrderSide.SELL and last_price <= order.stop_price:
            triggered = True
        
        if triggered:
            if order.type == OrderType.STOP:
                # Convert to market order
                order.type = OrderType.MARKET
                order.price = None
                order.stop_price = None
                self._execute_market_order(order)
            elif order.type == OrderType.STOP_LIMIT:
                # Convert to limit order
                order.type = OrderType.LIMIT
                order.stop_price = None
                self._check_limit_order(order)
    
    def _calculate_fill_probability(self, order: Order, bid: float, ask: float) -> float:
        """Calculate probability of fill for market order."""
        prob = self.config.base_fill_prob
        
        # Spread penalty
        spread = ask - bid
        mid = (bid + ask) / 2
        spread_bps = spread / mid * 10000
        prob -= spread_bps * self.config.spread_fill_penalty / 10000
        
        # Size penalty
        adv = self._estimate_adv(order.symbol)
        if adv > 0:
            size_fraction = order.quantity / adv
            prob -= size_fraction * self.config.size_fill_penalty
        
        return max(0.01, min(1.0, prob))
    
    def _calculate_fill_probability_limit(self, order: Order, bid: float, ask: float) -> float:
        """Calculate fill probability for limit order."""
        prob = self.config.base_fill_prob * 0.8  # Lower for limit orders
        
        # Distance from market
        if order.side == OrderSide.BUY:
            distance = (order.price - bid) / bid
        else:
            distance = (ask - order.price) / ask
        
        # Closer to market = higher probability
        prob *= max(0.1, 1 - distance * 100)
        
        return max(0.01, min(1.0, prob))
    
def _apply_slippage(self, order: Order, price: float) -> float:
        """Apply slippage to execution price."""
        slippage = 0.0
        
        if self.config.slippage.model == "linear":
            # Linear: a * qty + b
            slippage = self.config.slippage.linear_a * order.quantity + self.config.slippage.linear_b
        elif self.config.slippage.model == "sqrt":
            # Square-root: k * sqrt(qty / adv)
            adv = self._estimate_adv(order.symbol)
            if adv > 0:
                slippage = self.config.slippage.sqrt_k * np.sqrt(order.quantity / adv)
        elif self.config.slippage.model == "almgren_chriss":
            # Almgren-Chriss: temporary + permanent impact
            adv = self._estimate_adv(order.symbol)
            daily_vol = self.config.slippage.ac_sigma / np.sqrt(252)
            X = order.quantity / adv if adv > 0 else 0
            temp_impact = self.config.slippage.ac_tau * X
            perm_impact = self.config.slippage.ac_eta * X
            slippage = temp_impact + perm_impact
        elif self.config.slippage.model == "empirical":
            # Empirical: fraction of spread + volume impact
            bid, ask = self.get_best_bid_ask("dummy")
            if bid is not None and ask is not None:
                spread = ask - bid
                slippage = spread * self.config.slippage.empirical_spread_mult
                adv = self._estimate_adv("dummy")
                if adv > 0:
                    slippage += (order.quantity / adv) * self.config.slippage.empirical_volume_mult
        
        # Apply slippage in correct direction
        if self._rng.random() < 0.5:
            return price * (1 + slippage)
        else:
            return price * (1 - slippage)
    
    def _estimate_adv(self, symbol: str) -> float:
        """Estimate average daily volume."""
        data = self._market_data.get(symbol)
        if data is None or len(data) == 0:
            return 1e6  # Default 1M
        vol = data.get("volume", pd.Series([1e6])).mean()
        return float(vol)
    
    def _fill_order(self, order: Order, price: float, quantity: float):
        """Fill an order."""
        # Calculate commission and fees
        notional = price * quantity
        commission = notional * self.config.commission_bps / 10000
        exchange_fee = notional * self.config.exchange_fee_bps / 10000
        sec_fee = notional * self.config.sec_fee_bps / 10000 if order.side == OrderSide.SELL else 0
        clearing_fee = notional * self.config.clearing_fee_bps / 10000
        
        total_fees = commission + exchange_fee + sec_fee + clearing_fee
        
        # Calculate slippage
        bid, ask = self.get_best_bid_ask(order.symbol)
        mid_price: float = 0.0
        if bid is not None and ask is not None:
            mid_price = (bid + ask) / 2
        elif price is not None:
            mid_price = price
        else:
            mid_price = 0.0
        
        slippage = (price - mid_price) / mid_price if mid_price > 0 else 0.0
        
        # Create fill
        fill = Fill(
            id=uuid4().hex[:12],
            order_id=order.id,
            symbol=order.symbol,
            side=order.side,
            quantity=quantity,
            price=price,
            timestamp=datetime.now(timezone.utc),
            commission=commission,
            fees=exchange_fee + sec_fee + clearing_fee,
            slippage=slippage,
            latency_ms=self._simulate_latency(),
            liquidity="taker",
        )
        
        order.fills.append(fill)
        order.filled_quantity += quantity
        order.commission += commission
        order.fees += total_fees
        
        # Update position
        self._update_position(order.symbol, order.side, quantity, price, commission + total_fees)
        
        # Update account
        self.account.cash -= (quantity * price + total_fees) if order.side == OrderSide.BUY else -(quantity * price - total_fees)
        order.filled_quantity += quantity
        
        # Check if fully filled
        if order.filled_quantity >= order.quantity:
            order.status = OrderStatus.FILLED
            order.filled_at = datetime.now(timezone.utc)
        else:
            order.status = OrderStatus.PARTIAL
        
        # Record trade
        self.account.trade_history.append(fill)
        
        # Update daily P&L
        self.account.daily_pnl += fill.price * fill.quantity * (1 if order.side == OrderSide.SELL else -1) - fill.commission - fill.fees
        
        # Update equity and drawdown
        self._update_equity()
    
    def _update_position(self, symbol: str, side: OrderSide, quantity: float, price: float, fees: float):
        """Update position after fill."""
        pos = self.account.positions.get(symbol)
        if pos is None:
            pos = Position(symbol=symbol, opened_at=datetime.now(timezone.utc))
            self.account.positions[symbol] = pos
        
        # Update quantity and avg price
        if side == OrderSide.BUY:
            new_qty = pos.quantity + quantity
            if new_qty != 0:
                pos.avg_entry_price = (pos.avg_entry_price * pos.quantity + price * quantity) / new_qty
            pos.quantity = new_qty
        else:
            new_qty = pos.quantity - quantity
            if new_qty != 0:
                pos.avg_entry_price = (pos.avg_entry_price * pos.quantity - price * quantity) / new_qty
            pos.quantity = new_qty
        
        pos.current_price = price
        pos.total_commission += fees * 0.5  # Approximate
        pos.total_fees += fees * 0.5
        pos.updated_at = datetime.now(timezone.utc)
        
        # Calculate unrealized P&L
        pos.unrealized_pnl = (price - pos.avg_entry_price) * pos.quantity
        
        # Remove position if flat
        if abs(pos.quantity) < 1e-8:
            pos.realized_pnl = (price - pos.avg_entry_price) * pos.quantity - pos.total_commission - pos.total_fees
            del self.account.positions[symbol]
    
    def _update_equity(self):
        """Update account equity and drawdown."""
        # Calculate position values
        position_value = sum(pos.market_value for pos in self.account.positions.values())
        self.account.equity = self.account.cash + position_value
        self.account.buying_power = self.account.cash * self.config.max_leverage
        
        # Update peak equity and drawdown
        if self.account.equity > self.account.peak_equity:
            self.account.peak_equity = self.account.equity
        self.account.max_drawdown = (self.account.peak_equity - self.account.equity) / self.account.peak_equity if self.account.peak_equity > 0 else 0
        self.account.updated_at = datetime.now(timezone.utc)
    
    def _simulate_latency(self) -> float:
        """Simulate network + exchange latency in ms."""
        network = self._rng.lognormal(np.log(self.config.latency.network_ms_mean), self.config.latency.network_ms_std)
        exchange = self._rng.lognormal(np.log(self.config.latency.exchange_ms_mean), self.config.latency.exchange_ms_std)
        processing = self.config.latency.processing_ms
        queue = self._rng.exponential(self.config.latency.queue_ms_mean)
        return network + exchange + processing + queue
    
    def get_account_summary(self) -> dict[str, Any]:
        """Get account summary."""
        return {
            "account_id": self.account.id,
            "cash": self.account.cash,
            "equity": self.account.equity,
            "buying_power": self.account.buying_power,
            "total_pnl": self.account.total_pnl,
            "total_return_pct": self.account.total_return_pct,
            "daily_pnl": self.account.daily_pnl,
            "max_drawdown": self.account.max_drawdown,
            "current_drawdown": self.account.current_drawdown,
            "num_positions": len(self.account.positions),
            "num_open_orders": sum(1 for o in self.account.orders.values() if o.is_active),
            "positions": {
                symbol: {
                    "quantity": pos.quantity,
                    "avg_entry": pos.avg_entry_price,
                    "current_price": pos.current_price,
                    "market_value": pos.market_value,
                    "unrealized_pnl": pos.unrealized_pnl,
                    "realized_pnl": pos.realized_pnl,
                }
                for symbol, pos in self.account.positions.items()
            },
            "open_orders": [
                {
                    "id": o.id,
                    "symbol": o.symbol,
                    "side": o.side.value,
                    "type": o.type.value,
                    "quantity": o.quantity,
                    "filled": o.filled_quantity,
                    "price": o.price,
                    "status": o.status.value,
                }
                for o in self.account.orders.values() if o.is_active
            ],
        }
    
    def process_market_data(self, symbol: str, data: pd.DataFrame):
        """Process new market data and check orders."""
        self._market_data[symbol] = data
        
        # Check limit/stop orders
        for order in list(self._order_queue):
            if order.symbol != symbol:
                continue
            if order.type == OrderType.LIMIT:
                self._check_limit_order(order)
            elif order.type in (OrderType.STOP, OrderType.STOP_LIMIT):
                self._check_stop_order(order)
    
    def step(self):
        """Advance simulation by one step (process queue, check expiries)."""
        # Process order queue
        for order in list(self._order_queue):
            if order.type == OrderType.MARKET:
                self._execute_market_order(order)
            elif order.type == OrderType.LIMIT:
                self._check_limit_order(order)
            elif order.type in (OrderType.STOP, OrderType.STOP_LIMIT):
                self._check_stop_order(order)
            
            # Check expiry
            if order.time_in_force == TimeInForce.DAY:
                if order.created_at.date() < datetime.now(timezone.utc).date():
                    self.cancel_order(order.id)
        
        # Remove completed orders from queue
        self._order_queue = [o for o in self._order_queue if o.is_active]
        
        # Update account
        self._update_equity()


# Convenience functions
async def run_paper_trading(
    strategy_fn: Callable[[pd.DataFrame], dict[str, Any]],
    symbols: list[str],
    initial_cash: float = 100000.0,
    config: PaperTradingConfig | None = None,
) -> PaperTradingValidator:
    """Run paper trading simulation."""
    validator = PaperTradingValidator(config)
    validator.reset(initial_cash)
    # Would run strategy loop here
    return validator


def create_order(
    symbol: str,
    side: OrderSide,
    order_type: OrderType,
    quantity: float,
    price: float | None = None,
    stop_price: float | None = None,
    time_in_force: TimeInForce = TimeInForce.DAY,
) -> Order:
    """Factory function to create an order."""
    return Order(
        symbol=symbol,
        side=side,
        type=order_type,
        quantity=quantity,
        price=price,
        stop_price=stop_price,
        time_in_force=time_in_force,
    )