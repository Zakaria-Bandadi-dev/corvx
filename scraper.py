import os
import re
import time
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

try:
    import psycopg
except Exception:  # pragma: no cover
    psycopg = None

try:
    import psycopg2
except Exception:  # pragma: no cover
    psycopg2 = None

try:
    from sqlalchemy import create_engine
except Exception:  # pragma: no cover
    create_engine = None


DATABASE_URL = os.getenv("DATABASE_URL")
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 20

SOURCES = [
    {
        "name": "Almaster Maroc",
        "url": "https://almaster-maroc.com/",
        "type": "general",
    },
    {
        "name": "Almaster Maroc Master",
        "url": "https://almaster-maroc.com/category/master/",
        "type": "general",
    },
    {
        "name": "Almaster Maroc Licence",
        "url": "https://almaster-maroc.com/category/licence/",
        "type": "general",
    },
    {
        "name": "Almaster Maroc RSS",
        "url": "https://almaster-maroc.com/feed/",
        "type": "rss",
    },
    {
        "name": "UM6P Actualités",
        "url": "https://www.um6p.ma/fr/actualites",
        "type": "general",
    },
    {
        "name": "UM6P Admissions",
        "url": "https://www.um6p.ma/fr/actualites?category=admissions",
        "type": "general",
    },
    {
        "name": "FS Rabat",
        "url": "https://www.fsr.ac.ma/fr/actualites",
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
    {
        "name": "ENCG Casablanca",
        "url": "https://www.encg.ucd.ac.ma/",
        "type": "general",
    },
    {
        "name": "ENSA Marrakech",
        "url": "https://www.ensa.ac.ma/",
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
        "title": "Master Intelligence Artificielle UM6P 2026",
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
        "title": "Cycle d'ingénieur - Électronique, IA et Robotique",
        "category": "Cycles d'Ingénieurs",
        "institution": "Écoles d'ingénieurs et établissements publics marocains",
        "deadline": "25 Octobre 2026",
        "description": "Dossiers d’admission pour les cycles ingénieurs en électronique, robotique, IA et systèmes embarqués.",
        "apply_link": "https://ensias.um5s.ac.ma/",
    },
    {
        "title": "Inscription ENCG - Master Finance et Gestion 2026",
        "category": "Master & Master Spécialisé",
        "institution": "ENCG Casablanca",
        "deadline": "05 Novembre 2026",
        "description": "Ouverture des inscriptions au master en finance, gestion, comptabilité et management des organisations.",
        "apply_link": "https://www.encg.ucd.ac.ma/",
    },
]

CATEGORY_KEYWORDS = {
    "Après Bac (Concours Bac)": [
        "concours", "concours bac", "admission", "baccalaureat", "bac 2026", "selection", "inscription", "ena"
    ],
    "Bac +2 (DEUG, DUT, BTS, CPGE, etc.)": [
        "bac +2", "bac+2", "bts", "dut", "deug", "cpge", "prepa", "prépa", "diplome universitaire", "est", "fst"
    ],
    "Licence d'Excellence & Bachelor": [
        "licence d'excellence", "licence excellence", "licence", "bachelor", "bachelor's", "excellence"
    ],
    "Cycles d'Ingénieurs": [
        "cycle d ingenieur", "cycle ingenieur", "ingenieur", "ingenierie", "engineering", "ecole d ingenieurs", "école d'ingénieurs", "ensa", "ensam", "est", "fst"
    ],
    "Master & Master Spécialisé": [
        "master", "mastere", "mastère", "master specialise", "master spécialisé", "mastérisé", "encg"
    ],
    "Doctorat": [
        "doctorat", "phd", "these", "thèse", "doctorale"
    ],
}

VALID_TITLE_KEYWORDS = (
    "concours", "master", "licence", "bourse", "bac", "inscription", "selection", "cycle d'ingénieur",
    "cycle ingenieur", "cpge", "est", "fst", "ensa", "ensam", "encg"
)

EXCLUDED_TITLE_TOKENS = (
    "santé", "logement", "a propos", "about", "campus france live", "campus france",
    "actualite", "actualité", "contact", "faq", "blog", "evenement", "evenementiel",
    "news", "devenir", "presse", "partenariat", "emploi", "stage", "recrutement"
)

ACCENT_TRANSLATION = str.maketrans({
    'à': 'a', 'â': 'a', 'ä': 'a', 'á': 'a', 'ã': 'a',
    'ç': 'c',
    'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
    'î': 'i', 'ï': 'i', 'í': 'i',
    'ô': 'o', 'ö': 'o', 'ó': 'o',
    'ù': 'u', 'û': 'u', 'ü': 'u', 'ú': 'u',
    'ý': 'y', 'ÿ': 'y',
    'ñ': 'n',
    'œ': 'oe',
    'æ': 'ae',
})


def normalize_for_match(value: Optional[str]) -> str:
    if value is None:
        return ""
    return str(value).lower().translate(ACCENT_TRANSLATION)


def is_valid_orientation_title(title: str, description: str = "") -> bool:
    combined = normalize_for_match(f"{title} {description}")
    if not combined:
        return False

    if any(token in combined for token in EXCLUDED_TITLE_TOKENS):
        return False

    if any(keyword in combined for keyword in VALID_TITLE_KEYWORDS):
        return True

    return False


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
        r"(?:dernier\s+délai|dernier\s+delai|avant\s+le|jusqu\'au|jusqu'au|jusqu\s*à\s*\d)"
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            if "dernier" in match.group(0).lower() or "avant" in match.group(0).lower() or "jusqu" in match.group(0).lower():
                return match.group(0)
            return match.group(0)

    return "Non spécifié"


def extract_deadline_from_text(text: str) -> str:
    if not text:
        return "Non spécifié"

    text = normalize_text(text)
    date_patterns = [
        r"(?:Dernier\s+délai|Dernier\s+delai|Avant\s+le|Jusqu\'au|Jusqu'au|Jusqu\s*à|Date\s+limite|Date\s+limite\s*:)\s*[:\-]?\s*\d{1,2}\s*(?:janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre)\s*\d{4}",
        r"\b\d{1,2}\s*(?:janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre)\s*\d{4}\b",
        r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",
        r"\b\d{4}-\d{2}-\d{2}\b",
    ]

    for pattern in date_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0)

    return "Non spécifié"


