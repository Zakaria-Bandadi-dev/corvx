import os
import json
import time
import urllib.parse
import ipaddress
from datetime import datetime
from threading import Lock

import feedparser
import requests
import psycopg

from flask import (
    Flask,
    request,
    render_template_string,
    redirect,
    url_for,
    jsonify
)

from groq import Groq
from apscheduler.schedulers.background import BackgroundScheduler

# ============================================================
# APP
# ============================================================

app = Flask(__name__)

# ============================================================
# ENVIRONMENT VARIABLES
# ============================================================

GA_ID = os.getenv("GA_ID", "")
ADSENSE_CLIENT = os.getenv("ADSENSE_CLIENT", "")
DATABASE_URL = os.getenv("DATABASE_URL")
SITE_URL = os.getenv("SITE_URL", "").rstrip("/")

GROQ_KEYS = [
    os.getenv("GROQ_API_KEY1"),
    os.getenv("GROQ_API_KEY2"),
    os.getenv("GROQ_API_KEY3"),
    os.getenv("GROQ_API_KEY4"),
    os.getenv("GROQ_API_KEY5"),
]

# Remove empty variables
GROQ_KEYS = [key.strip() for key in GROQ_KEYS if key and key.strip()]

# Current Groq key
current_groq_key = 0

# Prevent two robot jobs from running simultaneously
robot_lock = Lock()

# ============================================================
# ROBOT LIVE STATUS (transparency: show visitors the robot works)
# ============================================================

robot_status = {
    "running": False,
    "current_country": None,
    "last_run_start": None,
    "last_run_end": None,
    "last_run_saved": 0,
    "total_articles_this_run": 0,
}

# ============================================================
# SETTINGS
# ============================================================

GROQ_MODEL = "llama-3.3-70b-versatile"

ROBOT_INTERVAL_HOURS = 6

# Number of articles per country when robot runs
ARTICLES_PER_COUNTRY = 5

# ============================================================
# COUNTRIES
# ============================================================

COUNTRIES = {

    "ma": {
        "name": "Morocco",
        "native": "المغرب",
        "region": "africa",
        "google_news": "MA",
        "languages": ["ar", "fr", "en"]
    },

    "dz": {
        "name": "Algeria",
        "native": "الجزائر",
        "region": "africa",
        "google_news": "DZ",
        "languages": ["ar", "fr", "en"]
    },

    "tn": {
        "name": "Tunisia",
        "native": "تونس",
        "region": "africa",
        "google_news": "TN",
        "languages": ["ar", "fr", "en"]
    },

    "fr": {
        "name": "France",
        "native": "France",
        "region": "eu",
        "google_news": "FR",
        "languages": ["fr", "en", "ar"]
    },

    "es": {
        "name": "Spain",
        "native": "España",
        "region": "eu",
        "google_news": "ES",
        "languages": ["es", "en", "fr"]
    },

    "gb": {
        "name": "United Kingdom",
        "native": "United Kingdom",
        "region": "eu",
        "google_news": "GB",
        "languages": ["en", "fr", "es"]
    },

    "de": {
        "name": "Germany",
        "native": "Deutschland",
        "region": "eu",
        "google_news": "DE",
        "languages": ["de", "en", "fr"]
    },

    "it": {
        "name": "Italy",
        "native": "Italia",
        "region": "eu",
        "google_news": "IT",
        "languages": ["it", "en", "fr"]
    },

    "us": {
        "name": "United States",
        "native": "United States",
        "region": "usa",
        "google_news": "US",
        "languages": ["en", "es", "fr"]
    },

    "ca": {
        "name": "Canada",
        "native": "Canada",
        "region": "usa",
        "google_news": "CA",
        "languages": ["en", "fr"]
    },

    "br": {
        "name": "Brazil",
        "native": "Brasil",
        "region": "global",
        "google_news": "BR",
        "languages": ["pt", "en", "es"]
    },

    "in": {
        "name": "India",
        "native": "India",
        "region": "global",
        "google_news": "IN",
        "languages": ["en", "hi"]
    },

    "sa": {
        "name": "Saudi Arabia",
        "native": "السعودية",
        "region": "khalij",
        "google_news": "SA",
        "languages": ["ar", "en", "fr"]
    },

    "ae": {
        "name": "United Arab Emirates",
        "native": "الإمارات",
        "region": "khalij",
        "google_news": "AE",
        "languages": ["ar", "en", "fr"]
    },

    "qa": {
        "name": "Qatar",
        "native": "قطر",
        "region": "khalij",
        "google_news": "QA",
        "languages": ["ar", "en", "fr"]
    },

    "eg": {
        "name": "Egypt",
        "native": "مصر",
        "region": "africa",
        "google_news": "EG",
        "languages": ["ar", "en", "fr"]
    },

    "tr": {
        "name": "Turkey",
        "native": "Türkiye",
        "region": "global",
        "google_news": "TR",
        "languages": ["tr", "en", "ar"]
    },

    "jp": {
        "name": "Japan",
        "native": "日本",
        "region": "global",
        "google_news": "JP",
        "languages": ["ja", "en"]
    },

    "au": {
        "name": "Australia",
        "native": "Australia",
        "region": "global",
        "google_news": "AU",
        "languages": ["en"]
    },

}

