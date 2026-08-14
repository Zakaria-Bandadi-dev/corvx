import re

from flask import abort, request, render_template
from app import app
from config.countries import COUNTRIES
from config.languages import LANGUAGES
from database.connection import get_db_connection
from services.country_detection import detect_country, detect_language
from utils.seo_helpers import absolute_url

ORIENTATION_CATEGORIES = [
    {
        "key": "all",
        "label": "All / Tout",
        "title": "All / Tout",
    },
    {
        "key": "bac",
        "label": "BAC",
        "title": "BAC",
    },
    {
        "key": "bac+2",
        "label": "BAC+2",
        "title": "BAC+2",
    },
    {
        "key": "bac+3",
        "label": "BAC+3",
        "title": "BAC+3",
    },
    {
        "key": "ingenieur",
        "label": "Ingénieur",
        "title": "Ingénieur",
    },
    {
        "key": "bourses_etranger",
        "label": "Bourses à l'étranger",
        "title": "Bourses à l'étranger",
    },
]


def normalize_category_key(raw_category):
    if raw_category is None:
        return "all"

    value = str(raw_category).strip()
    normalized = value.lower().replace("&", " and ").replace("-", " ").replace("_", " ")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized.replace(" ", "_") if normalized else "all"


def fetch_orientation_items(category="all"):
    query = """
        SELECT
            id, category, title, institution, deadline, description, apply_link,
            source_name, source_url, country, academic_level, announcement_type,
            publication_date, city, eligibility, required_diploma, study_field, image_url
        FROM orientation_announcements
        WHERE publication_date ILIKE '%2026%'
    """
    params = []

    if category and category != "all":
        query += " AND LOWER(category) = LOWER(%s)"
        params.append(category)

    query += " ORDER BY created_at DESC"

    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
            items = []
            for row in rows:
                (
                    item_id, db_category, title, institution, deadline, description, apply_link,
                    source_name, source_url, country, academic_level, announcement_type,
                    publication_date, city, eligibility, required_diploma, study_field, image_url,
                ) = row
                items.append(
                    {
                        "id": item_id,
                        "category": normalize_category_key(db_category),
                        "title": title or "Annonce",
                        "institution": institution or "Institution",
                        "deadline": deadline or "Aucun délai",
                        "description": description or "",
                        "cta": "Voir plus",
                        "apply_link": apply_link or "",
                        "source_name": source_name or "Orientation Chabab",
                        "source_url": source_url or "",
                        "country": country or "MA",
                        "academic_level": academic_level or "bac",
                        "announcement_type": announcement_type or "other",
                        "publication_date": publication_date or "",
                        "city": city or "",
                        "eligibility": eligibility or "",
                        "required_diploma": required_diploma or "",
                        "study_field": study_field or "",
                        "image_url": image_url or "",
                    }
                )
            return items
    except Exception as exc:
        print(f"!! Orientation database query failed: {exc}")
        return []


def fetch_orientation_item_by_id(item_id):
    query = """
        SELECT
            id, category, title, institution, deadline, description, apply_link,
            source_name, source_url, country, academic_level, announcement_type,
            publication_date, city, eligibility, required_diploma, study_field, image_url
        FROM orientation_announcements
        WHERE id = %s
        LIMIT 1
    """

    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(query, (item_id,))
            row = cur.fetchone()
            if not row:
                return None

            (
                item_id, db_category, title, institution, deadline, description, apply_link,
                source_name, source_url, country, academic_level, announcement_type,
                publication_date, city, eligibility, required_diploma, study_field, image_url,
            ) = row
            return {
                "id": item_id,
                "category": normalize_category_key(db_category),
                "title": title or "Annonce",
                "institution": institution or "Institution",
                "deadline": deadline or "Aucun délai",
                "description": description or "",
                "cta": "Postuler",
                "apply_link": apply_link or "",
                "source_name": source_name or "Orientation Chabab",
                "source_url": source_url or "",
                "country": country or "MA",
                "academic_level": academic_level or "bac",
                "announcement_type": announcement_type or "other",
                "publication_date": publication_date or "",
                "city": city or "",
                "eligibility": eligibility or "",
                "required_diploma": required_diploma or "",
                "study_field": study_field or "",
                "image_url": image_url or "",
            }
    except Exception as exc:
        print(f"!! Orientation detail query failed: {exc}")
        return None


@app.route("/orientation")
def orientation_page():
    country = request.args.get("country")
    if country not in COUNTRIES:
        country = detect_country()

    lang = request.args.get("lang")
    if lang not in LANGUAGES:
        lang = detect_language(country)

    country_info = COUNTRIES.get(country, COUNTRIES["ma"])
    active_category = request.args.get("category", "all")
    if active_category not in {category["key"] for category in ORIENTATION_CATEGORIES}:
        active_category = "all"

    items = fetch_orientation_items(active_category)

    return render_template(
        "orientation.html",
        items=items,
        orientation_items=items,
        orientation_categories=ORIENTATION_CATEGORIES,
        active_category=active_category,
        countries=COUNTRIES,
        languages=LANGUAGES,
        current_country=country,
        current_language=lang,
        country_name=country_info["name"],
        canonical_url=absolute_url(f"/orientation?country={country}&lang={lang}"),
    )


@app.route("/orientation/<int:item_id>")
def orientation_detail(item_id):
    item = fetch_orientation_item_by_id(item_id)
    if not item:
        abort(404)

    country = request.args.get("country")
    if country not in COUNTRIES:
        country = detect_country()

    lang = request.args.get("lang")
    if lang not in LANGUAGES:
        lang = detect_language(country)

    country_info = COUNTRIES.get(country, COUNTRIES["ma"])

    return render_template(
        "orientation_detail.html",
        item=item,
        countries=COUNTRIES,
        languages=LANGUAGES,
        current_country=country,
        current_language=lang,
        country_name=country_info["name"],
        canonical_url=absolute_url(f"/orientation/{item_id}?country={country}&lang={lang}"),
    )
