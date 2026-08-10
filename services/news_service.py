import feedparser
from config.countries import COUNTRIES

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
