import os
import json
import sqlite3
import time
import urllib.parse

import feedparser

from flask import Flask, render_template_string, request
from groq import Groq
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime


# ============================================================
# 1. FLASK
# ============================================================

app = Flask(__name__)


# ============================================================
# 2. CONFIGURATION
# ============================================================

DATABASE_URL = os.getenv("DATABASE_URL")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

GA_ID = os.getenv("GA_ID", "")
ADSENSE_ID = os.getenv("ADSENSE_ID", "")


# ============================================================
# 3. GROQ
# ============================================================

if GROQ_API_KEY:

    groq_client = Groq(
        api_key=GROQ_API_KEY
    )

    print("-> Groq API Key detected")

else:

    groq_client = None

    print("!! GROQ_API_KEY not found")


# Model actuel
GROQ_MODEL = "openai/gpt-oss-20b"


# ============================================================
# 4. REGIONS
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
# 5. DATABASE
# ============================================================

def get_db_connection():

    # PostgreSQL / Supabase
    if DATABASE_URL:

        import psycopg

        return psycopg.connect(
            DATABASE_URL
        )

    # SQLite fallback
    conn = sqlite3.connect(
        "corvex.db"
    )

    conn.row_factory = sqlite3.Row

    return conn


# ============================================================
# 6. INIT DATABASE
# ============================================================

def init_db():

    try:

        conn = get_db_connection()

        cur = conn.cursor()

        if DATABASE_URL:

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

                    created_at
                    TIMESTAMP DEFAULT CURRENT_TIMESTAMP

                );
            """

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

                    created_at
                    DATETIME DEFAULT CURRENT_TIMESTAMP

                );
            """

        cur.execute(query)

        conn.commit()

        cur.close()

        conn.close()

        print("-> Database Ready")

    except Exception as e:

        print(
            f"!! init_db failed: {e}"
        )


# IMPORTANT:
# Works with Gunicorn too.

init_db()


# ============================================================
# 7. GROQ GENERATION
# ============================================================

def generate_with_groq(prompt):

    if not groq_client:

        print(
            "!! GROQ_API_KEY is missing"
        )

        return None

    try:

        print(
            f"-> Using Groq model: {GROQ_MODEL}"
        )

        response = groq_client.chat.completions.create(

            model=GROQ_MODEL,

            messages=[
                {
                    "role": "system",
                    "content":
                    "You are a professional international news journalist."
                },

                {
                    "role": "user",
                    "content": prompt
                }
            ],

            temperature=0.7,

            max_tokens=2500

        )

        if not response.choices:

            print(
                "!! Groq returned no choices"
            )

            return None

        content = (
            response
            .choices[0]
            .message
            .content
        )

        if not content:

            print(
                "!! Groq returned empty content"
            )

            return None

        return content.strip()

    except Exception as e:

        print(
            f"!! Groq API error: {e}"
        )

        return None


# ============================================================
# 8. CLEAN JSON
# ============================================================

def clean_json(text):

    if not text:

        return None

    text = text.strip()

    # Remove markdown fences
    text = text.replace(
        "```json",
        ""
    )

    text = text.replace(
        "```JSON",
        ""
    )

    text = text.replace(
        "```",
        ""
    )

    text = text.strip()

    # Try direct JSON
    try:

        return json.loads(text)

    except Exception:

        pass

    # Try extracting JSON
    start = text.find("{")

    end = text.rfind("}")

    if start != -1 and end != -1:

        try:

            return json.loads(
                text[start:end + 1]
            )

        except Exception:

            pass

    return None


# ============================================================
# 9. GOOGLE TRENDS
# ============================================================

def get_trends(region):

    geo_map = {

        "global": "",

        "usa": "US",

        "eu": "GB",

        "africa": "ZA",

        "khalij": "SA"

    }

    geo = geo_map.get(
        region,
        ""
    )

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

        feed = feedparser.parse(
            url
        )

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
            f"!! Google Trends error: {e}"
        )

    # Fallback
    return [

        "Artificial Intelligence",

        "Technology News",

        "Future of Technology"

    ]


# ============================================================
# 10. GENERATE ARTICLE
# ============================================================

def generate_article(topic):

    prompt = f"""
Write a high-quality news article about:

{topic}

Requirements:

- Professional journalism style.
- Informative and engaging.
- Do not invent specific facts, numbers or quotes.
- If the topic is broad, write a general technology news article.
- Article should be around 500-700 words.

Return ONLY valid JSON.

Use exactly this structure:

{{
    "title": "article title",
    "content": "full article",
    "img_prompt": "professional realistic news image prompt",
    "cat": "technology"
}}

IMPORTANT:

- Valid JSON only.
- Use double quotes.
- No Markdown.
- No ```json.
"""

    raw = generate_with_groq(
        prompt
    )

    if not raw:

        return None

    data = clean_json(
        raw
    )

    if not data:

        print(
            "!! Could not parse article JSON"
        )

        print(
            f"Raw response: {raw[:500]}"
        )

        return None

    return data


# ============================================================
# 11. TRANSLATION
# ============================================================

