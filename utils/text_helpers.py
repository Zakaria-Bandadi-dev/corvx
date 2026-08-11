import hashlib
import json
import re


def looks_like_lang(text, lang):
    if not text:
        return False

    arabic_chars = len(re.findall(r"[\u0600-\u06FF]", text))
    letters = len(re.findall(r"[^\W\d_]", text, flags=re.UNICODE))
    if letters == 0:
        return False
    arabic_ratio = arabic_chars / letters

    if lang == "ar":
        return arabic_ratio > 0.4
    return arabic_ratio < 0.2


def clean_json(raw):
    """Extract and parse a JSON *object* from a raw LLM response."""
    if not raw:
        return None
    text = str(raw).strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    try:
        return json.loads(text)
    except Exception:
        return None


def extract_jobs_json(raw_text):
    """Extract and parse a JSON *array* from a raw LLM response (jobs robot)."""
    if not raw_text:
        return []

    text = raw_text.strip()
    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()

    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1:
        return []

    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return []


def make_offer_hash(site_name, offer):
    base = "|".join([
        site_name,
        (offer.get("title_ar") or "").strip().lower(),
        (offer.get("company_ar") or "").strip().lower(),
        (offer.get("source_url") or "").strip().lower(),
    ])
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def seo_score_local(article_data):
    title = str(article_data.get("title", ""))
    content = str(article_data.get("content", ""))
    keyword = str(article_data.get("primary_keyword", "")).strip().lower()
    meta = str(article_data.get("meta_description", ""))
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
