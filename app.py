from flask import Flask

app = Flask(__name__)

# Register all routes after the Flask app object exists.
from routes import home  # noqa: E402,F401
from routes import articles  # noqa: E402,F401
from routes import ai_tools  # noqa: E402,F401
from routes import jobs  # noqa: E402,F401
from routes import seo  # noqa: E402,F401
from routes import robot_status  # noqa: E402,F401
from routes import system  # noqa: E402,F401

from database.initialization import init_db, init_jobs_db  # noqa: E402
from robots.scheduler import start_scheduler  # noqa: E402

init_db()
init_jobs_db()
start_scheduler()

if __name__ == "__main__":
    import os

    port = int(os.getenv("PORT", "5000"))
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
