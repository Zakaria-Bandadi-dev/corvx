import json
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse, urlsplit, urlunsplit
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
REQUEST_RETRIES = 3
REQUEST_DELAY_SECONDS = 1.0
ORIENTATION_SOURCE_DOMAIN = "orientation-chabab.com"
ORIENTATION_SITEMAPS = [
    "https://orientation-chabab.com/sitemap1.xml",
    "https://orientation-chabab.com/sitemap-news.xml",
]


def normalize_text(value: Optional[str]) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def normalize_url(raw_url: Optional[str]) -> Optional[str]:
    if not raw_url:
        return None
    url = str(raw_url).strip()
    if not url:
        return None
    if url.startswith("//"):
        url = "https:" + url
    try:
        parsed = urlsplit(url)
    except Exception:
        return None
    if not parsed.scheme or not parsed.netloc:
        return None
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        return None
    cleaned = urlunsplit((scheme, parsed.netloc, parsed.path, "", ""))
    if cleaned and cleaned != "/":
        return cleaned
    return cleaned or "https://" + parsed.netloc


def normalize_for_match(value: Optional[str]) -> str:
    if value is None:
        return ""
    text = str(value).lower()
    translation = str.maketrans({
        'à': 'a', 'â': 'a', 'ä': 'a', 'á': 'a', 'ã': 'a',
        'ç': 'c',
        'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
        'î': 'i', 'ï': 'i', 'í': 'i',
        'ô': 'o', 'ö': 'o', 'ó': 'o',
        'ù': 'u', 'û': 'u', 'ü': 'u', 'ú': 'u',
        'ý': 'y', 'ÿ': 'y',
        'ñ': 'n',
        'œ': 'oe', 'æ': 'ae',
    })
    return text.translate(translation)


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


def http_get(url: str, timeout: int = REQUEST_TIMEOUT, retries: int = REQUEST_RETRIES, allow_redirects: bool = True):
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=timeout,
                allow_redirects=allow_redirects,
            )
            if response.status_code in {403, 429} and attempt < retries:
                time.sleep(2 ** attempt)
                continue
            if response.status_code >= 400:
                raise requests.HTTPError(f"HTTP {response.status_code}")
            return response
        except Exception as exc:  # pragma: no cover
            last_error = exc
            if attempt < retries:
                time.sleep(1.5 * attempt)
    raise last_error or RuntimeError(f"Request failed for {url}")


def is_orientation_chabab_url(url: Optional[str]) -> bool:
    normalized = normalize_url(url)
    if not normalized:
        return False
    host = urlparse(normalized).netloc.lower()
    return ORIENTATION_SOURCE_DOMAIN in host


def parse_sitemap_urls(sitemap_url: str) -> List[str]:
    urls: List[str] = []
    try:
        response = http_get(sitemap_url)
        root = ET.fromstring(response.text)
        for node in root.iter():
            if node.tag.endswith("loc") and node.text:
                url = normalize_url(node.text)
                if url:
                    urls.append(url)
    except Exception as exc:
        print(f"[ORIENTATION] Sitemap failed: {sitemap_url} -> {exc}")
    return urls


def discover_orientation_urls() -> List[str]:
    discovered: List[str] = []
    seen: Set[str] = set()
    for sitemap_url in ORIENTATION_SITEMAPS:
        print(f"[ORIENTATION] Sitemap: {sitemap_url}")
        for item_url in parse_sitemap_urls(sitemap_url):
            normalized = normalize_url(item_url)
            if not normalized or not is_orientation_chabab_url(normalized):
                continue
            if normalized not in seen:
                seen.add(normalized)
                discovered.append(normalized)
    print(f"[ORIENTATION] Sitemap discovery complete: {len(discovered)} URLs discovered")
    return discovered


def safe_meta(soup: BeautifulSoup, *names: str) -> str:
    for name in names:
        tag = soup.select_one(f"meta[{name}]")
        if tag and tag.get("content"):
            return normalize_text(tag.get("content"))
    return ""


