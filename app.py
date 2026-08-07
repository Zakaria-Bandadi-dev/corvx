import os
import re
import json
import time
import random
import sqlite3
import urllib.parse
import threading
from datetime import datetime

import feedparser
import psycopg
from flask import Flask, request, render_template_string, abort
from groq import Groq
from apscheduler.schedulers.background import BackgroundScheduler


# ============================================================
# APP
# ============================================================

app = Flask(__name__)


# ============================================================
# CONFIGURATION
# ============================================================

PORT = int(os.getenv("PORT", "5000"))

# Supabase / Railway PostgreSQL
DB_URL = os.getenv("DATABASE_URL", "").strip()

# ------------------------------------------------------------
# GROQ API KEYS
#
# Railway variables can be:
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

single_key = os.getenv("GROQ_API_KEY")
if single_key:
    GROQ_KEYS.append(single_key)

for i in range(1, 6):
    key = os.getenv(f"GROQ_API_KEY{i}")
    if key and key not in GROQ_KEYS:
        GROQ_KEYS.append(key)

# Current recommended production model on Groq
GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-120b"
)

current_key_index = 0
key_lock = threading.Lock()


# ============================================================
# REGIONS
# ============================================================

REGIONS = {

    "morocco": {
        "name": {
            "ar": "المغرب",
            "fr": "Maroc",
            "en": "Morocco",
            "es": "Marruecos"
        },
        "default_lang": "ar",
        "countries": ["Morocco"],
        "google_news": [
            "Morocco",
            "Morocco politics",
            "Morocco economy",
            "Morocco business",
            "Morocco technology",
            "Morocco sports",
            "Morocco science"
        ]
    },

    "global": {
        "name": {
            "ar": "العالم",
            "fr": "Monde",
            "en": "Global",
            "es": "Mundo"
        },
        "default_lang": "en",
        "countries": ["World"],
        "google_news": [
            "World",
            "World politics",
            "World economy",
            "World business",
            "World technology",
            "World science",
            "World sports"
        ]
    },

    "usa": {
        "name": {
            "ar": "أمريكا",
            "fr": "USA",
            "en": "USA",
            "es": "EE.UU.",
        },
        "default_lang": "en",
        "countries": ["United States"],
        "google_news": [
            "United States",
            "USA politics",
            "USA economy",
            "USA technology",
            "USA business",
            "USA sports",
            "USA science"
        ]
    },

    "europe": {
        "name": {
            "ar": "أوروبا",
            "fr": "Europe",
            "en": "Europe",
            "es": "Europa"
        },
        "default_lang": "fr",
        "countries": ["Europe"],
        "google_news": [
            "Europe",
            "Europe politics",
            "Europe economy",
            "Europe business",
            "Europe technology",
            "Europe science",
            "Europe sports"
        ]
    },

    "africa": {
        "name": {
            "ar": "إفريقيا",
            "fr": "Afrique",
            "en": "Africa",
            "es": "África"
        },
        "default_lang": "fr",
        "countries": ["Africa"],
        "google_news": [
            "Africa",
            "Africa politics",
            "Africa economy",
            "Africa business",
            "Africa technology",
            "Africa science",
            "Africa sports"
        ]
    },

    "gulf": {
        "name": {
            "ar": "الخليج",
            "fr": "Golfe",
            "en": "Gulf",
            "es": "Golfo"
        },
        "default_lang": "ar",
        "countries": ["Gulf"],
        "google_news": [
            "Gulf countries",
            "Saudi Arabia",
            "UAE",
            "Qatar",
            "Gulf economy",
            "Gulf business",
            "Gulf technology",
            "Gulf sports"
        ]
    }
}


LANGUAGES = {
    "ar": "العربية",
    "fr": "Français",
    "en": "English",
    "es": "Español"
}


CATEGORIES = [
    "politics",
    "economy",
    "business",
    "technology",
    "science",
    "sports",
    "health",
    "world",
    "society",
    "culture"
]


# ============================================================
# DATABASE
# ============================================================

