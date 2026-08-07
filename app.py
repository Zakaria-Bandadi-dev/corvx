import os
import json
import time
import random
import urllib.parse
import urllib.request
import sqlite3
import threading

import feedparser
import psycopg
from flask import Flask, request, render_template_string, redirect, url_for
from apscheduler.schedulers.background import BackgroundScheduler
from groq import Groq
from datetime import datetime


# ============================================================
# APP
# ============================================================

app = Flask(__name__)


# ============================================================
# CONFIGURATION
# ============================================================

DATABASE_URL = os.getenv("DATABASE_URL")

# ------------------------------------------------------------
# Groq API keys
#
# Railway variables:
#
# GROQ_API_KEY
# OR
# GROQ_API_KEY1
# GROQ_API_KEY2
# GROQ_API_KEY3
# GROQ_API_KEY4
# GROQ_API_KEY5
# ------------------------------------------------------------

GROQ_KEYS = []

for i in range(1, 6):
    key = os.getenv(f"GROQ_API_KEY{i}")
    if key:
        GROQ_KEYS.append(key)

# Support also simple GROQ_API_KEY
simple_key = os.getenv("GROQ_API_KEY")

if simple_key and simple_key not in GROQ_KEYS:
    GROQ_KEYS.insert(0, simple_key)

CURRENT_GROQ_KEY = 0

# Model
GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "llama-3.3-70b-versatile"
)


# ============================================================
# COUNTRIES
# ============================================================

COUNTRIES = {
    "MA": {
        "name": "Morocco",
        "ar": "المغرب",
        "fr": "Maroc",
        "en": "Morocco",
        "es": "Marruecos",
        "news": "MA"
    },

    "FR": {
        "name": "France",
        "ar": "فرنسا",
        "fr": "France",
        "en": "France",
        "es": "Francia",
        "news": "FR"
    },

    "ES": {
        "name": "Spain",
        "ar": "إسبانيا",
        "fr": "Espagne",
        "en": "Spain",
        "es": "España",
        "news": "ES"
    },

    "US": {
        "name": "United States",
        "ar": "الولايات المتحدة",
        "fr": "États-Unis",
        "en": "United States",
        "es": "Estados Unidos",
        "news": "US"
    },

    "GB": {
        "name": "United Kingdom",
        "ar": "المملكة المتحدة",
        "fr": "Royaume-Uni",
        "en": "United Kingdom",
        "es": "Reino Unido",
        "news": "GB"
    },

    "CA": {
        "name": "Canada",
        "ar": "كندا",
        "fr": "Canada",
        "en": "Canada",
        "es": "Canadá",
        "news": "CA"
    },

    "DE": {
        "name": "Germany",
        "ar": "ألمانيا",
        "fr": "Allemagne",
        "en": "Germany",
        "es": "Alemania",
        "news": "DE"
    },

    "IT": {
        "name": "Italy",
        "ar": "إيطاليا",
        "fr": "Italie",
        "en": "Italy",
        "es": "Italia",
        "news": "IT"
    },

    "SA": {
        "name": "Saudi Arabia",
        "ar": "السعودية",
        "fr": "Arabie saoudite",
        "en": "Saudi Arabia",
        "es": "Arabia Saudita",
        "news": "SA"
    },

    "AE": {
        "name": "United Arab Emirates",
        "ar": "الإمارات",
        "fr": "Émirats arabes unis",
        "en": "United Arab Emirates",
        "es": "Emiratos Árabes Unidos",
        "news": "AE"
    }
}


LANGUAGES = {
    "ar": "العربية",
    "fr": "Français",
    "en": "English",
    "es": "Español"
}


# ============================================================
# DATABASE
# ============================================================

