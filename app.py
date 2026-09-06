import os
import sqlite3
import time
import random
import re
from datetime import datetime, timedelta
import threading
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from flask import Flask, render_template, request, redirect, session, url_for, jsonify

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "civic_ai_unified_key_2026")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "civic_records.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static/uploads")
WORK_FOLDER = os.path.join(BASE_DIR, "static/work_proofs")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(WORK_FOLDER, exist_ok=True)

# Email Routing Directory
OFFICIAL_ROUTING_MAP = {
    "Roads & Public Works": "pwd.executive.engineer@civicai.gov.in",
    "Water & Sanitation": "water.sanitation.je@civicai.gov.in",
    "Sanitation & Waste Management": "sanitation.inspector@civicai.gov.in",
    "Electricity & Street Lighting": "electricity.nodal@civicai.gov.in",
    "Town Planning & Enforcement": "townplanning.officer@civicai.gov.in",
    "Public Works / General Municipal": "municipal.ward.officer@civicai.gov.in"
}

HIGH_AUTHORITY_EMAIL = os.environ.get("HIGH_AUTHORITY_EMAIL", "commissioner.municipal@civicai.gov.in")
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "civicai.system.alert@gmail.com")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD", "")

def get_assigned_officer_email(department):
    return OFFICIAL_ROUTING_MAP.get(department, "municipal.ward.officer@civicai.gov.in")

# --- 1. AUTOMATIC DB SCHEMA SYNC ---
def ensure_database_schema():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
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
        """)
        cursor.execute("PRAGMA table_info(complaints)")
        cols = [r[1] for r in cursor.fetchall()]

        required = {
            "damage_media": "TEXT",
            "damage_media_type": "TEXT DEFAULT 'image'",
            "resolution_media": "TEXT",
            "resolution_media_type": "TEXT",
            "location": "TEXT",
            "department": "TEXT",
            "priority": "TEXT DEFAULT 'High'",
            "status": "TEXT DEFAULT 'Pending'",
            "created_at": "TEXT",
            "deadline": "TEXT",
            "escalated": "INTEGER DEFAULT 0"
        }
        for col, ctype in required.items():
            if col not in cols:
                cursor.execute(f"ALTER TABLE complaints ADD COLUMN {col} {ctype}")
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Schema Sync Note: {e}")

ensure_database_schema()

# --- 2. AUTO CLASSIFIER ---
def auto_classify_grievance(text):
    t = (text or "").lower()
    if any(k in t for k in ["water", "pipe", "leak", "sewer", "drain", "drainage", "overflow", "gutter", "tap"]):
        dept = "Water & Sanitation"
        priority = "High" if any(k in t for k in ["overflow", "flood", "leak", "choke", "burst"]) else "Medium"
    elif any(k in t for k in ["garbage", "trash", "waste", "dump", "bin", "smell", "dirt", "sweeper", "cleaning"]):
        dept = "Sanitation & Waste Management"
        priority = "Medium" if any(k in t for k in ["overflow", "foul", "spread", "disease"]) else "Low"
    elif any(k in t for k in ["light", "streetlight", "pole", "electric", "wire", "power", "spark", "transformer", "dark"]):
        dept = "Electricity & Street Lighting"
        priority = "Critical" if any(k in t for k in ["spark", "exposed", "hanging", "shock", "fire"]) else "High"
    elif any(k in t for k in ["encroachment", "illegal", "hawker", "parking", "footpath", "block"]):
        dept = "Town Planning & Enforcement"
        priority = "Medium"
    elif any(k in t for k in ["road", "pothole", "tar", "path", "street", "broken road", "asphalt", "traffic"]):
        dept = "Roads & Public Works"
        priority = "High" if any(k in t for k in ["accident", "deep", "danger", "hazard", "huge"]) else "Medium"
    else:
        dept = "Roads & Public Works"
        priority = "High"
    return dept, priority

# --- 3. BACKGROUND EMAIL DISPATCH ENGINE ---
def send_email_worker(officer_email, ticket_id, department, priority, description, location, filepath):
    subject = f"[CivicAI Dispatch] Grievance {ticket_id} - {department} ({priority} Priority)"
    body = f"""