# ============================================================
# LANGUAGES
# ============================================================

LANGUAGES = {
    "ar": "العربية",
    "fr": "Français",
    "en": "English",
    "es": "Español"
}

# ============================================================
# SEO HELPERS
# ============================================================

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


# ============================================================
# DATABASE
# ============================================================

def get_db_connection():
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is missing in Railway Variables."
        )
    return psycopg.connect(DATABASE_URL)


def init_db():
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Main table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id SERIAL PRIMARY KEY,

                country TEXT,
                region TEXT,
                category TEXT,

                title_ar TEXT,
                title_fr TEXT,
                title_en TEXT,
                title_es TEXT,

                content_ar TEXT,
                content_fr TEXT,
                content_en TEXT,
                content_es TEXT,

                image_url TEXT,

                source_url TEXT,
                source_name TEXT,

                original_title TEXT,

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # ======================================================
        # Migration for old articles table
        # ======================================================

        columns = {
            "country": "TEXT",
            "region": "TEXT",
            "category": "TEXT",

            "title_ar": "TEXT",
            "title_fr": "TEXT",
            "title_en": "TEXT",
            "title_es": "TEXT",

            "content_ar": "TEXT",
            "content_fr": "TEXT",
            "content_en": "TEXT",
            "content_es": "TEXT",

            "image_url": "TEXT",

            "source_url": "TEXT",
            "source_name": "TEXT",

            "original_title": "TEXT"
        }

        for column, column_type in columns.items():
            cur.execute(
                f"""
                ALTER TABLE articles
                ADD COLUMN IF NOT EXISTS {column} {column_type};
                """
            )

        # Indexes
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_articles_country
            ON articles(country);
        """)

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_articles_created_at
            ON articles(created_at DESC);
        """)

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_articles_region
            ON articles(region);
        """)

        conn.commit()
        cur.close()
        conn.close()

        print("-> Database Ready")

    except Exception as e:
        print(f"!! Database initialization failed: {e}")


# ============================================================
# GROQ ROTATION
# ============================================================

def generate_with_groq(prompt):
    global current_groq_key

    if not GROQ_KEYS:
        print("!! NO GROQ API KEYS FOUND")
        return None

    total_keys = len(GROQ_KEYS)

    # Try every key
    for attempt in range(total_keys):

        key_index = current_groq_key
        api_key = GROQ_KEYS[key_index]

        print(f"-> Using Groq API #{key_index + 1}/{total_keys}")

        try:
            client = Groq(api_key=api_key)

            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a professional international news writer.\n\n"
                            "Your job is to transform real news topics into "
                            "clear, neutral and informative news articles.\n\n"
                            "IMPORTANT:\n"
                            "Do NOT turn every topic into an AI article.\n"
                            "Write about the actual subject.\n"
                            "If the topic is politics, explain the political event.\n"
                            "If the topic is sports, explain the sports event.\n"
                            "If the topic is economy, explain the economy event.\n"
                            "If the topic is technology, explain the technology event.\n"
                            "Do not invent names, numbers or facts.\n"
                            "Do not claim information that is not supported by the source.\n\n"
                            "Keep the article readable for normal users."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.35,
                max_tokens=1200
            )

            result = response.choices[0].message.content

            if not result:
                raise Exception("Empty Groq response")

            print(f"-> Groq API #{key_index + 1} SUCCESS")

            # Round-robin
            current_groq_key = (current_groq_key + 1) % total_keys

            return result.strip()

        except Exception as e:
            error = str(e)

            print(f"!! Groq API #{key_index + 1} FAILED: {error}")

            # Move to next key
            current_groq_key = (current_groq_key + 1) % total_keys

            # Rate limit
            if "429" in error or "rate_limit" in error.lower():
                print(f"!! API #{key_index + 1} RATE LIMITED")
                # Don't sleep for a long time.
                # Immediately try the next account.
                continue

            continue

    print("!! ALL GROQ KEYS FAILED")
    return None


# ============================================================
# IMAGE
# ============================================================

def generate_image(prompt):
    if not prompt:
        prompt = "international news"

    clean_prompt = urllib.parse.quote(
        prompt + ", realistic professional news photography"
    )

    return f"https://image.pollinations.ai/prompt/{clean_prompt}"


# ============================================================
# COUNTRY DETECTION
# ============================================================

def get_client_ip():
    # Railway / proxy
    forwarded = request.headers.get("X-Forwarded-For")

    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.remote_addr

    return ip


def detect_country():
    # Try cookie first
    saved_country = request.cookies.get("country")

    if saved_country in COUNTRIES:
        return saved_country

    try:
        ip = get_client_ip()

        # Local/private IP
        try:
            ip_obj = ipaddress.ip_address(ip)

            if (
                ip_obj.is_private
                or ip_obj.is_loopback
                or ip_obj.is_reserved
            ):
                return "ma"

        except Exception:
            pass

        response = requests.get(
            f"https://ipapi.co/{ip}/json/",
            timeout=3
        )

        if response.ok:
            data = response.json()
            country_code = data.get("country_code", "").lower()

            if country_code in COUNTRIES:
                return country_code

    except Exception as e:
        print(f"!! Country detection failed: {e}")

    # Default
    return "ma"


# ============================================================
# LANGUAGE DETECTION
# ============================================================

def detect_language(country):
    saved_language = request.cookies.get("lang")

    if saved_language in LANGUAGES:
        return saved_language

    accept_language = request.headers.get("Accept-Language", "").lower()

    # Browser language
    for language in LANGUAGES:
        if accept_language.startswith(language):
            return language

    # Country preferred language
    if country in COUNTRIES:
        languages = COUNTRIES[country]["languages"]

        if languages:
            # Only use our supported languages
            for language in languages:
                if language in LANGUAGES:
                    return language

    return "en"


# ============================================================
# NEWS RSS
# ============================================================

def get_country_news(country):
    if country not in COUNTRIES:
        country = "ma"

    country_info = COUNTRIES[country]
    google_country = country_info["google_news"]

    # Google News RSS
    url = (
        "https://news.google.com/rss"
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

            # Source
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


# ============================================================
# GENERATE ARTICLE
# ============================================================

def generate_article(news_item, country):
    country_info = COUNTRIES.get(country, COUNTRIES["ma"])
    country_name = country_info["name"]

    original_title = news_item["title"]
    source_description = news_item.get("description", "")

    prompt = f"""Create a news article based on this real news item.

