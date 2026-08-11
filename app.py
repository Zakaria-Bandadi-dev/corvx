import os

from flask import Flask

from database.schema import init_db, init_jobs_db
from routes.news_routes import news_bp
from routes.jobs_routes import jobs_bp
from routes.system_routes import system_bp
from config.settings import NEWS_GROQ_KEYS, JOB_GROQ_KEYS, GROQ_MODEL, JOBS_GROQ_MODEL, SEO_GROQ_MODEL


def create_app():
    app = Flask(__name__)

    app.register_blueprint(news_bp)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(system_bp)

    return app


# ============================================================
# START DATABASE
# ============================================================

init_db()
init_jobs_db()

app = create_app()

# ============================================================
# START ROBOT SCHEDULER
# ============================================================

from scheduler import start_scheduler  # noqa: E402  (after app/db init, same as original)

start_scheduler()

print("-> News Robot Scheduler Started")
print(f"-> Groq API keys — news: {len(NEWS_GROQ_KEYS)} | jobs: {len(JOB_GROQ_KEYS)}")
print(f"-> Groq models — news: {GROQ_MODEL} | jobs: {JOBS_GROQ_MODEL} | seo: {SEO_GROQ_MODEL}")

# ============================================================
# LOCAL DEVELOPMENT
# ============================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
