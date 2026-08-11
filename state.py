"""
Shared in-memory / runtime state.

Kept in its own tiny module (instead of inside a service file) so that
routes, schedulers and services can all import the SAME dict/lock
instances without circular imports.
"""

from threading import Lock

# Prevent two robot jobs from running simultaneously
robot_lock = Lock()

# Prevent two jobs-robot runs from running simultaneously
jobs_robot_lock = Lock()

# ============================================================
# ROBOT LIVE STATUS (transparency: show visitors the robot works)
# ============================================================

robot_status = {
    "running": False,
    "current_country": None,
    "last_run_start": None,
    "last_run_end": None,
    "last_run_saved": 0,
    "total_articles_this_run": 0,
}

jobs_robot_status = {
    "running": False,
    "current_site": None,
    "last_run_start": None,
    "last_run_end": None,
    "last_run_saved": 0,
    "total_offers_this_run": 0,
}

# Groq key rotation cursors
current_groq_key = 0
current_job_groq_key = 0