def sanitize_text(value: Optional[str]) -> str:
    return normalize_text(re.sub(r"\s+", " ", str(value or ""))).strip()


def extract_title(soup: BeautifulSoup, fallback: str = "") -> str:
    candidates = [
        safe_meta(soup, "property='og:title'", "name='twitter:title'", "name='title'"),
        soup.title.get_text(" ", strip=True) if soup.title and soup.title.get_text(" ", strip=True) else "",
    ]
    for candidate in candidates:
        if candidate:
            return candidate
    for selector in ["h1", ".entry-title", ".post-title", "article h1", "main h1"]:
        node = soup.select_one(selector)
        text = sanitize_text(node.get_text(" ", strip=True)) if node else ""
        if text:
            return text
    return fallback


def extract_description(soup: BeautifulSoup) -> str:
    desc = safe_meta(soup, "property='og:description'", "name='description'", "name='twitter:description'")
    if desc:
        return desc
    for selector in ["article p", ".entry-content p", ".post-content p", "main p"]:
        for node in soup.select(selector):
            text = sanitize_text(node.get_text(" ", strip=True))
            if len(text) > 30:
                return text
    return ""


def extract_article_body(soup: BeautifulSoup) -> str:
    article = soup.select_one("article") or soup.select_one("main") or soup
    chunks: List[str] = []
    for selector in ["p", "li", "h1", "h2", "h3", "h4", "div"]:
        for node in article.select(selector):
            text = sanitize_text(node.get_text(" ", strip=True))
            if len(text) > 20:
                chunks.append(text)
    text = "\n".join(chunks)
    if text:
        return text[:6000]
    return sanitize_text(soup.get_text(" ", strip=True))[:6000]


def parse_publication_date(raw_date: Optional[str]) -> Optional[datetime]:
    if raw_date is None:
        return None

    value = sanitize_text(raw_date)
    if not value:
        return None

    text = value.lower().strip()
    if text in {"non spécifié", "non specifie", "unknown", "n/a", "na"}:
        return None

    normalized = text
    month_map = {
        "janvier": "january", "fevrier": "february", "février": "february", "mars": "march",
        "avril": "april", "mai": "may", "juin": "june", "juillet": "july",
        "aout": "august", "août": "august", "septembre": "september", "octobre": "october",
        "novembre": "november", "décembre": "december", "decembre": "december",
    }
    for month_fr, month_en in month_map.items():
        normalized = normalized.replace(month_fr, month_en)

    formats = [
        "%d %B %Y", "%d %b %Y", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
        "%Y-%m-%d", "%d/%m/%y", "%d-%m-%y", "%d.%m.%y",
        "%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%m-%d-%y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            pass

    # Fallback for French textual dates when the month translation is not enough.
    try:
        return datetime.strptime(normalized, "%d %B %Y")
    except ValueError:
        return None


def should_accept_publication_date(raw_date: Optional[str]) -> bool:
    parsed = parse_publication_date(raw_date)
    return parsed is not None and parsed.year == 2026


def extract_dates_from_text(text: str) -> Dict[str, str]:
    result: Dict[str, str] = {"publication_date": "", "updated_at": ""}
    if not text:
        return result
    text_norm = normalize_text(text)
    patterns = [
        r"(?:publi(?:e|é)\s*le|published on|publish date|date de publication)\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}\s+(?:janvier|fevrier|février|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre)\s+\d{4})",
        r"(?:mise\s*à\s*jour|updated|modifi(?:e|é)\s*le|dernière mise à jour)\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}\s+(?:janvier|fevrier|février|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre)\s+\d{4})",
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}\s+(?:janvier|fevrier|février|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre)\s+\d{4})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text_norm, flags=re.IGNORECASE)
        if match:
            candidate = match.group(1) if match.lastindex else match.group(0)
            if not result["publication_date"]:
                result["publication_date"] = candidate.strip()
                break
    return result


