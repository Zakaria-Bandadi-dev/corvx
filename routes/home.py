import urllib.parse
from flask import request, render_template
from app import app
from config.countries import COUNTRIES
from config.languages import LANGUAGES
from config.settings import GA_ID, ADSENSE_CLIENT, SITE_URL, ROBOT_INTERVAL_HOURS
from database.connection import get_db_connection
from database.articles import cache_translation
from services.country_detection import detect_country, detect_language
from services.translation_service import looks_like_lang, safe_translate
from ai.seo import build_website_schema
from utils.seo_helpers import absolute_url, seo_description
from robots.news_robot import robot_status

def home():
    country = request.args.get("country")
    if country not in COUNTRIES:
        country = detect_country()

    lang = request.args.get("lang")
    if lang not in LANGUAGES:
        lang = detect_language(country)

    country_info = COUNTRIES.get(country, COUNTRIES["ma"])
    title_column = f"title_{lang}"
    content_column = f"content_{lang}"
    articles = []
    ai_tools_articles = []

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # ========================================================
        # MAIN NEWS
        # Country articles + Global articles for everyone.
        # Global articles are not restricted by the visitor country.
        # ========================================================
        query = f"""
            SELECT
                id, {title_column}, {content_column}, title_en, content_en,
                image_url, category, source_name, created_at
            FROM articles
            WHERE country = %s
               OR LOWER(COALESCE(region, '')) = 'global'
            ORDER BY created_at DESC
            LIMIT 30
        """
        cur.execute(query, (country,))
        rows = cur.fetchall()

        for row in rows:
            article_id = row[0]
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

            articles.append({
                "id": article_id,
                "title": title,
                "content": content or "",
                "image": row[5],
                "category": row[6],
                "source": row[7],
                "created_at": row[8]
            })

        # ========================================================
        # AI TOOLS SECTION
        # Only articles whose category is Artificial Intelligence.
        # Global AI articles are therefore visible to everyone here.
        # ========================================================
        ai_query = f"""
            SELECT
                id, {title_column}, {content_column}, title_en, content_en,
                image_url, category, source_name, created_at
            FROM articles
            WHERE LOWER(COALESCE(category, '')) = 'artificial intelligence'
            ORDER BY created_at DESC
            LIMIT 10
        """
        cur.execute(ai_query)
        ai_rows = cur.fetchall()

        for row in ai_rows:
            article_id = row[0]
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
        print(f"!! Home database error: {e}")

    return render_template(
        "home.html",
        articles=articles,
        ai_tools_articles=ai_tools_articles,
        countries=COUNTRIES,
        languages=LANGUAGES,
        current_country=country,
        current_language=lang,
        ga_id=GA_ID,
        adsense_client=ADSENSE_CLIENT,
        country_name=country_info["name"],
        site_url=SITE_URL,
        seo_description=seo_description,
        canonical_url=absolute_url(
            f"/?country={urllib.parse.quote(country)}&lang={urllib.parse.quote(lang)}"
        ),
        absolute_home_urls={
            code: absolute_url(
                f"/?country={urllib.parse.quote(country)}&lang={urllib.parse.quote(code)}"
            )
            for code in LANGUAGES
        },
        robot_status=robot_status,
        robot_interval=ROBOT_INTERVAL_HOURS,
        current_country_name=(
            COUNTRIES[robot_status["current_country"]]["name"]
            if robot_status["current_country"] in COUNTRIES
            else None
        ),
        website_schema=build_website_schema(),
    )