def translate_article(
    title,
    content,
    language
):

    prompt = f"""
Translate this news article into {language}.

Preserve the meaning and facts.

Return ONLY valid JSON:

{{
    "title": "translated title",
    "content": "translated article"
}}

Original title:

{title}

Original article:

{content}
"""

    raw = generate_with_groq(
        prompt
    )

    if not raw:

        return None, None

    data = clean_json(
        raw
    )

    if not data:

        return None, None

    translated_title = data.get(
        "title"
    )

    translated_content = data.get(
        "content"
    )

    return (
        translated_title,
        translated_content
    )


# ============================================================
# 12. IMAGE URL
# ============================================================

def generate_image(prompt):

    if not prompt:

        prompt = "technology news"

    clean_prompt = urllib.parse.quote(

        prompt
        + ", photorealistic, professional journalism photography, realistic news photo"

    )

    return (
        "https://image.pollinations.ai/prompt/"
        + clean_prompt
    )


# ============================================================
# 13. SAVE ARTICLE
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

        if DATABASE_URL:

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
            f"-> Saved: {title_en[:80]}"
        )

        return True

    except Exception as e:

        print(
            f"!! DB insert failed: {e}"
        )

        return False


# ============================================================
# 14. ROBOT
# ============================================================

def run_robot():

    print("")
    print("=" * 70)
    print(
        f"[{datetime.now()}] ROBOT STARTED"
    )
    print("=" * 70)
    print("")

    for region in REGIONS.keys():

        print(
            f"-> Processing region: {region}"
        )

        topics = get_trends(
            region
        )

        for topic in topics:

            print("")
            print(
                f"-> Processing topic: {topic}"
            )

            # ------------------------------------------------
            # Generate English article
            # ------------------------------------------------

            data = generate_article(
                topic
            )

            if not data:

                print(
                    "!! Article generation failed"
                )

                continue

            title_en = str(
                data.get(
                    "title",
                    ""
                )
            ).strip()

            content_en = str(
                data.get(
                    "content",
                    ""
                )
            ).strip()

            category = data.get(
                "cat",
                "technology"
            )

            if not title_en:

                print(
                    "!! Empty article title"
                )

                continue

            if not content_en:

                print(
                    "!! Empty article content"
                )

                continue

            print(
                f"-> Article generated: {title_en}"
            )

            # ------------------------------------------------
            # Arabic
            # ------------------------------------------------

            print(
                "-> Translating Arabic..."
            )

            title_ar, content_ar = (
                translate_article(
                    title_en,
                    content_en,
                    "Arabic"
                )
            )

            # ------------------------------------------------
            # French
            # ------------------------------------------------

            print(
                "-> Translating French..."
            )

            title_fr, content_fr = (
                translate_article(
                    title_en,
                    content_en,
                    "French"
                )
            )

            # ------------------------------------------------
            # Spanish
            # ------------------------------------------------

            print(
                "-> Translating Spanish..."
            )

            title_es, content_es = (
                translate_article(
                    title_en,
                    content_en,
                    "Spanish"
                )
            )

            # ------------------------------------------------
            # Translation fallback
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
    print("=" * 70)
    print(
        f"[{datetime.now()}] ROBOT FINISHED"
    )
    print("=" * 70)
    print("")


# ============================================================
# 15. SCHEDULER
# ============================================================

scheduler = BackgroundScheduler(
    timezone="UTC"
)

scheduler.add_job(

    run_robot,

    trigger="interval",

    hours=6,

    # Run immediately after deployment
    next_run_time=datetime.now(),

    # Prevent overlapping robot executions
    max_instances=1,

    # If one execution is missed, don't run many times
    coalesce=True

)

scheduler.start()

print(
    "-> Robot Scheduler Started"
)

print(
    "-> First robot execution will start now"
)

print(
    "-> Next executions: every 6 hours"
)


# ============================================================
# 16. HOME
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

    if region not in REGIONS:

        region = "global"

    if lang not in LANGUAGES:

        lang = "en"

    articles = []

    try:

        conn = get_db_connection()

        cur = conn.cursor()

        title_column = (
            f"title_{lang}"
        )

        content_column = (
            f"content_{lang}"
        )

        if DATABASE_URL:

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

                "content":
                    (
                        row[2] or ""
                    )[:300] + "...",

                "img": row[3],

                "created_at": row[4]

            })

    except Exception as e:

        print(
            f"!! home() DB query failed: {e}"
        )

    return render_template_string(

        HTML_TEMPLATE,

        articles=articles,

        regions=REGIONS,

        languages=LANGUAGES,

        region=region,

        lang=lang,

        page_title=
            REGIONS[region][lang],

        ga_id=GA_ID,

        adsense_id=ADSENSE_ID

    )


# ============================================================
# 17. HEALTH CHECK
# ============================================================

@app.route("/health")
def health():

    return {

        "status": "ok",

        "database":
            bool(DATABASE_URL),

        "groq":
            bool(GROQ_API_KEY),

        "model":
            GROQ_MODEL,

        "robot":
            scheduler.running

    }


# ============================================================
# 18. FRONTEND
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

            justify-content:
                space-between;

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
                Refresh the page in a moment.
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
# 19. LOCAL DEVELOPMENT
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