def get_db_connection():

    if DB_URL:

        return psycopg.connect(
            DB_URL,
            connect_timeout=15
        )

    conn = sqlite3.connect(
        "corvex.db",
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    return conn


def column_exists(cur, table_name, column_name):

    if DB_URL:

        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = %s
                AND column_name = %s
            )
            """,
            (table_name, column_name)
        )

        return cur.fetchone()[0]

    else:

        cur.execute(
            f"PRAGMA table_info({table_name})"
        )

        columns = [
            row[1]
            for row in cur.fetchall()
        ]

        return column_name in columns


def add_column_if_missing(
    cur,
    column_name,
    column_type
):

    if not column_exists(
        cur,
        "articles",
        column_name
    ):

        cur.execute(
            f"""
            ALTER TABLE articles
            ADD COLUMN {column_name} {column_type}
            """
        )


def init_db():

    try:

        conn = get_db_connection()
        cur = conn.cursor()

        if DB_URL:

            cur.execute(
                """
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

                    source_url TEXT,
                    source_name TEXT,

                    created_at TIMESTAMP
                        DEFAULT CURRENT_TIMESTAMP

                )
                """
            )

        else:

            cur.execute(
                """
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

                    source_url TEXT,
                    source_name TEXT,

                    created_at DATETIME
                        DEFAULT CURRENT_TIMESTAMP

                )
                """
            )

        # ----------------------------------------------------
        # Migration for old database
        # ----------------------------------------------------

        add_column_if_missing(
            cur,
            "source_url",
            "TEXT"
        )

        add_column_if_missing(
            cur,
            "source_name",
            "TEXT"
        )

        # ----------------------------------------------------
        # Indexes
        # ----------------------------------------------------

        try:

            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_articles_region
                ON articles(region)
                """
            )

        except Exception:
            pass

        try:

            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_articles_created
                ON articles(created_at)
                """
            )

        except Exception:
            pass

        conn.commit()
        conn.close()

        print("-> Database Ready")

    except Exception as e:

        print(
            f"!! init_db failed: {e}"
        )


# IMPORTANT:
# Gunicorn imports app.py, so initialize here.
init_db()


# ============================================================
# GROQ
# ============================================================

def get_next_groq_client():

    global current_key_index

    if not GROQ_KEYS:

        return None

    with key_lock:

        key = GROQ_KEYS[current_key_index]

        current_key_index = (
            current_key_index + 1
        ) % len(GROQ_KEYS)

    return Groq(api_key=key)


def ask_groq(
    prompt,
    temperature=0.4,
    max_tokens=3000
):

    if not GROQ_KEYS:

        print(
            "!! No GROQ API KEY found"
        )

        return None

    attempts = len(GROQ_KEYS)

    for attempt in range(attempts):

        client = get_next_groq_client()

        if client is None:
            return None

        try:

            response = client.chat.completions.create(

                model=GROQ_MODEL,

                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a professional multilingual "
                            "international news editor. "
                            "Write factual, neutral, clear news content. "
                            "Never invent specific facts, names, numbers "
                            "or events that are not present in the source."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],

                temperature=temperature,

                max_completion_tokens=max_tokens

            )

            text = (
                response
                .choices[0]
                .message
                .content
            )

            if text:
                return text.strip()

        except Exception as e:

            print(
                f"!! Groq attempt {attempt + 1} failed: {e}"
            )

            time.sleep(2)

    return None


# ============================================================
# GOOGLE NEWS RSS
# ============================================================

def google_news_rss(query):

    encoded = urllib.parse.quote_plus(
        query
    )

    url = (
        "https://news.google.com/rss/search?"
        f"q={encoded}"
        "&hl=en-US"
        "&gl=US"
        "&ceid=US:en"
    )

    try:

        feed = feedparser.parse(url)

        return feed.entries

    except Exception as e:

        print(
            f"!! RSS error: {e}"
        )

        return []


# ============================================================
# NEWS FETCHING
# ============================================================

def clean_text(text):

    if not text:
        return ""

    text = re.sub(
        r"<[^>]+>",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def get_news_for_region(region):

    config = REGIONS.get(
        region,
        REGIONS["morocco"]
    )

    all_articles = []

    queries = config["google_news"]

    # Shuffle so the robot doesn't always
    # process the same category first.
    queries = list(queries)
    random.shuffle(queries)

    for query in queries:

        entries = google_news_rss(query)

        for entry in entries[:5]:

            title = clean_text(
                getattr(
                    entry,
                    "title",
                    ""
                )
            )

            summary = clean_text(
                getattr(
                    entry,
                    "summary",
                    ""
                )
            )

            link = getattr(
                entry,
                "link",
                ""
            )

            source_name = ""

            if hasattr(entry, "source"):

                try:
                    source_name = (
                        entry.source.title
                    )
                except Exception:
                    pass

            if not title or not link:
                continue

            all_articles.append(
                {
                    "title": title,
                    "summary": summary,
                    "url": link,
                    "source": source_name
                }
            )

    # --------------------------------------------------------
    # Remove duplicates by URL
    # --------------------------------------------------------

    unique = {}

    for article in all_articles:

        url = article["url"]

        if url not in unique:
            unique[url] = article

    articles = list(
        unique.values()
    )

    random.shuffle(articles)

    return articles


# ============================================================
# DUPLICATE CHECK
# ============================================================

def article_exists(source_url):

    try:

        conn = get_db_connection()
        cur = conn.cursor()

        placeholder = (
            "%s"
            if DB_URL
            else "?"
        )

        cur.execute(
            f"""
            SELECT id
            FROM articles
            WHERE source_url = {placeholder}
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
# AI ARTICLE GENERATION
# ============================================================