def extract_institution_name(text: str) -> str:
    if not text:
        return "Université Marocaine"

    text = normalize_text(text)
    matches = [
        "FS Rabat", "Faculté des Sciences Rabat", "Faculte des Sciences Rabat", "FSJES", "FSJES Rabat",
        "ENCG Settat", "ENCG Casablanca", "UM6P", "ENSA Marrakech", "ENSA", "ENSAM", "ENSIAS",
        "FST", "FS Tétouan", "FS Tetouan", "Institut National", "Université Mohammed VI"
    ]
    for candidate in matches:
        if candidate.lower() in text.lower():
            return candidate

    possible = re.search(r"(?:Faculté|Faculte|Université|Université|Institut|Ecole|École|ENCG|ENSA|FSJES|FS\s+[A-Za-zÀ-ÿ]+)\s+[A-Za-zÀ-ÿ\- ]{2,}", text, re.IGNORECASE)
    if possible:
        cleaned = possible.group(0)
        if len(cleaned) < 120:
            return cleaned.strip()

    return "Université Marocaine"


def is_navigation_or_menu_link(title: str, href: str = "", classes: Optional[List[str]] = None) -> bool:
    label = normalize_for_match(f"{title} {href or ''} {' '.join(classes or [])}")
    if not label:
        return False

    nav_keywords = (
        "menu", "accueil", "home", "about", "a propos", "contact", "faq", "blog",
        "actualites", "actualité", "news", "campus", "carriere", "emploi", "partenariat",
        "recrutement", "presse", "evenement", "événement", "sante", "logement"
    )
    return any(keyword in label for keyword in nav_keywords)