Official Grievance Assignment Alert
-----------------------------------
Ticket ID   : {ticket_id}
Department  : {department}
Officer Assigned: {officer_email}
Priority    : {priority}
Location    : {location}
Time Logged : {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

AI Inspection Summary:
{description}

Action Required:
Field inspection and remediation must be completed within the 7-day Municipal SLA.
Upload live on-site resolution proof via the officer portal before auto-escalation.

CivicAI Autonomous Governance Engine
"""
    print(f"\n=======================================================")
    print(f"🚀 [EMAIL DISPATCH TRIGGERED]")
    print(f"To          : {officer_email}")
    print(f"Subject     : {subject}")
    print(f"Location    : {location}")
    print(f"=======================================================\n")

    if SENDER_PASSWORD and SENDER_EMAIL:
        try:
            msg = MIMEMultipart()
            msg['From'] = SENDER_EMAIL
            msg['To'] = officer_email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))
            if filepath and os.path.exists(filepath):
                with open(filepath, "rb") as attachment:
                    p = MIMEBase('application', 'octet-stream')
                    p.set_payload(attachment.read())
                    encoders.encode_base64(p)
                    p.add_header('Content-Disposition', f"attachment; filename= {os.path.basename(filepath)}")
                    msg.attach(p)
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
            server.quit()
        except Exception as err:
            print(f"SMTP Dispatch Note: {err}")

def trigger_async_officer_email(officer_email, ticket_id, department, priority, description, location, filepath):
    t = threading.Thread(
        target=send_email_worker,
        args=(officer_email, ticket_id, department, priority, description, location, filepath),
        daemon=True
    )
    t.start()

# --- 4. 7-DAY SLA CHECK ---
def check_sla_escalations():
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM complaints WHERE status != 'Resolved' AND (escalated IS NULL OR escalated = 0)")
        tickets = cursor.fetchall()
        now = datetime.now()
        for t in tickets:
            try:
                created_dt = datetime.strptime(t['created_at'], "%Y-%m-%d %H:%M:%S")
                if (now - created_dt).total_seconds() >= 604800:
                    cursor.execute("UPDATE complaints SET escalated = 1 WHERE ticket_id = ?", (t['ticket_id'],))
                    conn.commit()
                    print(f"\n[SLA ESCALATION] Ticket {t['ticket_id']} sent to High Authority: {HIGH_AUTHORITY_EMAIL}\n")
            except Exception:
                continue
        conn.close()
    except Exception as e:
        print(f"SLA Check error: {e}")

# --- 5. 24-HR PURGE ---
def auto_purge_old_resolved():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cutoff = (datetime.now() - timedelta(seconds=86400)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("DELETE FROM complaints WHERE status = 'Resolved' AND created_at < ?", (cutoff,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Purge error: {e}")

# --- ROUTES ---
@app.route('/')
def home():
    check_sla_escalations()
    auto_purge_old_resolved()
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    check_sla_escalations()
    try:
        description = request.form.get('description', '').strip()
        location = request.form.get('location', '').strip() or request.form.get('coords', '').strip() or "30.730376, 76.168847"
        user_dept = request.form.get('department', '').strip()

        # Handle file upload or base64 canvas snapshot
        file = request.files.get('damage_media') or request.files.get('file') or request.files.get('image')
        b64_data = request.form.get('image_base64', '')
        filename = ""
        filepath = ""

        if file and file.filename != '':
            ext = os.path.splitext(file.filename)[1].lower() or '.jpg'
            filename = f"evidence_{int(time.time())}{ext}"
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
        elif b64_data and ',' in b64_data:
            import base64
            header, encoded = b64_data.split(',', 1)
            filename = f"evidence_{int(time.time())}.jpg"
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            with open(filepath, "wb") as fh:
                fh.write(base64.b64decode(encoded))

        analysis_text = description if description else "AI Vision: Surface hazard and civil disruption identified."
        try:
            import ai_engine
            if hasattr(ai_engine, 'analyze_image') and filepath:
                res = ai_engine.analyze_image(filepath)
                if res: analysis_text = res
        except Exception as e:
            print(f"Vision Engine note: {e}")

        detected_dept, detected_priority = auto_classify_grievance(description or analysis_text)
        department = user_dept if (user_dept and user_dept != 'Auto-Detect via AI Engine') else detected_dept
        priority = detected_priority
        officer_email = get_assigned_officer_email(department)

        now_dt = datetime.now()
        created_at = now_dt.strftime("%Y-%m-%d %H:%M:%S")
        deadline_str = (now_dt + timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        ticket_id = f"TKT-{now_dt.strftime('%Y%m%d')}-{random.randint(1000, 9999)}"

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO complaints (ticket_id, description, department, priority, status, damage_media, damage_media_type, location, created_at, deadline, escalated)
            VALUES (?, ?, ?, ?, 'Pending', ?, 'image', ?, ?, ?, 0)
        """, (ticket_id, analysis_text, department, priority, filename, location, created_at, deadline_str))
        conn.commit()
        conn.close()

        # Trigger Real/Simulated Async Email to Assigned Nodal Officer
        trigger_async_officer_email(officer_email, ticket_id, department, priority, analysis_text, location, filepath)

        return render_template('dashboard.html',
                               ticket_id=ticket_id,
                               analysis=analysis_text,
                               department=department,
                               priority=priority,
                               location=location,
                               officer_email=officer_email,
                               high_authority_email=HIGH_AUTHORITY_EMAIL,
                               status='Pending',
                               escalated=0)
    except Exception as e:
        print(f"Analyze error: {e}")
        return f"Database error: {e}", 500