def generate_article(
    source_article,
    region
):

    source_title = source_article["title"]
    source_summary = source_article["summary"]
    source_name = source_article["source"]

    prompt = f"""
Create a professional news article from the source below.

REGION:
{region}

SOURCE TITLE:
{source_title}

SOURCE:
{source_name}

SOURCE SUMMARY:
{source_summary}

IMPORTANT:

1. Do not invent facts.
2. Do not change names, countries, organizations or numbers.
3. Do not make the article about AI unless the source itself is about AI.
4. Identify the real category:
   politics, economy, business, technology, science,
   sports, health, world, society or culture.
5. Write a useful article, not just two sentences.
6. Explain:
   - what happened
   - who is involved
   - why it matters
   - important context available in the source
7. Neutral journalistic style.
8. Do not mention that AI generated the article.

Return ONLY valid JSON:

{{
    "title": "article title",
    "content": "article content with paragraphs",
    "category": "one category from the list"
}}

Categories:
politics
economy
business
technology
science
sports
health
world
society
culture
"""

    raw = ask_groq(
        prompt,
        temperature=0.25,
        max_tokens=2500
    )

    if not raw:
        return None

    # Remove Markdown fences
    raw = raw.replace(
        "```json",
        ""
    )

    raw = raw.replace(
        "```",
        ""
    )

    raw = raw.strip()

    try:

        data = json.loads(raw)

        title = str(
            data.get("title", "")
        ).strip()

        content = str(
            data.get("content", "")
        ).strip()

        category = str(
            data.get("category", "world")
        ).lower().strip()

        if category not in CATEGORIES:

            category = "world"

        if not title or not content:
            return None

        return {
            "title": title,
            "content": content,
            "category": category
        }

    except Exception as e:

        print(
            f"!! JSON parsing failed: {e}"
        )

        print(
            f"AI response: {raw[:500]}"
        )

        return None


# ============================================================
# TRANSLATION
# ============================================================

def translate_article(
    title,
    content,
    language
):

    language_names = {
        "ar": "Arabic",
        "fr": "French",
        "en": "English",
        "es": "Spanish"
    }

    target = language_names[
        language
    ]

    prompt = f"""
Translate this news article into {target}.

IMPORTANT:

- Keep the exact meaning.
- Do not add facts.
- Do not remove facts.
- Keep names of people and organizations correct.
- Keep numbers and dates correct.
- Use natural journalistic language.
- Do not say "translation".
- Do not put the answer inside Markdown.
- Return ONLY JSON.

SOURCE TITLE:
{title}

SOURCE CONTENT:
{content}

Return:

{{
    "title": "translated title",
    "content": "translated article"
}}
"""

    raw = ask_groq(
        prompt,
        temperature=0.15,
        max_tokens=3000
    )

    if not raw:
        return None

    raw = raw.replace(
        "```json",
        ""
    )

    raw = raw.replace(
        "```",
        ""
    )

    raw = raw.strip()

    try:

        data = json.loads(raw)

        return {
            "title": str(
                data.get("title", title)
            ).strip(),

            "content": str(
                data.get("content", content)
            ).strip()
        }

    except Exception as e:

        print(
            f"!! Translation JSON failed "
            f"({language}): {e}"
        )

        return None


# ============================================================
# IMAGE
# ============================================================

def generate_image(
    title
):

    prompt = (
        f"{title}, "
        "professional newspaper photography, "
        "realistic editorial photograph, "
        "no text, no watermark"
    )

    encoded = urllib.parse.quote(
        prompt
    )

    return (
        "https://image.pollinations.ai/"
        f"prompt/{encoded}"
    )