def extract_deadline(text: str) -> str:
    if not text:
        return "Non spécifié"
    text_norm = normalize_text(text)
    patterns = [
        r"(?:dernier\s*délai|dernier\s*delai|date\s*limite|clôture|cloture|candidatures\s*jusqu\'?au|jusqu\'?au|avant\s*le|au\s+plus\s+tard\s+le|deadline)\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}\s+(?:janvier|fevrier|février|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre)\s+\d{4})",
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}\s+(?:janvier|fevrier|février|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre)\s+\d{4})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text_norm, flags=re.IGNORECASE)
        if match:
            candidate = match.group(1) if match.lastindex else match.group(0)
            return candidate.strip()
    return "Non spécifié"


def extract_institution(text: str) -> str:
    text_norm = normalize_text(text)
    known = [
        "ENSA", "ENSA Marrakech", "ENSEM", "INPT", "UM6P", "FSR", "FST", "ENCG", "ENSIAS",
        "Université Mohammed VI", "Institut National", "Faculté des Sciences", "Ecole Nationale",
        "École Nationale", "Université Hassan II", "Université Cadi Ayyad", "Université Ibn Tofail",
        "Université de Marrakech", "Université Sidi Mohamed Ben Abdellah", "Université Abdelmalek Essaadi",
        "École Supérieure", "Ecole Supérieure", "Centre d'Etudes", "Centre d'Études"
    ]
    for item in known:
        if normalize_for_match(item) in normalize_for_match(text_norm):
            return item
    patterns = [
        r"(?:École|Ecole|Institut|Université|Faculté|Faculte|Centre|Campus)\s+[A-Za-zÀ-ÿ0-9\- ]{2,}",
        r"(?:ENSA|ENSAM|ENCG|FSR|FST|UM6P|INPT|ENSEM|ENSIAS)\s+[A-Za-zÀ-ÿ0-9\- ]{2,}",
    ]
    for pattern in patterns:
        match = re.search(pattern, text_norm, flags=re.IGNORECASE)
        if match:
            cleaned = sanitize_text(match.group(0))
            if len(cleaned) < 150:
                return cleaned
    return "Université / établissement partenaire"


def extract_city(text: str) -> str:
    cities = [
        "Casablanca", "Rabat", "Marrakech", "Fès", "Fez", "Tanger", "Agadir", "Meknès", "Kenitra",
        "Oujda", "Tétouan", "Tetouan", "Settat", "Khouribga", "Laayoune", "Dakhla", "Mohammedia"
    ]
    text_norm = normalize_text(text)
    for city in cities:
        if normalize_for_match(city) in normalize_for_match(text_norm):
            return city
    return ""


def extract_country(text: str) -> str:
    countries = [
        "Maroc", "France", "Allemagne", "Espagne", "Italie", "Suisse", "Canada", "Royaume-Uni",
        "UK", "USA", "États-Unis", "Belgique", "Pays-Bas", "Tunisie", "Algérie", "Mauritanie", "Sénégal"
    ]
    text_norm = normalize_text(text)
    matches = [country for country in countries if normalize_for_match(country) in normalize_for_match(text_norm)]
    return matches[0] if matches else "MA"


def classify_academic_level(title: str, content: str, url: str = "") -> str:
    text = normalize_for_match(f"{title} {content} {url}")
    if any(token in text for token in ["bourse", "scholarship", "etudes a l etranger", "etudes a l’étranger", "study abroad", "mobilite internationale", "programme de bourse", "scholarship program", "financement des etudes"]):
        return "bourses_etranger"
    if any(token in text for token in ["bac+2", "bac +2", "deug", "deust", "deup", "dut", "bts", "diplome equivalent", "diplôme équivalent", "2 ans après le bac", "deux années après le bac"]):
        return "bac+2"
    if any(token in text for token in ["bac+3", "bac +3", "licence", "licence professionnelle", "licence pro", "bachelor", "diplome de licence", "diplôme de licence"]):
        return "bac+3"
    if any(token in text for token in ["cycle ingenieur", "cycle d ingenieur", "cycle d'ingénieur", "cycle ingénieur", "ingenieur d etat", "ingénieur d'état", "concours ingenieur", "ecole d ingenieurs", "école d'ingénieurs", "premiere annee cycle ingenieur", "première année cycle ingénieur", "deuxieme annee cycle ingenieur", "deuxième année cycle ingénieur"]):
        if any(token in text for token in ["concours", "inscription", "admission", "candidature", "access", "preinscription", "préinscription"]):
            return "ingenieur"
    if any(token in text for token in ["baccalaureat", "baccalauréat", "bac ", "apres bac", "après bac", "apres le bac", "après le bac", "concours apres bac", "concours d acces apres bac"]):
        return "bac"
    return "bac"


