```python
import json
import re

from config.countries import COUNTRIES
from config.settings import (
    SEO_MIN_SCORE,
    QUALITY_MIN_SCORE,
    SEO_RESEARCH_ENABLED,
)
from ai.groq_news import (
    generate_with_groq,
    generate_with_groq_compound,
)
from ai.seo import _clean_json, seo_score_local
from utils.seo_helpers import seo_description


def generate_article(news_item, country, seo_plan=None, verification=None):
    country_info = COUNTRIES.get(country, COUNTRIES["ma"])
    country_name = country_info["name"]

    seo_plan = seo_plan or {}
    verification = verification or {}

    secondary_keywords = seo_plan.get("secondary_keywords", [])
    competitor_gaps = seo_plan.get("competitor_gaps", [])

    prompt = f"""
Create a high-quality original news article using ONLY the verified material.

COUNTRY: {country_name}
HEADLINE: {news_item.get("title", "")}
SUMMARY: {news_item.get("description", "")}
SOURCE: {news_item.get("source", "")}
URL: {news_item.get("link", "")}

SEO:
Primary: {seo_plan.get("primary_keyword", "")}
Secondary: {json.dumps(secondary_keywords, ensure_ascii=False)}
Intent: {seo_plan.get("search_intent", "news")}
Angle: {seo_plan.get("content_angle", "")}
Gaps: {json.dumps(competitor_gaps, ensure_ascii=False)}
Title: {seo_plan.get("recommended_title", "")}

VERIFICATION:
{json.dumps(verification, ensure_ascii=False)}

Rules:
- Write about the real news only.
- Do not invent facts.
- Return ONLY valid JSON.

{{
"title": "...",
"content": "...",
"category": "Politics|Business|Technology|Sports|World|Health|Entertainment|Science|Other",
"image_prompt": "...",
"primary_keyword": "...",
"secondary_keywords": ["..."],
"search_intent": "news|informational|navigational|mixed",
"seo_title": "...",
"meta_description": "120-160 characters",
"slug": "...",
"faq": [{{"question":"...","answer":"..."}}]
}}
"""

    raw = generate_with_groq(prompt)
    data = _clean_json(raw)

    if not data:
        return None

    data["primary_keyword"] = (
        data.get("primary_keyword")
        or seo_plan.get("primary_keyword")
        or news_item.get("title", "")
    )

    data["secondary_keywords"] = (
        data.get("secondary_keywords")
        or secondary_keywords
    )

    data["search_intent"] = (
        data.get("search_intent")
        or seo_plan.get("search_intent", "news")
    )

    data["seo_title"] = (
        data.get("seo_title")
        or data.get("title", "")
    )

    data["meta_description"] = seo_description(
        data.get("meta_description")
        or data.get("content", ""),
        160,
    )

    data["slug"] = (
        re.sub(
            r"[^a-z0-9]+",
            "-",
            str(data.get("slug") or data.get("title", "")).lower(),
        )
        .strip("-")[:90]
        or "news"
    )

    data["faq"] = data.get("faq") or []
    data["content_angle"] = seo_plan.get("content_angle", "")

    return data


def quality_check(article_data, news_item, verification, seo_plan):
    # Send only the information actually needed by the audit.
    source_item = {
        "title": news_item.get("title", ""),
        "description": news_item.get("description", ""),
        "source": news_item.get("source", ""),
        "link": news_item.get("link", ""),
    }

    seo_info = {
        "primary_keyword": seo_plan.get("primary_keyword", ""),
        "search_intent": seo_plan.get("search_intent", "news"),
        "content_angle": seo_plan.get("content_angle", ""),
        "source_quality": seo_plan.get("source_quality", 50),
    }

    verification_info = verification

    prompt = f"""
Audit this news article for publication.

ARTICLE:
Title: {article_data.get("title", "")}
Content:
{article_data.get("content", "")}

SEO:
Primary: {article_data.get("primary_keyword", "")}
Title: {article_data.get("seo_title", "")}
Meta: {article_data.get("meta_description", "")}

SOURCE:
{json.dumps(source_item, ensure_ascii=False)}

VERIFICATION:
{json.dumps(verification_info, ensure_ascii=False)}

SEO PLAN:
{json.dumps(seo_info, ensure_ascii=False)}

Score each from 0-100.
Return ONLY JSON:

{{
"publish": true,
"factual_accuracy": 0,
"originality": 0,
"usefulness": 0,
"readability": 0,
"seo": 0,
"source_quality": 0,
"overall": 0,
"issues": [],
"fixes": []
}}
"""

    # The audit JSON is small, so 1200 tokens is more than enough.
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
        local = seo_score_local(article_data)

        return {
            "publish": local >= SEO_MIN_SCORE,
            "factual_accuracy": 70,
            "originality": 70,
            "usefulness": 70,
            "readability": 75,
            "seo": local,
            "source_quality": int(
                seo_plan.get("source_quality", 50)
            ),
            "overall": local,
            "issues": ["Automated web audit unavailable."],
            "fixes": [],
        }

    for key in [
        "factual_accuracy",
        "originality",
        "usefulness",
        "readability",
        "seo",
        "source_quality",
        "overall",
    ]:
        try:
            data[key] = int(
                max(
                    0,
                    min(
                        100,
                        data.get(key, 0),
                    ),
                )
            )
        except (TypeError, ValueError):
            data[key] = 0

    return data


def optimize_article(
    article_data,
    audit,
    seo_plan,
    news_item,
    verification,
):
    if audit.get("overall", 0) >= max(
        SEO_MIN_SCORE,
        QUALITY_MIN_SCORE,
    ):
        return article_data

    # Only send the data needed for optimization.
    optimization_data = {
        "title": article_data.get("title", ""),
        "content": article_data.get("content", ""),
        "category": article_data.get("category", ""),
        "image_prompt": article_data.get("image_prompt", ""),
        "primary_keyword": article_data.get("primary_keyword", ""),
        "secondary_keywords": article_data.get(
            "secondary_keywords",
            [],
        ),
        "search_intent": article_data.get(
            "search_intent",
            "news",
        ),
        "seo_title": article_data.get(
            "seo_title",
            "",
        ),
        "meta_description": article_data.get(
            "meta_description",
            "",
        ),
        "slug": article_data.get(
            "slug",
            "",
        ),
        "faq": article_data.get(
            "faq",
            [],
        ),
    }

    prompt = f"""
Improve this news article using the audit.

Keep all factual claims supported.
Do not add unsupported facts.

ARTICLE:
{json.dumps(optimization_data, ensure_ascii=False)}

AUDIT:
{json.dumps(audit, ensure_ascii=False)}

SEO:
Primary keyword: {seo_plan.get("primary_keyword", "")}
Intent: {seo_plan.get("search_intent", "news")}
Angle: {seo_plan.get("content_angle", "")}

Return ONLY valid JSON with the same article fields.
Improve only what is necessary.
"""

    raw = generate_with_groq(prompt)
    data = _clean_json(raw)

    if not data:
        return article_data

    data["primary_keyword"] = (
        data.get("primary_keyword")
        or article_data.get("primary_keyword")
    )

    data["secondary_keywords"] = (
        data.get("secondary_keywords")
        or article_data.get("secondary_keywords", [])
    )

    data["search_intent"] = (
        data.get("search_intent")
        or article_data.get("search_intent", "news")
    )

    data["seo_title"] = (
        data.get("seo_title")
        or article_data.get("seo_title")
        or data.get("title", "")
    )

    data["meta_description"] = seo_description(
        data.get("meta_description")
        or data.get("content", ""),
        160,
    )

    data["slug"] = (
        re.sub(
            r"[^a-z0-9]+",
            "-",
            str(
                data.get("slug")
                or data.get("title", "")
            ).lower(),
        )
        .strip("-")[:90]
        or "news"
    )

    data["faq"] = (
        data.get("faq")
        or article_data.get("faq", [])
    )

    return data
```
