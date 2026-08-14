from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

from config.settings import (
    ROBOT_INTERVAL_HOURS,
    JOBS_ROBOT_INTERVAL_HOURS,
    NEWS_GROQ_KEYS,
    JOB_GROQ_KEYS,
    GROQ_MODEL,
    JOBS_GROQ_MODEL,
    SEO_GROQ_MODEL,
)
from robots.news_robot import run_robot
from robots.jobs_robot import run_jobs_robot
from scraper import run_orientation_scraper

scheduler = None

def start_scheduler():
    global scheduler
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

    scheduler.add_job(
        run_orientation_scraper,
        trigger="date",
        run_date=datetime.now(),
        id="initial_orientation_scraper",
        replace_existing=True
    )

    scheduler.add_job(
        run_orientation_scraper,
        trigger="interval",
        hours=6,
        id="orientation_scraper",
        replace_existing=True
    )

    scheduler.start()

    print("-> News Robot Scheduler Started")
    print(f"-> Groq API keys — news: {len(NEWS_GROQ_KEYS)} | jobs: {len(JOB_GROQ_KEYS)}")
    print(f"-> Groq models — news: {GROQ_MODEL} | jobs: {JOBS_GROQ_MODEL} | seo: {SEO_GROQ_MODEL}")
    print("-> Orientation scraper scheduler started (every 6 hours)")
