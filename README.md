# Corvex News

هادي نفس الكود ديال Corvex News، غير مقسم على بلاصة ملف واحد كبير، بحيث
كل جزء ولا صفحة عندها الملف ديالها. **ماتبدلاتش ولا خاصية** — غير تنظيم.

## بنية المشروع

```
corvex_news/
├── app.py                     # نقطة الدخول (Flask app factory + init DB + scheduler)
├── scheduler.py                # إعداد APScheduler (robot الأخبار + robot الخدمة)
├── state.py                    # الحالة المشتركة (robot_status, locks, key rotation)
│
├── config/
│   └── settings.py             # كل متغيرات البيئة + COUNTRIES + LANGUAGES + JOB_SITES
│
├── database/
│   ├── connection.py           # الاتصال بـ PostgreSQL
│   ├── schema.py                # init_db / init_jobs_db
│   ├── articles_repo.py         # كل queries ديال جدول articles
│   └── jobs_repo.py             # كل queries ديال جدول job_offers
│
├── services/
│   ├── groq_client.py           # كل نداءات Groq (news / jobs / compound)
│   ├── news_engine.py           # RSS + Google Trends + SEO analysis + توليد المقالات
│   ├── news_robot.py            # process_country + run_robot
│   ├── jobs_robot.py            # process_job_category + run_jobs_robot
│   ├── translation.py           # الترجمة (Groq + deep-translator fallback)
│   ├── geo.py                   # كشف البلد واللغة ديال الزائر
│   └── images.py                # توليد صورة المقال (Pollinations)
│
├── routes/
│   ├── news_routes.py           # / , /article/<id> , /set-country , /set-language , /ads.txt
│   ├── jobs_routes.py           # /jobs , /jobs-status , /run-jobs-robot
│   └── system_routes.py         # /robots.txt , /sitemap.xml , /seo-status , /robot-status ,
│                                 # /run-robot , /fix-translations , /health
│
├── templates/
│   ├── home.html                # الصفحة الرئيسية
│   ├── article.html             # صفحة المقال
│   └── jobs.html                # صفحة عروض الخدمة
│
├── static/
│   └── css/
│       └── base.css             # كل الـ CSS (كان مكتوب inline فـ Python)
│
└── requirements.txt
```

## ملاحظة مهمة

خاصك تزيد ملف `static/logo.png` (اللوغو ديالك) باش يخدم `favicon` فكل الصفحات،
بحال ما كان فالكود الأصلي (`url_for('static', filename='logo.png')`).

## تشغيل محلي

```bash
pip install -r requirements.txt
export DATABASE_URL=postgres://...
export GROQ_API_KEY1=...
python app.py
```