# ============================================================
# SAVE ARTICLE
# ============================================================

def save_article(
    region,
    category,
    titles,
    contents,
    image_url,
    source_url,
    source_name
):

    try:

        conn = get_db_connection()
        cur = conn.cursor()

        placeholder = (
            "%s"
            if DB_URL
            else "?"
        )

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
            image_url,
            source_url,
            source_name
        """

        values = (
            region,
            category,

            titles["ar"],
            titles["fr"],
            titles["en"],
            titles["es"],

            contents["ar"],
            contents["fr"],
            contents["en"],
            contents["es"],

            image_url,

            source_url,
            source_name
        )

        placeholders = ",".join(
            [placeholder] * len(values)
        )

        cur.execute(
            f"""
            INSERT INTO articles
            ({columns})
            VALUES ({placeholders})
            """,
            values
        )

        conn.commit()
        conn.close()

        print(
            f"-> SAVED [{region}] "
            f"[{category}] "
            f"{titles['en'][:80]}"
        )

        return True

    except Exception as e:

        print(
            f"!! DB insert failed: {e}"
        )

        return False


# ============================================================
# ROBOT
# ============================================================

robot_lock = threading.Lock()


def run_robot():

    if not robot_lock.acquire(
        blocking=False
    ):

        print(
            "!! Robot already running"
        )

        return

    try:

        print(
            "\n"
            "===================================="
        )

        print(
            f"[{datetime.now()}] "
            "ROBOT STARTED"
        )

        print(
            "===================================="
        )

        if not GROQ_KEYS:

            print(
                "!! ROBOT STOPPED: "
                "No Groq API key."
            )

            return

        # ----------------------------------------------------
        # Process every region
        # ----------------------------------------------------

        for region in REGIONS.keys():

            print(
                f"\n>>> Searching news for: "
                f"{region}"
            )

            news = get_news_for_region(
                region
            )

            if not news:

                print(
                    f"!! No news found for {region}"
                )

                continue

            # Limit per region per robot run.
            # Increase if you have enough API quota.
            selected_news = news[:4]

            print(
                f"Found {len(news)} news. "
                f"Processing {len(selected_news)}."
            )

            for source_article in selected_news:

                source_url = source_article["url"]

                # ------------------------------------------------
                # Don't publish duplicate
                # ------------------------------------------------

                if article_exists(
                    source_url
                ):

                    print(
                        "-> Already exists: "
                        f"{source_article['title'][:60]}"
                    )

                    continue

                print(
                    "\n"
                    "------------------------------------"
                )

                print(
                    "SOURCE: "
                    f"{source_article['title']}"
                )

                # ------------------------------------------------
                # Generate article
                # ------------------------------------------------

                article = generate_article(
                    source_article,
                    region
                )

                if not article:

                    print(
                        "!! Article generation failed"
                    )

                    continue

                base_title = article["title"]
                base_content = article["content"]

                # ------------------------------------------------
                # Translation
                # ------------------------------------------------

                titles = {
                    "en": base_title
                }

                contents = {
                    "en": base_content
                }

                for lang in [
                    "ar",
                    "fr",
                    "es"
                ]:

                    print(
                        f"-> Translating to {lang}"
                    )

                    translated = translate_article(
                        base_title,
                        base_content,
                        lang
                    )

                    if translated:

                        titles[lang] = translated[
                            "title"
                        ]

                        contents[lang] = translated[
                            "content"
                        ]

                    else:

                        # fallback
                        titles[lang] = base_title
                        contents[lang] = base_content

                # ------------------------------------------------
                # Image
                # ------------------------------------------------

                image_url = generate_image(
                    base_title
                )

                # ------------------------------------------------
                # Save
                # ------------------------------------------------

                save_article(
                    region=region,
                    category=article["category"],
                    titles=titles,
                    contents=contents,
                    image_url=image_url,
                    source_url=source_url,
                    source_name=source_article["source"]
                )

                # Small delay to avoid
                # hammering the API
                time.sleep(2)

        print(
            "\n"
            "===================================="
        )

        print(
            f"[{datetime.now()}] "
            "ROBOT FINISHED"
        )

        print(
            "====================================\n"
        )

    except Exception as e:

        print(
            f"!! ROBOT ERROR: {e}"
        )

    finally:

        robot_lock.release()


# ============================================================
# FRONTEND
# ============================================================

HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="{{ lang }}" dir="{{ 'rtl' if lang == 'ar' else 'ltr' }}">

<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
>

<title>{{ page_title }}</title>

<style>

* {
    box-sizing: border-box;
}

body {
    margin: 0;
    font-family:
        Arial,
        "Noto Sans Arabic",
        sans-serif;

    background: #f4f6f8;
    color: #18202a;
}

header {
    background: #111827;
    color: white;
    padding: 18px 5%;
}

.header-inner {
    max-width: 1200px;
    margin: auto;

    display: flex;
    justify-content: space-between;
    align-items: center;

    gap: 20px;
}

.logo {
    font-size: 28px;
    font-weight: bold;
}

.controls {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
}

select {
    padding: 9px 12px;
    border-radius: 8px;
    border: none;
}

nav {
    background: white;
    border-bottom: 1px solid #ddd;
    padding: 12px 5%;
}

.nav-inner {
    max-width: 1200px;
    margin: auto;

    display: flex;
    gap: 8px;
    flex-wrap: wrap;
}

.nav-inner a {
    text-decoration: none;
    color: #374151;

    padding: 8px 13px;
    border-radius: 20px;

    background: #f1f5f9;
}

.nav-inner a.active {
    background: #111827;
    color: white;
}

.container {
    max-width: 1200px;
    margin: 30px auto;
    padding: 0 20px;
}

.page-title {
    font-size: 32px;
    margin-bottom: 25px;
}

.grid {
    display: grid;

    grid-template-columns:
        repeat(
            auto-fit,
            minmax(280px, 1fr)
        );

    gap: 22px;
}

.card {
    background: white;

    border-radius: 14px;

    overflow: hidden;

    box-shadow:
        0 4px 15px
        rgba(0,0,0,0.08);

    transition:
        transform .2s,
        box-shadow .2s;
}

.card:hover {
    transform: translateY(-4px);

    box-shadow:
        0 8px 25px
        rgba(0,0,0,0.12);
}

.card-link {
    text-decoration: none;
    color: inherit;
}

.card img {
    width: 100%;
    height: 190px;
    object-fit: cover;
}

.card-body {
    padding: 18px;
}

.category {
    display: inline-block;

    background: #e5e7eb;

    padding: 5px 10px;

    border-radius: 20px;

    font-size: 12px;

    margin-bottom: 10px;
}

.card h2 {
    font-size: 20px;
    margin: 5px 0 10px;
}

.card p {
    color: #64748b;
    line-height: 1.6;
}

.article {
    max-width: 900px;
    margin: 35px auto;

    background: white;

    padding: 30px;

    border-radius: 15px;
}

.article img {
    width: 100%;
    max-height: 500px;
    object-fit: cover;

    border-radius: 12px;

    margin: 20px 0;
}

.article h1 {
    font-size: 38px;
    line-height: 1.25;
}

.article-content {
    font-size: 19px;
    line-height: 1.9;
    white-space: pre-line;
}

.source {
    margin-top: 30px;

    padding: 15px;

    background: #f1f5f9;

    border-radius: 10px;
}

.source a {
    color: #2563eb;
}

.back {
    display: inline-block;

    margin-bottom: 20px;

    text-decoration: none;

    color: #2563eb;
}

.empty {
    background: white;
    padding: 40px;
    border-radius: 12px;
    text-align: center;
}

footer {
    text-align: center;

    padding: 40px;

    color: #64748b;
}

@media(max-width: 600px) {

    .header-inner {
        flex-direction: column;
        align-items: flex-start;
    }

    .article h1 {
        font-size: 28px;
    }

}

</style>

</head>

<body>

<header>

<div class="header-inner">

<div class="logo">
CORVEX
</div>

<div class="controls">

<select
    onchange="changeRegion(this.value)"
>

{% for key, value in regions.items() %}

<option
    value="{{ key }}"
    {% if key == region %}selected{% endif %}
>
    {{ value.name[lang] }}
</option>

{% endfor %}

</select>

<select
    onchange="changeLanguage(this.value)"
>

{% for key, value in languages.items() %}

<option
    value="{{ key }}"
    {% if key == lang %}selected{% endif %}
>
    {{ value }}
</option>

{% endfor %}

</select>

</div>

</div>

</header>


<nav>

<div class="nav-inner">

{% for key, value in regions.items() %}

<a
    href="/?region={{ key }}&lang={{ lang }}"
    class="{% if key == region %}active{% endif %}"
>
    {{ value.name[lang] }}
</a>

{% endfor %}

</div>

</nav>


<div class="container">

<h1 class="page-title">
    {{ page_title }}
</h1>


{% if articles %}

<div class="grid">

{% for article in articles %}

<a
    class="card-link"
    href="/article/{{ article.id }}?region={{ region }}&lang={{ lang }}"
>

<div class="card">

<img
    src="{{ article.img }}"
    loading="lazy"
    onerror="this.src='https://placehold.co/800x450?text=News'"
>

<div class="card-body">

<span class="category">
    {{ article.category }}
</span>

<h2>
    {{ article.title }}
</h2>

<p>
    {{ article.content }}
</p>

</div>

</div>

</a>

{% endfor %}

</div>

{% else %}

<div class="empty">

<h2>
    No articles yet
</h2>

<p>
    The robot is searching for news.
</p>

</div>

{% endif %}

</div>


<footer>
    CORVEX News
</footer>


<script>

function changeRegion(region) {

    const params =
        new URLSearchParams(
            window.location.search
        );

    params.set(
        "region",
        region
    );

    window.location.href =
        "/?" + params.toString();
}


function changeLanguage(lang) {

    const params =
        new URLSearchParams(
            window.location.search
        );

    params.set(
        "lang",
        lang
    );

    window.location.href =
        "/?" + params.toString();
}

</script>

</body>

</html>
"""


