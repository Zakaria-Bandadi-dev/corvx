import json
import re
from config.countries import COUNTRIES
from config.settings import SEO_MIN_SCORE, QUALITY_MIN_SCORE
from ai.groq_news import generate_with_groq, generate_with_groq_compound
from utils.seo_helpers import seo_description

def generate_article(news_item, country, seo_plan=None, verification=None):
    country_info = COUNTRIES.get(country, COUNTRIES["ma"])
    country_name = country_info["name"]
    seo_plan = seo_plan or {}
    verification = verification or {}
    prompt = f"""
Create a high-quality, original news article based ONLY on the verified material below.

COUNTRY: {country_name}
ORIGINAL HEADLINE: {news_item.get('title', '')}
RSS SUMMARY: {news_item.get('description', '')}
SOURCE: {news_item.get('source', '')} / {news_item.get('link', '')}

SEO PLAN:
Primary keyword: {seo_plan.get('primary_keyword', '')}
Secondary keywords: {json.dumps(seo_plan.get('secondary_keywords', []), ensure_ascii=False)}
Search intent: {seo_plan.get('search_intent', 'news')}
Content angle: {seo_plan.get('content_angle', '')}
Competitor gaps: {json.dumps(seo_plan.get('competitor_gaps', []), ensure_ascii=False)}
Recommended title: {seo_plan.get('recommended_title', '')}

VERIFICATION:
{json.dumps(verification, ensure_ascii=False)}

Rules:
- Discuss the actual news event, not AI or generic filler.
- Do not invent facts.
- Return ONLY JSON:
{{
  "title": "SEO-friendly editorial title",
  "content": "article text with headings",
  "category": "Politics|Business|Technology|Sports|World|Health|Entertainment|Science|Other",
  "image_prompt": "realistic editorial news image description",
  "primary_keyword": "...",
  "secondary_keywords": ["..."],
  "search_intent": "news|informational|navigational|mixed",
  "seo_title": "title for search results",
  "meta_description": "120-160 characters",
  "slug": "short-keyword-rich-slug",
  "faq": [{{"question":"...","answer":"..."}}]
}}
"""
    raw = generate_with_groq(prompt)
    data = _clean_json(raw)
    if not data:
        return None
    data["primary_keyword"] = data.get("primary_keyword") or seo_plan.get("primary_keyword", news_item.get("title", ""))
    data["secondary_keywords"] = data.get("secondary_keywords") or seo_plan.get("secondary_keywords", [])
    data["search_intent"] = data.get("search_intent") or seo_plan.get("search_intent", "news")
    data["seo_title"] = data.get("seo_title") or data.get("title", "")
    data["meta_description"] = seo_description(data.get("meta_description") or data.get("content", ""), 160)
    data["slug"] = re.sub(r"[^a-z0-9]+", "-", str(data.get("slug") or data.get("title", "")).lower()).strip("-")[:90] or "news"
    data["faq"] = data.get("faq") or []
    data["content_angle"] = seo_plan.get("content_angle", "")
    return data

def quality_check(article_data, news_item, verification, seo_plan):
    prompt = f"""
Audit this proposed news article for publication.

ARTICLE:
Title: {article_data.get('title', '')}
Content:
{article_data.get('content', '')}

PRIMARY KEYWORD: {article_data.get('primary_keyword', '')}
SEO TITLE: {article_data.get('seo_title', '')}
META: {article_data.get('meta_description', '')}

SOURCE ITEM:
{json.dumps(news_item, ensure_ascii=False)}

VERIFICATION:
{json.dumps(verification, ensure_ascii=False)}

SEO PLAN:
{json.dumps(seo_plan, ensure_ascii=False)}

Score these independently from 0-100 and return ONLY JSON:
{{
  "publish": true,
  "factual_accuracy": 0,
  "originality": 0,
  "usefulness": 0,
  "readability": 0,
  "seo": 0,
  "source_quality": 0,
  "overall": 0,
  "issues": ["..."],
  "fixes": ["..."]
}}
"""
    raw = generate_with_groq_compound(prompt, max_tokens=3000) if SEO_RESEARCH_ENABLED else None
    data = _clean_json(raw)
    if not data:
        local = seo_score_local(article_data)
        return {
            "publish": local >= SEO_MIN_SCORE,
            "factual_accuracy": 70,
            "originality": 70,
            "usefulness": 70,
            "readability": 75,
            "seo": local,
            "source_quality": int(seo_plan.get("source_quality", 50)),
            "overall": local,
            "issues": ["Automated web audit unavailable."],
            "fixes": [],
        }
    for key in ["factual_accuracy", "originality", "usefulness", "readability", "seo", "source_quality", "overall"]:
        data[key] = int(max(0, min(100, data.get(key, 0))))
    return data

def optimize_article(article_data, audit, seo_plan, news_item, verification):
    if audit.get("overall", 0) >= max(SEO_MIN_SCORE, QUALITY_MIN_SCORE):
        return article_data
    prompt = f"""
Improve this news article using the audit. Keep every factual claim supported.
Do NOT add unsupported facts.

ARTICLE:
{json.dumps(article_data, ensure_ascii=False)}

AUDIT:
{json.dumps(audit, ensure_ascii=False)}

SEO PLAN:
{json.dumps(seo_plan, ensure_ascii=False)}

Return ONLY the same JSON structure as the article, with the improved title,
content, SEO title, meta description, keywords, slug and FAQs.
"""
    raw = generate_with_groq(prompt)
    data = _clean_json(raw)
    if not data:
        return article_data
    data["primary_keyword"] = data.get("primary_keyword") or article_data.get("primary_keyword")
    data["secondary_keywords"] = data.get("secondary_keywords") or article_data.get("secondary_keywords", [])
    data["search_intent"] = data.get("search_intent") or article_data.get("search_intent", "news")
    data["seo_title"] = data.get("seo_title") or article_data.get("seo_title") or data.get("title", "")
    data["meta_description"] = seo_description(data.get("meta_description") or data.get("content", ""), 160)
    data["slug"] = re.sub(r"[^a-z0-9]+", "-", str(data.get("slug") or data.get("title", "")).lower()).strip("-")[:90] or "news"
    data["faq"] = data.get("faq") or article_data.get("faq", [])
    return data
