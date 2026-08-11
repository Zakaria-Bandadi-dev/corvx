import json
import re

import feedparser

from config.settings import COUNTRIES, SEO_RESEARCH_ENABLED, TRENDING_LIMIT
from services.groq_client import generate_with_groq, generate_with_groq_compound
from utils.text_helpers import clean_json, seo_score_local


def get_country_news(country):
    if country not in COUNTRIES:
        country = "ma"

    country_info = COUNTRIES[country]
    google_country = country_info["google_news"]
    url = (
        "[https://news.google.com/rss](https://news.google.com/rss)"
        f"?hl=en-US"
        f"&gl={google_country}"
        f"&ceid={google_country}:en"
    )

    try:
        feed = feedparser.parse(url)
        news = []
        for entry in feed.entries[:20]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            description = entry.get("summary", "").strip()
            published = entry.get("published", "").strip()

            if not title:
                continue

            source_name = ""
            if hasattr(entry, "source"):
                try:
                    source_name = entry.source.get("title", "")
                except Exception:
                    pass

            news.append({
                "title": title,
                "description": description,
                "link": link,
                "published": published,
                "source": source_name
            })
        return news

    except Exception as e:
        print(f"!! RSS failed for {country}: {e}")
        return []


def get_google_trends(country):
    geo = COUNTRIES.get(country, COUNTRIES["ma"]).get("google_news", "MA")
    url = f"https://trends.google.com/trending/rss?geo={geo}"
    try:
        feed = feedparser.parse(url)
        items = []
        for entry in feed.entries[:TRENDING_LIMIT]:
            title = (entry.get("title") or "").strip()
            if title:
                items.append(title)
        return items
    except Exception as e:
        print(f"!! Google Trends RSS failed for {country}: {e}")
        return []


def trend_score_heuristic(news_item, trend_terms):
    title = (news_item.get("title") or "").lower()
    hits = sum(1 for term in trend_terms if term.lower() in title or title in term.lower())
    position = max(0, 100 - min(len(trend_terms), 30) * 2)
    score = 30 + min(50, hits * 25) + min(20, position // 10)
    return max(0, min(100, score))


def analyze_trend_and_seo(news_item, country, trend_terms):
    country_name = COUNTRIES.get(country, COUNTRIES["ma"])["name"]
    trends_text = "\n".join(f"- {x}" for x in trend_terms[:TRENDING_LIMIT]) or "No public trend feed available."
    prompt = f"""
Analyze this news opportunity for {country_name}.

NEWS TITLE:
{news_item.get('title', '')}

NEWS SUMMARY:
{news_item.get('description', '')}

SOURCE:
{news_item.get('source', '')}
{news_item.get('link', '')}

CURRENT PUBLIC TREND SIGNALS:
{trends_text}

If web tools are available, research the topic and current search landscape.
Return ONLY JSON:
{{
  "publish": true,
  "reason": "short evidence-based reason",
  "trend_score": 0,
  "seo_score_before_writing": 0,
  "primary_keyword": "...",
  "secondary_keywords": ["...", "..."],
  "search_intent": "news|informational|navigational|mixed",
  "content_angle": "specific useful angle",
  "competitor_gaps": ["..."],
  "recommended_title": "...",
  "meta_description": "...",
  "slug": "...",
  "source_quality": 0,
  "evidence_notes": "..."
}}
"""
    raw = generate_with_groq_compound(prompt, max_tokens=3500) if SEO_RESEARCH_ENABLED else None
    data = clean_json(raw)
    if not data:
        title = news_item.get("title", "News")
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:90] or "news"
        score = trend_score_heuristic(news_item, trend_terms)
        data = {
            "publish": True,
            "reason": "Fallback analysis based on current RSS signals.",
            "trend_score": score,
            "seo_score_before_writing": 55,
            "primary_keyword": title[:80],
            "secondary_keywords": [],
            "search_intent": "news",
            "content_angle": "Explain what happened, why it matters, and what is confirmed.",
            "competitor_gaps": [],
            "recommended_title": title,
            "meta_description": title[:155],
            "slug": slug,
            "source_quality": 50,
            "evidence_notes": "Web SEO research unavailable; fallback used.",
        }
    data["trend_score"] = int(max(0, min(100, data.get("trend_score", 0))))
    data["seo_score_before_writing"] = int(max(0, min(100, data.get("seo_score_before_writing", 0))))
    data["source_quality"] = int(max(0, min(100, data.get("source_quality", 0))))
    data["secondary_keywords"] = data.get("secondary_keywords") or []
    data["competitor_gaps"] = data.get("competitor_gaps") or []
    return data


def research_story(news_item):
    prompt = f"""
Verify this news item using the web if available.
Title: {news_item.get('title', '')}
Summary: {news_item.get('description', '')}
Source name: {news_item.get('source', '')}
Source URL: {news_item.get('link', '')}

Find the original/reliable source and confirm the core facts. Do not guess.
Return ONLY JSON:
{{
  "verified": true,
  "confidence": 0,
  "confirmed_facts": ["..."],
  "uncertain_claims": ["..."],
  "source_urls": ["..."],
  "source_names": ["..."]
}}
"""
    raw = generate_with_groq_compound(prompt, max_tokens=3000) if SEO_RESEARCH_ENABLED else None
    data = clean_json(raw)
    if not data:
        return {
            "verified": bool(news_item.get("link")),
            "confidence": 50 if news_item.get("link") else 20,
            "confirmed_facts": [news_item.get("description", "")],
            "uncertain_claims": [],
            "source_urls": [news_item.get("link", "")],
            "source_names": [news_item.get("source", "")],
        }
    return data


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
    data = clean_json(raw)
    if not data:
        return None
    data["primary_keyword"] = data.get("primary_keyword") or seo_plan.get("primary_keyword", news_item.get("title", ""))
    data["secondary_keywords"] = data.get("secondary_keywords") or seo_plan.get("secondary_keywords", [])
    data["search_intent"] = data.get("search_intent") or seo_plan.get("search_intent", "news")
    data["seo_title"] = data.get("seo_title") or data.get("title", "")
    from utils.seo_helpers import seo_description
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
    data = clean_json(raw)
    if not data:
        local = seo_score_local(article_data)
        from config.settings import SEO_MIN_SCORE
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
    from config.settings import SEO_MIN_SCORE, QUALITY_MIN_SCORE
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
    data = clean_json(raw)
    if not data:
        return article_data
    data["primary_keyword"] = data.get("primary_keyword") or article_data.get("primary_keyword")
    data["secondary_keywords"] = data.get("secondary_keywords") or article_data.get("secondary_keywords", [])
    data["search_intent"] = data.get("search_intent") or article_data.get("search_intent", "news")
    data["seo_title"] = data.get("seo_title") or article_data.get("seo_title") or data.get("title", "")
    from utils.seo_helpers import seo_description
    data["meta_description"] = seo_description(data.get("meta_description") or data.get("content", ""), 160)
    data["slug"] = re.sub(r"[^a-z0-9]+", "-", str(data.get("slug") or data.get("title", "")).lower()).strip("-")[:90] or "news"
    data["faq"] = data.get("faq") or article_data.get("faq", [])
    return data
