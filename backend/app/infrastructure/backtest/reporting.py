"""Automated report generation — HTML (interactive) and PDF (static).

Uses Jinja2 for HTML templating with Plotly.js for interactive charts.
PDF generation uses WeasyPrint (HTML to PDF conversion).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.app.core.config import settings
from backend.app.core.logging import get_logger
from backend.app.infrastructure.backtest.models import BacktestRunRecord, ReportConfig, ReportResult

log = get_logger("conflu.backtest.reporting")
TEMPLATES_DIR = Path(settings.backtest.reporting.templates_dir)


class ReportGenerator:
    """Generate HTML and PDF backtest reports from run results."""

    def __init__(self) -> None:
        self._log = get_logger("conflu.backtest.reporting")

    def generate(
        self,
        run_record: BacktestRunRecord,
        config: ReportConfig | None = None,
        extra_data: dict[str, Any] | None = None,
    ) -> list[ReportResult]:
        cfg = config or ReportConfig()
        results: list[ReportResult] = []
        report_id = str(uuid4())
        extra = extra_data or {}

        for fmt in cfg.formats:
            try:
                if fmt == "html":
                    result = self._generate_html(report_id, run_record, cfg, extra)
                elif fmt == "pdf":
                    result = self._generate_pdf(report_id, run_record, cfg, extra)
                elif fmt == "json":
                    result = self._generate_json(report_id, run_record, cfg, extra)
                else:
                    continue
                results.append(result)
            except Exception:
                self._log.exception("report_generation_failed", format=fmt)

        return results

    def _generate_html(
        self, report_id: str, run_record: BacktestRunRecord, config: ReportConfig, extra: dict[str, Any]
    ) -> ReportResult:
        from jinja2 import Environment, FileSystemLoader, select_autoescape

        template_dir = TEMPLATES_DIR if TEMPLATES_DIR.exists() else Path("config/report_templates")
        env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=select_autoescape(["html", "xml"]))
        template_name = (
            config.template_name if (template_dir / config.template_name).exists() else "backtest_report.html"
        )
        template = env.get_template(template_name)

        report_data = self._build_report_data(run_record, config, extra)
        html_content = template.render(**report_data)

        reports_dir = Path("data/reports")
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / f"{report_id}.html"
        report_path.write_text(html_content, encoding="utf-8")

        return ReportResult(
            report_id=report_id,
            run_id=run_record.run_id,
            format="html",
            template=config.template_name,
            report_path=str(report_path),
            size_bytes=report_path.stat().st_size,
            created_at=datetime.now(UTC).isoformat(),
        )

    def _generate_pdf(
        self, report_id: str, run_record: BacktestRunRecord, config: ReportConfig, extra: dict[str, Any]
    ) -> ReportResult:
        try:
            from weasyprint import HTML as WeasyHTML
        except ImportError:
            self._log.warning("weasyprint_not_installed_falling_back_to_html")
            return self._generate_html(report_id, run_record, config, extra)

        html_result = self._generate_html(report_id, run_record, config, extra)
        if not html_result.report_path:
            return html_result

        reports_dir = Path("data/reports")
        pdf_path = reports_dir / f"{report_id}.pdf"
        try:
            WeasyHTML(filename=str(html_result.report_path)).write_pdf(str(pdf_path))
            return ReportResult(
                report_id=report_id,
                run_id=run_record.run_id,
                format="pdf",
                template=config.template_name,
                report_path=str(pdf_path),
                size_bytes=pdf_path.stat().st_size,
                created_at=datetime.now(UTC).isoformat(),
            )
        except Exception:
            self._log.exception("pdf_conversion_failed")
            return html_result

    def _generate_json(
        self, report_id: str, run_record: BacktestRunRecord, config: ReportConfig, extra: dict[str, Any]
    ) -> ReportResult:
        report_data = self._build_report_data(run_record, config, extra)
        reports_dir = Path("data/reports")
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / f"{report_id}.json"
        report_path.write_text(json.dumps(report_data, default=str, indent=2), encoding="utf-8")
        return ReportResult(
            report_id=report_id,
            run_id=run_record.run_id,
            format="json",
            template=config.template_name,
            report_path=str(report_path),
            size_bytes=report_path.stat().st_size,
            created_at=datetime.now(UTC).isoformat(),
        )

    def _build_report_data(
        self, run_record: BacktestRunRecord, config: ReportConfig, extra: dict[str, Any]
    ) -> dict[str, Any]:
        metrics = run_record.metrics
        equity_curve = extra.get("equity_curve", [])
        trades = extra.get("trades", [])
        regime_result = extra.get("regime_result")
        optimization_result = extra.get("optimization_result")

        return {
            "title": f"Backtest Report — {run_record.symbol}",
            "run_id": run_record.run_id,
            "symbol": run_record.symbol,
            "timeframe": run_record.timeframe,
            "start_date": str(run_record.start_date),
            "end_date": str(run_record.end_date),
            "initial_cash": run_record.initial_cash,
            "position_sizing": run_record.position_sizing,
            "generated_at": datetime.now(UTC).isoformat(),
            "duration_ms": run_record.duration_ms,
            "sharpe": metrics.sharpe if metrics else None,
            "sortino": metrics.sortino if metrics else None,
            "calmar": metrics.calmar if metrics else None,
            "max_dd": metrics.max_dd if metrics else None,
            "win_rate": metrics.win_rate if metrics else None,
            "expectancy": metrics.expectancy if metrics else None,
            "profit_factor": metrics.profit_factor if metrics else None,
            "sqn": metrics.sqn if metrics else None,
            "ulcer": metrics.ulcer if metrics else None,
            "cagr": metrics.cagr if metrics else None,
            "include_equity_curve": config.include_equity_curve and bool(equity_curve),
            "include_drawdown": config.include_drawdown,
            "include_trade_analysis": config.include_trade_analysis and bool(trades),
            "include_regime_analysis": config.include_regime_analysis and regime_result is not None,
            "include_parameter_sensitivity": config.include_parameter_sensitivity and optimization_result is not None,
            "equity_curve": json.dumps(equity_curve[: config.max_chart_points]),
            "trades": trades,
            "regime_result": regime_result,
            "optimization_result": optimization_result,
            "total_trades": run_record.trades_count,
            "total_fees": run_record.total_fees,
            "final_equity": equity_curve[-1].get("equity", run_record.initial_cash)
            if equity_curve
            else run_record.initial_cash,
        }
