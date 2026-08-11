import json
import re
from datetime import datetime
from config.countries import COUNTRIES
from config.languages import LANGUAGES
from database.connection import get_db_connection
from services.image_service import generate_image
from services.translation_service import safe_translate
from ai.seo import build_schema
from utils.seo_helpers import seo_description

def cache_translation(article_id, lang, title, content):
    if lang not in LANGUAGES or lang == "en":
        return
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            f"UPDATE articles SET title_{lang} = %s, content_{lang} = %s WHERE id = %s",
            (title, content, article_id)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"!! Cache translation failed: {e}")

def article_exists(country, source_url):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id FROM articles
            WHERE country = %s AND source_url = %s
            LIMIT 1
            """,
            (country, source_url)
        )
        result = cur.fetchone()
        cur.close()
        conn.close()
        return result is not None
    except Exception as e:
        print(f"!! Duplicate check failed: {e}")
        return False

def save_article(country, news_item, article_data, translations, audit=None, seo_plan=None):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        country_info = COUNTRIES.get(country, COUNTRIES["ma"])
        region = country_info["region"]
        category = article_data.get("category", "News")
        title_en = article_data.get("title", news_item["title"])
        content_en = article_data.get("content", "")
        ar = translations.get("ar", {})
        fr = translations.get("fr", {})
        es = translations.get("es", {})

        def resolve_lang(lang_dict, lang_code):
            title = lang_dict.get("title")
            content = lang_dict.get("content")
            if not title:
                title = safe_translate(title_en, lang_code) or title_en
            if not content:
                content = safe_translate(content_en, lang_code) or content_en
            return title, content

        title_ar, content_ar = resolve_lang(ar, "ar")
        title_fr, content_fr = resolve_lang(fr, "fr")
        title_es, content_es = resolve_lang(es, "es")
        image_url = generate_image(article_data.get("image_prompt", news_item["title"]))
        seo_plan = seo_plan or {}
        audit = audit or {}
        faq = article_data.get("faq", [])
        seo_title = article_data.get("seo_title") or title_en
        meta_description = seo_description(article_data.get("meta_description") or content_en, 160)
        slug = re.sub(r"[^a-z0-9]+", "-", str(article_data.get("slug") or title_en).lower()).strip("-")[:90] or "news"
        primary_keyword = article_data.get("primary_keyword") or seo_plan.get("primary_keyword", "")
        secondary_keywords = json.dumps(article_data.get("secondary_keywords") or [], ensure_ascii=False)
        search_intent = article_data.get("search_intent") or seo_plan.get("search_intent", "news")
        trend_score = int(seo_plan.get("trend_score", 0))
        seo_score = int(audit.get("seo", seo_score_local(article_data)))
        quality_score = int(audit.get("overall", 0))
        seo_reason = json.dumps({
            "reason": seo_plan.get("reason", ""),
            "evidence": seo_plan.get("evidence_notes", ""),
            "audit_issues": audit.get("issues", []),
        }, ensure_ascii=False)
        schema_json = json.dumps(build_schema(0, country, "en", {
            "title": title_en, "seo_title": seo_title, "meta_description": meta_description,
            "content": content_en, "image": image_url, "created_at": datetime.now().isoformat()
        }, faq), ensure_ascii=False)
        cur.execute("""
            INSERT INTO articles (
                country, region, category,
                title_ar, title_fr, title_en, title_es,
                content_ar, content_fr, content_en, content_es,
                image_url, source_url, source_name, original_title,
                seo_title, meta_description, slug, primary_keyword,
                secondary_keywords, search_intent, trend_score, seo_score,
                quality_score, seo_reason, faq_json, schema_json, created_at
            ) VALUES (
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP
            )
            ON CONFLICT DO NOTHING
        """, (
            country, region, category,
            title_ar, title_fr, title_en, title_es,
            content_ar, content_fr, content_en, content_es,
            image_url, news_item.get("link", ""), news_item.get("source", ""), news_item.get("title", ""),
            seo_title, meta_description, slug, primary_keyword,
            secondary_keywords, search_intent, trend_score, seo_score,
            quality_score, seo_reason, json.dumps(faq, ensure_ascii=False), schema_json
        ))
        conn.commit()
        inserted = cur.rowcount > 0
        cur.close(); conn.close()
        if inserted:
            print(f"-> SAVED [{country}] {title_en[:80]} | trend={trend_score} seo={seo_score} quality={quality_score}")
        return inserted
    except Exception as e:
        print(f"!! Save article failed: {e}")
        return False

def get_related_articles(article_id, country, category, primary_keyword, limit=5):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        kw = f"%{(primary_keyword or '').strip()}%"
        cur.execute("""
            SELECT id, title_en, category
            FROM articles
            WHERE id <> %s AND country = %s
              AND (category = %s OR primary_keyword ILIKE %s)
            ORDER BY CASE WHEN category = %s THEN 0 ELSE 1 END, created_at DESC
            LIMIT %s
        """, (article_id, country, category, kw, category, limit))
        rows = cur.fetchall()
        cur.close(); conn.close()
        return [{"id": r[0], "title": r[1], "category": r[2]} for r in rows]
    except Exception as e:
        print(f"!! Related articles failed: {e}")
        return []
