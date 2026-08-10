import urllib.parse
from flask import request, render_template
from app import app
from config.countries import COUNTRIES
from config.languages import LANGUAGES
from database.connection import get_db_connection
from database.articles import cache_translation
from services.country_detection import detect_country, detect_language
from services.translation_service import looks_like_lang, safe_translate
from utils.seo_helpers import absolute_url

@app.route("/ai-tools")
def ai_tools_page():
    country = request.args.get("country")
    if country not in COUNTRIES:
        country = detect_country()

    lang = request.args.get("lang")
    if lang not in LANGUAGES:
        lang = detect_language(country)

    country_info = COUNTRIES.get(country, COUNTRIES["ma"])
    title_column = f"title_{lang}"
    content_column = f"content_{lang}"
    ai_tools_articles = []

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        query = f"""
            SELECT
                id, {title_column}, {content_column}, title_en, content_en,
                image_url, category, source_name, created_at
            FROM articles
            WHERE LOWER(COALESCE(category, '')) = 'artificial intelligence'
            ORDER BY created_at DESC
            LIMIT 50
        """
        cur.execute(query)
        rows = cur.fetchall()

        for row in rows:
            article_id = row[0]
            title = row[1]
            content = row[2]
            fallback_title = row[3]
            fallback_content = row[4]

            if lang != "en" and (
                not looks_like_lang(title, lang)
                or not looks_like_lang(content, lang)
            ):
                new_title = fallback_title if not looks_like_lang(title, lang) else title
                new_content = fallback_content if not looks_like_lang(content, lang) else content
                new_title = safe_translate(new_title, lang) or new_title
                new_content = safe_translate(new_content, lang) or new_content
                cache_translation(article_id, lang, new_title, new_content)
                title, content = new_title, new_content

            ai_tools_articles.append({
                "id": article_id,
                "title": title,
                "content": content or "",
                "image": row[5],
                "category": row[6],
                "source": row[7],
                "created_at": row[8]
            })

        cur.close()
        conn.close()

    except Exception as e:
        print(f"!! AI Tools database error: {e}")

    return render_template(
        "ai_tools.html",
        ai_tools_articles=ai_tools_articles,
        countries=COUNTRIES,
        languages=LANGUAGES,
        current_country=country,
        current_language=lang,
        country_name=country_info["name"],
        canonical_url=absolute_url(
            f"/ai-tools?country={urllib.parse.quote(country)}&lang={urllib.parse.quote(lang)}"
        ),
    )