def classify_announcement(title: str, content: str, url: str = "", institution: str = "") -> str:
    return classify_academic_level(title, content, url)


def classify_announcement_type(title: str, content: str) -> str:
    text = normalize_for_match(f"{title} {content}")
    if any(token in text for token in ["resultat", "résultat", "resultats", "résultats"]):
        return "resultats"
    if "preselection" in text or "présélection" in text or "preselection" in text:
        return "preselection"
    if "preinscription" in text or "préinscription" in text:
        return "preinscription"
    if "inscription" in text:
        return "inscription"
    if "concours" in text:
        return "concours"
    if "bourse" in text or "scholarship" in text:
        return "bourse"
    if "candidature" in text or "postuler" in text or "admission" in text:
        return "admission"
    return "other"


def detect_announcement_type(title: str, content: str) -> str:
    return classify_announcement_type(title, content)


def find_best_apply_link(html: str, page_url: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    title = extract_title(soup, "")
    body = extract_article_body(soup)
    return pick_best_apply_link(page_url, title, body, soup)


def is_likely_real_orientation_article(title: str, content: str, url: str) -> bool:
    text = normalize_for_match(f"{title} {content} {url}")
    if not text:
        return False

    parsed = urlparse(url)
    path_segments = [seg for seg in parsed.path.strip("/").split("/") if seg]
    generic_root_paths = {
        "actualite", "actualites", "concours", "master", "licence-professionnelle",
        "licence-d-excellence", "bourse", "emploi", "emploi-public", "formations",
        "a-propos", "contact", "faq", "partenariat", "news", "blog"
    }
    if len(path_segments) == 1 and path_segments[0].lower() in generic_root_paths:
        return False

    announcement_tokens = [
        "concours", "inscription", "candidature", "admission", "licence", "bachelor",
        "bts", "dut", "bourse", "cycle ingenieur", "preinscription", "preinscription",
        "campus", "equipe", "ecole", "universite"
    ]
    generic_page_tokens = [
        "contact", "faq", "a propos", "about", "blog", "emploi", "presse", "partenariat",
        "news"
    ]

    if any(token in text for token in announcement_tokens):
        return True

    if any(token in text for token in generic_page_tokens):
        return False

    return False


def is_maybe_application_url(url: Optional[str]) -> bool:
    normalized = normalize_url(url)
    if not normalized:
        return False
    hostname = urlparse(normalized).hostname or ""
    if not hostname:
        return False
    if "orientation-chabab" in hostname.lower():
        return False
    if any(hostname.lower().endswith(sfx) for sfx in ["facebook.com", "twitter.com", "x.com", "linkedin.com", "instagram.com", "youtube.com", "tiktok.com"]):
        return False
    if normalized.lower().endswith((".pdf", ".jpg", ".png", ".jpeg", ".gif", ".svg")):
        return False
    return True


def extract_candidate_application_links(soup: BeautifulSoup, page_url: str) -> List[str]:
    candidates: List[str] = []
    seen: Set[str] = set()
    for anchor in soup.select("a[href]"):
        href = anchor.get("href")
        if not href:
            continue
        text = sanitize_text(anchor.get_text(" ", strip=True))
        normalized_href = normalize_url(urljoin(page_url, href))
        if not normalized_href or not is_maybe_application_url(normalized_href):
            continue
        lowered = normalize_for_match(f"{text} {normalized_href}")
        if any(token in lowered for token in [
            "inscription", "preinscription", "candidature", "postuler", "admission", "apply", "register", "signup", "portal",
            "concours", "candidate", "recrutement", "demande", "selection", "submit"
        ]):
            if normalized_href not in seen:
                seen.add(normalized_href)
                candidates.append(normalized_href)
    raw_links = re.findall(r"https?://[^\s\"'<>]+", soup.get_text(" ", strip=True))
    for href in raw_links:
        normalized = normalize_url(href)
        if normalized and is_maybe_application_url(normalized) and normalized not in seen:
            if any(token in normalize_for_match(href) for token in [
                "inscription", "preinscription", "admission", "concours", "candidature", "apply", "register", "signup"
            ]):
                seen.add(normalized)
                candidates.append(normalized)
    return candidates


def pick_best_apply_link(page_url: str, title: str, content: str, soup: BeautifulSoup) -> str:
    candidates = extract_candidate_application_links(soup, page_url)
    if not candidates:
        return ""
    text_blob = normalize_for_match(f"{title} {content}")
    scored: List[Tuple[int, str]] = []
    for candidate in candidates:
        score = 0
        host = (urlparse(candidate).hostname or "").lower()
        if any(host.endswith(sfx) for sfx in [".ac.ma", ".edu", ".gov", ".ma"]):
            score += 30
        if any(token in normalize_for_match(candidate) for token in ["inscription", "preinscription", "candidature", "admission", "concours", "register", "apply"]):
            score += 25
        if any(token in text_blob for token in ["inscription", "preinscription", "concours", "admission", "candidature"]):
            score += 10
        if any(token in text_blob for token in ["deug", "dut", "bts", "licence", "ingénieur", "ingenieur", "bourse"]):
            score += 5
        scored.append((score, candidate))
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


def parse_orientation_article(url: str) -> Optional[Dict[str, Any]]:
    try:
        response = http_get(url)
    except Exception as exc:
        print(f"[ORIENTATION] Failed to fetch article {url}: {exc}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    title = extract_title(soup, "")
    description = extract_description(soup)
    body = extract_article_body(soup)
    text_blob = f"{title} {description} {body}"
    if not title or not is_likely_real_orientation_article(title, body, url):
        print(f"[ORIENTATION] Rejected article: {url}")
        return None

    apply_link = pick_best_apply_link(url, title, body, soup)
    institution = extract_institution(text_blob)
    city = extract_city(text_blob)
    country = extract_country(text_blob)
    academic_level = classify_academic_level(title, body, url)
    announcement_type = classify_announcement_type(title, body)
    deadline = extract_deadline(text_blob)
    publication_date_raw = extract_dates_from_text(text_blob).get("publication_date", "")
    updated_at = extract_dates_from_text(text_blob).get("updated_at", "")
    if not should_accept_publication_date(publication_date_raw):
        print(f"[ORIENTATION] Rejected article with non-2026 publication date: {url} -> {publication_date_raw or 'missing'}")
        return None
    publication_date = publication_date_raw
    image_url = safe_meta(soup, "property='og:image'", "name='twitter:image'", "itemprop='image'")
    required_diploma = ""
    if any(token in normalize_for_match(text_blob) for token in ["deug", "deust", "deup", "dut", "bts", "diplome"]):
        required_diploma = "DEUG / DEUST / DEUP / DUT / BTS / diplôme équivalent"
    elif any(token in normalize_for_match(text_blob) for token in ["licence", "bachelor"]):
        required_diploma = "Licence / Bachelor / Bac+3"
    elif any(token in normalize_for_match(text_blob) for token in ["baccalaureat", "bac"]):
        required_diploma = "Baccalauréat / BAC"
    eligibility = ""
    for label in ["conditions d'accès", "conditions d admission", "conditions d'accès", "eligibilite", "éligibilité", "admission", "candidature"]:
        if normalize_for_match(label) in normalize_for_match(text_blob):
            eligibility = label
            break
    study_field = ""
    if any(token in normalize_for_match(text_blob) for token in ["informatique", "ia", "data", "finance", "gestion", "electrique", "mecanique", "electronique", "agronomie", "sante", "medecine"]):
        match = re.search(r"(?:informatique|ia|data|finance|gestion|électronique|electrique|mécanique|mecanique|agronomie|santé|medecine|management)", normalize_for_match(text_blob), flags=re.IGNORECASE)
        if match:
            study_field = match.group(0)

    return {
        "title": title[:250],
        "description": (description[:2500] if description else body[:2500]),
        "content": body[:6000],
        "publication_date": publication_date,
        "updated_at": updated_at,
        "institution": institution,
        "city": city,
        "country": country,
        "academic_level": academic_level,
        "announcement_type": announcement_type,
        "deadline": deadline,
        "apply_link": apply_link,
        "source_name": "Orientation Chabab",
        "source_url": url,
        "image_url": image_url,
        "eligibility": eligibility,
        "required_diploma": required_diploma,
        "study_field": study_field,
    }


def ensure_orientation_table(conn):
    try:
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
                    academic_level TEXT,
                    announcement_type TEXT,
                    publication_date TEXT,
                    updated_at TEXT,
                    city TEXT,
                    eligibility TEXT,
                    required_diploma TEXT,
                    study_field TEXT,
                    image_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (title, source_url)
                );
                """
            )

            orientation_columns = {
                "category": "TEXT",
                "title": "TEXT",
                "institution": "TEXT",
                "deadline": "TEXT",
                "description": "TEXT",
                "apply_link": "TEXT",
                "source_name": "TEXT",
                "source_url": "TEXT",
                "country": "TEXT DEFAULT 'MA'",
                "academic_level": "TEXT",
                "announcement_type": "TEXT",
                "publication_date": "TEXT",
                "updated_at": "TEXT",
                "city": "TEXT",
                "eligibility": "TEXT",
                "required_diploma": "TEXT",
                "study_field": "TEXT",
                "image_url": "TEXT",
            }
            for field, field_type in orientation_columns.items():
                cur.execute(f"ALTER TABLE orientation_announcements ADD COLUMN IF NOT EXISTS {field} {field_type};")

            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_orientation_title_source_url ON orientation_announcements(title, source_url);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_orientation_category ON orientation_announcements(category);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_orientation_deadline ON orientation_announcements(deadline);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_orientation_academic_level ON orientation_announcements(academic_level);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_orientation_source_url ON orientation_announcements(source_url);")
            conn.commit()
    except Exception as exc:
        print(f"[ORIENTATION] Table ensure failed: {exc}")


def upsert_orientation_item(conn, item: Dict[str, Any]) -> str:
    payload = {
        "category": item.get("academic_level") or "bac",
        "title": item["title"],
        "institution": item.get("institution") or "Établissement partenaire",
        "deadline": item.get("deadline") or "Non spécifié",
        "description": item.get("description") or item.get("content") or "",
        "apply_link": item.get("apply_link") or "",
        "source_name": item.get("source_name") or "Orientation Chabab",
        "source_url": item.get("source_url") or "",
        "country": item.get("country") or "MA",
        "academic_level": item.get("academic_level") or "bac",
        "announcement_type": item.get("announcement_type") or "other",
        "publication_date": item.get("publication_date") or "",
        "updated_at": item.get("updated_at") or "",
        "city": item.get("city") or "",
        "eligibility": item.get("eligibility") or "",
        "required_diploma": item.get("required_diploma") or "",
        "study_field": item.get("study_field") or "",
        "image_url": item.get("image_url") or "",
    }

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO orientation_announcements (
                    category, title, institution, deadline, description, apply_link, source_name, source_url,
                    country, academic_level, announcement_type, publication_date, updated_at, city,
                    eligibility, required_diploma, study_field, image_url
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (title, source_url) DO UPDATE SET
                    category = EXCLUDED.category,
                    institution = EXCLUDED.institution,
                    deadline = EXCLUDED.deadline,
                    description = EXCLUDED.description,
                    apply_link = EXCLUDED.apply_link,
                    source_name = EXCLUDED.source_name,
                    country = EXCLUDED.country,
                    academic_level = EXCLUDED.academic_level,
                    announcement_type = EXCLUDED.announcement_type,
                    publication_date = EXCLUDED.publication_date,
                    updated_at = EXCLUDED.updated_at,
                    city = EXCLUDED.city,
                    eligibility = EXCLUDED.eligibility,
                    required_diploma = EXCLUDED.required_diploma,
                    study_field = EXCLUDED.study_field,
                    image_url = EXCLUDED.image_url;
                """,
                (
                    payload["category"],
                    payload["title"],
                    payload["institution"],
                    payload["deadline"],
                    payload["description"],
                    payload["apply_link"],
                    payload["source_name"],
                    payload["source_url"],
                    payload["country"],
                    payload["academic_level"],
                    payload["announcement_type"],
                    payload["publication_date"],
                    payload["updated_at"],
                    payload["city"],
                    payload["eligibility"],
                    payload["required_diploma"],
                    payload["study_field"],
                    payload["image_url"],
                ),
            )
        conn.commit()
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        print(f"[ORIENTATION] Upsert failed for {payload['title']}: {exc}")
        return "FAILED"

    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM orientation_announcements WHERE LOWER(title) = LOWER(%s) AND LOWER(COALESCE(source_url, '')) = LOWER(%s)",
            (payload["title"], payload["source_url"]),
        )
        row = cur.fetchone()
        if row is None:
            return "DUPLICATE"
        return "UPDATED" if row[0] else "INSERTED"


