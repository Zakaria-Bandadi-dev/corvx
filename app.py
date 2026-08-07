import os
import json
import sqlite3
import time
import urllib.parse

import feedparser
import google.generativeai as genai

from flask import Flask, render_template_string, request
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime


# ============================================================
# 1. FLASK
# ============================================================

app = Flask(__name__)


# ============================================================
# 2. CONFIGURATION
# ============================================================

# ------------------------------------------------------------
# Gemini API Keys
# Railway Variables:
#
# GEMINI_KEY1
# GEMINI_KEY2
# GEMINI_KEY3
# GEMINI_KEY4
# GEMINI_KEY5
# ------------------------------------------------------------

API_KEYS = [
    os.getenv(f"GEMINI_KEY{i}")
    for i in range(1, 6)
]

# Remove empty keys
API_KEYS = [key for key in API_KEYS if key]

current_key_index = 0


# ------------------------------------------------------------
# Database
# ------------------------------------------------------------

DB_URL = os.getenv("DATABASE_URL")

GA_ID = os.getenv("GA_ID", "")
ADSENSE_ID = os.getenv("ADSENSE_ID", "")


# ============================================================
# 3. REGIONS / LANGUAGES
# ============================================================

REGIONS = {
    "global": {
        "ar": "العالم",
        "fr": "Monde",
        "en": "Global",
        "es": "Mundo"
    },

    "usa": {
        "ar": "أمريكا",
        "fr": "USA",
        "en": "USA",
        "es": "EE.UU"
    },

    "eu": {
        "ar": "أوروبا",
        "fr": "Europe",
        "en": "Europe",
        "es": "Europa"
    },

    "africa": {
        "ar": "إفريقيا",
        "fr": "Afrique",
        "en": "Africa",
        "es": "África"
    },

    "khalij": {
        "ar": "الخليج",
        "fr": "Golfe",
        "en": "Gulf",
        "es": "Golfo"
    }
}


LANGUAGES = {
    "ar": "العربية",
    "fr": "FR",
    "en": "EN",
    "es": "ES"
}


# ============================================================
# 4. DATABASE CONNECTION
# ============================================================

def get_db_connection():

    # --------------------------------------------------------
    # Supabase / PostgreSQL
    # --------------------------------------------------------

    if DB_URL:

        import psycopg

        return psycopg.connect(DB_URL)

    # --------------------------------------------------------
    # SQLite fallback
    # --------------------------------------------------------

    conn = sqlite3.connect("corvex.db")

    conn.row_factory = sqlite3.Row

    return conn


# ============================================================
# 5. INITIALIZE DATABASE
# ============================================================

def init_db():

    try:

        conn = get_db_connection()
        cur = conn.cursor()

        # ----------------------------------------------------
        # PostgreSQL
        # ----------------------------------------------------

        if DB_URL:

            query = """
                CREATE TABLE IF NOT EXISTS articles (
                    id SERIAL PRIMARY KEY,

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

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """

        # ----------------------------------------------------
        # SQLite
        # ----------------------------------------------------

        else:

            query = """
                CREATE TABLE IF NOT EXISTS articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

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

                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """

        cur.execute(query)

        conn.commit()

        cur.close()
        conn.close()

        print("-> Database Ready")

    except Exception as e:

        print(f"!! init_db failed: {e}")


# ============================================================
# IMPORTANT
# This runs with Gunicorn too.
# ============================================================

init_db()


# ============================================================
# 6. GEMINI
# ============================================================

def generate_with_fallback(prompt):

    global current_key_index

    if not API_KEYS:

        print("!! No Gemini API Keys found.")

        return None

    # Try every available API key
    for _ in range(len(API_KEYS)):

        try:

            current_key = API_KEYS[current_key_index]

            print(
                f"-> Using Gemini API key #{current_key_index + 1}"
            )

            genai.configure(
                api_key=current_key
            )

            model = genai.GenerativeModel(
                "gemini-1.5-flash-latest"
            )

            response = model.generate_content(prompt)

            if response and response.text:

                return response.text

            print("!! Gemini returned empty response.")

        except Exception as e:

            print(
                f"!! Key #{current_key_index + 1} failed: {e}"
            )

            # Move to next key
            current_key_index = (
                current_key_index + 1
            ) % len(API_KEYS)

            time.sleep(2)

    print("!! All Gemini API keys failed.")

    return None