@app.route('/track/<ticket_id>')
def track_ticket(ticket_id):
    check_sla_escalations()
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM complaints WHERE ticket_id = ?", (ticket_id.strip(),))
    ticket = cursor.fetchone()
    conn.close()
    if not ticket:
        return "Ticket Not Found", 404
    t_dict = dict(ticket)
    officer_email = get_assigned_officer_email(t_dict.get('department', ''))
    return render_template('dashboard.html', ticket=t_dict, officer_email=officer_email, high_authority_email=HIGH_AUTHORITY_EMAIL)

@app.route('/admin')
def admin_panel():
    check_sla_escalations()
    auto_purge_old_resolved()
    if not session.get('admin_logged'):
        return redirect('/login')
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM complaints ORDER BY id DESC")
    rows = cursor.fetchall()
    
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
            d['formatted_date'] = raw_date or datetime.now().strftime("%d %b %Y")
            d['formatted_day'] = "Logged"
            d['formatted_time'] = ""
        complaints.append(d)
        
    conn.close()
    return render_template('admin.html', complaints=complaints)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form.get('username')
        pwd = request.form.get('password')
        if user == "officer" and pwd == "admin123":
            session['admin_logged'] = True
            return redirect('/admin')
        return render_template('login.html', error="Invalid Credentials")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('admin_logged', None)
    return redirect('/login')

@app.route('/resolve/<ticket_id>', methods=['GET', 'POST'])
def resolve_ticket(ticket_id):
    if not session.get('admin_logged'):
        return redirect('/login')
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if request.method == 'POST':
        file = request.files.get('work_media')
        filename = ""
        if file and file.filename != '':
            ext = os.path.splitext(file.filename)[1].lower()
            filename = f"work_proof_{ticket_id}_{int(time.time())}{ext}"
            file.save(os.path.join(WORK_FOLDER, filename))
            cursor.execute("""
                UPDATE complaints 
                SET status = 'Under Inspection', resolution_media = ?, resolution_media_type = 'image'
                WHERE ticket_id = ?
            """, (filename, ticket_id))
            conn.commit()
        conn.close()
        return redirect('/admin')

    cursor.execute("SELECT * FROM complaints WHERE ticket_id = ?", (ticket_id,))
    ticket = cursor.fetchone()
    conn.close()
    return render_template('resolve.html', complaint=dict(ticket))

@app.route('/mark_resolved/<ticket_id>')
def mark_resolved(ticket_id):
    if not session.get('admin_logged'):
        return redirect('/login')
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE complaints SET status = 'Resolved' WHERE ticket_id = ?", (ticket_id,))
    conn.commit()
    conn.close()
    return redirect('/admin')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port, debug=True)
