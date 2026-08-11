import urllib.parse

from flask import Blueprint, request, render_template, redirect, url_for

import state
from config.settings import COUNTRIES, LANGUAGES, GA_ID, ADSENSE_CLIENT, SITE_URL, ROBOT_INTERVAL_HOURS
from database.articles_repo import fetch_home_articles, fetch_article_by_id, cache_translation, get_related_articles
from services.geo import detect_country, detect_language
from services.translation import safe_translate
from utils.text_helpers import looks_like_lang
from utils.seo_helpers import seo_description, absolute_url, article_path, build_schema, build_website_schema

news_bp = Blueprint("news", __name__)


@news_bp.route("/")
def home():
    country = request.args.get("country")
    if country not in COUNTRIES:
        country = detect_country()

    lang = request.args.get("lang")
    if lang not in LANGUAGES:
        lang = detect_language(country)

    country_info = COUNTRIES.get(country, COUNTRIES["ma"])
    articles = []

    rows = fetch_home_articles(country, lang)
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

    return render_template(
        "home.html",
        articles=articles,
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
        robot_status=state.robot_status,
        robot_interval=ROBOT_INTERVAL_HOURS,
        current_country_name=(
            COUNTRIES[state.robot_status["current_country"]]["name"]
            if state.robot_status["current_country"] in COUNTRIES
            else None
        ),
        website_schema=build_website_schema(),
    )


@news_bp.route("/article/<int:article_id>")
def article_detail(article_id):
    country = request.args.get("country")
    if country not in COUNTRIES:
        country = detect_country()

    lang = request.args.get("lang")
    if lang not in LANGUAGES:
        lang = detect_language(country)

    article = None
    row = fetch_article_by_id(article_id, lang)

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

        import json
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


@news_bp.route("/set-country/<country>")
def set_country(country):
    if country not in COUNTRIES:
        country = "ma"
    lang = request.args.get("lang", "en")
    response = redirect(url_for("news.home", country=country, lang=lang))
    response.set_cookie("country", country, max_age=60 * 60 * 24 * 365)
    return response


@news_bp.route("/set-language/<lang>")
def set_language(lang):
    if lang not in LANGUAGES:
        lang = "en"
    country = request.args.get("country")
    if country not in COUNTRIES:
        country = detect_country()
    response = redirect(url_for("news.home", country=country, lang=lang))
    response.set_cookie("lang", lang, max_age=60 * 60 * 24 * 365)
    return response


@news_bp.route("/ads.txt")
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
