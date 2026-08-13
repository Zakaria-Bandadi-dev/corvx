from database.connection import get_db_connection


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


def fetch_job_offers(category=None, limit=60):
    rows = []
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        if category:
            cur.execute(
                """
                SELECT id, category, source_site, source_url, title_ar, company_ar, description_ar,
                       conditions_ar, documents_ar, how_to_apply_ar, deadline, created_at
                FROM job_offers WHERE category = %s ORDER BY created_at DESC LIMIT %s
                """,
                (category, limit)
            )
        else:
            cur.execute(
                """
                SELECT id, category, source_site, source_url, title_ar, company_ar, description_ar,
                       conditions_ar, documents_ar, how_to_apply_ar, deadline, created_at
                FROM job_offers ORDER BY created_at DESC LIMIT %s
                """,
                (limit,)
            )
        rows = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"!! [JOBS] Page database error: {e}")
    return rows



def fetch_job_offer_by_id(offer_id):
    """
    Fetch a single job offer by its id.
    Returns a single row (same column order as fetch_job_offers)
    or None if not found.
    """
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, category, source_site, source_url,
                   title_ar, company_ar, description_ar,
                   conditions_ar, documents_ar, how_to_apply_ar,
                   deadline, created_at
            FROM job_offers
            WHERE id = %s
            """,
            (offer_id,),
        )
        row = cur.fetchone()
        cur.close()
        return row
    finally:
        conn.close()
 