COUNTRY:
{country_name}

ORIGINAL HEADLINE:
{original_title}

SOURCE INFORMATION:
{source_description}

Return ONLY valid JSON.

Use exactly this structure:

{{
"title": "accurate title",
"content": "news article of around 400-600 words",
"category": "Politics",
"image_prompt": "short realistic image description"
}}

Rules:

Discuss the ACTUAL topic in the headline.
Do NOT automatically make it about AI.
Do NOT invent facts.
Do NOT invent statistics.
Do NOT invent quotes.
Do NOT change the main subject.
Be neutral.
Explain what happened and why it matters.
Mention the country/context when relevant.

The article must be useful for a normal reader.
"""

    raw = generate_with_groq(prompt)

    if not raw:
        return None

    try:
        clean = raw.strip()

        # Remove markdown fences
        if clean.startswith("```"):
            clean = clean.replace("```json", "")
            clean = clean.replace("```", "")
            clean = clean.strip()

        data = json.loads(clean)

        return data

    except Exception as e:
        print(f"!! JSON parsing failed: {e}")
        print(f"RAW RESPONSE: {raw[:500]}")
        return None


# ============================================================
# TRANSLATION
# ============================================================

def translate_article(title, content, language):
    language_names = {
        "ar": "Arabic",
        "fr": "French",
        "en": "English",
        "es": "Spanish"
    }

    target = language_names.get(language, "English")

    prompt = f"""Translate this news article into {target}.

IMPORTANT:

Preserve the meaning.
Do not add information.
Do not remove information.
Keep names and numbers correct.
Write natural professional news language.

TITLE:
{title}

CONTENT:
{content}

Return ONLY JSON:

{{
"title": "...",
"content": "..."
}}
"""

    raw = generate_with_groq(prompt)

    if not raw:
        return None

    try:
        clean = raw.strip()

        if clean.startswith("```"):
            clean = clean.replace("```json", "")
            clean = clean.replace("```", "")
            clean = clean.strip()

        data = json.loads(clean)

        return data

    except Exception as e:
        print(f"!! Translation failed: {e}")
        return None


# ============================================================
# CHECK DUPLICATE
# ============================================================

def article_exists(country, source_url):
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT id
            FROM articles
            WHERE country = %s
            AND source_url = %s
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


# ============================================================
# SAVE ARTICLE
# ============================================================

def save_article(country, news_item, article_data, translations):
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        country_info = COUNTRIES.get(country, COUNTRIES["ma"])
        region = country_info["region"]

        category = article_data.get("category", "News")

        title_en = article_data.get("title", news_item["title"])
        content_en = article_data.get("content", "")

        # Arabic
        ar = translations.get("ar", {})
        title_ar = ar.get("title", title_en)
        content_ar = ar.get("content", content_en)

        # French
        fr = translations.get("fr", {})
        title_fr = fr.get("title", title_en)
        content_fr = fr.get("content", content_en)

        # Spanish
        es = translations.get("es", {})
        title_es = es.get("title", title_en)
        content_es = es.get("content", content_en)

        image_url = generate_image(
            article_data.get("image_prompt", news_item["title"])
        )

        cur.execute(
            """
            INSERT INTO articles (
                country,
                region,
                category,

                title_ar,
                title_fr,
                title_en,
                title_es,

                content_ar,
                content_fr,
                content_en,
                content_es,

                image_url,

                source_url,
                source_name,

                original_title,

                created_at
            )

            VALUES (
                %s, %s, %s,

                %s, %s, %s, %s,

                %s, %s, %s, %s,

                %s,

                %s, %s,

                %s,

                CURRENT_TIMESTAMP
            )
            """,
            (
                country,
                region,
                category,

                title_ar,
                title_fr,
                title_en,
                title_es,

                content_ar,
                content_fr,
                content_en,
                content_es,

                image_url,

                news_item.get("link", ""),
                news_item.get("source", ""),

                news_item.get("title", "")
            )
        )

        conn.commit()

        cur.close()
        conn.close()

        print(f"-> SAVED [{country}] {title_en[:80]}")

        return True

    except Exception as e:
        print(f"!! Save article failed: {e}")
        return False


# ============================================================
# ROBOT FOR ONE COUNTRY
# ============================================================

def process_country(country):
    print("\n====================================")
    print(f"-> Robot checking country: {country}")
    print("====================================")

    # Update live status so visitors can see which country is being processed
    robot_status["current_country"] = country

    news = get_country_news(country)

    if not news:
        print(f"!! No news found for {country}")
        return 0

    saved = 0

    for news_item in news:

        if saved >= ARTICLES_PER_COUNTRY:
            break

        source_url = news_item.get("link", "")

        # Avoid duplicates
        if source_url:
            if article_exists(country, source_url):
                print(f"-> Already exists: {news_item['title'][:70]}")
                continue

        print(f"\n-> Generating: {news_item['title']}")

        article_data = generate_article(news_item, country)

        if not article_data:
            print("!! Article generation failed")
            continue

        title = article_data.get("title", news_item["title"])
        content = article_data.get("content", "")

        translations = {}

        # ====================================================
        # Arabic
        # ====================================================
        print("-> Translating Arabic...")
        ar = translate_article(title, content, "ar")
        if ar:
            translations["ar"] = ar

        # ====================================================
        # French
        # ====================================================
        print("-> Translating French...")
        fr = translate_article(title, content, "fr")
        if fr:
            translations["fr"] = fr

        # ====================================================
        # Spanish
        # ====================================================
        print("-> Translating Spanish...")
        es = translate_article(title, content, "es")
        if es:
            translations["es"] = es

        # ====================================================
        # Save
        # ====================================================
        success = save_article(country, news_item, article_data, translations)

        if success:
            saved += 1
            # Keep the live counter growing during the run
            robot_status["total_articles_this_run"] += 1

        # Small pause
        time.sleep(2)

    print(f"-> Country {country}: {saved} new articles saved")

    return saved


# ============================================================
# MAIN ROBOT
# ============================================================

def run_robot():
    if not robot_lock.acquire(blocking=False):
        print("!! Robot already running")
        return

    # ---- mark robot as ON (visible to visitors) ----
    robot_status["running"] = True
    robot_status["current_country"] = None
    robot_status["last_run_start"] = datetime.now()
    robot_status["total_articles_this_run"] = 0

    try:
        print("\n\n==========================================")
        print(f"NEWS ROBOT STARTED {datetime.now()}")
        print("==========================================")

        # ====================================================
        # Generate for all configured countries
        # ====================================================

        for country in COUNTRIES.keys():
            try:
                process_country(country)
            except Exception as e:
                print(f"!! Country {country} failed: {e}")

            # pause between countries
            time.sleep(3)

        print("\n==========================================")
        print(f"NEWS ROBOT FINISHED {datetime.now()}")
        print("==========================================\n")

    finally:
        # ---- mark robot as OFF, save summary for the banner ----
        robot_status["running"] = False
        robot_status["current_country"] = None
        robot_status["last_run_end"] = datetime.now()
        robot_status["last_run_saved"] = robot_status["total_articles_this_run"]

        robot_lock.release()


# ============================================================
# ROUTES
# ============================================================

@app.route("/")
def home():
    # Detect user country
    country = request.args.get("country")

    if country not in COUNTRIES:
        country = detect_country()

    # Detect language
    lang = request.args.get("lang")

    if lang not in LANGUAGES:
        lang = detect_language(country)

    # Current country
    country_info = COUNTRIES.get(country, COUNTRIES["ma"])

    title_column = f"title_{lang}"
    content_column = f"content_{lang}"

    articles = []

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        query = f"""
            SELECT
                id,
                {title_column},
                {content_column},
                image_url,
                category,
                source_name,
                created_at
            FROM articles
            WHERE country = %s
            ORDER BY created_at DESC
            LIMIT 30
        """

        cur.execute(query, (country,))

        rows = cur.fetchall()

        cur.close()
        conn.close()

        for row in rows:
            articles.append({
                "id": row[0],
                "title": row[1],
                "content": row[2] or "",
                "image": row[3],
                "category": row[4],
                "source": row[5],
                "created_at": row[6]
            })

    except Exception as e:
        print(f"!! Home database error: {e}")

    return render_template_string(
        HOME_TEMPLATE,
        base_css=BASE_CSS,
        articles=articles,
        countries=COUNTRIES,
        languages=LANGUAGES,
        current_country=country,
        current_language=lang,
        ga_id=GA_ID,
        adsense_client=ADSENSE_CLIENT,
        country_name=country_info["name"],
        site_url=SITE_URL,
        seo_description=seo_description,
        canonical_url=absolute_url(
            f"/?country={urllib.parse.quote(country)}&lang={urllib.parse.quote(lang)}"
        ),
        absolute_home_urls={
            code: absolute_url(
                f"/?country={urllib.parse.quote(country)}&lang={urllib.parse.quote(code)}"
            )
            for code in LANGUAGES
        },
        robot_status=robot_status,
        robot_interval=ROBOT_INTERVAL_HOURS,
        current_country_name=(
            COUNTRIES[robot_status["current_country"]]["name"]
            if robot_status["current_country"] in COUNTRIES
            else None
        )
    )


@app.route("/ads.txt")
def ads_txt():
    if not ADSENSE_CLIENT:
        return (
            "AdSense publisher ID is not configured.",
            503,
            {"Content-Type": "text/plain; charset=utf-8"}
        )

    publisher_id = ADSENSE_CLIENT.replace("ca-", "").strip()

    return (
        f"google.com, {publisher_id}, DIRECT, f08c47fec0942fa0\n"
    ), 200, {
        "Content-Type": "text/plain; charset=utf-8"
    }


# ============================================================
# ARTICLE DETAILS
# ============================================================

@app.route("/article/<int:article_id>")
def article_detail(article_id):
    country = request.args.get("country")

    if country not in COUNTRIES:
        country = detect_country()

    lang = request.args.get("lang")

    if lang not in LANGUAGES:
        lang = detect_language(country)

    title_column = f"title_{lang}"
    content_column = f"content_{lang}"

    article = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        query = f"""
            SELECT
                id,
                {title_column},
                {content_column},
                image_url,
                category,
                source_url,
                source_name,
                original_title,
                created_at,
                country
            FROM articles
            WHERE id = %s
            LIMIT 1
        """

        cur.execute(query, (article_id,))

        row = cur.fetchone()

        cur.close()
        conn.close()

        if row:
            article = {
                "id": row[0],
                "title": row[1],
                "content": row[2],
                "image": row[3],
                "category": row[4],
                "source_url": row[5],
                "source_name": row[6],
                "original_title": row[7],
                "created_at": row[8],
                "country": row[9]
            }

    except Exception as e:
        print(f"!! Article detail error: {e}")

    if not article:
        return ("Article not found", 404)

    alternate_urls = {
        code: absolute_url(article_path(article_id, article["country"], code))
        for code in LANGUAGES
    }

    return render_template_string(
        ARTICLE_TEMPLATE,
        base_css=BASE_CSS,
        article=article,
        countries=COUNTRIES,
        languages=LANGUAGES,
        current_country=country,
        current_language=lang,
        ga_id=GA_ID,
        adsense_client=ADSENSE_CLIENT,
        site_url=SITE_URL,
        seo_description=seo_description,
        alternate_urls=alternate_urls,
        canonical_url=absolute_url(
            article_path(article_id, country, lang)
        )
    )


# ============================================================
# CHANGE COUNTRY
# ============================================================

@app.route("/set-country/<country>")
def set_country(country):
    if country not in COUNTRIES:
        country = "ma"

    lang = request.args.get("lang", "en")

    response = redirect(
        url_for("home", country=country, lang=lang)
    )

    response.set_cookie(
        "country",
        country,
        max_age=60 * 60 * 24 * 365
    )

    return response


# ============================================================
# CHANGE LANGUAGE
# ============================================================

@app.route("/set-language/<lang>")
def set_language(lang):
    if lang not in LANGUAGES:
        lang = "en"

    country = request.args.get("country")

    if country not in COUNTRIES:
        country = detect_country()

    response = redirect(
        url_for("home", country=country, lang=lang)
    )

    response.set_cookie(
        "lang",
        lang,
        max_age=60 * 60 * 24 * 365
    )

    return response


# ============================================================
# LIVE ROBOT STATUS (JSON) - used by the front-end badge to auto-refresh
# ============================================================

@app.route("/robot-status")
def robot_status_json():
    data = dict(robot_status)

    data["last_run_start"] = (
        robot_status["last_run_start"].isoformat()
        if robot_status["last_run_start"] else None
    )

    data["last_run_end"] = (
        robot_status["last_run_end"].isoformat()
        if robot_status["last_run_end"] else None
    )

    if robot_status["current_country"] in COUNTRIES:
        data["current_country_name"] = COUNTRIES[robot_status["current_country"]]["name"]
    else:
        data["current_country_name"] = None

    return jsonify(data)


# ============================================================
# SEO ROUTES
# ============================================================

@app.route("/robots.txt")
def robots_txt():
    sitemap_url = absolute_url("/sitemap.xml")
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /health\n"
        "Disallow: /run-robot\n\n"
        f"Sitemap: {sitemap_url}\n"
    ), 200, {"Content-Type": "text/plain; charset=utf-8"}


@app.route("/sitemap.xml")
def sitemap_xml():
    urls = []

    # Home pages for each configured country/language.
    for country_code in COUNTRIES:
        for lang_code in LANGUAGES:
            urls.append(
                absolute_url(
                    f"/?country={urllib.parse.quote(country_code)}"
                    f"&lang={urllib.parse.quote(lang_code)}"
                )
            )

    # Article URLs.
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, country, created_at
            FROM articles
            ORDER BY created_at DESC
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        for article_id, country_code, created_at in rows:
            for lang_code in LANGUAGES:
                urls.append(
                    absolute_url(
                        article_path(article_id, country_code, lang_code)
                    )
                )
    except Exception as e:
        print(f"!! Sitemap database error: {e}")

    # Remove duplicates while preserving order.
    urls = list(dict.fromkeys(urls))

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    ]

    for url in urls:
        parts.append(
            "<url><loc>" + url.replace("&", "&amp;") + "</loc></url>"
        )

    parts.append("</urlset>")

    return "\n".join(parts), 200, {
        "Content-Type": "application/xml; charset=utf-8"
    }


# ============================================================
# MANUAL ROBOT TEST
# ============================================================

@app.route("/run-robot")
def manual_robot():
    # Simple manual trigger
    run_robot()

    return """
    <h2>Robot finished.</h2>
    <a href="/">Back to website</a>
    """


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/health")
def health():
    return {
        "status": "ok",
        "groq_keys": len(GROQ_KEYS),
        "database": bool(DATABASE_URL),
        "robot": "running" if robot_status["running"] else "idle"
    }


# ============================================================
# SHARED CSS
# ============================================================

BASE_CSS = """
:root {
    --bg: #0b0e14;
    --surface: #12161f;
    --surface-2: #1a1f2b;
    --border: #232938;
    --text: #eef1f6;
    --text-dim: #9aa3b5;
    --accent: #4f7cff;
    --accent-2: #22c55e;
}
* { box-sizing: border-box; }
body {
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    line-height: 1.55;
}
a { color: inherit; text-decoration: none; }
header.site-header {
    position: sticky;
    top: 0;
    z-index: 10;
    background: rgba(11,14,20,0.92);
    backdrop-filter: blur(8px);
    border-bottom: 1px solid var(--border);
    padding: 14px 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 12px;
}
.logo {
    font-weight: 800;
    font-size: 1.3rem;
    letter-spacing: 0.5px;
    color: var(--accent);
}
.controls { display: flex; gap: 10px; flex-wrap: wrap; }
.controls select {
    background: var(--surface-2);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 8px 10px;
    font-size: 0.9rem;
}
main { max-width: 1100px; margin: 0 auto; padding: 24px 20px 60px; }
.hero { padding: 24px 0 10px; }
.hero h1 { margin: 0 0 6px; font-size: 1.8rem; }
.hero p { color: var(--text-dim); margin: 0; }
.robot-banner {
    display: flex;
    align-items: center;
    gap: 10px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 10px 14px;
    margin: 16px 0;
    font-size: 0.9rem;
    color: var(--text-dim);
}
.robot-dot {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    background: var(--accent-2);
    display: inline-block;
    box-shadow: 0 0 0 0 rgba(34,197,94,0.6);
    animation: pulse 1.6s infinite;
}
@keyframes pulse {
    0% { box-shadow: 0 0 0 0 rgba(34,197,94,0.6); }
    70% { box-shadow: 0 0 0 8px rgba(34,197,94,0); }
    100% { box-shadow: 0 0 0 0 rgba(34,197,94,0); }
}
.grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 18px;
    margin-top: 20px;
}
.card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 14px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    transition: transform 0.15s ease, border-color 0.15s ease;
}
.card:hover { transform: translateY(-2px); border-color: var(--accent); }
.card img { width: 100%; height: 160px; object-fit: cover; display: block; background: var(--surface-2); }
.card-content { padding: 14px 16px 18px; display: flex; flex-direction: column; gap: 8px; flex: 1; }
.category {
    align-self: flex-start;
    background: var(--surface-2);
    color: var(--accent);
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding: 3px 9px;
    border-radius: 999px;
}
.card h2 { margin: 0; font-size: 1.05rem; line-height: 1.35; }
.card p { margin: 0; color: var(--text-dim); font-size: 0.9rem; flex: 1; }
.badge-ai {
    display: inline-block;
    margin-left: 6px;
    font-size: 0.65rem;
    font-weight: 700;
    background: var(--surface-2);
    color: var(--text-dim);
    padding: 2px 6px;
    border-radius: 6px;
    vertical-align: middle;
}
.read { color: var(--accent); font-weight: 600; font-size: 0.9rem; margin-top: 4px; }
.no-news {
    text-align: center;
    padding: 60px 20px;
    color: var(--text-dim);
}
.no-news h2 { color: var(--text); display: flex; align-items: center; justify-content: center; gap: 8px; }
.article-header { max-width: 760px; margin: 0 auto; }
.back { color: var(--accent); font-weight: 600; display: inline-block; margin-bottom: 16px; }
.article-header img { width: 100%; max-height: 420px; object-fit: cover; border-radius: 14px; margin: 12px 0 20px; }
.article-header h1 { font-size: 1.9rem; line-height: 1.3; margin: 6px 0 20px; }
.content { white-space: pre-line; font-size: 1.05rem; }
.disclaimer {
    margin-top: 30px;
    padding: 14px 16px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    font-size: 0.85rem;
    color: var(--text-dim);
}
.source {
    margin-top: 20px;
    padding: 14px 16px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    font-size: 0.9rem;
}
.source a { color: var(--accent); font-weight: 600; }
footer {
    text-align: center;
    color: var(--text-dim);
    font-size: 0.8rem;
    padding: 30px 20px;
    border-top: 1px solid var(--border);
    margin-top: 30px;
}
"""

# ============================================================
# HOME HTML
# ============================================================

HOME_TEMPLATE = """<!DOCTYPE html>
<html lang="{{ current_language }}" dir="{{ 'rtl' if current_language == 'ar' else 'ltr' }}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" type="image/png" href="{{ url_for('static', filename='logo.png') }}">
<title>Corvex News — {{ country_name }}</title>
<meta name="description" content="{{ seo_description(country_name ~ ' latest news') }}">
<link rel="canonical" href="{{ canonical_url }}">
{% for code, url in absolute_home_urls.items() %}
<link rel="alternate" hreflang="{{ code }}" href="{{ url }}">
{% endfor %}