# ============================================================
# 7. IMAGE GENERATION
# ============================================================

def generate_image(prompt_text):

    clean_prompt = urllib.parse.quote(
        prompt_text
        + ", photorealistic, 8k, professional news photo"
    )

    return (
        f"https://image.pollinations.ai/prompt/{clean_prompt}"
    )


# ============================================================
# 8. GOOGLE TRENDS
# ============================================================

def get_trends(region):

    geo_map = {
        "usa": "US",
        "eu": "GB",
        "africa": "ZA",
        "khalij": "SA",
        "global": ""
    }

    geo = geo_map.get(region, "")

    if geo:

        url = (
            "https://trends.google.com/trends/"
            f"trendingsearches/daily?geo={geo}"
        )

    else:

        url = (
            "https://trends.google.com/trends/"
            "trendingsearches/daily"
        )

    try:

        feed = feedparser.parse(url)

        titles = [
            entry.title
            for entry in feed.entries[:3]
        ]

        if titles:

            print(
                f"-> Trends [{region}]: {titles}"
            )

            return titles

    except Exception as e:

        print(
            f"!! Google Trends failed for {region}: {e}"
        )

    # Fallback
    return [
        "Artificial Intelligence",
        "Technology News",
        "Future of Technology"
    ]


# ============================================================
# 9. CLEAN GEMINI JSON
# ============================================================

def clean_gemini_json(raw_text):

    if not raw_text:
        return None

    text = raw_text.strip()

    # Remove Markdown code blocks
    text = text.replace("```json", "")
    text = text.replace("```JSON", "")
    text = text.replace("```", "")

    text = text.strip()

    try:

        return json.loads(text)

    except Exception:

        # Try to find JSON between { }
        start = text.find("{")
        end = text.rfind("}")

        if start != -1 and end != -1:

            try:

                return json.loads(
                    text[start:end + 1]
                )

            except Exception:

                return None

    return None


# ============================================================
# 10. TRANSLATION
# ============================================================

def translate_article(title, content, language):

    prompt = f"""
Translate the following news article to {language}.

Return ONLY this format:

TITLE
CONTENT

Do not add explanations.
Do not add Markdown.
Do not add labels like "TITLE:" or "CONTENT:".

Original title:
{title}

Original content:
{content}
"""

    result = generate_with_fallback(prompt)

    if not result:

        return None, None

    parts = result.strip().split("\n", 1)

    translated_title = parts[0].strip()

    if len(parts) > 1:

        translated_content = parts[1].strip()

    else:

        translated_content = result.strip()

    return translated_title, translated_content


# ============================================================
# 11. SAVE ARTICLE
# ============================================================

def save_article(
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
    image_url
):

    try:

        conn = get_db_connection()
        cur = conn.cursor()

        if DB_URL:

            placeholder = "%s"

        else:

            placeholder = "?"

        columns = """
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
            image_url
        """

        values = (
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
            image_url
        )

        placeholders = ",".join(
            [placeholder] * 11
        )

        query = f"""
            INSERT INTO articles
            ({columns})
            VALUES ({placeholders})
        """

        cur.execute(
            query,
            values
        )

        conn.commit()

        cur.close()
        conn.close()

        print(
            f"-> Saved: {title_en[:60]}"
        )

        return True

    except Exception as e:

        print(
            f"!! DB insert failed: {e}"
        )

        return False


# ============================================================
# 12. ROBOT
# ============================================================

