"""Market regime detection — HMM and volatility quantile methods.

Provides regime classification for:
1. HMM (Hidden Markov Model): 2-4 state Gaussian HMM on returns/volatility
2. Volatility quantile buckets: Divides historical volatility into quantile-based regimes
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from backend.app.core.logging import get_logger
from backend.app.infrastructure.backtest.models import RegimeConfig, RegimeResult, RegimeSeries

log = get_logger("conflu.backtest.regimes")

REGIME_NAMES: dict[int, list[str]] = {
    2: ["Bear", "Bull"],
    3: ["Bear", "Neutral", "Bull"],
    4: ["Bear", "Low-Vol Bull", "High-Vol Bull", "Bubble"],
}
VOL_REGIME_NAMES: list[str] = ["Very Low Vol", "Low Vol", "Medium Vol", "High Vol", "Very High Vol"]


class RegimeDetector:
    """Detect market regimes using HMM or volatility quantile methods."""

    def __init__(self) -> None:
        self._log = get_logger("conflu.backtest.regimes")

    def detect(self, ohlcv: pd.DataFrame, config: RegimeConfig | None = None) -> RegimeResult:
        """Detect market regimes for the given OHLCV data."""
        cfg = config or RegimeConfig()
        if cfg.method == "hmm":
            return self._detect_hmm(ohlcv, cfg)
        elif cfg.method == "volatility_quantile":
            return self._detect_volatility_quantile(ohlcv, cfg)
        else:
            raise ValueError(f"Unknown method: '{cfg.method}'")

    def detect_series(self, ohlcv: pd.DataFrame, config: RegimeConfig | None = None) -> RegimeSeries:
        result = self.detect(ohlcv, config)
        return RegimeSeries(
            timestamps=pd.DatetimeIndex(result.timestamps),
            labels=result.regime_labels,
            names=result.regime_names,
        )

    def _detect_hmm(self, ohlcv: pd.DataFrame, config: RegimeConfig) -> RegimeResult:
        """Detect regimes using a Gaussian HMM on returns and volatility."""
        try:
            from hmmlearn import hmm
        except ImportError:
            self._log.warning("hmmlearn_not_installed_falling_back_to_volatility")
            return self._detect_volatility_quantile(ohlcv, config)

        close = ohlcv["close"]
        returns = close.pct_change().dropna()
        features_list: list[pd.Series] = []
        if "returns" in config.features:
            features_list.append(returns)
        if "volatility" in config.features:
            features_list.append(returns.rolling(window=config.vol_window_days).std())

        feature_df = pd.concat(features_list, axis=1).dropna()
        feature_df.columns = [f"f{i}" for i in range(len(features_list))]
        X = feature_df.values

        if len(X) < config.n_states * 5:
            return self._make_default_result(ohlcv, "hmm", config.n_states)

        n_states = max(2, min(config.n_states, 4))
        try:
            model = hmm.GaussianHMM(
                n_components=n_states, covariance_type="full", n_iter=100, random_state=42, tol=1e-4
            )
            model.fit(X)
            hidden_states = model.predict(X)
        except Exception:
            self._log.exception("hmm_fit_failed")
            return self._make_default_result(ohlcv, "hmm", n_states)

        state_means = model.means_[:, 0] if model.means_ is not None else np.zeros(n_states)
        state_order = np.argsort(state_means)
        label_mapping = {old: new for new, old in enumerate(state_order)}
        regime_labels = [label_mapping[s] for s in hidden_states]
        regime_names = REGIME_NAMES.get(n_states, [f"Regime {i}" for i in range(n_states)])

        full_labels: list[int] = []
        full_timestamps: list[str] = []
        label_idx = 0
        for i in range(len(ohlcv)):
            full_timestamps.append(str(ohlcv.index[i]))
            if i >= len(ohlcv) - len(X):
                full_labels.append(int(regime_labels[label_idx]))
                label_idx += 1
            else:
                full_labels.append(int(regime_labels[0]) if regime_labels else 0)

        transition_matrix = model.transmat_.tolist() if hasattr(model, "transmat_") else None
        state_means_list = [float(model.means_[s, 0]) for s in state_order] if model.means_ is not None else None
        state_stds_list = None
        if model.covars_ is not None and model.covars_.ndim >= 2:
            state_stds_list = [float(np.sqrt(model.covars_[s, 0, 0])) for s in state_order]

        return RegimeResult(
            symbol="unknown",
            method="hmm",
            n_states=n_states,
            regime_labels=full_labels,
            regime_names=regime_names,
            transition_matrix=transition_matrix,
            state_means=state_means_list,
            state_stds=state_stds_list,
            timestamps=full_timestamps,
        )

    def _detect_volatility_quantile(self, ohlcv: pd.DataFrame, config: RegimeConfig) -> RegimeResult:
        """Detect regimes using rolling volatility quantile buckets."""
        close = ohlcv["close"]
        returns = close.pct_change()
        vol = returns.rolling(window=config.vol_window_days).std().dropna()
        if vol.empty:
            return self._make_default_result(ohlcv, "volatility_quantile", config.n_quantiles)

        n_quantiles = max(2, min(config.n_quantiles, 5))
        quantiles = np.linspace(0, 1, n_quantiles + 1)[1:-1]
        thresholds = vol.quantile(quantiles).values
        vol_aligned = vol.reindex(ohlcv.index, method="ffill").fillna(vol.iloc[0] if not vol.empty else 0)
        regime_labels = [min(int(np.searchsorted(thresholds, v)), n_quantiles - 1) for v in vol_aligned]
        regime_names = VOL_REGIME_NAMES[:n_quantiles]
        timestamps = [str(ts) for ts in ohlcv.index]

        return RegimeResult(
            symbol="unknown",
            method="volatility_quantile",
            n_states=n_quantiles,
            regime_labels=regime_labels,
            regime_names=regime_names,
            timestamps=timestamps,
        )

    @staticmethod
    def _make_default_result(ohlcv: pd.DataFrame, method: str, n_states: int) -> RegimeResult:
        n_states = max(2, min(n_states, 4))
        regime_names = REGIME_NAMES.get(n_states, [f"Regime {i}" for i in range(n_states)])
        return RegimeResult(
            symbol="unknown",
            method=method,
            n_states=n_states,
            regime_labels=[0] * len(ohlcv),
            regime_names=regime_names,
            timestamps=[str(ts) for ts in ohlcv.index],
        )

    @staticmethod
    def compute_regime_metrics(ohlcv: pd.DataFrame, regime_labels: list[int], n_regimes: int) -> dict[str, Any]:
        """Compute per-regime statistics (returns, volatility, Sharpe)."""
        close = ohlcv["close"]
        returns = close.pct_change().dropna()
        aligned_labels = regime_labels[-len(returns) :] if len(regime_labels) >= len(returns) else regime_labels
        regime_data: dict[str, Any] = {}
        for r in range(n_regimes):
            mask = np.array(aligned_labels[: len(returns)]) == r
            regime_returns = returns.values[: len(mask)][mask]
            if len(regime_returns) > 0:
                avg_ret = float(np.mean(regime_returns))
                vol_val = float(np.std(regime_returns))
                sharpe = avg_ret / vol_val * np.sqrt(252) if vol_val > 0 else 0.0
            else:
                avg_ret = vol_val = sharpe = 0.0
            regime_data[f"regime_{r}"] = {
                "n_bars": int(np.sum(mask)),
                "avg_return": avg_ret,
                "volatility": vol_val,
                "sharpe": sharpe,
            }
        return regime_data