{% if ga_id %}
<script async src="https://www.googletagmanager.com/gtag/js?id={{ ga_id }}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', '{{ ga_id }}');
</script>
{% endif %}

{% if adsense_client %}
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={{ adsense_client }}"
 crossorigin="anonymous"></script>
{% endif %}

<style>{{ base_css }}</style>
</head>
<body>

<header class="site-header">
    <div class="logo">CORVEX NEWS</div>

    <div class="controls">
        <form method="get">
            <input type="hidden" name="country" value="{{ current_country }}">
            <select name="lang" onchange="this.form.submit()">
                {% for code, name in languages.items() %}
                <option value="{{ code }}" {% if code == current_language %}selected{% endif %}>{{ name }}</option>
                {% endfor %}
            </select>
        </form>

        <form method="get">
            <input type="hidden" name="lang" value="{{ current_language }}">
            <select name="country" onchange="this.form.submit()">
                {% for code, info in countries.items() %}
                <option value="{{ code }}" {% if code == current_country %}selected{% endif %}>{{ info.native }}</option>
                {% endfor %}
            </select>
        </form>
    </div>
</header>

<main>

    <div class="hero">
        <h1>Latest News — {{ country_name }}</h1>
        <p>News selected for your country and language.</p>
    </div>
    {% if articles %}
        <div class="grid">
        {% for article in articles %}
            <article class="card">
                {% if article.image %}
                    <img src="{{ article.image }}" alt="{{ article.title }}" loading="lazy">
                {% endif %}
                <div class="card-content">
                    <span class="category">{{ article.category or "News" }}</span>
                    <h2>{{ article.title }}<span class="badge-ai">AI</span></h2>
                    <p>{{ article.content[:240] }}{% if article.content|length > 240 %}...{% endif %}</p>
                    <a class="read" href="{{ url_for('article_detail', article_id=article.id, country=current_country, lang=current_language) }}">
                        Read article &rarr;
                    </a>
                </div>
            </article>
        {% endfor %}
        </div>
    {% else %}
        <div class="no-news">
            <h2><span class="robot-dot"></span> No news yet</h2>
            <p>Collecting the latest news for {{ country_name }}. Check back in a few minutes.</p>
        </div>
    {% endif %}