def run_robot():

    print("")
    print("=" * 60)
    print(
        f"[{datetime.now()}] ROBOT STARTED"
    )
    print("=" * 60)

    # --------------------------------------------------------
    # Loop through regions
    # --------------------------------------------------------

    for region in REGIONS.keys():

        print("")
        print(
            f"-> Processing region: {region}"
        )

        # ----------------------------------------------------
        # Get Google Trends
        # ----------------------------------------------------

        topics = get_trends(region)

        # ----------------------------------------------------
        # Process each topic
        # ----------------------------------------------------

        for topic in topics:

            print(
                f"-> Processing topic: {topic}"
            )

            # ------------------------------------------------
            # Generate English article
            # ------------------------------------------------

            prompt = f"""
You are a professional international news journalist.

Write a high-quality news article about:

{topic}

The article should be factual, informative and engaging.

Return ONLY valid JSON.

Use EXACTLY this structure:

{{
    "title": "article title",
    "content": "full article content",
    "img_prompt": "image generation prompt",
    "cat": "technology"
}}

IMPORTANT:

- Return valid JSON only.
- Use double quotes.
- No Markdown.
- No ```json.
"""

            raw_response = generate_with_fallback(
                prompt
            )

            if not raw_response:

                print(
                    "!! No Gemini response. Skipping topic."
                )

                continue

            # ------------------------------------------------
            # Parse JSON
            # ------------------------------------------------

            data = clean_gemini_json(
                raw_response
            )

            if not data:

                print(
                    "!! Invalid JSON from Gemini."
                )

                continue

            # ------------------------------------------------
            # Get English article
            # ------------------------------------------------

            title_en = data.get(
                "title",
                ""
            ).strip()

            content_en = data.get(
                "content",
                ""
            ).strip()

            category = data.get(
                "cat",
                "technology"
            )

            if not title_en or not content_en:

                print(
                    "!! Missing title/content."
                )

                continue

            # ------------------------------------------------
            # Arabic
            # ------------------------------------------------

            title_ar, content_ar = translate_article(
                title_en,
                content_en,
                "Arabic"
            )

            # ------------------------------------------------
            # French
            # ------------------------------------------------

            title_fr, content_fr = translate_article(
                title_en,
                content_en,
                "French"
            )

            # ------------------------------------------------
            # Spanish
            # ------------------------------------------------

            title_es, content_es = translate_article(
                title_en,
                content_en,
                "Spanish"
            )

            # ------------------------------------------------
            # Fallback if translation fails
            # ------------------------------------------------

            if not title_ar:
                title_ar = title_en

            if not content_ar:
                content_ar = content_en

            if not title_fr:
                title_fr = title_en

            if not content_fr:
                content_fr = content_en

            if not title_es:
                title_es = title_en

            if not content_es:
                content_es = content_en

            # ------------------------------------------------
            # Image
            # ------------------------------------------------

            image_prompt = data.get(
                "img_prompt",
                topic
            )

            image_url = generate_image(
                image_prompt
            )

            # ------------------------------------------------
            # Save
            # ------------------------------------------------

            save_article(
                region=region,
                category=category,

                title_ar=title_ar,
                title_fr=title_fr,
                title_en=title_en,
                title_es=title_es,

                content_ar=content_ar,
                content_fr=content_fr,
                content_en=content_en,
                content_es=content_es,

                image_url=image_url
            )

    print("")
    print("=" * 60)
    print(
        f"[{datetime.now()}] ROBOT FINISHED"
    )
    print("=" * 60)
    print("")


# ============================================================
# 13. ROBOT SCHEDULER
# ============================================================

scheduler = BackgroundScheduler(
    timezone="UTC"
)

scheduler.add_job(
    run_robot,
    trigger="interval",
    hours=6,

    # IMPORTANT:
    # Robot runs immediately after Railway starts
    next_run_time=datetime.now()
)

scheduler.start()

print("-> Robot Scheduler Started")
print("-> First robot execution will start now")
print("-> Next executions: every 6 hours")


# ============================================================
# 14. HOME ROUTE
# ============================================================

@app.route("/")
def home():

    region = request.args.get(
        "region",
        "global"
    )

    lang = request.args.get(
        "lang",
        "en"
    )

    # Security
    if region not in REGIONS:

        region = "global"

    if lang not in LANGUAGES:

        lang = "en"

    articles = []

    try:

        conn = get_db_connection()
        cur = conn.cursor()

        # ----------------------------------------------------
        # Column names are controlled by LANGUAGES
        # so there is no SQL injection here.
        # ----------------------------------------------------

        title_column = (
            f"title_{lang}"
        )

        content_column = (
            f"content_{lang}"
        )

        if DB_URL:

            placeholder = "%s"

        else:

            placeholder = "?"

        query = f"""
            SELECT
                id,
                {title_column},
                {content_column},
                image_url,
                created_at
            FROM articles
            WHERE region = {placeholder}
            ORDER BY created_at DESC
            LIMIT 20
        """

        cur.execute(
            query,
            (region,)
        )

        rows = cur.fetchall()

        cur.close()
        conn.close()

        for row in rows:

            articles.append({
                "id": row[0],
                "title": row[1],
                "content": (
                    (row[2] or "")[:300]
                    + "..."
                ),
                "img": row[3],
                "created_at": row[4]
            })

    except Exception as e:

        print(
            f"!! home() DB query failed: {e}"
        )

    page_title = REGIONS[
        region
    ][lang]

    return render_template_string(
        HTML_TEMPLATE,

        articles=articles,

        regions=REGIONS,

        languages=LANGUAGES,

        region=region,

        lang=lang,

        page_title=page_title,

        ga_id=GA_ID,

        adsense_id=ADSENSE_ID
    )