def find_official_application_link(article_text: str, fallback_url: str) -> str:
    text = article_text or ""
    if not text:
        return fallback_url

    lower_text = text.lower()
    keywords = (
        "inscription", "candidature", "postuler", "forms", "preinscription", "pre-inscription",
        "e-services", "touwsit", "enssup", "e-service", "admission", "apply", "portal", ".ac.ma", ".ma"
    )

    urls = re.findall(r"https?:\/\/[^\s)\]>\"']+", text)
    for url in urls:
        normalized = url.lower()
        if any(keyword in normalized for keyword in [
            "inscription", "candidature", "postuler", "form", "preinscription", "touwsit",
            "enssup", "admission", "apply", ".ac.ma", ".ma"
        ]):
            return url

    for keyword in keywords:
        if keyword in lower_text:
            for match in re.finditer(r"https?:\/\/[^\s)\]>\"']+", text, flags=re.IGNORECASE):
                candidate = match.group(0)
                if ".ac.ma" in candidate.lower() or ".ma" in candidate.lower() or any(k in candidate.lower() for k in ["inscription", "candidature", "postuler", "form", "touwsit", "enssup"]):
                    return candidate

    return fallback_url


def detect_category(title: str, description: str = "") -> str:
    text = normalize_for_match(f"{title} {description}")
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(normalize_for_match(keyword) in text for keyword in keywords):
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

    if psycopg is not None:
        return psycopg.connect(DATABASE_URL)
    if psycopg2 is not None:
        return psycopg2.connect(DATABASE_URL)
    if create_engine is not None:
        return create_engine(DATABASE_URL).connect()

    raise RuntimeError("No supported PostgreSQL driver found. Install psycopg, psycopg2, or SQLAlchemy.")


def ensure_table(conn):
    try:
        cursor = conn.cursor()
        cursor.execute(
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
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_orientation_category ON orientation_announcements(category);"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_orientation_deadline ON orientation_announcements(deadline);"
        )
        conn.commit()
    except AttributeError:
        conn.exec_driver_sql(
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
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_orientation_category ON orientation_announcements(category);")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_orientation_deadline ON orientation_announcements(deadline);")
        conn.commit()


def clear_orientation_announcements(conn):
    try:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE orientation_announcements RESTART IDENTITY;")
            conn.commit()
    except Exception:
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM orientation_announcements;")
                conn.commit()
        except Exception:
            try:
                conn.exec_driver_sql("TRUNCATE TABLE orientation_announcements RESTART IDENTITY;")
                conn.commit()
            except Exception:
                conn.exec_driver_sql("DELETE FROM orientation_announcements;")
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

        if not is_valid_orientation_title(title, description):
            continue

        deadline = extract_deadline(f"{title} {description}")
        category = "Master & Master Spécialisé" if "almaster-maroc" in source_url.lower() or "almaster" in source_name.lower() else detect_category(title, description)
        items.append(
            {
                "title": title[:250],
                "category": category,
                "institution": "Almaster Maroc" if "almaster-maroc" in source_url.lower() or "almaster" in source_name.lower() else source_name,
                "deadline": deadline,
                "description": description[:500],
                "apply_link": link,
                "source_name": source_name,
                "source_url": source_url,
            }
        )

    return items


