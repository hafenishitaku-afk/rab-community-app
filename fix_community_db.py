import sqlite3

conn = sqlite3.connect("community.db")
c = conn.cursor()

try:
    # Check if columns exist
    c.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in c.fetchall()]
    
    # ✅ Step 1: Add columns WITHOUT default values (SQLite requirement)
    if "last_active" not in columns:
        c.execute("ALTER TABLE users ADD COLUMN last_active TEXT")
        print("✅ Added last_active column")
        
    if "last_read_chat" not in columns:
        c.execute("ALTER TABLE users ADD COLUMN last_read_chat TEXT")
        print("✅ Added last_read_chat column")

    # ✅ Step 2: Update existing rows to have the current time
    c.execute("UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE last_active IS NULL")
    c.execute("UPDATE users SET last_read_chat = CURRENT_TIMESTAMP WHERE last_read_chat IS NULL")
    
    conn.commit()
    print("🎉 Local database fixed successfully!")
    
except Exception as e:
    print(f"❌ Error: {e}")
finally:
    conn.close()