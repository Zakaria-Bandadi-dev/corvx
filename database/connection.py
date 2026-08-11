import psycopg

from config.settings import DATABASE_URL


def get_db_connection():
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is missing in Railway Variables."
        )
    return psycopg.connect(DATABASE_URL)
