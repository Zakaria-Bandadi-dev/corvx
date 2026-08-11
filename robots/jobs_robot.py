import time
from datetime import datetime
from threading import Lock
from config.job_sites import JOB_SITES
from ai.groq_jobs import generate_with_groq_jobs
from database.jobs import job_offer_exists, save_job_offer, _extract_jobs_json, make_offer_hash

jobs_robot_lock = Lock()

jobs_robot_status = {
    "running": False,
    "current_site": None,
    "last_run_start": None,
    "last_run_end": None,
    "last_run_saved": 0,
    "total_offers_this_run": 0,
}

def search_site_for_jobs(site_name, site_url):
    user_prompt = f"""قلب على آخر عروض الخدمة الجداد فهاد الموقع: {site_name} ({site_url})

خاصك تدخل للموقع (visit_website) و/أو تدير بحث (web_search) باش تلقى
العروض الحقيقية الموجودة دابا، ماشي عروض قديمة ولا مختلقة."""

    raw = generate_with_groq_jobs(user_prompt)
    offers = _extract_jobs_json(raw)

    for offer in offers:
        offer["source_site"] = site_name
        offer["offer_hash"] = make_offer_hash(site_name, offer)

    return offers

def process_job_category(category):
    info = JOB_SITES[category]
    saved = 0

    for site_name, site_url in info["sites"]:
        jobs_robot_status["current_site"] = f"{site_name} ({info['label']})"
        print(f"\n-> [JOBS] Checking {site_name}...")

        try:
            offers = search_site_for_jobs(site_name, site_url)
        except Exception as e:
            print(f"!! [JOBS] {site_name} failed: {e}")
            continue

        for offer in offers:
            offer_hash = offer.get("offer_hash")
            if not offer_hash:
                continue

            if job_offer_exists(offer_hash):
                continue

            if save_job_offer(category, offer):
                saved += 1
                jobs_robot_status["total_offers_this_run"] += 1
                print(f"-> [JOBS] SAVED: {offer.get('title_ar', '')[:60]}")

        time.sleep(2)

    return saved

def run_jobs_robot():
    if not jobs_robot_lock.acquire(blocking=False):
        print("!! [JOBS] Robot already running")
        return

    jobs_robot_status["running"] = True
    jobs_robot_status["current_site"] = None
    jobs_robot_status["last_run_start"] = datetime.now()
    jobs_robot_status["total_offers_this_run"] = 0

    try:
        print("\n\n==========================================")
        print(f"JOBS ROBOT STARTED {datetime.now()}")
        print("==========================================")

        for category in JOB_SITES.keys():
            try:
                process_job_category(category)
            except Exception as e:
                print(f"!! [JOBS] Category {category} failed: {e}")
            time.sleep(2)

        print("\n==========================================")
        print(f"JOBS ROBOT FINISHED {datetime.now()}")
        print("==========================================\n")
    finally:
        jobs_robot_status["running"] = False
        jobs_robot_status["current_site"] = None
        jobs_robot_status["last_run_end"] = datetime.now()
        jobs_robot_status["last_run_saved"] = jobs_robot_status["total_offers_this_run"]
        jobs_robot_lock.release()
