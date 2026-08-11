from flask import request, redirect, url_for, jsonify
from app import app
from config.countries import COUNTRIES
from config.languages import LANGUAGES
from config.settings import ADSENSE_CLIENT, DATABASE_URL, GROQ_KEYS, NEWS_GROQ_KEYS, JOB_GROQ_KEYS, GROQ_MODEL, JOBS_GROQ_MODEL, SEO_GROQ_MODEL, SEO_RESEARCH_ENABLED, SEO_MIN_SCORE, QUALITY_MIN_SCORE, TREND_MIN_SCORE
from database.connection import get_db_connection
from services.country_detection import detect_country
from services.translation_service import looks_like_lang, safe_translate
from robots.news_robot import robot_status
from robots.jobs_robot import jobs_robot_status
from utils.seo_helpers import absolute_url

@app.route("/ads.txt")
def ads_txt():
    if not ADSENSE_CLIENT:
        return (
            "AdSense publisher ID is not configured.",
            503,
            {"Content-Type": "text/plain; charset=utf-8"}
        )
    publisher_id = ADSENSE_CLIENT.replace("ca-", "").strip()
    return (
        f"google.com, {publisher_id}, DIRECT, f08c47fec0942fa0\n"
    ), 200, {
        "Content-Type": "text/plain; charset=utf-8"
    }


@app.route("/set-country/<country>")
def set_country(country):
    if country not in COUNTRIES:
        country = "ma"
    lang = request.args.get("lang", "en")
    response = redirect(url_for("home", country=country, lang=lang))
    response.set_cookie("country", country, max_age=60 * 60 * 24 * 365)
    return response


@app.route("/set-language/<lang>")
def set_language(lang):
    if lang not in LANGUAGES:
        lang = "en"
    country = request.args.get("country")
    if country not in COUNTRIES:
        country = detect_country()
    response = redirect(url_for("home", country=country, lang=lang))
    response.set_cookie("lang", lang, max_age=60 * 60 * 24 * 365)
    return response


@app.route("/fix-translations")
def fix_translations():
    fixed = 0
    checked = 0
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, title_en, content_en, title_ar, content_ar, title_fr, content_fr, title_es, content_es FROM articles")
        rows = cur.fetchall()
        cur.close()
        conn.close()

        for row in rows:
            (article_id, title_en, content_en,
             title_ar, content_ar, title_fr, content_fr, title_es, content_es) = row
            checked += 1
            updates = {}

            for lang, title_val, content_val in (
                ("ar", title_ar, content_ar),
                ("fr", title_fr, content_fr),
                ("es", title_es, content_es),
            ):
                bad_title = not looks_like_lang(title_val, lang)
                bad_content = not looks_like_lang(content_val, lang)
                if bad_title or bad_content:
                    new_title = safe_translate(title_en, lang) or title_en if bad_title else title_val
                    new_content = safe_translate(content_en, lang) or content_en if bad_content else content_val
                    updates[lang] = (new_title, new_content)

            if updates:
                conn2 = get_db_connection()
                cur2 = conn2.cursor()
                set_parts = []
                params = []
                for lang, (t, c) in updates.items():
                    set_parts.append(f"title_{lang} = %s")
                    set_parts.append(f"content_{lang} = %s")
                    params.extend([t, c])
                params.append(article_id)
                cur2.execute(
                    f"UPDATE articles SET {', '.join(set_parts)} WHERE id = %s",
                    params
                )
                conn2.commit()
                cur2.close()
                conn2.close()
                fixed += 1

        return jsonify({"checked": checked, "fixed": fixed})
    except Exception as e:
        return jsonify({"error": str(e), "checked": checked, "fixed": fixed}), 500


@app.route("/health")
def health():
    return {
        "status": "ok",
        "groq_keys_total": len(GROQ_KEYS),
        "groq_keys_news": len(NEWS_GROQ_KEYS),
        "groq_keys_jobs": len(JOB_GROQ_KEYS),
        "groq_model_news": GROQ_MODEL,
        "groq_model_jobs": JOBS_GROQ_MODEL,
        "groq_model_seo": SEO_GROQ_MODEL,
        "database": bool(DATABASE_URL),
        "robot": "running" if robot_status["running"] else "idle",
        "jobs_robot": "running" if jobs_robot_status["running"] else "idle",
        "seo_research_enabled": SEO_RESEARCH_ENABLED,
        "seo_min_score": SEO_MIN_SCORE,
        "quality_min_score": QUALITY_MIN_SCORE,
        "trend_min_score": TREND_MIN_SCORE,
    }

