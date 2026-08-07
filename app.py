import os, flask, google.generativeai as genai, feedparser, json, sqlite3, random, time, urllib.parse
from flask import Flask, render_template_string, request
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

app = Flask(__name__)

# ================== 1. CONFIGURATION ==================
# Récupération des clés API Gemini (Rotation)
API_KEYS = [os.getenv(f"GEMINI_KEY{i}") for i in range(1, 6)]
API_KEYS = [k for k in API_KEYS if k]
current_key_index = 0

DB_URL = os.getenv("DATABASE_URL") # Railway Postgres URL
GA_ID = os.getenv("GA_ID", "")
ADSENSE_ID = os.getenv("ADSENSE_ID", "")

REGIONS = {
    "global": {"ar": "العالم", "fr": "Monde", "en": "Global", "es": "Mundo"},
    "usa": {"ar": "أمريكا", "fr": "USA", "en": "USA", "es": "EE.UU"},
    "eu": {"ar": "أوروبا", "fr": "Europe", "en": "Europe", "es": "Europa"},
    "africa": {"ar": "إفريقيا", "fr": "Afrique", "en": "Africa", "es": "África"},
    "khalij": {"ar": "الخليج", "fr": "Golfe", "en": "Gulf", "es": "Golfo"}
}
LANGUAGES = {'ar': 'العربية', 'fr': 'FR', 'en': 'EN', 'es': 'ES'}

# ================== 2. DATABASE HELPER ==================
def get_db_connection():
    if DB_URL:
        import psycopg # bdel mn psycopg2
        return psycopg.connect(DB_URL) # psycopg3 kay9bl URL nichan
    else:
        # Fallback SQLite
        conn = sqlite3.connect('corvex.db')
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    # Utilisation de TEXT pour la compatibilité SQLite/Postgres simplifiée
    query = """
        CREATE TABLE IF NOT EXISTS articles (
            id SERIAL PRIMARY KEY if not exists, 
            region TEXT, category TEXT,
            title_ar TEXT, title_fr TEXT, title_en TEXT, title_es TEXT,
            content_ar TEXT, content_fr TEXT, content_en TEXT, content_es TEXT,
            image_url TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """
    # Note: SERIAL PRIMARY KEY est spécifique à Postgres. Pour SQLite on adapte:
    if not DB_URL:
        query = """
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT, region TEXT, category TEXT,
                title_ar TEXT, title_fr TEXT, title_en TEXT, title_es TEXT,
                content_ar TEXT, content_fr TEXT, content_en TEXT, content_es TEXT,
                image_url TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """
    cur.execute(query)
    conn.commit()
    conn.close()
    print("-> Database Ready")

# ================== 3. AI & IMAGE GENERATION ==================
def generate_with_fallback(prompt):
    global current_key_index
    if not API_KEYS:
        print("!! No API Keys found. Returning dummy data.")
        return None
        
    for _ in range(len(API_KEYS)):
        try:
            genai.configure(api_key=API_KEYS[current_key_index])
            model = genai.GenerativeModel('gemini-1.5-flash-latest')
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"!! Key #{current_key_index + 1} failed: {e}")
            current_key_index = (current_key_index + 1) % len(API_KEYS)
            time.sleep(5)
    return None

def generate_image(prompt_text):
    clean_prompt = urllib.parse.quote(prompt_text + ", photorealistic, 8k, news photo")
    return f"https://image.pollinations.ai/prompt/{clean_prompt}"

# ================== 4. ROBOT LOGIC ==================
def get_trends(region):
    geo_map = {"usa": "US", "eu": "GB", "africa": "ZA", "khalij": "SA", "global": ""}
    geo = geo_map.get(region, "")
    url = f"https://trends.google.com/trends/trendingsearches/daily?geo={geo}" if geo else "https://trends.google.com/trends/trendingsearches/daily"
    feed = feedparser.parse(url)
    titles = [e.title for e in feed.entries[:3]]
    return titles if titles else ["AI Revolution", "Future of Tech"] # Fallback

