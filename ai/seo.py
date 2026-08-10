````python
import json
import re
import feedparser

from config.countries import COUNTRIES
from config.settings import (
    SEO_RESEARCH_ENABLED,
    TRENDING_LIMIT,
    SEO_MIN_SCORE,
    QUALITY_MIN_SCORE,
)
from ai.groq_news import generate_with_groq_compound
from utils.seo_helpers import absolute_url, article_path, seo_description


def _clean_json(raw):
    if not raw:
        return None

    text = str(raw).strip()

    if text.startswith("`"):
        text = re.sub(r"^`(?:json)?", "", text).strip()

    text = re.sub(r"```$", "", text).strip()

    start = text.find("{")
    end = text.rfind("}")

    if start >= 0 and end > start:
        text = text[start:end + 1]

    try:
        return json.loads(text)
    except Exception:
        return None


def get_google_trends(country):
    geo = COUNTRIES.get(
        country,
        COUNTRIES["ma"]
    ).get("google_news", "MA")

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

    hits = sum(
        1
        for term in trend_terms
        if term.lower() in title or title in term.lower()
    )

    position = max(
        0,
        100 - min(len(trend_terms), 30) * 2
    )

    score = (
        30
        + min(50, hits * 25)
        + min(20, position // 10)
    )

    return max(0, min(100, score))


def analyze_trend_and_seo(
    news_item,
    country,
    trend_terms
):
    country_name = COUNTRIES.get(
        country,
        COUNTRIES["ma"]
    )["name"]

    trends_text = "\n".join(
        f"- {x}"
        for x in trend_terms[:TRENDING_LIMIT]
    ) or "No public trend feed available."

    prompt = f"""
Analyze this news opportunity for {country_name}.

TITLE:
{news_item.get('title', '')}

SUMMARY:
{news_item.get('description', '')}

SOURCE:
{news_item.get('source', '')}
{news_item.get('link', '')}

CURRENT TRENDS:
{trends_text}

If web tools are available, research the topic and current search landscape.

Return ONLY valid JSON:
{{
"publish": true,
"reason": "short evidence-based reason",
"trend_score": 0,
"seo_score_before_writing": 0,
"primary_keyword": "...",
"secondary_keywords": ["..."],
"search_intent": "news|informational|navigational|mixed",
"content_angle": "...",
"competitor_gaps": ["..."],
"recommended_title": "...",
"meta_description": "...",
"slug": "...",
"source_quality": 0,
"evidence_notes": "..."
}}
"""

    raw = (
        generate_with_groq_compound(
            prompt,
            max_tokens=1800,
        )
        if SEO_RESEARCH_ENABLED
        else None
    )

    data = _clean_json(raw)

    if not data:
        title = news_item.get("title", "News")

        slug = (
            re.sub(
                r"[^a-z0-9]+",
                "-",
                title.lower(),
            )
            .strip("-")[:90]
            or "news"
        )

        score = trend_score_heuristic(
            news_item,
            trend_terms,
        )

        data = {
            "publish": True,
            "reason": "Fallback analysis based on current RSS signals.",
            "trend_score": score,
            "seo_score_before_writing": 55,
            "primary_keyword": title[:80],
            "secondary_keywords": [],
            "search_intent": "news",
            "content_angle": (
                "Explain what happened, why it matters, "
                "and what is confirmed."
            ),
            "competitor_gaps": [],
            "recommended_title": title,
            "meta_description": title[:155],
            "slug": slug,
            "source_quality": 50,
            "evidence_notes": (
                "Web SEO research unavailable; fallback used."
            ),
        }

    data["trend_score"] = int(
        max(
            0,
            min(
                100,
                data.get("trend_score", 0),
            ),
        )
    )

    data["seo_score_before_writing"] = int(
        max(
            0,
            min(
                100,
                data.get(
                    "seo_score_before_writing",
                    0,
                ),
            ),
        )
    )

    data["source_quality"] = int(
        max(
            0,
            min(
                100,
                data.get("source_quality", 0),
            ),
        )
    )

    data["secondary_keywords"] = (
        data.get("secondary_keywords") or []
    )

    data["competitor_gaps"] = (
        data.get("competitor_gaps") or []
    )

    return data


def research_story(news_item):
    prompt = f"""
Verify this news item using the web if available.

Title: {news_item.get('title', '')}
Summary: {news_item.get('description', '')}
Source: {news_item.get('source', '')}
URL: {news_item.get('link', '')}

Find the original/reliable source and confirm the core facts.
Do not guess.

Return ONLY valid JSON:
{{
"verified": true,
"confidence": 0,
"confirmed_facts": ["..."],
"uncertain_claims": ["..."],
"source_urls": ["..."],
"source_names": ["..."]
}}
"""

    raw = (
        generate_with_groq_compound(
            prompt,
            max_tokens=1200,
        )
        if SEO_RESEARCH_ENABLED
        else None
    )

    data = _clean_json(raw)

    if not data:
        return {
            "verified": bool(news_item.get("link")),
            "confidence": (
                50
                if news_item.get("link")
                else 20
            ),
            "confirmed_facts": [
                news_item.get("description", "")
            ],
            "uncertain_claims": [],
            "source_urls": [
                news_item.get("link", "")
            ],
            "source_names": [
                news_item.get("source", "")
            ],
        }

    return data


def seo_score_local(article_data):
    title = str(
        article_data.get("title", "")
    )

    content = str(
        article_data.get("content", "")
    )

    keyword = str(
        article_data.get(
            "primary_keyword",
            "",
        )
    ).strip().lower()

    meta = str(
        article_data.get(
            "meta_description",
            "",
        )
    )

    score = 0

    if keyword and keyword in title.lower():
        score += 20

    if 35 <= len(title) <= 70:
        score += 15

    if 120 <= len(meta) <= 160:
        score += 15

    if keyword and keyword in content.lower():
        score += 15

    if len(content.split()) >= 450:
        score += 10

    if article_data.get("secondary_keywords"):
        score += 10

    if article_data.get("faq"):
        score += 5

    if article_data.get("search_intent"):
        score += 5

    if article_data.get("content_angle"):
        score += 5

    return min(100, score)


def build_schema(
    article_id,
    country,
    lang,
    article,
    faq,
):
    url = absolute_url(
        article_path(
            article_id,
            country,
            lang,
        )
    )

    graph = [
        {
            "@type": "NewsArticle",
            "@id": url + "#article",
            "mainEntityOfPage": {
                "@type": "WebPage",
                "@id": url,
            },
            "headline": (
                article.get("seo_title")
                or article.get("title")
            ),
            "description": (
                article.get("meta_description")
                or seo_description(
                    article.get("content", "")
                )
            ),
            "image": [
                article.get("image", "")
            ],
            "datePublished": str(
                article.get(
                    "created_at",
                    "",
                )
            ),
            "author": {
                "@type": "Organization",
                "name": "Corvx News",
            },
            "publisher": {
                "@type": "Organization",
                "name": "Corvx News",
            },
        }
    ]

    if faq:
        graph.append(
            {
                "@type": "FAQPage",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": x.get(
                            "question",
                            "",
                        ),
                        "acceptedAnswer": {
                            "@type": "Answer",
                            "text": x.get(
                                "answer",
                                "",
                            ),
                        },
                    }
                    for x in faq
                    if x.get("question")
                    and x.get("answer")
                ],
            }
        )

    return {
        "@context": "https://schema.org",
        "@graph": graph,
    }


def build_website_schema():
    home_url = absolute_url("/")

    return {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Organization",
                "@id": home_url + "#organization",
                "name": "Corvx News",
                "url": home_url,
            },
            {
                "@type": "WebSite",
                "@id": home_url + "#website",
                "url": home_url,
                "name": "Corvx News",
                "publisher": {
                    "@id": home_url + "#organization"
                },
            },
        ],
    }
````
