import time
from datetime import datetime

import state
from config.settings import JOB_SITES
from database.jobs_repo import job_offer_exists, save_job_offer
from services.groq_client import generate_with_groq_jobs
from utils.text_helpers import extract_jobs_json, make_offer_hash


def search_site_for_jobs(site_name, site_url):
    user_prompt = f"""قلب على آخر عروض الخدمة الجداد فهاد الموقع: {site_name} ({site_url})

خاصك تدخل للموقع (visit_website) و/أو تدير بحث (web_search) باش تلقى
العروض الحقيقية الموجودة دابا، ماشي عروض قديمة ولا مختلقة."""

    raw = generate_with_groq_jobs(user_prompt)
    offers = extract_jobs_json(raw)

    for offer in offers:
        offer["source_site"] = site_name
        offer["offer_hash"] = make_offer_hash(site_name, offer)

    return offers


def process_job_category(category):
    info = JOB_SITES[category]
    saved = 0

    for site_name, site_url in info["sites"]:
        state.jobs_robot_status["current_site"] = f"{site_name} ({info['label']})"
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
                state.jobs_robot_status["total_offers_this_run"] += 1
                print(f"-> [JOBS] SAVED: {offer.get('title_ar', '')[:60]}")

        time.sleep(2)

    return saved


def run_jobs_robot():
    if not state.jobs_robot_lock.acquire(blocking=False):
        print("!! [JOBS] Robot already running")
        return

    state.jobs_robot_status["running"] = True
    state.jobs_robot_status["current_site"] = None
    state.jobs_robot_status["last_run_start"] = datetime.now()
    state.jobs_robot_status["total_offers_this_run"] = 0

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
        state.jobs_robot_status["running"] = False
        state.jobs_robot_status["current_site"] = None
        state.jobs_robot_status["last_run_end"] = datetime.now()
        state.jobs_robot_status["last_run_saved"] = state.jobs_robot_status["total_offers_this_run"]
        state.jobs_robot_lock.release()
