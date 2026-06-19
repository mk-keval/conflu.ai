"""RiskReportGenerator — HTML risk report generation.

Generates comprehensive HTML risk reports with inline CSS.
Sections: Executive Summary, VaR/CVaR Breakdown, Beta & Hedging,
Correlation, Kelly Optimization, Risk Alerts.

Pure string-based HTML generation — no Jinja2 dependency required.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.core.config import settings
from backend.app.core.logging import get_logger
from backend.app.infrastructure.risk.models import (
    CorrelationResult,
    HedgeRecommendation,
    KellyRecommendation,
    PortfolioBetaResult,
    RiskAlert,
    RiskAssessment,
    VaRResult,
)

log = get_logger("conflu.risk.reporting")


class RiskReportGenerator:
    """Generate HTML risk reports for portfolio risk assessments."""

    def __init__(self) -> None:
        self._max_symbols = settings.risk.report_max_symbols
        self._log = get_logger("conflu.risk.reporting")

    def generate_html_report(
        self,
        assessment: RiskAssessment,
        title: str | None = None,
    ) -> str:
        """Generate a full HTML risk report with inline CSS.

        Args:
            assessment: Complete RiskAssessment from RiskEngine.
            title: Optional report title. Defaults to portfolio ID + date.

        Returns:
            Complete HTML string with inline styles.
        """
        report_title = title or f"Risk Report — {assessment.portfolio_id}"
        timestamp = assessment.timestamp.isoformat() if assessment.timestamp else datetime.now(timezone.utc).isoformat()

        sections = [
            self._render_executive_summary(assessment),
            self._render_var_breakdown(assessment),
            self._render_beta_hedging(assessment),
            self._render_correlation(assessment),
            self._render_kelly(assessment),
            self._render_alerts(assessment),
        ]

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{self._escape_html(report_title)}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; color: #333; line-height: 1.6; padding: 20px; }}
.container {{ max-width: 1200px; margin: 0 auto; }}
.header {{ background: linear-gradient(135deg, #1a237e, #283593); color: white; padding: 30px; border-radius: 12px; margin-bottom: 24px; }}
.header h1 {{ font-size: 1.8em; margin-bottom: 8px; }}
.header .meta {{ opacity: 0.85; font-size: 0.9em; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 16px; margin-bottom: 24px; }}
.card {{ background: white; border-radius: 10px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
.card h3 {{ font-size: 0.85em; text-transform: uppercase; color: #666; margin-bottom: 8px; }}
.card .value {{ font-size: 1.8em; font-weight: 700; }}
.card .value.good {{ color: #2e7d32; }}
.card .value.warning {{ color: #f57c00; }}
.card .value.danger {{ color: #c62828; }}
.section {{ background: white; border-radius: 10px; padding: 24px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
.section h2 {{ font-size: 1.3em; color: #1a237e; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #e8eaf6; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #eee; font-size: 0.9em; }}
th {{ background: #f5f5f5; font-weight: 600; color: #555; }}
tr:hover {{ background: #fafafa; }}
.alert {{ padding: 12px 16px; border-radius: 8px; margin-bottom: 8px; font-size: 0.9em; }}
.alert.critical {{ background: #ffebee; border-left: 4px solid #c62828; color: #b71c1c; }}
.alert.warning {{ background: #fff3e0; border-left: 4px solid #f57c00; color: #e65100; }}
.alert.info {{ background: #e3f2fd; border-left: 4px solid #1565c0; color: #0d47a1; }}
.score-bar {{ height: 12px; border-radius: 6px; background: #e0e0e0; margin: 8px 0; overflow: hidden; }}
.score-bar .fill {{ height: 100%; border-radius: 6px; transition: width 0.5s; }}
@media (max-width: 768px) {{ .grid {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<div class="container">
<div class="header">
<h1>{self._escape_html(report_title)}</h1>
<div class="meta">Generated: {timestamp} | Portfolio: {self._escape_html(assessment.portfolio_id)}</div>
</div>
{"".join(sections)}
</div>
</body>
</html>"""

        return html

    def save_report(self, assessment: RiskAssessment, filepath: str | None = None) -> str:
        """Generate and save a risk report to disk.

        Args:
            assessment: RiskAssessment to report on.
            filepath: Target filepath. Defaults to reports/risk_{portfolio_id}_{date}.html.

        Returns:
            Absolute path to the saved report file.
        """
        if filepath is None:
            date_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = f"risk_{assessment.portfolio_id}_{date_str}.html"
            reports_dir = Path("reports")
            reports_dir.mkdir(parents=True, exist_ok=True)
            filepath = str(reports_dir / filename)

        html = self.generate_html_report(assessment)
        Path(filepath).write_text(html, encoding="utf-8")

        self._log.info("risk_report_saved", filepath=filepath)
        return str(Path(filepath).resolve())

    def _render_executive_summary(self, assessment: RiskAssessment) -> str:
        """Render executive summary cards."""
        var_95_str = f"{assessment.var_95.var:.2%}" if assessment.var_95 else "N/A"
        var_99_str = f"{assessment.var_99.var:.2%}" if assessment.var_99 else "N/A"
        beta_str = f"{assessment.portfolio_beta.weighted_beta:.2f}" if assessment.portfolio_beta and assessment.portfolio_beta.weighted_beta is not None else "N/A"
        div_str = f"{assessment.correlation.diversification_score:.2f}" if assessment.correlation and assessment.correlation.diversification_score is not None else "N/A"
        score = assessment.risk_score or 0

        score_class = "good" if score < 30 else ("warning" if score < 60 else "danger")

        return f"""
<div class="grid">
<div class="card"><h3>VaR (95%)</h3><div class="value {'warning' if assessment.var_95 and assessment.var_95.var > 0.03 else 'good'}">{var_95_str}</div></div>
<div class="card"><h3>VaR (99%)</h3><div class="value">{var_99_str}</div></div>
<div class="card"><h3>Portfolio Beta</h3><div class="value">{beta_str}</div></div>
<div class="card"><h3>Diversification</h3><div class="value">{div_str}</div></div>
<div class="card"><h3>Risk Score</h3><div class="value {score_class}">{score:.0f}/100</div><div class="score-bar"><div class="fill" style="width:{score}%;background:{'#2e7d32' if score < 30 else '#f57c00' if score < 60 else '#c62828'}"></div></div></div>
</div>"""

    def _render_var_breakdown(self, assessment: RiskAssessment) -> str:
        """Render VaR/CVaR breakdown table."""
        var_results = []
        if assessment.var_95:
            var_results.append(assessment.var_95)
        if assessment.var_99:
            var_results.append(assessment.var_99)

        if not var_results:
            return ""

        rows = ""
        for vr in var_results:
            rows += f"<tr><td>{self._escape_html(vr.method)}</td><td>{vr.confidence:.0%}</td><td>{vr.horizon_days}d</td><td>{vr.var:.4%}</td><td>{vr.cvar:.4% if vr.cvar else 'N/A'}</td></tr>"

        return f"""
<div class="section">
<h2>VaR / CVaR Breakdown</h2>
<table>
<thead><tr><th>Method</th><th>Confidence</th><th>Horizon</th><th>VaR</th><th>CVaR</th></tr></thead>
<tbody>{rows}</tbody>
</table>
</div>"""

    def _render_beta_hedging(self, assessment: RiskAssessment) -> str:
        """Render beta and hedging table."""
        if not assessment.portfolio_beta:
            return ""

        pb = assessment.portfolio_beta
        rows = ""
        for symbol, beta_val in pb.symbol_betas.items():
            rows += f"<tr><td>{self._escape_html(symbol)}</td><td>{beta_val:.4f}</td></tr>"

        hedges = ""
        for hr in assessment.hedge_recommendations:
            rec_class = "danger" if hr.recommendation == "required" else ("warning" if hr.recommendation == "optional" else "")
            hedges += f"<tr><td>{self._escape_html(hr.symbol)}</td><td>{hr.beta:.4f if hr.beta else 'N/A'}</td><td>{hr.r_squared:.2% if hr.r_squared else 'N/A'}</td><td class='{rec_class}'>{hr.recommendation}</td><td>{self._escape_html(hr.hedge_instrument or 'N/A')}</td></tr>"

        html = f"""
<div class="section">
<h2>Beta & Hedging</h2>
<h3>Portfolio Beta: {pb.weighted_beta:.4f if pb.weighted_beta is not None else 'N/A'} vs {self._escape_html(pb.benchmark)}</h3>"""
        if rows:
            html += f"""<table>
<thead><tr><th>Symbol</th><th>Beta</th></tr></thead>
<tbody>{rows}</tbody>
</table>"""
        if hedges:
            html += f"""<h3>Hedge Recommendations</h3>
<table>
<thead><tr><th>Symbol</th><th>Beta</th><th>R²</th><th>Recommendation</th><th>Instrument</th></tr></thead>
<tbody>{hedges}</tbody>
</table>"""
        html += "</div>"
        return html

    def _render_correlation(self, assessment: RiskAssessment) -> str:
        """Render correlation section."""
        if not assessment.correlation:
            return ""

        corr = assessment.correlation
        pairs = ""
        for pair in corr.high_correlation_pairs:
            symbols_str = " / ".join(pair.get("symbols", []))
            pairs += f"<tr><td>{self._escape_html(symbols_str)}</td><td>{pair.get('correlation', 0):.4f}</td></tr>"

        div_score = corr.diversification_score
        div_class = "good" if div_score and div_score > 0.5 else ("warning" if div_score and div_score > 0.3 else "danger")

        html = f"""
<div class="section">
<h2>Correlation</h2>
<p>Diversification Score: <strong class="{div_class}">{div_score:.2f if div_score else 'N/A'}</strong> (0=correlated, 1=uncorrelated)</p>
<p>Window: {corr.window_days} days | Symbols: {len(corr.symbols)}</p>"""
        if pairs:
            html += f"""<h3>High Correlation Pairs</h3>
<table>
<thead><tr><th>Pair</th><th>Correlation</th></tr></thead>
<tbody>{pairs}</tbody>
</table>"""
        html += "</div>"
        return html

    def _render_kelly(self, assessment: RiskAssessment) -> str:
        """Render Kelly optimization section."""
        if not assessment.kelly:
            return ""

        kelly = assessment.kelly
        params_html = ""
        for k, v in kelly.suggested_params.items():
            params_html += f"<tr><td>{self._escape_html(k)}</td><td>{v:.4f}</td></tr>"

        valid_text = "✅ Valid" if kelly.is_valid else "⚠️ Insufficient Data (using defaults)"
        status_class = "good" if kelly.is_valid else "warning"

        return f"""
<div class="section">
<h2>Kelly Optimization</h2>
<table>
<thead><tr><th>Metric</th><th>Value</th></tr></thead>
<tbody>
<tr><td>Status</td><td class="{status_class}">{valid_text}</td></tr>
<tr><td>Full Kelly</td><td>{kelly.full_kelly:.4f if kelly.full_kelly is not None else 'N/A'}</td></tr>
<tr><td>Constrained Kelly</td><td>{kelly.constrained_kelly:.4f if kelly.constrained_kelly is not None else 'N/A'}</td></tr>
<tr><td>Recommended Kelly</td><td><strong>{kelly.recommended_kelly:.4f if kelly.recommended_kelly is not None else 'N/A'}</strong></td></tr>
<tr><td>Win Rate</td><td>{kelly.win_rate:.2% if kelly.win_rate is not None else 'N/A'}</td></tr>
<tr><td>Avg Win/Loss Ratio</td><td>{kelly.avg_win_loss_ratio:.2f if kelly.avg_win_loss_ratio is not None else 'N/A'}</td></tr>
<tr><td>Max DD Target</td><td>{kelly.max_dd_target:.0%}</td></tr>
</tbody>
</table>
<h3>Suggested Sizing Parameters</h3>
<table>
<thead><tr><th>Parameter</th><th>Value</th></tr></thead>
<tbody>{params_html}</tbody>
</table>
</div>"""

    def _render_alerts(self, assessment: RiskAssessment) -> str:
        """Render risk alerts section."""
        if not assessment.alerts:
            return ""

        alert_html = ""
        for alert in assessment.alerts:
            alert_html += f"""
<div class="alert {alert.severity}">
<strong>[{alert.severity.upper()}] {self._escape_html(alert.category.upper())}</strong>
<p>{self._escape_html(alert.message)}</p>
<small>{alert.symbol or ''}{' | Value: ' + f'{alert.current_value:.4f}' if alert.current_value is not None else ''}{' | Threshold: ' + f'{alert.threshold:.4f}' if alert.threshold is not None else ''}</small>
</div>"""

        return f"""
<div class="section">
<h2>Risk Alerts ({len(assessment.alerts)})</h2>
{alert_html}
</div>"""

    @staticmethod
    def _escape_html(text: str) -> str:
        """Escape HTML special characters."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#x27;")
        )
