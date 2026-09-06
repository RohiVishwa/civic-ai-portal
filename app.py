import os
import sqlite3
import time
import random
import base64
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, session, url_for, jsonify

app = Flask(__name__)
app.secret_key = "civic_ai_unified_key_2026"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "civic_records.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static/uploads")
WORK_FOLDER = os.path.join(BASE_DIR, "static/work_proofs")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(WORK_FOLDER, exist_ok=True)

OFFICIAL_ROUTING_MAP = {
    "Roads & Public Works": "pwd.executive.engineer@civicai.gov.in",
    "Water & Sanitation": "water.sanitation.je@civicai.gov.in",
    "Sanitation & Waste Management": "sanitation.inspector@civicai.gov.in",
    "Electricity & Street Lighting": "electricity.nodal@civicai.gov.in",
    "Town Planning & Enforcement": "townplanning.officer@civicai.gov.in"
}
HIGH_AUTHORITY_EMAIL = "commissioner.municipal@civicai.gov.in"

def get_assigned_officer_email(dept):
    return OFFICIAL_ROUTING_MAP.get(dept, "pwd.executive.engineer@civicai.gov.in")

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT UNIQUE,
            description TEXT,
            department TEXT,
            priority TEXT DEFAULT 'High',
            status TEXT DEFAULT 'Pending',
            damage_media TEXT,
            damage_media_type TEXT DEFAULT 'image',
            resolution_media TEXT,
            resolution_media_type TEXT,
            location TEXT,
            created_at TEXT,
            deadline TEXT,
            escalated INTEGER DEFAULT 0
        )
    ''')
    # Run migration if columns are missing
    cur.execute("PRAGMA table_info(complaints)")
    cols = [c[1] for c in cur.fetchall()]
    for col_name in ['damage_media', 'damage_media_type', 'resolution_media', 'resolution_media_type']:
        if col_name not in cols:
            cur.execute(f"ALTER TABLE complaints ADD COLUMN {col_name} TEXT")
    conn.commit()
    conn.close()

init_db()

def classify_issue(text):
    t = (text or "").lower()
    if any(k in t for k in ["water", "pipe", "leak", "sewer", "drain", "drainage", "overflow", "gutter", "tap"]):
        return "Water & Sanitation", "High"
    elif any(k in t for k in ["garbage", "trash", "waste", "dump", "bin", "smell", "dirt", "cleaning"]):
        return "Sanitation & Waste Management", "Medium"
    elif any(k in t for k in ["light", "streetlight", "pole", "electric", "wire", "power", "spark"]):
        return "Electricity & Street Lighting", "Critical"
    elif any(k in t for k in ["encroachment", "illegal", "hawker", "parking", "footpath"]):
        return "Town Planning & Enforcement", "Medium"
    else:
        return "Roads & Public Works", "High"

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        desc = request.form.get('description', '').strip()
        loc = request.form.get('location', '').strip() or request.form.get('coords', '').strip() or "30.730376, 76.168847"
        sel_dept = request.form.get('department', '').strip()

        filename = ""
        file = request.files.get('damage_media') or request.files.get('file') or request.files.get('image')
        b64 = request.form.get('image_base64', '').strip()

        if file and file.filename != '':
            ext = os.path.splitext(file.filename)[1].lower() or '.jpg'
            filename = f"evidence_{int(time.time())}{ext}"
            file.save(os.path.join(UPLOAD_FOLDER, filename))
        elif b64 and ',' in b64:
            try:
                header, encoded = b64.split(',', 1)
                filename = f"evidence_{int(time.time())}.jpg"
                with open(os.path.join(UPLOAD_FOLDER, filename), "wb") as fh:
                    fh.write(base64.b64decode(encoded))
            except Exception as e:
                print("Base64 decode error:", e)

        detected_dept, priority = classify_issue(desc)
        department = detected_dept if (not sel_dept or sel_dept == "Auto-Detect via AI Engine") else sel_dept
        officer_email = get_assigned_officer_email(department)

        now_dt = datetime.now()
        created_at = now_dt.strftime("%Y-%m-%d %H:%M:%S")
        deadline = (now_dt + timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        ticket_id = f"GOV-CIVIC-{random.randint(10000, 99999)}"
        analysis_text = desc if desc else f"AI Vision: Identified physical hazard requiring prompt {department} intervention."

        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO complaints (ticket_id, description, department, priority, status, damage_media, location, created_at, deadline, escalated)
            VALUES (?, ?, ?, ?, 'Pending', ?, ?, ?, ?, 0)
        """, (ticket_id, analysis_text, department, priority, filename, loc, created_at, deadline))
        conn.commit()
        conn.close()

        return render_template('dashboard.html',
                               ticket_id=ticket_id,
                               analysis=analysis_text,
                               department=department,
                               priority=priority,
                               location=loc,
                               officer_email=officer_email,
                               high_authority_email=HIGH_AUTHORITY_EMAIL,
                               status='Pending',
                               escalated=0)
    except Exception as e:
        return f"Processing Error: {e}", 500

@app.route('/admin')
def admin_panel():
    if not session.get('admin_logged'):
        return redirect('/login')
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM complaints ORDER BY id DESC")
    rows = cur.fetchall()

    complaints = []
    for r in rows:
        d = dict(r)
        raw_date = d.get('created_at') or ''
        try:
            if raw_date:
                dt_obj = datetime.strptime(raw_date.split('.')[0], "%Y-%m-%d %H:%M:%S")
                d['formatted_date'] = dt_obj.strftime("%d %b %Y")
                d['formatted_day'] = dt_obj.strftime("%A")
                d['formatted_time'] = dt_obj.strftime("%I:%M %p")
            else:
                d['formatted_date'] = datetime.now().strftime("%d %b %Y")
                d['formatted_day'] = datetime.now().strftime("%A")
                d['formatted_time'] = "Logged"
        except Exception:
            d['formatted_date'] = datetime.now().strftime("%d %b %Y")
            d['formatted_day'] = datetime.now().strftime("%A")
            d['formatted_time'] = "Logged"

        complaints.append(d)
    conn.close()
    return render_template('admin.html', complaints=complaints)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = (request.form.get('username') or '').strip().lower()
        pwd = (request.form.get('password') or '').strip()
        if user in ['officer', 'admin'] and pwd == 'admin123':
            session['admin_logged'] = True
            return redirect('/admin')
        return render_template('login.html', error="Invalid Credentials")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('admin_logged', None)
    return redirect('/login')

@app.route('/deny/<ticket_id>')
def deny_ticket(ticket_id):
    if not session.get('admin_logged'):
        return redirect('/login')
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE complaints SET status = 'Denied' WHERE ticket_id = ?", (ticket_id,))
    conn.commit()
    conn.close()
    return redirect('/admin')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port, debug=True)
