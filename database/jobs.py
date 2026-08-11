import json
import hashlib
from database.connection import get_db_connection

def _extract_jobs_json(raw_text):
    if not raw_text:
        return []

    text = raw_text.strip()
    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()

    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1:
        return []

    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return []

def make_offer_hash(site_name, offer):
    base = "|".join([
        site_name,
        (offer.get("title_ar") or "").strip().lower(),
        (offer.get("company_ar") or "").strip().lower(),
        (offer.get("source_url") or "").strip().lower(),
    ])
    return hashlib.sha256(base.encode("utf-8")).hexdigest()

def job_offer_exists(offer_hash):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM job_offers WHERE offer_hash = %s LIMIT 1", (offer_hash,))
        result = cur.fetchone()
        cur.close()
        conn.close()
        return result is not None
    except Exception as e:
        print(f"!! [JOBS] Duplicate check failed: {e}")
        return False

def save_job_offer(category, offer):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO job_offers (
                category, source_site, source_url, title_ar, company_ar, description_ar,
                conditions_ar, documents_ar, how_to_apply_ar, deadline, offer_hash, created_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP
            )
            ON CONFLICT (offer_hash) DO NOTHING
            """,
            (
                category,
                offer.get("source_site"),
                offer.get("source_url"),
                offer.get("title_ar"),
                offer.get("company_ar"),
                offer.get("description_ar"),
                offer.get("conditions_ar"),
                offer.get("documents_ar"),
                offer.get("how_to_apply_ar"),
                offer.get("deadline"),
                offer.get("offer_hash"),
            )
        )
        conn.commit()
        inserted = cur.rowcount > 0
        cur.close()
        conn.close()
        return inserted
    except Exception as e:
        print(f"!! [JOBS] Save offer failed: {e}")
        return False
