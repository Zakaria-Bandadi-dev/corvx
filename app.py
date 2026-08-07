import os, flask, google.generativeai as genai, psycopg2, feedparser
from flask import Flask, render_template_string, request
from apscheduler.schedulers.background import BackgroundScheduler
import time, urllib.parse, random
from datetime import datetime

app = Flask(__name__)

# ================== 1. CONFIG MN RAILWAY ==================
API_KEYS = [
    os.getenv("GEMINI_KEY1"), os.getenv("GEMINI_KEY2"), os.getenv("GEMINI_KEY3"),
    os.getenv("GEMINI_KEY4"), os.getenv("GEMINI_KEY5")
]
API_KEYS = [key for key in API_KEYS if key]
current_key_index = 0

DB_URL = os.getenv("DATABASE_URL")
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

# ================== 2. ROTATOR DYAL GEMINI ==================
def generate_with_fallback(prompt):
    global current_key_index
    if not API_KEYS: return None
    for i in range(len(API_KEYS)):
        try:
            genai.configure(api_key=API_KEYS[current_key_index])
            model = genai.GenerativeModel('gemini-1.5-flash-latest')
            print(f"-> Using Key #{current_key_index + 1}")
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"Key #{current_key_index + 1} failed. Switching... Error: {e}")
            current_key_index = (current_key_index + 1) % len(API_KEYS)
            time.sleep(15)
    return None

# ================== 3. GENERATE IMAGE ==================
def generate_image(prompt_text):
    clean_prompt = urllib.parse.quote(prompt_text + ", photorealistic, 8k, news photo, high detail")
    return f"https://image.pollinations.ai/prompt/{clean_prompt}"

