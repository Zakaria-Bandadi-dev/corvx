import time
from datetime import datetime

import state
from config.settings import COUNTRIES, ARTICLES_PER_COUNTRY, TREND_MIN_SCORE, QUALITY_MIN_SCORE
from database.articles_repo import article_exists, save_article
from services.news_engine import (
    get_country_news,
    get_google_trends,
    analyze_trend_and_seo,
    research_story,
    generate_article,
    quality_check,
    optimize_article,
)
from services.translation import translate_article, safe_translate


def process_country(country):
    print("\n====================================")
    print(f"-> AI SEO Robot checking country: {country}")
    print("====================================")
    state.robot_status["current_country"] = country
    news = get_country_news(country)
    trends = get_google_trends(country)
    if not news:
        print(f"!! No news found for {country}")
        return 0
    saved = 0
    for news_item in news:
        if saved >= ARTICLES_PER_COUNTRY:
            break
        source_url = news_item.get("link", "")
        if source_url and article_exists(country, source_url):
            continue
        print(f"\n-> Candidate: {news_item.get('title', '')}")
        seo_plan = analyze_trend_and_seo(news_item, country, trends)
        print(f"-> Trend={seo_plan.get('trend_score')} SEO opportunity={seo_plan.get('seo_score_before_writing')} publish={seo_plan.get('publish')}")
        if not seo_plan.get("publish", True) or int(seo_plan.get("trend_score", 0)) < TREND_MIN_SCORE:
            print("-> SKIPPED: weak trend/search opportunity")
            continue
        verification = research_story(news_item)
        if not verification.get("verified", False) or int(verification.get("confidence", 0)) < 55:
            print("-> SKIPPED: insufficient source verification")
            continue
        article_data = generate_article(news_item, country, seo_plan, verification)
        if not article_data:
            print("!! Article generation failed")
            continue
        audit = quality_check(article_data, news_item, verification, seo_plan)
        if int(audit.get("overall", 0)) < QUALITY_MIN_SCORE:
            print(f"-> Optimizing article (quality={audit.get('overall')})")
            article_data = optimize_article(article_data, audit, seo_plan, news_item, verification)
            audit = quality_check(article_data, news_item, verification, seo_plan)
        if int(audit.get("factual_accuracy", 0)) < 75 or int(audit.get("overall", 0)) < QUALITY_MIN_SCORE:
            print(f"-> SKIPPED after optimization: quality={audit.get('overall')} factual={audit.get('factual_accuracy')}")
            continue
        translations = {}
        for lang in ("ar", "fr", "es"):
            translated = translate_article(article_data.get("title", news_item["title"]), article_data.get("content", ""), lang)
            if translated:
                translations[lang] = translated
        success = save_article(country, news_item, article_data, translations, safe_translate, audit, seo_plan)
        if success:
            saved += 1
            state.robot_status["total_articles_this_run"] += 1
        time.sleep(2)
    print(f"-> Country {country}: {saved} new articles saved")
    return saved


def run_robot():
    if not state.robot_lock.acquire(blocking=False):
        print("!! Robot already running")
        return

    state.robot_status["running"] = True
    state.robot_status["current_country"] = None
    state.robot_status["last_run_start"] = datetime.now()
    state.robot_status["total_articles_this_run"] = 0

    try:
        print("\n\n==========================================")
        print(f"NEWS ROBOT STARTED {datetime.now()}")
        print("==========================================")

        for country in COUNTRIES.keys():
            try:
                process_country(country)
            except Exception as e:
                print(f"!! Country {country} failed: {e}")
            time.sleep(3)

        print("\n==========================================")
        print(f"NEWS ROBOT FINISHED {datetime.now()}")
        print("==========================================\n")

    finally:
        state.robot_status["running"] = False
        state.robot_status["current_country"] = None
        state.robot_status["last_run_end"] = datetime.now()
        state.robot_status["last_run_saved"] = state.robot_status["total_articles_this_run"]
        state.robot_lock.release()
