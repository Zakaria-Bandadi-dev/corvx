from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from config.settings import ROBOT_INTERVAL_HOURS, JOBS_ROBOT_INTERVAL_HOURS
from services.news_robot import run_robot
from services.jobs_robot import run_jobs_robot


def start_scheduler():
    scheduler = BackgroundScheduler(daemon=True)

    scheduler.add_job(
        run_robot,
        trigger="date",
        run_date=datetime.now(),
        id="initial_robot",
        replace_existing=True
    )

    scheduler.add_job(
        run_robot,
        trigger="interval",
        hours=ROBOT_INTERVAL_HOURS,
        id="news_robot",
        replace_existing=True
    )

    scheduler.add_job(
        run_jobs_robot,
        trigger="date",
        run_date=datetime.now(),
        id="initial_jobs_robot",
        replace_existing=True
    )

    scheduler.add_job(
        run_jobs_robot,
        trigger="interval",
        hours=JOBS_ROBOT_INTERVAL_HOURS,
        id="jobs_robot",
        replace_existing=True
    )

    scheduler.start()
    return scheduler
