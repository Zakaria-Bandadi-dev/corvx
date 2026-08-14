from database.connection import get_db_connection

def init_db():
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id SERIAL PRIMARY KEY,
                country TEXT,
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
                original_title TEXT,
                seo_title TEXT,
                meta_description TEXT,
                slug TEXT,
                primary_keyword TEXT,
                secondary_keywords TEXT,
                search_intent TEXT,
                trend_score INTEGER DEFAULT 0,
                seo_score INTEGER DEFAULT 0,
                quality_score INTEGER DEFAULT 0,
                seo_reason TEXT,
                faq_json TEXT,
                schema_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        columns = {
            "country": "TEXT",
            "region": "TEXT",
            "category": "TEXT",
            "title_ar": "TEXT",
            "title_fr": "TEXT",
            "title_en": "TEXT",
            "title_es": "TEXT",
            "content_ar": "TEXT",
            "content_fr": "TEXT",
            "content_en": "TEXT",
            "content_es": "TEXT",
            "image_url": "TEXT",
            "source_url": "TEXT",
            "source_name": "TEXT",
            "original_title": "TEXT",
            "seo_title": "TEXT",
            "meta_description": "TEXT",
            "slug": "TEXT",
            "primary_keyword": "TEXT",
            "secondary_keywords": "TEXT",
            "search_intent": "TEXT",
            "trend_score": "INTEGER DEFAULT 0",
            "seo_score": "INTEGER DEFAULT 0",
            "quality_score": "INTEGER DEFAULT 0",
            "seo_reason": "TEXT",
            "faq_json": "TEXT",
            "schema_json": "TEXT"
        }

        for column, column_type in columns.items():
            cur.execute(
                f"""
                ALTER TABLE articles
                ADD COLUMN IF NOT EXISTS {column} {column_type};
                """
            )

        cur.execute("CREATE INDEX IF NOT EXISTS idx_articles_country ON articles(country);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_articles_created_at ON articles(created_at DESC);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_articles_region ON articles(region);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_articles_primary_keyword ON articles(primary_keyword);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_articles_trend_score ON articles(trend_score DESC);")

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

        for column, column_type in orientation_columns.items():
            cur.execute(
                f"ALTER TABLE orientation_announcements ADD COLUMN IF NOT EXISTS {column} {column_type};"
            )

        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_orientation_title_source_url ON orientation_announcements(title, source_url);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_orientation_category ON orientation_announcements(category);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_orientation_deadline ON orientation_announcements(deadline);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_orientation_academic_level ON orientation_announcements(academic_level);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_orientation_source_url ON orientation_announcements(source_url);")

        conn.commit()
        cur.close()
        conn.close()
        print("-> Database Ready")

    except Exception as e:
        print(f"!! Database initialization failed: {e}")

def init_jobs_db():
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS job_offers (
                id SERIAL PRIMARY KEY,
                category TEXT,
                source_site TEXT,
                source_url TEXT,
                title_ar TEXT,
                company_ar TEXT,
                description_ar TEXT,
                conditions_ar TEXT,
                documents_ar TEXT,
                how_to_apply_ar TEXT,
                deadline TEXT,
                offer_hash TEXT UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        columns = {
            "category": "TEXT",
            "source_site": "TEXT",
            "source_url": "TEXT",
            "title_ar": "TEXT",
            "company_ar": "TEXT",
            "description_ar": "TEXT",
            "conditions_ar": "TEXT",
            "documents_ar": "TEXT",
            "how_to_apply_ar": "TEXT",
            "deadline": "TEXT",
            "offer_hash": "TEXT",
        }

        for column, column_type in columns.items():
            cur.execute(
                f"""
                ALTER TABLE job_offers
                ADD COLUMN IF NOT EXISTS {column} {column_type};
                """
            )

        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_job_offers_hash ON job_offers(offer_hash);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_job_offers_category ON job_offers(category);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_job_offers_created_at ON job_offers(created_at DESC);")

        conn.commit()
        cur.close()
        conn.close()
        print("-> Jobs Database Ready")

    except Exception as e:
        print(f"!! Jobs database initialization failed: {e}")
