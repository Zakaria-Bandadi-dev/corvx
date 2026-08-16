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

scheduler = None

def start_scheduler():
    global scheduler
    scheduler = BackgroundScheduler(daemon=True)

    scheduler.start()

    print("-> Scheduler started with scraping disabled")
    print(f"-> Groq API keys — news: {len(NEWS_GROQ_KEYS)} | jobs: {len(JOB_GROQ_KEYS)}")
    print(f"-> Groq models — news: {GROQ_MODEL} | jobs: {JOBS_GROQ_MODEL} | seo: {SEO_GROQ_MODEL}")
