import re

from flask import request, render_template
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
        "key": "apres_bac",
        "label": "Après Bac (Concours Bac)",
        "title": "Après Bac",
    },
    {
        "key": "bac_plus_2",
        "label": "Bac +2 (DEUG, DUT, BTS, CPGE, etc.)",
        "title": "Bac +2",
    },
    {
        "key": "licence_excellence",
        "label": "Licence d'Excellence & Bachelor",
        "title": "Licence d'Excellence",
    },
    {
        "key": "cycles_ingenieurs",
        "label": "Cycles d'Ingénieurs",
        "title": "Cycles d'Ingénieurs",
    },
    {
        "key": "master",
        "label": "Master & Master Spécialisé",
        "title": "Master",
    },
    {
        "key": "doctorat",
        "label": "Doctorat",
        "title": "Doctorat",
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
        SELECT category, title, institution, deadline, description, apply_link
        FROM orientation_announcements
    """
    params = []

    if category and category != "all":
        query += " WHERE LOWER(category) = LOWER(%s)"
        params.append(category)

    query += " ORDER BY created_at DESC"

    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
            items = []
            for row in rows:
                db_category, title, institution, deadline, description, apply_link = row
                items.append(
                    {
                        "category": normalize_category_key(db_category),
                        "title": title or "Annonce",
                        "institution": institution or "Institution",
                        "deadline": deadline or "Aucun délai",
                        "description": description or "",
                        "cta": "Voir plus",
                        "apply_link": apply_link or "#",
                    }
                )
            return items
    except Exception as exc:
        print(f"!! Orientation database query failed: {exc}")
        return []


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
