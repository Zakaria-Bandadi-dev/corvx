import urllib.parse

from flask import Blueprint, jsonify

from config.settings import (
    COUNTRIES, LANGUAGES,
    GROQ_KEYS, NEWS_GROQ_KEYS, JOB_GROQ_KEYS,
    GROQ_MODEL, JOBS_GROQ_MODEL, SEO_GROQ_MODEL,
    DATABASE_URL, SEO_RESEARCH_ENABLED, SEO_MIN_SCORE,
    QUALITY_MIN_SCORE, TREND_MIN_SCORE,
)
import state
from database.articles_repo import (
    fetch_sitemap_rows, fetch_seo_status,
    fetch_all_articles_for_translation_fix, update_translations,
)
from services.news_robot import run_robot
from services.translation import safe_translate
from utils.seo_helpers import absolute_url, article_path
from utils.text_helpers import looks_like_lang

system_bp = Blueprint("system", __name__)


@system_bp.route("/robots.txt")
def robots_txt():
    sitemap_url = absolute_url("/sitemap.xml")
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /health\n"
        "Disallow: /run-robot\n"
        "Disallow: /run-jobs-robot\n\n"
        f"Sitemap: {sitemap_url}\n"
    ), 200, {"Content-Type": "text/plain; charset=utf-8"}


@system_bp.route("/sitemap.xml")
def sitemap_xml():
    urls = []

    # Home pages for each configured country/language.
    for country_code in COUNTRIES:
        for lang_code in LANGUAGES:
            urls.append(
                absolute_url(
                    f"/?country={urllib.parse.quote(country_code)}"
                    f"&lang={urllib.parse.quote(lang_code)}"
                )
            )

    # Jobs page.
    urls.append(absolute_url("/jobs"))

    # Article URLs.
    rows = fetch_sitemap_rows()
    for article_id, country_code, created_at in rows:
        for lang_code in LANGUAGES:
            urls.append(
                absolute_url(
                    article_path(
                        article_id,
                        country_code,
                        lang_code
                    )
                )
            )

    # Remove duplicates while preserving order.
    urls = list(dict.fromkeys(urls))

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    ]

    for url in urls:
        parts.append(
            "<url><loc>" +
            url.replace("&", "&amp;") +
            "</loc></url>"
        )

    parts.append("</urlset>")

    return "\n".join(parts), 200, {
        "Content-Type": "text/xml; charset=utf-8"
    }


@system_bp.route("/seo-status")
def seo_status():
    try:
        total, avg_seo, avg_quality, avg_trend = fetch_seo_status()
        return jsonify({
            "articles": total,
            "avg_seo_score": round(float(avg_seo), 1),
            "avg_quality_score": round(float(avg_quality), 1),
            "avg_trend_score": round(float(avg_trend), 1),
            "seo_research_enabled": SEO_RESEARCH_ENABLED,
            "seo_min_score": SEO_MIN_SCORE,
            "quality_min_score": QUALITY_MIN_SCORE,
            "trend_min_score": TREND_MIN_SCORE,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@system_bp.route("/robot-status")
def robot_status_json():
    data = dict(state.robot_status)
    data["last_run_start"] = state.robot_status["last_run_start"].isoformat() if state.robot_status["last_run_start"] else None
    data["last_run_end"] = state.robot_status["last_run_end"].isoformat() if state.robot_status["last_run_end"] else None
    if state.robot_status["current_country"] in COUNTRIES:
        data["current_country_name"] = COUNTRIES[state.robot_status["current_country"]]["name"]
    else:
        data["current_country_name"] = None
    return jsonify(data)


@system_bp.route("/run-robot")
def manual_robot():
    run_robot()
    return """
    <h2>Robot finished.</h2>
    <a href="/">Back to website</a>
    """


@system_bp.route("/fix-translations")
def fix_translations():
    fixed = 0
    checked = 0
    try:
        rows = fetch_all_articles_for_translation_fix()

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
                update_translations(article_id, updates)
                fixed += 1

        return jsonify({"checked": checked, "fixed": fixed})
    except Exception as e:
        return jsonify({"error": str(e), "checked": checked, "fixed": fixed}), 500


@system_bp.route("/health")
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
        "robot": "running" if state.robot_status["running"] else "idle",
        "jobs_robot": "running" if state.jobs_robot_status["running"] else "idle",
        "seo_research_enabled": SEO_RESEARCH_ENABLED,
        "seo_min_score": SEO_MIN_SCORE,
        "quality_min_score": QUALITY_MIN_SCORE,
        "trend_min_score": TREND_MIN_SCORE,
    }
