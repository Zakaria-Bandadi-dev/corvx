import os

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
# SETTINGS
# ============================================================

# llama-3.3-70b-versatile was deprecated by Groq (shutdown 2026-08-16).
# openai/gpt-oss-120b is Groq's recommended free-tier replacement:
# same rate-limit/free-tier structure, no billing required, and it's
# actually cheaper per-token than the old llama model if you ever
# upgrade to a paid plan.
GROQ_MODEL = "openai/gpt-oss-120b"

ROBOT_INTERVAL_HOURS = 6

# ============================================================
# AI SEO / TREND AUTOMATION SETTINGS
# ============================================================
SEO_GROQ_MODEL = os.getenv("SEO_GROQ_MODEL", "groq/compound")
SEO_MIN_SCORE = int(os.getenv("SEO_MIN_SCORE", "78"))
QUALITY_MIN_SCORE = int(os.getenv("QUALITY_MIN_SCORE", "82"))
TREND_MIN_SCORE = int(os.getenv("TREND_MIN_SCORE", "45"))
SEO_RESEARCH_ENABLED = os.getenv("SEO_RESEARCH_ENABLED", "true").lower() == "true"
TRENDING_LIMIT = int(os.getenv("TRENDING_LIMIT", "30"))
MAX_RESEARCH_ITEMS = int(os.getenv("MAX_RESEARCH_ITEMS", "8"))

# Number of articles per country when robot runs
ARTICLES_PER_COUNTRY = 5

# ============================================================
# JOBS ROBOT SETTINGS
# ============================================================

# groq/compound: عندو built-in tools (web_search + visit_website)
# باش يدخل بنفسه للمواقع ديال الخدمة ويقلب على العروض الجداد.
# (groq/compound is NOT deprecated, keep as-is)
JOBS_GROQ_MODEL = "groq/compound"

# كل بغا نهار (ساعات)
JOBS_ROBOT_INTERVAL_HOURS = 24
