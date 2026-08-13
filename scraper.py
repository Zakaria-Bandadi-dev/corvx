import os
import re
import time
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup
import psycopg


DATABASE_URL = os.getenv("DATABASE_URL")
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 20

SOURCES = [
    {
        "name": "UM6P Actualités",
        "url": "https://www.um6p.ma/fr/actualites",
        "type": "general",
    },
    {
        "name": "UM6P RSS",
        "url": "https://www.um6p.ma/fr/actualites?format=rss",
        "type": "rss",
    },
    {
        "name": "Campus France Maroc",
        "url": "https://www.campusfrance.org/fr",
        "type": "general",
    },
    {
        "name": "ENSIAS",
        "url": "https://ensias.um5s.ac.ma/",
        "type": "general",
    },
    {
        "name": "Ministère de l'Éducation Nationale",
        "url": "https://www.enssup.gov.ma/",
        "type": "general",
    },
]

FALLBACK_ANNOUNCEMENTS = [
    {
        "title": "Concours d'admission ENA 2026",
        "category": "Après Bac (Concours Bac)",
        "institution": "ENA — École Nationale d'Administration",
        "deadline": "15 Octobre 2026",
        "description": "Concours national d’accès aux programmes de formation et de recrutement de l’administration publique et des services de l’État au Maroc.",
        "apply_link": "https://www.ena.ma/",
    },
    {
        "title": "Admissions Master Intelligence Artificielle UM6P 2026",
        "category": "Master & Master Spécialisé",
        "institution": "Université Mohammed VI Polytechnique",
        "deadline": "30 Septembre 2026",
        "description": "Programme Master en intelligence artificielle, data science, apprentissage automatique et innovation numérique.",
        "apply_link": "https://www.um6p.ma/fr/actualites",
    },
    {
        "title": "Licence d'Excellence - Informatique et systèmes numériques",
        "category": "Licence d'Excellence & Bachelor",
        "institution": "Faculté des Sciences Rabat / Universités partenaires",
        "deadline": "12 Octobre 2026",
        "description": "Parcours d’excellence pour les étudiants de licence en sciences, informatique, data et projets appliqués.",
        "apply_link": "https://www.fsr.ac.ma/fr/actualites",
    },
    {
        "title": "Cycle Ingénieur — Électronique, IA et Robotique",
        "category": "Cycles d'Ingénieurs",
        "institution": "Écoles d'ingénieurs et établissements publics marocains",
        "deadline": "25 Octobre 2026",
        "description": "Dossiers d’admission pour les cycles ingénieurs en électronique, robotique, IA et systèmes embarqués.",
        "apply_link": "https://ensias.um5s.ac.ma/",
    },
]

CATEGORY_KEYWORDS = {
    "Après Bac (Concours Bac)": [
        "apres bac", "après bac", "concours bac", "bac 2026", "concours de recrutement", "concours bac"
    ],
    "Bac +2 (DEUG, DUT, BTS, CPGE, etc.)": [
        "bac+2", "bac +2", "bts", "dut", "deug", "cpge", "prepas", "diplome universitaire"
    ],
    "Licence d'Excellence & Bachelor": [
        "licence d'excellence", "licence excellence", "bachelor", "licence", "bachelor's"
    ],
    "Cycles d'Ingénieurs": [
        "cycle ingenieur", "cycle d'ingénieur", "engineering", "ingenieur", "ingénieur", "école d'ingénieurs"
    ],
    "Master & Master Spécialisé": [
        "master", "mastère", "mastere", "master specialise", "master spécialisé"
    ],
    "Doctorat": [
        "doctorat", "phd", "these", "doctorale"
    ],
}


def normalize_text(value: Optional[str]) -> str:
    if value is None:
        return ""
    cleaned = re.sub(r"\s+", " ", value)
    return cleaned.strip()


def safe_get_text(element) -> str:
    if element is None:
        return ""
    return normalize_text(element.get_text(" ", strip=True))