def run_robot():
    print(f"[{datetime.now()}] Robot Started")
    for region in REGIONS.keys():
        topics = get_trends(region)
        for topic in topics:
            prompt = f"Write a news article about {topic}. Return ONLY JSON: {{'title':'...', 'content':'...', 'img_prompt':'...', 'cat':'tech'}}"
            raw_res = generate_with_fallback(prompt)
            if not raw_res: continue
            
            try:
                # Nettoyage du JSON (Gemini entoure souvent de ```json)
                clean_json = raw_res.replace("```json","").replace("```","").strip()
                data = json.loads(clean_json)
            except: continue

            # Traductions
            for lang in ['ar','fr','es']:
                t_prompt = f"Translate to {lang}: {data['title']}\n\n{data['content']}"
                tr_res = generate_with_fallback(t_prompt)
                if tr_res:
                    parts = tr_res.split('\n', 1)
                    data[f'title_{lang}'] = parts[0]
                    data[f'content_{lang}'] = parts[1] if len(parts) > 1 else tr_res

            img_url = generate_image(data.get('img_prompt', topic))
            
            # Sauvegarde DB
            conn = get_db_connection()
            cur = conn.cursor()
            placeholder = "?" if not DB_URL else "%s"
            cols = "region, category, title_ar, title_fr, title_en, title_es, content_ar, content_fr, content_en, content_es, image_url"
            vals = (region, data.get('cat'), data.get('title_ar'), data.get('title_fr'), data['title'], data.get('title_es'),
                    data.get('content_ar'), data.get('content_fr'), data['content'], data.get('content_es'), img_url)
            cur.execute(f"INSERT INTO articles ({cols}) VALUES ({','.join([placeholder]*11)})", vals)
            conn.commit()
            conn.close()
            print(f"-> Saved: {data['title'][:30]}")
    print(f"[{datetime.now()}] Robot Finished")

# ================== 5. ROUTES & FRONTEND ==================
@app.route("/")
def home():
    region = request.args.get('region', 'global')
    lang = request.args.get('lang', 'en')
    
    conn = get_db_connection()
    cur = conn.cursor()
    # Protection contre injection SQL pour les noms de colonnes
    t_col = f"title_{lang}" if lang in LANGUAGES else "title_en"
    c_col = f"content_{lang}" if lang in LANGUAGES else "content_en"
    
    placeholder = "?" if not DB_URL else "%s"
    query = f"SELECT id, {t_col}, {c_col}, image_url FROM articles WHERE region={placeholder} ORDER BY created_at DESC LIMIT 20"
    cur.execute(query, (region,))
    rows = cur.fetchall()
    conn.close()
    
    articles = []
    for r in rows:
        articles.append({'id':r[0], 'title':r[1], 'content':(r[2] or "")[:200]+"...", 'img':r[3]})
        
    return render_template_string(HTML_TEMPLATE, articles=articles, regions=REGIONS, languages=LANGUAGES, region=region, lang=lang, page_title=REGIONS[region][lang])

HTML_TEMPLATE = """
<!DOCTYPE html><html lang="{{lang}}" dir="{{ 'rtl' if lang=='ar' else 'ltr' }}">
<head>
    <meta charset="UTF-8"><title>corvex.tech - {{page_title}}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background: #0b1120; color: #e5e7eb; font-family: sans-serif; }
        .card { background: #111827; border: 1px solid #374151; border-radius: 12px; margin-bottom: 20px; }
        .hero { background: linear-gradient(90deg, #3b82f6, #8b5cf6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: bold; }
    </style>
</head>
<body>
    <nav class="navbar border-bottom border-secondary p-3"><div class="container"><h2 class="hero">corvex.tech</h2></div></nav>
    <div class="container py-5">
        <div class="text-center mb-4">
            {% for k, v in regions.items() %}
            <a href="?region={{k}}&lang={{lang}}" class="btn btn-outline-primary m-1 {% if k==region %}active{% endif %}">{{v[lang]}}</a>
            {% endfor %}
        </div>
        <div class="row">
            {% for art in articles %}
            <div class="col-md-4">
                <div class="card h-100">
                    <img src="{{art.img}}" class="card-img-top">
                    <div class="card-body">
                        <h5>{{art.title}}</h5>
                        <p class="small text-muted">{{art.content|safe}}</p>
                    </div>
                </div>
            </div>
            {% else %}
            <div class="col-12 text-center">Aucun article trouvé. Le robot doit d'abord générer du contenu.</div>
            {% endfor %}
        </div>
    </div>
</body></html>
"""

if __name__ == "__main__":
    init_db()
    # Lancement du scheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_robot, 'interval', hours=6)
    scheduler.start()
    app.run(host="0.0.0.0", port=5000)