def fetch_article_details(article_url: str, article_title: str, source_name: str, source_url: str) -> Optional[Dict[str, str]]:
    try:
        article_response = requests.get(article_url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        article_response.raise_for_status()
    except Exception:
        return None

    article_soup = BeautifulSoup(article_response.text, "html.parser")

    for tag in article_soup.select("nav, header, footer, .menu, .navigation, .wp-block-navigation, .main-navigation, script, style"):
        tag.decompose()

    content_blocks = []
    content_candidates = article_soup.select("article, main, .entry-content, .post-content, .content, .article-content, .single-post, .description")
    if not content_candidates:
        content_candidates = [article_soup]

    for candidate in content_candidates:
        for sel in ["p", "li", "h1", "h2", "h3", "h4", "div"]:
            for node in candidate.select(sel):
                text = normalize_text(node.get_text(" ", strip=True))
                if text and len(text) > 20:
                    content_blocks.append(text)

    article_text = "\n".join(content_blocks)
    if not article_text:
        article_text = normalize_text(article_soup.get_text(" ", strip=True))

    if not article_text:
        return None

    full_title = normalize_text(article_title) or title_from_element(article_soup)
    if not full_title or not is_valid_orientation_title(full_title, article_text):
        return None

    if any(token in full_title.lower() for token in ["menu", "accueil", "contact", "home", "a propos", "about", "faq", "blog"]):
        return None

    deadline = extract_deadline_from_text(f"{full_title} {article_text}")
    institution = extract_institution_name(f"{full_title} {article_text}")
    apply_link = find_official_application_link(article_text, article_url)

    if "master" in full_title.lower():
        category = "Master & Master Spécialisé"
    elif "licence" in full_title.lower():
        category = "Licence d'Excellence & Bachelor"
    else:
        category = detect_category(full_title, article_text)

    return {
        "title": full_title[:250],
        "category": category,
        "institution": institution,
        "deadline": deadline,
        "description": article_text[:2000],
        "apply_link": apply_link,
        "source_name": source_name,
        "source_url": source_url,
    }


def parse_almaster_maroc_page(url: str, source_name: str, source_url: str) -> List[Dict[str, str]]:
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except Exception:
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    items: List[Dict[str, str]] = []
    seen = set()

    article_links = []
    for anchor in soup.select("a[href]"):
        href = anchor.get("href")
        if not href:
            continue
        text = normalize_text(anchor.get_text(" ", strip=True))
        classes = anchor.get("class") or []
        if is_navigation_or_menu_link(text, href, classes):
            continue
        if any(token in text.lower() for token in ["menu", "accueil", "contact", "a propos", "about", "faq", "blog", "emploi", "stage", "partenariat"]):
            continue
        if len(text) < 8:
            continue
        link = to_absolute_url(url, href)
        if not link.startswith("http"):
            continue
        if not is_valid_orientation_title(text, ""):
            continue
        if any(part in link.lower() for part in ["#", "javascript:", "tel:", "mailto:"]):
            continue
        article_links.append((text, link))

    for title, link in article_links[:200]:
        key = (title.lower(), link.lower())
        if key in seen:
            continue
        seen.add(key)

        article = fetch_article_details(link, title, source_name, source_url)
        if article:
            items.append(article)

    if not items:
        fallback_links = [
            url,
            "https://almaster-maroc.com/category/master/",
            "https://almaster-maroc.com/category/licence/",
        ]
        for fallback_url in fallback_links:
            try:
                page = requests.get(fallback_url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
                page.raise_for_status()
            except Exception:
                continue

            fallback_soup = BeautifulSoup(page.text, "html.parser")
            for anchor in fallback_soup.select("a[href]")[:200]:
                href = anchor.get("href")
                if not href:
                    continue
                text = normalize_text(anchor.get_text(" ", strip=True))
                if not text or len(text) < 10:
                    continue
                if is_navigation_or_menu_link(text, href, anchor.get("class") or []):
                    continue
                if not is_valid_orientation_title(text, ""):
                    continue
                full_link = to_absolute_url(fallback_url, href)
                item = fetch_article_details(full_link, text, source_name, source_url)
                if item:
                    items.append(item)

    return items


def parse_page(url: str, source_name: str, source_url: str) -> List[Dict[str, str]]:
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except Exception:
        return []

    if "almaster-maroc.com" in url.lower() or "almaster" in source_name.lower():
        items = parse_almaster_maroc_page(url, source_name, source_url)
        if items:
            return items

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

        final_title = normalize_text(title)
        if len(final_title) < 10:
            continue

        description = description_from_element(container)
        link = find_links_in_candidate(container, source_url) or url

        if not is_valid_orientation_title(final_title, description):
            continue

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
    clear_orientation_announcements(conn)

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
        print("-> No valid live items found from the current sources. Inserting fallback Moroccan orientation announcements.")
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
            if is_valid_orientation_title(item_payload["title"], item_payload["description"]):
                inserted = insert_if_new(conn, item_payload)
                if inserted:
                    total_inserted += 1
                    print(f"FALLBACK INSERTED -> {item_payload['title'][:120]}")

    conn.close()
    print(f"\nCompleted. Inserted: {total_inserted}. Checked: {total_seen}.")
    return total_inserted


if __name__ == "__main__":
    print("Starting Moroccan orientation scraper...")
    run_scraper()