def extract_deadline(text: str) -> str:
    if not text:
        return "Non spécifié"

    patterns = [
        r"\b\d{1,2}\s+(?:janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre)\s+\d{4}\b",
        r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",
        r"\b\d{4}-\d{2}-\d{2}\b",
        r"\b\d{1,2}\s+[A-Za-zÀ-ÿ]+\s+\d{4}\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0)

    return "Non spécifié"


def detect_category(title: str, description: str = "") -> str:
    text = f"{title} {description}".lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return category
    return "Autre"


def to_absolute_url(base_url: str, href: str) -> str:
    if not href:
        return base_url
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return urljoin(base_url, href)


def get_db_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is missing. Add it to your VS Code environment or local .env file.")
    return psycopg.connect(DATABASE_URL)


def ensure_table(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS orientation_announcements (
                id SERIAL PRIMARY KEY,
                category TEXT,
                title TEXT NOT NULL,
                institution TEXT,
                deadline TEXT,
                description TEXT,
                apply_link TEXT,
                source_name TEXT,
                source_url TEXT,
                country TEXT DEFAULT 'MA',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (title, apply_link)
            );
            """
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_orientation_category ON orientation_announcements(category);"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_orientation_deadline ON orientation_announcements(deadline);"
        )
        conn.commit()


def title_from_element(el) -> str:
    if not el:
        return ""

    for selector in ["h1", "h2", "h3", "h4", "a", ".title", ".entry-title"]:
        match = el.select_one(selector)
        if match:
            text = safe_get_text(match)
            if text:
                return text

    text = safe_get_text(el)
    return text[:200]


def description_from_element(el) -> str:
    if not el:
        return ""

    candidates = el.select("p, .summary, .description, .excerpt, .lead, .teaser")
    for candidate in candidates:
        text = safe_get_text(candidate)
        if len(text) > 20:
            return text
    return ""


def find_links_in_candidate(candidate, base_url: str) -> Optional[str]:
    if candidate is None:
        return None

    anchor = candidate.select_one("a[href]")
    if anchor:
        href = anchor.get("href")
        return to_absolute_url(base_url, href)

    for selector in ["a[href]", "a[data-href]", "link[href]"]:
        anchors = candidate.select(selector)
        for a in anchors:
            href = a.get("href") or a.get("data-href")
            if href:
                return to_absolute_url(base_url, href)
    return None


def parse_rss_feed(url: str, source_name: str, source_url: str) -> List[Dict[str, str]]:
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        root = ET.fromstring(response.content)
    except Exception:
        return []

    items: List[Dict[str, str]] = []
    entries = root.findall(".//item") or root.findall(".//entry")

    for entry in entries:
        title = ""
        link = ""
        description = ""

        for field in ["title", "link", "description", "summary", "content"]:
            tag = entry.find(field)
            if tag is not None and tag.text:
                if field == "title":
                    title = normalize_text(tag.text)
                elif field == "link":
                    link = normalize_text(tag.text)
                elif field in {"description", "summary", "content"}:
                    description = normalize_text(tag.text)

        if not title:
            continue

        if not link:
            link = source_url

        deadline = extract_deadline(f"{title} {description}")
        category = detect_category(title, description)
        items.append(
            {
                "title": title[:250],
                "category": category,
                "institution": source_name,
                "deadline": deadline,
                "description": description[:500],
                "apply_link": link,
                "source_name": source_name,
                "source_url": source_url,
            }
        )

    return items


def parse_page(url: str, source_name: str, source_url: str) -> List[Dict[str, str]]:
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except Exception:
        return []

    content_type = (response.headers.get("Content-Type") or "").lower()
    if "xml" in content_type or url.lower().endswith(".xml") or "rss" in url.lower():
        items = parse_rss_feed(url, source_name, source_url)
        if items:
            return items

    soup = BeautifulSoup(response.text, "html.parser")
    items: List[Dict[str, str]] = []

    containers = soup.select(
        "article, li, .news-item, .announcement, .event, .card, .post, .item, .entry, .programme, .content-item, .listing-item, .result-item, .publication-item"
    )

    fallback_selectors = [
        "div", "section", "main", "td", "tr"
    ]
    for selector in fallback_selectors:
        if not containers:
            containers = soup.select(selector)
        else:
            break

    if not containers:
        containers = [soup]

    seen = set()
    for container in containers[:250]:
        title = title_from_element(container)
        if not title:
            continue

        if len(title) < 10:
            continue

        description = description_from_element(container)
        link = find_links_in_candidate(container, source_url) or url

        final_title = normalize_text(title)
        final_key = (final_title.lower(), link.lower())
        if final_key in seen:
            continue
        seen.add(final_key)

        deadline = extract_deadline(f"{final_title} {description}")
        category = detect_category(final_title, description)

        items.append(
            {
                "title": final_title[:250],
                "category": category,
                "institution": source_name,
                "deadline": deadline,
                "description": description[:500],
                "apply_link": link,
                "source_name": source_name,
                "source_url": source_url,
            }
        )

    return items


def insert_if_new(conn, item: Dict[str, str]) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM orientation_announcements
            WHERE LOWER(title) = LOWER(%s)
               OR LOWER(apply_link) = LOWER(%s)
            LIMIT 1;
            """,
            (item["title"], item["apply_link"]),
        )
        existing = cur.fetchone()
        if existing:
            return False

        cur.execute(
            """
            INSERT INTO orientation_announcements (
                category, title, institution, deadline, description, apply_link, source_name, source_url, country
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
            """,
            (
                item["category"],
                item["title"],
                item["institution"],
                item["deadline"],
                item["description"],
                item["apply_link"],
                item["source_name"],
                item["source_url"],
                "MA",
            ),
        )
        conn.commit()
        return True


def run_scraper():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is missing. Set it in your environment before running the scraper.")

    conn = get_db_connection()
    ensure_table(conn)

    total_inserted = 0
    total_seen = 0

    for source in SOURCES:
        url = source["url"]
        source_name = source["name"]
        print(f"-> Scraping {source_name}: {url}")

        items = parse_page(url, source_name, url)
        if not items:
            print(f"No items found for {source_name}.")
            continue

        for item in items:
            total_seen += 1
            inserted = insert_if_new(conn, item)
            if inserted:
                total_inserted += 1
                print(f"INSERTED -> {item['title'][:120]}")
            else:
                print(f"SKIP DUPLICATE -> {item['title'][:120]}")

        time.sleep(1)

    if total_inserted == 0:
        print("-> No live items found from the current sources. Inserting fallback Moroccan orientation announcements.")
        for item in FALLBACK_ANNOUNCEMENTS:
            item_payload = {
                "title": item["title"],
                "category": item["category"],
                "institution": item["institution"],
                "deadline": item["deadline"],
                "description": item["description"],
                "apply_link": item["apply_link"],
                "source_name": "Fallback seed",
                "source_url": item["apply_link"],
            }
            if insert_if_new(conn, item_payload):
                total_inserted += 1
                print(f"FALLBACK INSERTED -> {item_payload['title'][:120]}")

    conn.close()
    print(f"\nCompleted. Inserted: {total_inserted}. Checked: {total_seen}.")
    return total_inserted


if __name__ == "__main__":
    print("Starting Moroccan orientation scraper...")
    run_scraper()
