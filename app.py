from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
from database import db, execute_query, init_db
from datetime import datetime, timedelta
import os
import uuid

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "community-dev-secret")


AUDIO_FOLDER = os.path.join(app.root_path, 'static', 'audio')
os.makedirs(AUDIO_FOLDER, exist_ok=True)


# ✅ NEW: Brute-force protection
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["10000 per day", "1000 per hour"],
    storage_uri="memory://"
)

# Security Decorator
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please login first.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

# =============================================
# ROUTES
# =============================================

@app.route("/")
def home():
    if session.get("user_id"):
        return redirect(url_for("about")) # Or a dashboard
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute") # 👈 ADD THIS LINE
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        
        conn = db()
        c = conn.cursor()
        user = execute_query(c, "SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["full_name"] = user["full_name"]
            session["role"] = user["role"]
            flash(f"Welcome, {user['full_name']}!", "success")
            
            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("about"))
            
        flash("Invalid username or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for("login"))

# =============================================
# STAFF PAGES
# =============================================

@app.route("/about")
@login_required
def about():
    """The Vision & Mission page for staff."""
    return render_template("about.html")



@app.route("/privacy")
@login_required
def privacy():
    return render_template("privacy.html")

@app.route("/chat", methods=["GET", "POST"])
@login_required
def chat():
    conn = db()
    c = conn.cursor()
    
    if request.method == "POST":
        content = request.form.get("content", "").strip()
        
        # Handle Text Message
        if content:
            execute_query(c, """
                INSERT INTO messages (user_id, content)
                VALUES (?, ?)
            """, (session["user_id"], content))
            conn.commit()
            return redirect(url_for("chat"))
            
        # Handle Audio Upload
        audio_data = request.files.get("audio_data")
        if audio_data:
            # Generate a unique filename
            filename = f"voice_{session['user_id']}_{uuid.uuid4().hex}.webm"
            filepath = os.path.join(AUDIO_FOLDER, filename)
            audio_data.save(filepath)
            
            # Save path to database (relative to static folder)
            db_path = f"audio/{filename}"
            execute_query(c, """
                INSERT INTO voice_notes (user_id, file_path)
                VALUES (?, ?)
            """, (session["user_id"], db_path))
            conn.commit()
            return redirect(url_for("chat"))
    
    # Fetch Text Messages
    messages = execute_query(c, """
        SELECT m.*, u.full_name, u.role 
        FROM messages m 
        JOIN users u ON u.id = m.user_id 
    """).fetchall()
    
    # Fetch Voice Notes
    voice_notes = execute_query(c, """
        SELECT v.*, u.full_name, u.role 
        FROM voice_notes v 
        JOIN users u ON u.id = v.user_id 
    """).fetchall()
    
    # Combine them into a single timeline and sort by date
    timeline = []
    
    # Helper function to format time perfectly on both SQLite and Postgres
    def format_dt(raw_dt):
        if not raw_dt:
            return ""
        
        # If it's a string (SQLite), convert it to datetime
        if isinstance(raw_dt, str):
            try:
                # Handle SQLite format (e.g., "2026-11-08 12:57:00")
                # Some SQLite versions include milliseconds, so we slice to 19 chars
                raw_dt = datetime.strptime(raw_dt[:19], "%Y-%m-%d %H:%M:%S")
            except Exception as e:
                return raw_dt # Return the raw string if parsing fails
                
        # Add 2 hours for Namibia time
        local_dt = raw_dt + timedelta(hours=2)
        return local_dt.strftime("%H:%M | %d %b %Y")

    for m in messages:
        m["display_time"] = format_dt(m.get("created_at"))
        timeline.append({"type": "text", "data": m})
        
    for v in voice_notes:
        v["display_time"] = format_dt(v.get("created_at"))
        timeline.append({"type": "voice", "data": v})


    # Sort by created_at
    timeline.sort(key=lambda x: x["data"]["created_at"])
    
    conn.close()
    
    return render_template("chat.html", timeline=timeline)


@app.route("/chat/clear", methods=["POST"])
@login_required
def clear_chat():
    # Only allow admin to clear the chat
    if session.get("role") != "admin":
        flash("Access denied. Only admins can clear the chat.", "danger")
        return redirect(url_for("chat"))
        
    conn = db()
    c = conn.cursor()
    
    try:
        # Delete all text messages
        execute_query(c, "DELETE FROM messages")
        # Delete all voice notes (and we should delete the actual files from the folder too)
        execute_query(c, "DELETE FROM voice_notes")
        conn.commit()
        
        # Optional: Delete the audio files from the static folder
        for filename in os.listdir(AUDIO_FOLDER):
            file_path = os.path.join(AUDIO_FOLDER, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)
                
        flash("Community chat has been cleared successfully.", "success")
    except Exception as e:
        flash(f"Error clearing chat: {e}", "danger")
    finally:
        conn.close()
        
    return redirect(url_for("chat"))

@app.route("/chat/delete/<string:msg_type>/<int:msg_id>", methods=["POST"])
@login_required
def delete_single_message(msg_type, msg_id):
    conn = db()
    c = conn.cursor()
    
    # Determine which table to use
    table = "messages" if msg_type == "text" else "voice_notes"
    
    # Fetch the message to check who owns it
    message = execute_query(c, f"SELECT * FROM {table} WHERE id = ?", (msg_id,)).fetchone()
    
    if not message:
        flash("Message not found.", "danger")
        conn.close()
        return redirect(url_for("chat"))
        
    # Security Check: Only Admin OR the person who sent it can delete it
    if session.get("role") != "admin" and message["user_id"] != session.get("user_id"):
        flash("You can only delete your own messages.", "danger")
        conn.close()
        return redirect(url_for("chat"))
        
    try:
        # If it's a voice note, delete the physical file first
        if msg_type == "voice":
            file_path = os.path.join(app.root_path, 'static', message["file_path"])
            if os.path.exists(file_path):
                os.remove(file_path)
                
        # Delete the record from the database
        execute_query(c, f"DELETE FROM {table} WHERE id = ?", (msg_id,))
        conn.commit()
        flash("Message deleted.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error deleting message: {e}", "danger")
    finally:
        conn.close()
        
    return redirect(url_for("chat"))

# =============================================
# ADMIN PAGES
# =============================================

@app.route("/admin")
@login_required
def admin_dashboard():
    if session.get("role") != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("about"))
        
    conn = db()
    c = conn.cursor()
    users = execute_query(c, "SELECT * FROM users ORDER BY created_at DESC").fetchall()
    conn.close()
    
    return render_template("admin.html", users=users)