# ============================================================
# ARTICLE PAGE
# ============================================================

ARTICLE_TEMPLATE = r"""
<!DOCTYPE html>
<html
lang="{{ lang }}"
dir="{{ 'rtl' if lang == 'ar' else 'ltr' }}"
>

<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
>

<title>{{ article.title }}</title>

<style>

body {
    margin: 0;
    background: #f4f6f8;

    color: #18202a;

    font-family:
        Arial,
        "Noto Sans Arabic",
        sans-serif;
}

.container {
    max-width: 900px;
    margin: 40px auto;
    padding: 20px;
}

.back {
    display: inline-block;
    margin-bottom: 20px;

    text-decoration: none;
    color: #2563eb;
}

.article {
    background: white;
    padding: 30px;

    border-radius: 15px;

    box-shadow:
        0 5px 20px
        rgba(0,0,0,.08);
}

.category {
    display: inline-block;

    background: #e5e7eb;

    padding: 6px 12px;

    border-radius: 20px;

    font-size: 13px;
}

h1 {
    font-size: 40px;
    line-height: 1.3;
}

.article img {
    width: 100%;
    max-height: 550px;

    object-fit: cover;

    border-radius: 12px;

    margin: 20px 0;
}

.content {
    font-size: 20px;
    line-height: 2;

    white-space: pre-line;
}

.source {
    margin-top: 35px;

    padding: 18px;

    background: #f1f5f9;

    border-radius: 10px;
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
href="/?region={{ region }}&lang={{ lang }}"
>
← {{ back_text }}
</a>

<article class="article">

<span class="category">
    {{ article.category }}
</span>

<h1>
    {{ article.title }}
</h1>

<img
src="{{ article.img }}"
onerror="this.src='https://placehold.co/1000x600?text=News'"
>

<div class="content">
{{ article.content }}
</div>


{% if article.source_url %}

<div class="source">

<strong>
    {{ source_text }}
</strong>

<br>

{{ article.source_name }}

<br><br>

<a
href="{{ article.source_url }}"
target="_blank"
rel="noopener noreferrer"
>
    {{ original_text }}
</a>

</div>

{% endif %}

</article>

</div>

</body>

</html>
"""


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    region = request.args.get(
        "region",
        "morocco"
    )

    if region not in REGIONS:
        region = "morocco"

    default_lang = REGIONS[
        region
    ]["default_lang"]

    lang = request.args.get(
        "lang",
        default_lang
    )

    if lang not in LANGUAGES:
        lang = default_lang

    articles = []

    try:

        conn = get_db_connection()
        cur = conn.cursor()

        t_col = (
            f"title_{lang}"
        )

        c_col = (
            f"content_{lang}"
        )

        placeholder = (
            "%s"
            if DB_URL
            else "?"
        )

        query = f"""
            SELECT
                id,
                category,
                {t_col},
                {c_col},
                image_url
            FROM articles

            WHERE region = {placeholder}

            ORDER BY created_at DESC

            LIMIT 50
        """

        cur.execute(
            query,
            (region,)
        )

        rows = cur.fetchall()

        conn.close()

        for row in rows:

            if DB_URL:

                article_id = row[0]
                category = row[1]
                title = row[2]
                content = row[3]
                image = row[4]

            else:

                article_id = row[0]
                category = row[1]
                title = row[2]
                content = row[3]
                image = row[4]

            articles.append(
                {
                    "id": article_id,

                    "category":
                        category or "world",

                    "title":
                        title or "",

                    "content":
                        (
                            (content or "")[:220]
                            + "..."
                        ),

                    "img":
                        image
                }
            )

    except Exception as e:

        print(
            f"!! home DB error: {e}"
        )

    return render_template_string(
        HTML_TEMPLATE,

        articles=articles,

        regions=REGIONS,

        languages=LANGUAGES,

        region=region,

        lang=lang,

        page_title=REGIONS[
            region
        ]["name"][lang]
    )


