import os

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

# ------------------------------------------------------------
# JOBS SECTION: 3 dedicated keys out of the 5.
# NEWS keeps working exactly like before, but only rotates over
# the remaining 2 keys (so it never collides with the jobs robot).
# If less than 5 keys are configured, we still split as evenly
# as possible so nothing crashes.
# ------------------------------------------------------------
NEWS_GROQ_KEYS = GROQ_KEYS[:2] if len(GROQ_KEYS) >= 2 else GROQ_KEYS
JOB_GROQ_KEYS = GROQ_KEYS[2:5] if len(GROQ_KEYS) > 2 else GROQ_KEYS

# ============================================================
# MODELS
# ============================================================

# llama-3.3-70b-versatile was deprecated by Groq (shutdown 2026-08-16).
# openai/gpt-oss-120b is Groq's recommended free-tier replacement:
# same rate-limit/free-tier structure, no billing required, and it's
# actually cheaper per-token than the old llama model if you ever
# upgrade to a paid plan.
GROQ_MODEL = "openai/gpt-oss-120b"

# groq/compound: عندو built-in tools (web_search + visit_website)
# باش يدخل بنفسه للمواقع ديال الخدمة ويقلب على العروض الجداد.
# (groq/compound is NOT deprecated, keep as-is)
JOBS_GROQ_MODEL = "groq/compound"

SEO_GROQ_MODEL = os.getenv("SEO_GROQ_MODEL", "groq/compound")

# ============================================================
# ROBOT SETTINGS
# ============================================================

ROBOT_INTERVAL_HOURS = 6
ARTICLES_PER_COUNTRY = 5

# كل بغا نهار (ساعات)
JOBS_ROBOT_INTERVAL_HOURS = 24

# ============================================================
# AI SEO / TREND AUTOMATION SETTINGS
# ============================================================

SEO_MIN_SCORE = int(os.getenv("SEO_MIN_SCORE", "78"))
QUALITY_MIN_SCORE = int(os.getenv("QUALITY_MIN_SCORE", "82"))
TREND_MIN_SCORE = int(os.getenv("TREND_MIN_SCORE", "45"))
SEO_RESEARCH_ENABLED = os.getenv("SEO_RESEARCH_ENABLED", "true").lower() == "true"
TRENDING_LIMIT = int(os.getenv("TRENDING_LIMIT", "30"))
MAX_RESEARCH_ITEMS = int(os.getenv("MAX_RESEARCH_ITEMS", "8"))

# ============================================================
# JOB SITES (مقسمين على 4 فئات)
# ============================================================

JOB_SITES = {
    "private_ma": {
        "label": "الخدمة فالمغرب (القطاع الخاص)",
        "sites": [
            ("LinkedIn", "https://www.linkedin.com/jobs/jobs-in-morocco/"),
            ("ReKrute", "https://www.rekrute.com/"),
            ("Emploitic", "https://emploitic.com/"),
            ("Dreamjob", "https://www.dreamjob.ma/"),
            ("Careerlink", "https://careerlink.ma/"),
        ],
    },
    "public_ma": {
        "label": "الوظائف العمومية (المغرب)",
        "sites": [
            ("Emploi Public", "https://www.emploi-public.ma/"),
            ("ANAPEC", "https://www.anapec.org/"),
        ],
    },
    "gulf": {
        "label": "الخدمة فالخليج",
        "sites": [
            ("Bayt", "https://www.bayt.com/"),
            ("Naukrigulf", "https://www.naukrigulf.com/"),
        ],
    },
    "abroad": {
        "label": "الخدمة فالخارج (أوروبا / كندا)",
        "sites": [
            ("ANAPEC Infitah", "https://skills.ma/infitah/"),
            ("EURES", "https://eures.europa.eu/"),
            ("France Travail", "https://candidat.francetravail.fr/"),
            ("Guichet-Emplois Canada", "https://www.guichetemplois.gc.ca/"),
        ],
    },
}

# ============================================================
# COUNTRIES
# ============================================================

COUNTRIES = {
    "ma": {"name": "Morocco", "native": "المغرب", "region": "africa", "google_news": "MA", "languages": ["ar", "fr", "en"]},
    "dz": {"name": "Algeria", "native": "الجزائر", "region": "africa", "google_news": "DZ", "languages": ["ar", "fr", "en"]},
    "tn": {"name": "Tunisia", "native": "تونس", "region": "africa", "google_news": "TN", "languages": ["ar", "fr", "en"]},
    "fr": {"name": "France", "native": "France", "region": "eu", "google_news": "FR", "languages": ["fr", "en", "ar"]},
    "es": {"name": "Spain", "native": "España", "region": "eu", "google_news": "ES", "languages": ["es", "en", "fr"]},
    "gb": {"name": "United Kingdom", "native": "United Kingdom", "region": "eu", "google_news": "GB", "languages": ["en", "fr", "es"]},
    "de": {"name": "Germany", "native": "Deutschland", "region": "eu", "google_news": "DE", "languages": ["de", "en", "fr"]},
    "it": {"name": "Italy", "native": "Italia", "region": "eu", "google_news": "IT", "languages": ["it", "en", "fr"]},
    "us": {"name": "United States", "native": "United States", "region": "usa", "google_news": "US", "languages": ["en", "es", "fr"]},
    "ca": {"name": "Canada", "native": "Canada", "region": "usa", "google_news": "CA", "languages": ["en", "fr"]},
    "br": {"name": "Brazil", "native": "Brasil", "region": "global", "google_news": "BR", "languages": ["pt", "en", "es"]},
    "in": {"name": "India", "native": "India", "region": "global", "google_news": "IN", "languages": ["en", "hi"]},
    "sa": {"name": "Saudi Arabia", "native": "السعودية", "region": "khalij", "google_news": "SA", "languages": ["ar", "en", "fr"]},
    "ae": {"name": "United Arab Emirates", "native": "الإمارات", "region": "khalij", "google_news": "AE", "languages": ["ar", "en", "fr"]},
    "qa": {"name": "Qatar", "native": "قطر", "region": "khalij", "google_news": "QA", "languages": ["ar", "en", "fr"]},
    "eg": {"name": "Egypt", "native": "مصر", "region": "africa", "google_news": "EG", "languages": ["ar", "en", "fr"]},
    "tr": {"name": "Turkey", "native": "Türkiye", "region": "global", "google_news": "TR", "languages": ["tr", "en", "ar"]},
    "jp": {"name": "Japan", "native": "日本", "region": "global", "google_news": "JP", "languages": ["ja", "en"]},
    "au": {"name": "Australia", "native": "Australia", "region": "global", "google_news": "AU", "languages": ["en"]},
}

# ============================================================
# LANGUAGES
# ============================================================

LANGUAGES = {
    "ar": "العربية",
    "fr": "Français",
    "en": "English",
    "es": "Español",
}
