from flask import request, render_template, jsonify
from app import app
from config.job_sites import JOB_SITES
from config.settings import GA_ID, ADSENSE_CLIENT, JOBS_ROBOT_INTERVAL_HOURS
from database.connection import get_db_connection
from robots.jobs_robot import jobs_robot_status, run_jobs_robot

def jobs_page():
    category = request.args.get("category")
    if category not in JOB_SITES:
        category = None

    offers = []
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        if category:
            cur.execute(
                """
                SELECT id, category, source_site, source_url, title_ar, company_ar, description_ar,
                       conditions_ar, documents_ar, how_to_apply_ar, deadline, created_at
                FROM job_offers WHERE category = %s ORDER BY created_at DESC LIMIT 60
                """,
                (category,)
            )
        else:
            cur.execute(
                """
                SELECT id, category, source_site, source_url, title_ar, company_ar, description_ar,
                       conditions_ar, documents_ar, how_to_apply_ar, deadline, created_at
                FROM job_offers ORDER BY created_at DESC LIMIT 60
                """
            )

        rows = cur.fetchall()
        cur.close()
        conn.close()

        for row in rows:
            offers.append({
                "id": row[0], "category": row[1], "source_site": row[2], "source_url": row[3],
                "title_ar": row[4], "company_ar": row[5], "description_ar": row[6],
                "conditions_ar": row[7], "documents_ar": row[8], "how_to_apply_ar": row[9],
                "deadline": row[10], "created_at": row[11],
            })
    except Exception as e:
        print(f"!! [JOBS] Page database error: {e}")

    return render_template(
        "jobs.html",
        offers=offers,
        job_categories=JOB_SITES,
        current_category=category,
        ga_id=GA_ID,
        adsense_client=ADSENSE_CLIENT,
        jobs_robot_status=jobs_robot_status,
        jobs_robot_interval=JOBS_ROBOT_INTERVAL_HOURS,
    )


def jobs_status_json():
    data = dict(jobs_robot_status)
    data["last_run_start"] = jobs_robot_status["last_run_start"].isoformat() if jobs_robot_status["last_run_start"] else None
    data["last_run_end"] = jobs_robot_status["last_run_end"].isoformat() if jobs_robot_status["last_run_end"] else None
    return jsonify(data)


def manual_jobs_robot():
    run_jobs_robot()
    return """
    <h2>Jobs robot finished.</h2>
    <a href="/jobs">Back to jobs page</a>
    """