# ============================================================
# 15. HEALTH CHECK
# ============================================================

@app.route("/health")
def health():

    return {
        "status": "ok",
        "database": bool(DB_URL),
        "gemini_keys": len(API_KEYS),
        "robot": scheduler.running
    }


# ============================================================
# 16. SIMPLE FRONTEND
# ============================================================

HTML_TEMPLATE = """
<!DOCTYPE html>

<html lang="{{ lang }}">

<head>

    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>
        {{ page_title }} - Corvex
    </title>

    {% if adsense_id %}
    <meta
        name="google-adsense-account"
        content="{{ adsense_id }}"
    >
    {% endif %}

    <style>

        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            font-family:
                Arial,
                Helvetica,
                sans-serif;

            background: #f5f7fb;

            color: #111827;
        }

        header {
            background: #111827;
            color: white;

            padding: 20px;
        }

        .header-inner {
            max-width: 1200px;
            margin: auto;

            display: flex;
            justify-content: space-between;
            align-items: center;

            gap: 20px;
            flex-wrap: wrap;
        }

        .logo {
            font-size: 28px;
            font-weight: bold;
        }

        .nav {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }

        .nav a {
            color: white;
            text-decoration: none;

            padding: 8px 12px;

            border-radius: 8px;

            background: #374151;
        }

        .nav a:hover {
            background: #4b5563;
        }

        main {
            max-width: 1200px;
            margin: 30px auto;

            padding: 0 20px;
        }

        .title {
            margin-bottom: 25px;
        }

        .title h1 {
            margin-bottom: 5px;
        }

        .articles {
            display: grid;

            grid-template-columns:
                repeat(
                    auto-fit,
                    minmax(280px, 1fr)
                );

            gap: 20px;
        }

        .article {
            background: white;

            border-radius: 14px;

            overflow: hidden;

            box-shadow:
                0 5px 20px
                rgba(0,0,0,.08);
        }

        .article img {
            width: 100%;
            height: 200px;

            object-fit: cover;

            display: block;
        }

        .article-body {
            padding: 18px;
        }

        .article h2 {
            font-size: 20px;

            margin-top: 0;
            margin-bottom: 12px;
        }

        .article p {
            color: #4b5563;
            line-height: 1.6;
        }

        .empty {
            background: white;

            padding: 40px;

            border-radius: 14px;

            text-align: center;
        }

        footer {
            margin-top: 50px;

            padding: 30px;

            background: #111827;

            color: white;

            text-align: center;
        }

    </style>

</head>


<body>

<header>

    <div class="header-inner">

        <div class="logo">
            CORVEX
        </div>

        <div class="nav">

            {% for region_id, region_names in regions.items() %}

                <a
                    href="/?region={{ region_id }}&lang={{ lang }}"
                >
                    {{ region_names[lang] }}
                </a>

            {% endfor %}

        </div>

    </div>

</header>


<main>

    <div class="title">

        <h1>
            {{ page_title }}
        </h1>

        <p>
            Latest news
        </p>

    </div>


    {% if articles %}

        <div class="articles">

            {% for article in articles %}

                <article class="article">

                    {% if article.img %}

                        <img
                            src="{{ article.img }}"
                            alt="{{ article.title }}"
                            loading="lazy"
                        >

                    {% endif %}


                    <div class="article-body">

                        <h2>
                            {{ article.title }}
                        </h2>

                        <p>
                            {{ article.content }}
                        </p>

                    </div>

                </article>

            {% endfor %}

        </div>

    {% else %}

        <div class="empty">

            <h2>
                No articles yet
            </h2>

            <p>
                The robot is generating the first articles.
                Please refresh the page in a moment.
            </p>

        </div>

    {% endif %}

</main>


<footer>

    <p>
        © 2026 Corvex
    </p>

</footer>


</body>

</html>
"""


# ============================================================
# 17. LOCAL DEVELOPMENT
# ============================================================

if __name__ == "__main__":

    port = int(
        os.getenv(
            "PORT",
            "5000"
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
