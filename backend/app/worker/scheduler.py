"""APScheduler job definitions for Professional Mode.

Three scheduled jobs:
1. Morning Brief (6 AM ET Mon-Fri) — generate + email dispatch
2. Earnings Alert Check (6 PM ET Mon-Fri) — upcoming earnings alerts
3. Regime Change Detection (hourly at :05 ET) — detect market regime shifts

All jobs use US/Eastern timezone, max_instances=1, coalesce=True.
"""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.app.core.config import settings
from backend.app.core.logging import get_logger

logger = get_logger("conflu.professional.scheduler")

scheduler = AsyncIOScheduler(timezone="US/Eastern")


def setup_jobs() -> None:
    """Register all Professional Mode scheduled jobs.

    Call once during FastAPI lifespan startup.
    """
    # ── 6:00 AM ET Mon-Fri — Morning Brief ──
    scheduler.add_job(
        generate_and_send_morning_brief,
        CronTrigger.from_crontab(settings.professional.morning_brief_cron, timezone="US/Eastern"),
        id="morning_brief",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )
    logger.info("scheduler_job_registered", job_id="morning_brief", cron=settings.professional.morning_brief_cron)

    # ── 6:00 PM ET Mon-Fri — Earnings Alert Check ──
    scheduler.add_job(
        check_earnings_tomorrow,
        CronTrigger.from_crontab(settings.professional.earnings_check_cron, timezone="US/Eastern"),
        id="earnings_check",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )
    logger.info("scheduler_job_registered", job_id="earnings_check", cron=settings.professional.earnings_check_cron)

    # ── Hourly at :05 ET — Regime Change Detection ──
    scheduler.add_job(
        check_regime_change,
        CronTrigger.from_crontab(settings.professional.regime_check_cron, timezone="US/Eastern"),
        id="regime_check",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=120,
    )
    logger.info("scheduler_job_registered", job_id="regime_check", cron=settings.professional.regime_check_cron)


# ── Job Functions ──


async def generate_and_send_morning_brief() -> None:
    """Generate morning brief and dispatch to subscribed users."""
    logger.info("morning_brief_job_start")
    try:
        if not settings.professional.morning_brief_enabled:
            logger.info("morning_brief_disabled")
            return

        from backend.app.infrastructure.professional.morning_brief import MorningBriefService
        from backend.app.worker.email_sender import EmailSender

        service = MorningBriefService()
        brief = await service.generate_morning_brief()

        logger.info(
            "morning_brief_generated",
            date=brief.date,
            regime=brief.regime,
            sections=len(brief.screen_sections),
        )

        # TODO: Fetch subscribed user emails from user preferences (Phase 6+)
        # For v1: log the brief content; email dispatch integrated later
        sender = EmailSender()
        # For each subscribed user: await sender.send_morning_brief(user.email, brief)

        logger.info("morning_brief_job_complete")
    except Exception:
        logger.exception("morning_brief_job_failed")


async def check_earnings_tomorrow() -> None:
    """Check for earnings events tomorrow and send alerts."""
    logger.info("earnings_check_job_start")
    try:
        # TODO: Implement when earnings calendar integration exists
        # from backend.app.infrastructure.professional.alert_service import AlertService
        # service = AlertService()
        # await service.send_earnings_alerts()
        logger.info("earnings_check_job_complete (stub)")
    except Exception:
        logger.exception("earnings_check_job_failed")


async def check_regime_change() -> None:
    """Detect regime changes and alert if changed from previous state."""
    logger.info("regime_check_job_start")
    try:
        # TODO: Implement regime change detection + alerting
        # from backend.app.infrastructure.professional.alert_service import AlertService
        # service = AlertService()
        # await service.check_and_alert_regime_change()
        logger.info("regime_check_job_complete (stub)")
    except Exception:
        logger.exception("regime_check_job_failed")