def run_orientation_scraper() -> Dict[str, int]:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is missing. Set it in your environment before running the scraper.")

    summary = {
        "discovered": 0,
        "processed": 0,
        "inserted": 0,
        "updated": 0,
        "duplicates": 0,
        "rejected": 0,
        "failed": 0,
    }

    conn = get_db_connection()
    ensure_orientation_table(conn)

    with conn.cursor() as cur:
        cur.execute("DELETE FROM orientation_announcements WHERE publication_date IS NULL OR publication_date = '' OR publication_date NOT ILIKE '%2026%'")
    conn.commit()

    discovered_urls = discover_orientation_urls()
    summary["discovered"] = len(discovered_urls)

    for url in discovered_urls:
        print(f"[ORIENTATION] Processing: {url}")
        article = parse_orientation_article(url)
        summary["processed"] += 1
        if article is None:
            summary["failed"] += 1
            continue

        if not is_likely_real_orientation_article(article["title"], article["content"], article["source_url"]):
            summary["rejected"] += 1
            print(f"[ORIENTATION] REJECTED: {article['title']}")
            continue

        status = upsert_orientation_item(conn, article)
        if status == "UPDATED":
            summary["updated"] += 1
            print(f"[ORIENTATION] UPDATED: {article['title']}")
        elif status == "INSERTED":
            summary["inserted"] += 1
            print(f"[ORIENTATION] INSERTED: {article['title']}")
        elif status == "FAILED":
            summary["failed"] += 1
            print(f"[ORIENTATION] FAILED: {article['title']}")
        else:
            summary["duplicates"] += 1
            print(f"[ORIENTATION] DUPLICATE: {article['title']}")

        time.sleep(REQUEST_DELAY_SECONDS)

    conn.close()
    print("[ORIENTATION] SUMMARY")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def run_scraper():
    return run_orientation_scraper()


if __name__ == "__main__":
    print("[ORIENTATION] Starting Orientation Chabab scraper...")
    run_orientation_scraper()