</main>

<footer>
    &copy; {{ 2026 }} Corvex News.
</footer>

</body>
</html>
"""

# ============================================================
# ARTICLE HTML
# ============================================================

ARTICLE_TEMPLATE = """<!DOCTYPE html>
<html lang="{{ current_language }}" dir="{{ 'rtl' if current_language == 'ar' else 'ltr' }}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ article.title }} — Corvex News</title>
<meta name="description" content="{{ seo_description(article.content) }}">
<link rel="canonical" href="{{ canonical_url }}">
<link rel="icon" type="image/png" href="{{ url_for('static', filename='logo.png') }}">
{% for code, url in alternate_urls.items() %}
<link rel="alternate" hreflang="{{ code }}" href="{{ url }}">
{% endfor %}

{% if ga_id %}
<script async src="https://www.googletagmanager.com/gtag/js?id={{ ga_id }}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', '{{ ga_id }}');
</script>
{% endif %}

{% if adsense_client %}
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={{ adsense_client }}"
 crossorigin="anonymous"></script>
{% endif %}

<style>{{ base_css }}</style>
</head>
<body>

<header class="site-header">
    <a class="logo" href="{{ url_for('home', country=current_country, lang=current_language) }}">CORVEX NEWS</a>
</header>

<main>
    <div class="article-header">

        <a class="back" href="{{ url_for('home', country=current_country, lang=current_language) }}">&larr; Back to news</a>

        {% if article.image %}
            <img src="{{ article.image }}" alt="{{ article.title }}">
        {% endif %}

        <span class="category">{{ article.category or "News" }}</span>

        <h1>{{ article.title }}<span class="badge-ai">Generated by AI</span></h1>

        <div class="content">{{ article.content }}</div>

        <div class="disclaimer">
            This article was automatically generated and translated by our robot
            from a real source cited below. It may contain inaccuracies; please
            check the original source for verification.
        </div>

        {% if article.source_url %}
            <div class="source">
                <strong>Source:</strong>
                {% if article.source_name %}{{ article.source_name }}{% endif %}
                <br><br>
                <a href="{{ article.source_url }}" target="_blank" rel="noopener noreferrer">
                    View original source &rarr;
                </a>
            </div>
        {% endif %}

    </div>
</main>

<footer>
    &copy; {{ 2026 }} Corvex News.

</body>
</html>
"""

# ============================================================
# START DATABASE
# ============================================================

init_db()

# ============================================================
# START ROBOT SCHEDULER
# ============================================================

scheduler = BackgroundScheduler(daemon=True)

# Run immediately after startup
scheduler.add_job(
    run_robot,
    trigger="date",
    run_date=datetime.now(),
    id="initial_robot",
    replace_existing=True
)

# Then every 6 hours
scheduler.add_job(
    run_robot,
    trigger="interval",
    hours=ROBOT_INTERVAL_HOURS,
    id="news_robot",
    replace_existing=True
)

scheduler.start()

print("-> News Robot Scheduler Started")
print(f"-> Groq API keys available: {len(GROQ_KEYS)}")

# ============================================================
# LOCAL DEVELOPMENT
# ============================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
