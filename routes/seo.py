import urllib.parse
from flask import jsonify
from app import app
from config.countries import COUNTRIES
from config.languages import LANGUAGES
from config.settings import SEO_RESEARCH_ENABLED, SEO_MIN_SCORE, QUALITY_MIN_SCORE, TREND_MIN_SCORE
from database.connection import get_db_connection
from utils.seo_helpers import absolute_url, article_path

@app.route("/robots.txt")
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


@app.route("/sitemap.xml")
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
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT id, country, created_at
            FROM articles
            ORDER BY created_at DESC
        """)

        rows = cur.fetchall()
        cur.close()
        conn.close()

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

    except Exception as e:
        print(f"!! Sitemap database error: {e}")

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


@app.route("/seo-status")
def seo_status():
    try:
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute("""
            SELECT COUNT(*), COALESCE(AVG(seo_score),0), COALESCE(AVG(quality_score),0), COALESCE(AVG(trend_score),0)
            FROM articles
        """)
        total, avg_seo, avg_quality, avg_trend = cur.fetchone()
        cur.close(); conn.close()
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

