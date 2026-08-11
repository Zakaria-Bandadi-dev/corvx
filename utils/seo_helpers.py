import urllib.parse

from config.settings import SITE_URL


def absolute_url(path="/"):
    if not SITE_URL:
        return path
    return f"{SITE_URL}{path}"


def seo_description(text, max_length=160):
    if not text:
        return "Corvex News — Latest international news and updates."
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


def build_schema(article_id, country, lang, article, faq):
    url = absolute_url(article_path(article_id, country, lang))
    graph = [
        {
            "@type": "NewsArticle",
            "@id": url + "#article",
            "mainEntityOfPage": {"@type": "WebPage", "@id": url},
            "headline": article.get("seo_title") or article.get("title"),
            "description": article.get("meta_description") or seo_description(article.get("content", "")),
            "image": [article.get("image", "")],
            "datePublished": str(article.get("created_at", "")),
            "author": {"@type": "Organization", "name": "Corvex News"},
            "publisher": {"@type": "Organization", "name": "Corvex News"},
        }
    ]
    if faq:
        graph.append({
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": x.get("question", ""),
                 "acceptedAnswer": {"@type": "Answer", "text": x.get("answer", "")}}
                for x in faq if x.get("question") and x.get("answer")
            ]
        })
    return {"@context": "https://schema.org", "@graph": graph}


def build_website_schema():
    home_url = absolute_url("/")
    return {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Organization",
                "@id": home_url + "#organization",
                "name": "Corvex News",
                "url": home_url,
            },
            {
                "@type": "WebSite",
                "@id": home_url + "#website",
                "url": home_url,
                "name": "Corvex News",
                "publisher": {"@id": home_url + "#organization"},
            },
        ],
    }