@app.route("/admin/create-user", methods=["POST"])
@login_required
def create_user():
    if session.get("role") != "admin":
        return redirect(url_for("about"))
        
    full_name = request.form.get("full_name")
    phone = request.form.get("phone")
    location = request.form.get("location")
    username = request.form.get("username")
    password = request.form.get("password")
    
    conn = db()
    c = conn.cursor()
    
    try:
        execute_query(c, """
            INSERT INTO users (full_name, phone, location, username, password_hash, role)
            VALUES (?, ?, ?, ?, ?, 'staff')
        """, (full_name, phone, location, username, generate_password_hash(password)))
        conn.commit()
        flash(f"Station owner '{full_name}' registered successfully!", "success")
    except Exception as e:
        flash(f"Error: Username might already exist. ({e})", "danger")
    finally:
        conn.close()
        
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/edit-user/<int:user_id>", methods=["GET", "POST"])
@login_required
def edit_user(user_id):
    if session.get("role") != "admin":
        return redirect(url_for("about"))
        
    conn = db()
    c = conn.cursor()
    user = execute_query(c, "SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    
    if not user:
        flash("User not found.", "danger")
        conn.close()
        return redirect(url_for("admin_dashboard"))
        
    if request.method == "POST":
        full_name = request.form.get("full_name")
        phone = request.form.get("phone")
        location = request.form.get("location")
        
        execute_query(c, """
            UPDATE users SET full_name = ?, phone = ?, location = ? 
            WHERE id = ?
        """, (full_name, phone, location, user_id))
        conn.commit()
        conn.close()
        
        flash("Station details updated successfully!", "success")
        return redirect(url_for("admin_dashboard"))
        
    conn.close()
    return render_template("edit_user.html", user=user)

@app.route("/admin/delete-user/<int:user_id>", methods=["POST"])
@login_required
def delete_user(user_id):
    if session.get("role") != "admin":
        return redirect(url_for("about"))
        
    # Prevent admin from deleting themselves
    if user_id == session.get("user_id"):
        flash("You cannot delete your own admin account!", "danger")
        return redirect(url_for("admin_dashboard"))
        
    conn = db()
    c = conn.cursor()
    execute_query(c, "DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    
    flash("Station account deleted.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/reset-password/<int:user_id>", methods=["POST"])
@login_required
def admin_reset_password(user_id):
    if session.get("role") != "admin":
        return redirect(url_for("about"))
        
    new_password = request.form.get("new_password", "").strip()
    
    if len(new_password) < 6:
        flash("Password must be at least 6 characters.", "danger")
        return redirect(url_for("admin_dashboard"))
        
    conn = db()
    c = conn.cursor()
    
    # Update the password
    execute_query(c, """
        UPDATE users SET password_hash = ? WHERE id = ?
    """, (generate_password_hash(new_password), user_id))
    conn.commit()
    conn.close()
    
    flash(f"Password successfully reset!", "success")
    return redirect(url_for("admin_dashboard"))

# =============================================
# STARTUP
# =============================================

with app.app_context():
    try:
        init_db()
        # Create default admin if it doesn't exist
        conn = db()
        c = conn.cursor()
        execute_query(c, "SELECT * FROM users WHERE username = 'KaxHafeni'")

        if not c.fetchone():
            execute_query(c, """
                INSERT INTO users (full_name, phone, location, username, password_hash, role)
                VALUES ('Mr Shitaku Hafeni', '0818412379', 'Okahandja Park', 'KaxHafeni', ?, 'admin')
            """, (generate_password_hash("KaxHafeni004"),))
            conn.commit()
        conn.close()
    except Exception as e:
        print(f"Bootstrap error: {e}")

if __name__ == "__main__":
    app.run(debug=True, port=5501)

