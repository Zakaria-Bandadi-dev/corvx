import urllib.parse
from config.settings import SITE_URL

def absolute_url(path="/"):
    if not SITE_URL:
        return path
    return f"{SITE_URL}{path}"

def seo_description(text, max_length=160):
    if not text:
        return "Corvx News — Latest international news and updates."
    clean = " ".join(str(text).split())
    if len(clean) <= max_length:
        return clean
    return clean[:max_length - 3].rsplit(" ", 1)[0] + "..."

def article_path(article_id, country, lang):
    return (
        f"/article/{article_id}"
        f"?country={urllib.parse.quote(country)}"
        f"&lang={urllib.parse.quote(lang)}"
    )