# ============================================================
# ARTICLE DETAILS
# ============================================================

@app.route(
    "/article/<int:article_id>"
)
def article_details(
    article_id
):

    region = request.args.get(
        "region",
        "morocco"
    )

    if region not in REGIONS:
        region = "morocco"

    default_lang = REGIONS[
        region
    ]["default_lang"]

    lang = request.args.get(
        "lang",
        default_lang
    )

    if lang not in LANGUAGES:
        lang = default_lang

    try:

        conn = get_db_connection()
        cur = conn.cursor()

        t_col = (
            f"title_{lang}"
        )

        c_col = (
            f"content_{lang}"
        )

        placeholder = (
            "%s"
            if DB_URL
            else "?"
        )

        query = f"""
            SELECT
                id,
                category,
                {t_col},
                {c_col},
                image_url,
                source_url,
                source_name
            FROM articles
            WHERE id = {placeholder}
            LIMIT 1
        """

        cur.execute(
            query,
            (article_id,)
        )

        row = cur.fetchone()

        conn.close()

        if not row:
            abort(404)

        article = {

            "id": row[0],

            "category":
                row[1] or "world",

            "title":
                row[2] or "",

            "content":
                row[3] or "",

            "img":
                row[4],

            "source_url":
                row[5],

            "source_name":
                row[6]
        }

        back_text = {
            "ar": "العودة",
            "fr": "Retour",
            "en": "Back",
            "es": "Volver"
        }[lang]

        source_text = {
            "ar": "المصدر",
            "fr": "Source",
            "en": "Source",
            "es": "Fuente"
        }[lang]

        original_text = {
            "ar": "قراءة المصدر الأصلي",
            "fr": "Lire la source originale",
            "en": "Read original source",
            "es": "Leer fuente original"
        }[lang]

        return render_template_string(
            ARTICLE_TEMPLATE,

            article=article,

            region=region,

            lang=lang,

            back_text=back_text,

            source_text=source_text,

            original_text=original_text
        )

    except Exception as e:

        print(
            f"!! article page error: {e}"
        )

        abort(500)


# ============================================================
# MANUAL ROBOT TRIGGER
# ============================================================

@app.route("/run-robot")
def manual_robot():

    # IMPORTANT:
    # This endpoint is useful for testing.
    # You can open /run-robot manually.

    threading.Thread(
        target=run_robot,
        daemon=True
    ).start()

    return """
    <h2>Robot started.</h2>
    <p>Check Railway logs.</p>
    """


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/health")
def health():

    return {
        "status": "ok",
        "groq_keys": len(GROQ_KEYS),
        "model": GROQ_MODEL
    }


# ============================================================
# SCHEDULER
# ============================================================

scheduler = BackgroundScheduler(
    timezone="UTC"
)

# First execution shortly after startup.
# Then every 6 hours.

scheduler.add_job(
    run_robot,
    "interval",
    hours=6,
    next_run_time=datetime.now(),
    id="news_robot",
    replace_existing=True,
    max_instances=1,
    coalesce=True
)

scheduler.start()

print(
    "-> Scheduler started"
)

print(
    f"-> Groq keys loaded: "
    f"{len(GROQ_KEYS)}"
)

print(
    f"-> Groq model: "
    f"{GROQ_MODEL}"
)


# ============================================================
# LOCAL DEVELOPMENT
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False
    )