# ================== 4. DATABASE ==================
def init_db():
    if not DB_URL: return
    try:
        conn = psycopg2.connect(DB_URL); cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id SERIAL PRIMARY KEY, region VARCHAR(20), category VARCHAR(50),
                title_ar TEXT, title_fr TEXT, title_en TEXT, title_es TEXT,
                content_ar TEXT, content_fr TEXT, content_en TEXT, content_es TEXT,
                image_url VARCHAR(500), created_at TIMESTAMP DEFAULT NOW()
            );
        """)
        conn.commit(); cur.close(); conn.close()
        print("DB Connected")
    except Exception as e: print(f"DB Error: {e}")
init_db()

# ================== 5. ROBOT ==================
def get_trends_for_region(region):
    geo = {"usa": "US", "eu": "GB", "africa": "ZA", "khalij": "SA", "global": ""}[region]
    url = f"https://trends.google.com/trends/trendingsearches/daily/rss?geo={geo}" if geo else "https://trends.google.com/trends/trendingsearches/daily/rss"
    trends = feedparser.parse(url)
    return [entry.title for entry in trends.entries[:4]]

def run_robot():
    print(f"\n[{datetime.now()}] === Robot Started ===")
    for region in REGIONS.keys():
        print(f"-> Building Region: {region.upper()}")
        topics = get_trends_for_region(region)
        for topic in topics:
            prompt_en = f"You are a senior journalist. Write a unique, 600-word SEO news article about: {topic}. Return JSON: {{'title':'...', 'content':'<p>...</p>', 'img_prompt':'detailed prompt for image', 'cat':'ai'}}"
            res_en = generate_with_fallback(prompt_en)
            if not res_en: continue
            try: data = eval(res_en.replace("```json","").replace("```",""))
            except: continue

            for lang in ['ar','fr','es']:
                lang_name = {"ar":"Arabic", "fr":"French", "es":"Spanish"}[lang]
                prompt_tr = f"Translate this news article to {lang_name}. Keep journalistic and SEO style. Title: {data['title']}\nContent: {data['content']}"
                res_tr = generate_with_fallback(prompt_tr)
                if res_tr:
                    parts = res_tr.split('\n', 1)
                    data[f'title_{lang}'] = parts[0]
                    data[f'content_{lang}'] = parts[1] if len(parts) > 1 else res_tr

            data['img_url'] = generate_image(data['img_prompt'])

            conn = psycopg2.connect(DB_URL); cur = conn.cursor()
            cur.execute("INSERT INTO articles (region,category,title_ar,title_fr,title_en,title_es,content_ar,content_fr,content_en,content_es,image_url) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (region, data['cat'], data.get('title_ar'), data.get('title_fr'), data['title'], data.get('title_es'), data.get('content_ar'), data.get('content_fr'), data['content'], data.get('content_es'), data['img_url']))
            conn.commit(); cur.close(); conn.close()
            print(f"-> Article done: {data['title'][:30]}")
            time.sleep(30)
    print(f"[{datetime.now()}] === Robot Finished ===")

# ================== 6. SCHEDULER 3CHWA2I 6H-18H ==================
def job_wrapper():
    hour = datetime.now().hour
    if hour >= 18: # Ila wsal 6h d l3chiya y7bes
        print("-> It's after 18h. Stopping for today.")
        scheduler.pause_job('random_job')
        return

    run_robot()

    next_minutes = random.choice([21, 33, 45, 12, 18, 27, 39, 51])
    print(f"-> Next run in {next_minutes} minutes")
    scheduler.reschedule_job('random_job', trigger='interval', minutes=next_minutes, jitter=120)

scheduler = BackgroundScheduler()
scheduler.add_job(job_wrapper, 'cron', hour=6, minute=0, id='random_job') # Ybda m3a 6h sbah
scheduler.start()

# ================== 7. FRONTEND ==================
HTML_TEMPLATE = """
<!DOCTYPE html><html lang="{{lang}}" dir="{{ 'rtl' if lang=='ar' else 'ltr' }}"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>corvex.tech - {{page_title}}</title>
<meta name="description" content="Latest AI News, Business, Crypto for {{region_name}} in 4 languages">
{% if ga_id %}<script async src="https://www.googletagmanager.com/gtag/js?id={{ga_id}}"></script><script>window.dataLayer = window.dataLayer || [];function gtag(){dataLayer.push(arguments);}gtag('js', new Date());gtag('config', '{{ga_id}}');</script>{% endif %}
{% if adsense_id %}<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={{adsense_id}}" crossorigin="anonymous"></script>{% endif %}
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700;900&family=Inter:wght@400;700;900&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
<style>
:root{--bg:#0b1120; --card:#111827; --border:#374151; --primary:#3b82f6; --text:#e5e7eb}
body{background:var(--bg); color:var(--text); font-family: 'Inter', 'Tajawal', sans-serif;}
.navbar{background:rgba(17,24,39,0.8); backdrop-filter: blur(10px); border-bottom: 1px solid var(--border);}
.btn-region{border-radius: 50px; border: 1px solid var(--border); margin: 4px; transition: 0.3s;}
.btn-region.active,.btn-region:hover{background: var(--primary); border-color: var(--primary); color: white;}
.card{background: var(--card); border: 1px solid var(--border); border-radius: 16px; overflow: hidden; transition: 0.3s;}
.card:hover{transform: translateY(-8px); box-shadow: 0 10px 20px rgba(59,130,246,0.2);}
.card-img-top{height: 200px; object-fit: cover;}
.whatsapp-btn{background:#25D366; color:white; font-weight: 700;}
.ads-box{margin: 30px auto; text-align: center; background: #111827; padding: 10px; border-radius: 8px;}
.hero{background: linear-gradient(90deg, #3b82f6, #8b5cf6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: 900;}
</style></head><body>

<nav class="navbar sticky-top"><div class="container-fluid">
  <a class="navbar-brand text-white fw-bold fs-3 hero"><i class="fa-solid fa-rocket"></i> corvex.tech</a>
  <div>{% for code,name in languages.items() %}<a href="?region={{region}}&lang={{code}}" class="btn btn-sm btn-outline-light mx-1">{{name}}</a>{% endfor %}</div>
</div></nav>

<div class="container py-5">
  <div class="text-center mb-5">
    <h1 class="display-4 hero">{{page_title}}</h1>
    <p class="lead text-muted">AI-Generated News for {{region_name}} - Updated Every 20min</p>
  </div>

  <div class="text-center mb-5">
    {% for key, names in regions.items() %}
      <a href="?region={{key}}&lang={{lang}}" class="btn btn-outline-light btn-region {% if key==region %}active{% endif %}"><i class="fa-solid fa-globe"></i> {{names[lang]}}</a>
    {% endfor %}
  </div>

  {% if adsense_id %}<div class="ads-box"><ins class="adsbygoogle" style="display:block" data-ad-client="{{adsense_id}}" data-ad-slot="123456" data-ad-format="auto" data-full-width-responsive="true"></ins><script>(adsbygoogle = window.adsbygoogle || []).push({});</script></div>{% endif %}

  <div class="row">{% for art in articles %}
    <div class="col-12 col-md-6 col-lg-3 mb-4"><div class="card h-100">
      <img src="{{art.img}}" class="card-img-top" loading="lazy" alt="{{art.title}}">
      <div class="card-body d-flex flex-column">
        <h5 class="card-title fw-bold">{{art.title}}</h5>
        <p class="card-text flex-grow-1 text-muted">{{art.content|safe}}</p>
        <a href="/article/{{art.id}}?lang={{lang}}" class="btn btn-primary mt-2 w-100">Read More</a>
        <a href="https://wa.me/?text={{art.title | urlencode}}%20-%20{{request.url_root}}article/{{art.id}}" target="_blank" class="btn whatsapp-btn mt-2 w-100"><i class="fa-brands fa-whatsapp"></i> Share</a>
      </div>
    </div></div>
  {% else %}
    <div class="col-12 text-center"><p>Robot is building articles... Check back in 10 minutes.</p></div>
  {% endfor %}</div>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body></html>
"""

# ================== 8. SITEMAP + ARTICLE PAGE ==================
@app.route("/sitemap.xml")
def sitemap():
    if not DB_URL: return "DB not connected", 500
    conn = psycopg2.connect(DB_URL); cur = conn.cursor()
    cur.execute("SELECT id, created_at FROM articles ORDER BY created_at DESC LIMIT 500")
    articles = cur.fetchall()
    conn.close()
    base_url = request.url_root
    sitemap_xml = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    sitemap_xml += f'<url><loc>{base_url}</loc><changefreq>hourly</changefreq><priority>1.0</priority></url>'
    for art in articles:
        art_id, created_at = art
        date = created_at.strftime("%Y-%m-%d")
        sitemap_xml += f'<url><loc>{base_url}article/{art_id}</loc><lastmod>{date}</lastmod><changefreq>never</changefreq><priority>0.9</priority></url>'
    sitemap_xml += '</urlset>'
    return sitemap_xml, 200, {'Content-Type': 'application/xml'}

@app.route("/article/<int:art_id>")
def article_page(art_id):
    if not DB_URL: return "DB not connected", 500
    lang = request.args.get('lang', 'en')
    conn = psycopg2.connect(DB_URL); cur = conn.cursor()
    query = "SELECT %s, %s, image_url, created_at FROM articles WHERE id=%%s" % (f'title_{lang}', f'content_{lang}')
    cur.execute(query, (art_id,))
    data = cur.fetchone()
    conn.close()
    if not data: return "Article not found", 404
    title, content, img, date = data
    article_html = f"""<!DOCTYPE html><html lang="{lang}"><head><title>corvex.tech - {title}</title><meta name="description" content="{content[:150]}"><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><style>body{{background:#0b1120; color:#e5e7eb}}</style></head><body><div class="container py-5"><a href="/" class="btn btn-outline-light mb-4"><i class="fa-solid fa-arrow-left"></i> Back</a><img src="{img}" class="img-fluid rounded mb-4"><h1 class="fw-900">{title}</h1><p class="text-muted">{date.strftime('%B %d, %Y')}</p><div class="fs-5">{content}</div></div></body></html>"""
    return article_html

@app.route("/")
def home():
    if not DB_URL: return "Please set DATABASE_URL in Railway Variables"
    region = request.args.get('region', 'global')
    lang = request.args.get('lang', 'en')
    conn = psycopg2.connect(DB_URL); cur = conn.cursor()
    query = "SELECT id, %s, %s, image_url FROM articles WHERE region=%%s ORDER BY created_at DESC LIMIT 20" % (f'title_{lang}', f'content_{lang}')
    cur.execute(query, (region,))
    data = cur.fetchall()
    articles = [{'id':d[0], 'title':d[1], 'content':d[2][:350]+"...", 'img':d[3]} for d in data]
    page_title = REGIONS[region][lang]
    return render_template_string(HTML_TEMPLATE, articles=articles, regions=REGIONS, languages=LANGUAGES, region=region, lang=lang, page_title=page_title, region_name=REGIONS[region]['en'], ga_id=GA_ID, adsense_id=ADSENSE_ID)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
