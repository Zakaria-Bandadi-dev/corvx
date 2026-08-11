import json
import urllib.parse
from flask import request, render_template
from app import app
from config.countries import COUNTRIES
from config.languages import LANGUAGES
from config.settings import GA_ID, ADSENSE_CLIENT, SITE_URL
from database.connection import get_db_connection
from database.articles import cache_translation, get_related_articles
from services.country_detection import detect_country, detect_language
from services.translation_service import looks_like_lang, safe_translate
from ai.seo import build_schema
from utils.seo_helpers import absolute_url, article_path, seo_description

@app.route("/article/<int:article_id>")
def article_detail(article_id):
    country = request.args.get("country")
    if country not in COUNTRIES:
        country = detect_country()

    lang = request.args.get("lang")
    if lang not in LANGUAGES:
        lang = detect_language(country)

    title_column = f"title_{lang}"
    content_column = f"content_{lang}"
    article = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        query = f"""
            SELECT
                id, {title_column}, {content_column}, title_en, content_en,
                image_url, category, source_url, source_name, original_title, created_at, country,
                seo_title, meta_description, slug, primary_keyword, secondary_keywords,
                search_intent, trend_score, seo_score, quality_score, seo_reason, faq_json, schema_json
            FROM articles
            WHERE id = %s
            LIMIT 1
        """
        cur.execute(query, (article_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()

        if row:
            title = row[1]
            content = row[2]
            fallback_title = row[3]
            fallback_content = row[4]

            if lang != "en" and (not looks_like_lang(title, lang) or not looks_like_lang(content, lang)):
                new_title = fallback_title if not looks_like_lang(title, lang) else title
                new_content = fallback_content if not looks_like_lang(content, lang) else content
                new_title = safe_translate(new_title, lang) or new_title
                new_content = safe_translate(new_content, lang) or new_content
                cache_translation(article_id, lang, new_title, new_content)
                title, content = new_title, new_content

            article = {
                "id": row[0], "title": title, "content": content, "image": row[5],
                "category": row[6], "source_url": row[7], "source_name": row[8],
                "original_title": row[9], "created_at": row[10], "country": row[11],
                "seo_title": row[12], "meta_description": row[13], "slug": row[14],
                "primary_keyword": row[15], "secondary_keywords": row[16],
                "search_intent": row[17], "trend_score": row[18], "seo_score": row[19],
                "quality_score": row[20], "seo_reason": row[21],
                "faq": json.loads(row[22] or "[]"), "schema": json.loads(row[23] or "{}")
            }
    except Exception as e:
        print(f"!! Article detail error: {e}")

    if not article:
        return ("Article not found", 404)

    article["schema"] = build_schema(article_id, article["country"], lang, article, article.get("faq", []))
    article["related"] = get_related_articles(
        article_id, article["country"], article.get("category"), article.get("primary_keyword", "")
    )

    alternate_urls = {
        code: absolute_url(article_path(article_id, article["country"], code))
        for code in LANGUAGES
    }

    return render_template(
        "article.html",
        article=article,
        countries=COUNTRIES,
        languages=LANGUAGES,
        current_country=country,
        current_language=lang,
        ga_id=GA_ID,
        adsense_client=ADSENSE_CLIENT,
        site_url=SITE_URL,
        seo_description=seo_description,
        alternate_urls=alternate_urls,
        canonical_url=absolute_url(
            article_path(article_id, country, lang)
        )
    )