def get_db_connection():

    if DATABASE_URL:

        return psycopg.connect(DATABASE_URL)

    conn = sqlite3.connect(
        "corvex.db",
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    return conn


def init_db():

    try:

        conn = get_db_connection()

        cur = conn.cursor()

        if DATABASE_URL:

            query = """
            CREATE TABLE IF NOT EXISTS articles (

                id SERIAL PRIMARY KEY,

                country TEXT NOT NULL,

                category TEXT,

                source_title TEXT,

                source_url TEXT,

                image_url TEXT,

                title_ar TEXT,
                title_fr TEXT,
                title_en TEXT,
                title_es TEXT,

                content_ar TEXT,
                content_fr TEXT,
                content_en TEXT,
                content_es TEXT,

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

            );
            """

        else:

            query = """
            CREATE TABLE IF NOT EXISTS articles (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                country TEXT NOT NULL,

                category TEXT,

                source_title TEXT,

                source_url TEXT,

                image_url TEXT,

                title_ar TEXT,
                title_fr TEXT,
                title_en TEXT,
                title_es TEXT,

                content_ar TEXT,
                content_fr TEXT,
                content_en TEXT,
                content_es TEXT,

                created_at DATETIME DEFAULT CURRENT_TIMESTAMP

            );
            """

        cur.execute(query)

        conn.commit()

        conn.close()

        print("-> Database Ready")

    except Exception as e:

        print(
            f"!! Database initialization failed: {e}"
        )


# IMPORTANT:
# Gunicorn imports app.py.
# Therefore database initialization happens here.

init_db()


# ============================================================
# GROQ
# ============================================================

def get_groq_client():

    global CURRENT_GROQ_KEY

    if not GROQ_KEYS:

        print("!! No GROQ API keys found")

        return None

    key = GROQ_KEYS[CURRENT_GROQ_KEY]

    return Groq(api_key=key)


def ask_groq(prompt):

    global CURRENT_GROQ_KEY

    if not GROQ_KEYS:

        return None

    for attempt in range(len(GROQ_KEYS)):

        try:

            client = get_groq_client()

            response = client.chat.completions.create(

                model=GROQ_MODEL,

                messages=[

                    {
                        "role": "system",

                        "content": """
You are a professional international news editor.

You must NEVER invent facts.

Use ONLY the information contained in the provided source.

Write a clear, neutral and informative article.

The article can be about ANY category:
politics, economy, business, technology,
sports, science, health, entertainment,
culture, society, environment, education,
international affairs, local news, etc.

Do not turn every story into a technology story.

Return valid JSON when requested.
"""
                    },

                    {
                        "role": "user",
                        "content": prompt
                    }

                ],

                temperature=0.3,

                max_tokens=1800

            )

            return response.choices[0].message.content

        except Exception as e:

            print(
                f"!! Groq key #{CURRENT_GROQ_KEY + 1} failed: {e}"
            )

            CURRENT_GROQ_KEY = (
                CURRENT_GROQ_KEY + 1
            ) % len(GROQ_KEYS)

            time.sleep(2)

    return None


# ============================================================
# GOOGLE NEWS RSS
# ============================================================

def get_country_news(country_code):

    """
    Get current news for a country using Google News RSS.

    This is the important part:
    the robot does NOT randomly invent topics.

    It first gets real current news.
    """

    country = COUNTRIES.get(country_code)

    if not country:
        return []

    google_country = country["news"]

    url = (
        "https://news.google.com/rss"
        f"?hl=en-US&gl={google_country}"
        "&ceid="
        f"{google_country}:en"
    )

    try:

        feed = feedparser.parse(url)

        articles = []

        for entry in feed.entries[:8]:

            title = getattr(
                entry,
                "title",
                ""
            )

            link = getattr(
                entry,
                "link",
                ""
            )

            summary = getattr(
                entry,
                "summary",
                ""
            )

            if not title:
                continue

            articles.append({

                "title": title,

                "url": link,

                "summary": summary

            })

        return articles

    except Exception as e:

        print(
            f"!! News RSS failed for {country_code}: {e}"
        )

        return []


# ============================================================
# IMAGE
# ============================================================

def generate_image(prompt):

    encoded = urllib.parse.quote(
        prompt
        + ", realistic professional news photography"
    )

    return (
        "https://image.pollinations.ai/prompt/"
        + encoded
    )


# ============================================================
# GENERATE ARTICLE
# ============================================================

def generate_article(country_code, source):

    country = COUNTRIES[country_code]

    prompt = f"""
Create a professional news article based ONLY on this source.

COUNTRY:
{country["name"]}

SOURCE TITLE:
{source["title"]}

SOURCE SUMMARY:
{source["summary"]}

SOURCE URL:
{source["url"]}

Important:

1. Identify the real category of the story.
2. Do NOT automatically classify it as technology.
3. Categories can be:
   politics
   economy
   business
   technology
   sports
   science
   health
   entertainment
   culture
   society
   environment
   education
   international
   local

4. Write approximately 400-600 words.
5. Do not invent statistics.
6. Do not invent quotes.
7. Do not invent events.
8. Keep the article neutral.
9. Make the title attractive but factual.

Return ONLY valid JSON:

{{
    "title_en": "...",
    "category": "...",
    "content_en": "...",
    "image_prompt": "..."
}}
"""

    raw = ask_groq(prompt)

    if not raw:

        return None

    try:

        raw = raw.strip()

        # Remove markdown fences
        raw = raw.replace(
            "```json",
            ""
        )

        raw = raw.replace(
            "```",
            ""
        )

        raw = raw.strip()

        data = json.loads(raw)

        return data

    except Exception as e:

        print(
            f"!! JSON parsing failed: {e}"
        )

        print(raw[:1000])

        return None


# ============================================================
# TRANSLATIONS
# ============================================================

def translate_article(title, content):

    result = {}

    languages = {
        "ar": "Arabic",
        "fr": "French",
        "es": "Spanish"
    }

    for code, language in languages.items():

        prompt = f"""
Translate the following news article into {language}.

Do NOT change the facts.

Do NOT add information.

Keep the title and article separate.

Return ONLY valid JSON:

{{
    "title": "...",
    "content": "..."
}}

TITLE:
{title}

ARTICLE:
{content}
"""

        raw = ask_groq(prompt)

        if not raw:

            continue

        try:

            raw = raw.replace(
                "```json",
                ""
            )

            raw = raw.replace(
                "```",
                ""
            )

            raw = raw.strip()

            data = json.loads(raw)

            result[code] = data

        except Exception as e:

            print(
                f"!! Translation {code} failed: {e}"
            )

    return result


# ============================================================
# CHECK DUPLICATE
# ============================================================

def article_exists(source_url):

    try:

        conn = get_db_connection()

        cur = conn.cursor()

        if DATABASE_URL:

            cur.execute(
                """
                SELECT id
                FROM articles
                WHERE source_url = %s
                LIMIT 1
                """,
                (source_url,)
            )

        else:

            cur.execute(
                """
                SELECT id
                FROM articles
                WHERE source_url = ?
                LIMIT 1
                """,
                (source_url,)
            )

        result = cur.fetchone()

        conn.close()

        return result is not None

    except Exception as e:

        print(
            f"!! Duplicate check failed: {e}"
        )

        return False


# ============================================================
# SAVE ARTICLE
# ============================================================

def save_article(
    country_code,
    source,
    article,
    translations
):

    try:

        title_en = article.get(
            "title_en",
            ""
        )

        content_en = article.get(
            "content_en",
            ""
        )

        ar = translations.get(
            "ar",
            {}
        )

        fr = translations.get(
            "fr",
            {}
        )

        es = translations.get(
            "es",
            {}
        )

        image_url = generate_image(
            article.get(
                "image_prompt",
                title_en
            )
        )

        conn = get_db_connection()

        cur = conn.cursor()

        values = (

            country_code,

            article.get(
                "category",
                "general"
            ),

            source["title"],

            source["url"],

            image_url,

            ar.get("title", title_en),

            fr.get("title", title_en),

            title_en,

            es.get("title", title_en),

            ar.get("content", content_en),

            fr.get("content", content_en),

            content_en,

            es.get("content", content_en)

        )

        if DATABASE_URL:

            cur.execute(
                """
                INSERT INTO articles
                (
                    country,
                    category,
                    source_title,
                    source_url,
                    image_url,

                    title_ar,
                    title_fr,
                    title_en,
                    title_es,

                    content_ar,
                    content_fr,
                    content_en,
                    content_es
                )

                VALUES
                (
                    %s,%s,%s,%s,%s,
                    %s,%s,%s,%s,
                    %s,%s,%s,%s
                )
                """,
                values
            )

        else:

            cur.execute(
                """
                INSERT INTO articles
                (
                    country,
                    category,
                    source_title,
                    source_url,
                    image_url,

                    title_ar,
                    title_fr,
                    title_en,
                    title_es,

                    content_ar,
                    content_fr,
                    content_en,
                    content_es
                )

                VALUES
                (
                    ?,?,?,?,?,?,?,?,?,?,?,?,?
                )
                """,
                values
            )

        conn.commit()

        conn.close()

        print(
            f"-> Saved [{country_code}] {title_en[:70]}"
        )

        return True

    except Exception as e:

        print(
            f"!! Save article failed: {e}"
        )

        return False


# ============================================================
# ROBOT FOR ONE COUNTRY
# ============================================================

def run_robot_for_country(country_code):

    print(
        f"\n[{datetime.now()}]"
        f" Robot started for {country_code}"
    )

    news = get_country_news(
        country_code
    )

    if not news:

        print(
            f"!! No news for {country_code}"
        )

        return

    generated = 0

    for source in news:

        if generated >= 3:

            break

        if article_exists(
            source["url"]
        ):

            print(
                "-> Already exists:",
                source["title"][:60]
            )

            continue

        print(
            "-> Generating:",
            source["title"]
        )

        article = generate_article(
            country_code,
            source
        )

        if not article:

            continue

        translations = translate_article(
            article.get(
                "title_en",
                ""
            ),
            article.get(
                "content_en",
                ""
            )
        )

        save_article(
            country_code,
            source,
            article,
            translations
        )

        generated += 1

        # Small delay to avoid hammering API
        time.sleep(1)

    print(
        f"[{datetime.now()}]"
        f" Robot finished for {country_code}"
    )


# ============================================================
# GLOBAL ROBOT
# ============================================================

def run_robot():

    print(
        f"\n=============================="
    )

    print(
        f"[{datetime.now()}] GLOBAL ROBOT STARTED"
    )

    print(
        "=============================="
    )

    # IMPORTANT:
    # We don't generate for every country at once.
    #
    # This protects your Groq free API limits.

    for country_code in COUNTRIES.keys():

        try:

            run_robot_for_country(
                country_code
            )

        except Exception as e:

            print(
                f"!! Robot error "
                f"{country_code}: {e}"
            )

        # pause between countries
        time.sleep(2)

    print(
        f"[{datetime.now()}] GLOBAL ROBOT FINISHED"
    )


# ============================================================
# DETECT USER COUNTRY
# ============================================================

def get_user_country():

    """
    Try to detect the user's country.

    Railway usually forwards the real client IP
    through X-Forwarded-For.

    For local development it falls back to MA.
    """

    try:

        forwarded = request.headers.get(
            "X-Forwarded-For",
            ""
        )

        if forwarded:

            ip = forwarded.split(",")[0].strip()

        else:

            ip = request.remote_addr

        # localhost
        if ip in [
            "127.0.0.1",
            "::1",
            "localhost"
        ]:

            return "MA"

        url = (
            f"https://ipwho.is/{ip}"
        )

        with urllib.request.urlopen(
            url,
            timeout=3
        ) as response:

            data = json.loads(
                response.read().decode()
            )

        country_code = (
            data.get("country_code")
            or "MA"
        ).upper()

        if country_code in COUNTRIES:

            return country_code

        return "MA"

    except Exception as e:

        print(
            f"!! Country detection failed: {e}"
        )

        return "MA"


# ============================================================
# DEFAULT LANGUAGE
# ============================================================

def get_default_language(country):

    # Morocco -> Arabic
    if country == "MA":
        return "ar"

    # France -> French
    if country == "FR":
        return "fr"

    # Spain -> Spanish
    if country == "ES":
        return "es"

    # Most other countries -> English
    return "en"


# ============================================================
# GET ARTICLES
# ============================================================

def get_articles(country, limit=30):

    try:

        conn = get_db_connection()

        cur = conn.cursor()

        if DATABASE_URL:

            cur.execute(
                """
                SELECT
                    id,
                    country,
                    category,
                    source_title,
                    source_url,
                    image_url,
                    title_ar,
                    title_fr,
                    title_en,
                    title_es,
                    created_at
                FROM articles
                WHERE country = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (
                    country,
                    limit
                )
            )

        else:

            cur.execute(
                """
                SELECT
                    id,
                    country,
                    category,
                    source_title,
                    source_url,
                    image_url,
                    title_ar,
                    title_fr,
                    title_en,
                    title_es,
                    created_at
                FROM articles
                WHERE country = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (
                    country,
                    limit
                )
            )

        rows = cur.fetchall()

        conn.close()

        return rows

    except Exception as e:

        print(
            f"!! Get articles failed: {e}"
        )

        return []


# ============================================================
# GET ONE ARTICLE
# ============================================================

def get_article(article_id):

    try:

        conn = get_db_connection()

        cur = conn.cursor()

        if DATABASE_URL:

            cur.execute(
                """
                SELECT
                    id,
                    country,
                    category,
                    source_title,
                    source_url,
                    image_url,

                    title_ar,
                    title_fr,
                    title_en,
                    title_es,

                    content_ar,
                    content_fr,
                    content_en,
                    content_es,

                    created_at

                FROM articles
                WHERE id = %s
                """,
                (article_id,)
            )

        else:

            cur.execute(
                """
                SELECT
                    id,
                    country,
                    category,
                    source_title,
                    source_url,
                    image_url,

                    title_ar,
                    title_fr,
                    title_en,
                    title_es,

                    content_ar,
                    content_fr,
                    content_en,
                    content_es,

                    created_at

                FROM articles
                WHERE id = ?
                """,
                (article_id,)
            )

        row = cur.fetchone()

        conn.close()

        return row

    except Exception as e:

        print(
            f"!! Get article failed: {e}"
        )

        return None


# ============================================================
# HOME PAGE
# ============================================================

@app.route("/")
def home():

    # Detect country automatically
    detected_country = get_user_country()

    # User can manually select country
    country = request.args.get(
        "country",
        detected_country
    ).upper()

    if country not in COUNTRIES:

        country = detected_country

    # Language
    lang = request.args.get(
        "lang"
    )

    if lang not in LANGUAGES:

        lang = get_default_language(
            country
        )

    rows = get_articles(
        country,
        30
    )

    # If this country has no articles,
    # generate a few immediately.
    if not rows:

        print(
            f"-> No articles for {country}. "
            "Starting robot..."
        )

        thread = threading.Thread(
            target=run_robot_for_country,
            args=(country,),
            daemon=True
        )

        thread.start()

    articles = []

    for row in rows:

        # PostgreSQL tuple indexes
        article = {

            "id": row[0],

            "country": row[1],

            "category": row[2],

            "source_title": row[3],

            "source_url": row[4],

            "image": row[5],

            "title": row[
                {
                    "ar": 6,
                    "fr": 7,
                    "en": 8,
                    "es": 9
                }[lang]
            ]

        }

        articles.append(article)

    country_name = COUNTRIES[
        country
    ][lang]

    return render_template_string(

        HOME_HTML,

        articles=articles,

        countries=COUNTRIES,

        languages=LANGUAGES,

        country=country,

        lang=lang,

        country_name=country_name

    )


# ============================================================
# ARTICLE PAGE
# ============================================================

@app.route("/article/<int:article_id>")
def article_page(article_id):

    country = request.args.get(
        "country"
    )

    if not country:

        country = get_user_country()

    country = country.upper()

    if country not in COUNTRIES:

        country = "MA"

    lang = request.args.get(
        "lang"
    )

    if lang not in LANGUAGES:

        lang = get_default_language(
            country
        )

    row = get_article(
        article_id
    )

    if not row:

        return (
            "Article not found",
            404
        )

    indexes = {

        "ar": (6, 10),

        "fr": (7, 11),

        "en": (8, 12),

        "es": (9, 13)

    }

    title_index, content_index = indexes[
        lang
    ]

    article = {

        "id": row[0],

        "country": row[1],

        "category": row[2],

        "source_title": row[3],

        "source_url": row[4],

        "image": row[5],

        "title": row[title_index],

        "content": row[content_index],

        "created_at": row[14]

    }

    return render_template_string(

        ARTICLE_HTML,

        article=article,

        countries=COUNTRIES,

        languages=LANGUAGES,

        country=country,

        lang=lang

    )


# ============================================================
# MANUAL ROBOT ROUTE
# ============================================================

@app.route("/run-robot")
def manual_robot():

    country = request.args.get(
        "country"
    )

    if not country:

        country = get_user_country()

    country = country.upper()

    if country not in COUNTRIES:

        country = "MA"

    thread = threading.Thread(

        target=run_robot_for_country,

        args=(country,),

        daemon=True

    )

    thread.start()

    return redirect(
        url_for(
            "home",
            country=country
        )
    )


# ============================================================
# HTML
# ============================================================

HOME_HTML = """

<!DOCTYPE html>

<html lang="{{ lang }}">

<head>

<meta charset="UTF-8">

<meta name="viewport"
content="width=device-width, initial-scale=1.0">

<title>{{ country_name }} News</title>

<style>

* {
    box-sizing: border-box;
}

body {

    margin: 0;

    font-family:
    Arial,
    sans-serif;

    background: #f4f6f8;

    color: #111;

}

header {

    background: #111827;

    color: white;

    padding: 20px;

}

.header {

    max-width: 1100px;

    margin: auto;

    display: flex;

    justify-content: space-between;

    align-items: center;

    gap: 15px;

}

.logo {

    font-size: 25px;

    font-weight: bold;

}

select {

    padding: 9px;

    border-radius: 8px;

    border: none;

}

.container {

    max-width: 1100px;

    margin: 30px auto;

    padding: 0 15px;

}

h1 {

    margin-bottom: 25px;

}

.grid {

    display: grid;

    grid-template-columns:
    repeat(auto-fit, minmax(280px, 1fr));

    gap: 20px;

}

.card {

    background: white;

    border-radius: 14px;

    overflow: hidden;

    box-shadow:
    0 4px 15px rgba(0,0,0,.08);

    transition: .2s;

}

.card:hover {

    transform: translateY(-4px);

}

.card img {

    width: 100%;

    height: 190px;

    object-fit: cover;

}

.card-content {

    padding: 18px;

}

.category {

    color: #2563eb;

    font-size: 13px;

    font-weight: bold;

    text-transform: uppercase;

}

.card h2 {

    font-size: 20px;

    line-height: 1.3;

}

.card a {

    text-decoration: none;

    color: inherit;

}

.read {

    display: inline-block;

    margin-top: 10px;

    color: #2563eb;

    font-weight: bold;

}

.empty {

    background: white;

    padding: 30px;

    border-radius: 12px;

    text-align: center;

}

</style>

</head>

<body>

<header>

<div class="header">

<div class="logo">

CORVEX NEWS

</div>

<div>

<form method="get">

<select
name="country"
onchange="this.form.submit()">

{% for code, c in countries.items() %}

<option
value="{{ code }}"
{% if code == country %}selected{% endif %}>

{{ c[lang] }}

</option>

{% endfor %}

</select>

<select
name="lang"
onchange="this.form.submit()">

{% for code, name in languages.items() %}

<option
value="{{ code }}"
{% if code == lang %}selected{% endif %}>

{{ name }}

</option>

{% endfor %}

</select>

</form>

</div>

</div>

</header>


<div class="container">

<h1>
Latest News — {{ country_name }}
</h1>

{% if articles %}

<div class="grid">

{% for article in articles %}

<div class="card">

<a href="/article/{{ article.id }}?country={{ country }}&lang={{ lang }}">

<img
src="{{ article.image }}"
alt="{{ article.title }}"
loading="lazy">

<div class="card-content">

<div class="category">

{{ article.category }}

</div>

<h2>

{{ article.title }}

</h2>

<div class="read">

Read full article →

</div>

</div>

</a>

</div>

{% endfor %}

</div>

{% else %}

<div class="empty">

<h2>
Preparing the latest news...
</h2>

<p>
Our robot is currently collecting news for
{{ country_name }}.
</p>

<meta
http-equiv="refresh"
content="8">

</div>

{% endif %}

</div>

</body>

</html>

"""


# ============================================================
# ARTICLE HTML
# ============================================================

ARTICLE_HTML = """

<!DOCTYPE html>

<html lang="{{ lang }}">

<head>

<meta charset="UTF-8">

<meta name="viewport"
content="width=device-width, initial-scale=1.0">

<title>{{ article.title }}</title>

<style>

body {

    margin: 0;

    background: #f4f6f8;

    font-family: Arial, sans-serif;

    color: #111827;

}

.container {

    max-width: 850px;

    margin: 40px auto;

    padding: 20px;

}

.article {

    background: white;

    padding: 30px;

    border-radius: 16px;

    box-shadow:
    0 5px 20px rgba(0,0,0,.08);

}

.article img {

    width: 100%;

    max-height: 450px;

    object-fit: cover;

    border-radius: 12px;

    margin: 20px 0;

}

.category {

    color: #2563eb;

    font-weight: bold;

    text-transform: uppercase;

}

h1 {

    font-size: 38px;

    line-height: 1.2;

}

.content {

    font-size: 19px;

    line-height: 1.8;

    white-space: pre-line;

}

.back {

    display: inline-block;

    margin-bottom: 20px;

    color: #2563eb;

    text-decoration: none;

    font-weight: bold;

}

.source {

    margin-top: 30px;

    padding-top: 20px;

    border-top: 1px solid #ddd;

}

.source a {

    color: #2563eb;

}

</style>

</head>

<body>

<div class="container">

<a
class="back"
href="/?country={{ country }}&lang={{ lang }}">

← Back to news

</a>

<article class="article">

<div class="category">

{{ article.category }}

</div>

<h1>

{{ article.title }}

</h1>

<img
src="{{ article.image }}"
alt="{{ article.title }}">

<div class="content">

{{ article.content }}

</div>

<div class="source">

<strong>
Original source:
</strong>

<br>

{{ article.source_title }}

<br><br>

<a
href="{{ article.source_url }}"
target="_blank"
rel="noopener">

Read original source →

</a>

</div>

</article>

</div>

</body>

</html>

"""


# ============================================================
# SCHEDULER
# ============================================================

scheduler = BackgroundScheduler()

# Every 6 hours
scheduler.add_job(
    run_robot,
    "interval",
    hours=6,
    id="news_robot",
    replace_existing=True
)

scheduler.start()

print(
    "-> News Robot Scheduler Started"
)


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(
            os.getenv(
                "PORT",
                "5000"
            )
        ),
        debug=False
    )
