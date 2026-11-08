import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# 👇 PASTE YOUR EXTERNAL DATABASE URL HERE (The one ending in /rab_main_db)
DATABASE_URL = "postgresql://rab_main_db_user:hNYrV6OfYmxNDw5ZvQdNZe4d3d1sGbqy@dpg-dbne3m0u01pc73cgn5rg-a.virginia-postgres.render.com/rab_main_db"

def create_community_db():
    print("Connecting to Postgres...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()

    try:
        cursor.execute("CREATE DATABASE community_db;")
        print("✅ Successfully created 'community_db'!")
    except psycopg2.errors.DuplicateDatabase:
        print("ℹ️ 'community_db' already exists.")
    except Exception as e:
        print(f"❌ Error creating community_db: {e}")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    create_community_db()