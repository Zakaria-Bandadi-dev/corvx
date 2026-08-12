from flask import Blueprint, request, render_template, jsonify, abort

import state
from config.settings import JOB_SITES, GA_ID, ADSENSE_CLIENT, JOBS_ROBOT_INTERVAL_HOURS
from database.jobs_repo import fetch_job_offers, fetch_job_offer_by_id
from services.jobs_robot import run_jobs_robot

jobs_bp = Blueprint("jobs", __name__)


def _row_to_offer(row):
    return {
        "id": row[0], "category": row[1], "source_site": row[2], "source_url": row[3],
        "title_ar": row[4], "company_ar": row[5], "description_ar": row[6],
        "conditions_ar": row[7], "documents_ar": row[8], "how_to_apply_ar": row[9],
        "deadline": row[10], "created_at": row[11],
    }


@jobs_bp.route("/jobs")
def jobs_page():
    category = request.args.get("category")
    if category not in JOB_SITES:
        category = None

    offers = []
    rows = fetch_job_offers(category=category, limit=60)
    for row in rows:
        offers.append(_row_to_offer(row))

    return render_template(
        "jobs.html",
        offers=offers,
        job_categories=JOB_SITES,
        current_category=category,
        ga_id=GA_ID,
        adsense_client=ADSENSE_CLIENT,
        jobs_robot_status=state.jobs_robot_status,
        jobs_robot_interval=JOBS_ROBOT_INTERVAL_HOURS,
    )


@jobs_bp.route("/jobs/<int:offer_id>")
def job_detail(offer_id):
    row = fetch_job_offer_by_id(offer_id)
    if not row:
        abort(404)

    offer = _row_to_offer(row)

    return render_template(
        "job_detail.html",
        offer=offer,
        ga_id=GA_ID,
        adsense_client=ADSENSE_CLIENT,
    )


@jobs_bp.route("/jobs-status")
def jobs_status_json():
    data = dict(state.jobs_robot_status)
    data["last_run_start"] = state.jobs_robot_status["last_run_start"].isoformat() if state.jobs_robot_status["last_run_start"] else None
    data["last_run_end"] = state.jobs_robot_status["last_run_end"].isoformat() if state.jobs_robot_status["last_run_end"] else None
    return jsonify(data)


@jobs_bp.route("/run-jobs-robot")
def manual_jobs_robot():
    run_jobs_robot()
    return """
    <h2>Jobs robot finished.</h2>
    <a href="/jobs">Back to jobs page</a>
    """
