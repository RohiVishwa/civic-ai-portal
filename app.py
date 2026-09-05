import os
import random
import sqlite3
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from flask import Flask, render_template, request, redirect, session
from werkzeug.utils import secure_filename
from ai_engine import analyze_damage, assign_department

app = Flask(__name__)
app.secret_key = 'civic_master_gov_portal_key_2026'

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
CITIZEN_FOLDER = os.path.join(UPLOAD_FOLDER, 'citizen_evidence')
WORK_FOLDER = os.path.join(UPLOAD_FOLDER, 'work_proof')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CITIZEN_FOLDER, exist_ok=True)
os.makedirs(WORK_FOLDER, exist_ok=True)

DB_NAME = "civic_records.db"
VIDEO_EXTENSIONS = ('.mp4', '.mov', '.avi', '.mkv', '.webm')

# =====================================================================
# 1. SMTP DISPATCH CREDENTIALS (GMAIL)
# =====================================================================
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# Yahan apna sender Gmail aur 16-digit app password likhein
SENDER_EMAIL = "your_actual_gmail@gmail.com"
SENDER_PASSWORD = "your_16_digit_app_password"

# Testing Mode: Jab tak aap test kar rahe hain, is flag ko True rakhein
# taaki har department ka email seedha aapke hi inbox me aaye live check karne ke liye!
TESTING_MODE_OVERRIDE_TO_MY_EMAIL = True
MY_TEST_EMAIL = "your_actual_gmail@gmail.com"

# =====================================================================
# 2. DEPARTMENT OFFICER REGISTRY WITH DEMO EMAILS
# =====================================================================
DEPARTMENT_OFFICERS = {
    "Roads & Highway Authority": {
        "dept_id": "GOV-DEPT-PWD-01",
        "officer_name": "Er. Sandeep Verma",
        "designation": "Executive Engineer (PWD Roads Division)",
        "demo_email": "pwd.roads.controlroom@gmail.com"
    },
    "Water & Sewage Board": {
        "dept_id": "GOV-DEPT-JAL-02",
        "officer_name": "Er. Manpreet Singh",
        "designation": "Sub-Divisional Officer (Water & Sewage)",
        "demo_email": "jalboard.emergency.cell@gmail.com"
    },
    "Municipal Corporation (Sanitation Dept)": {
        "dept_id": "GOV-DEPT-SAN-03",
        "officer_name": "Shri Rajesh Kalia",
        "designation": "Chief Sanitation Inspector (Solid Waste)",
        "demo_email": "swachh.sanitation.dispatch@gmail.com"
    },
    "Electricity & Lighting Board": {
        "dept_id": "GOV-DEPT-ELEC-04",
        "officer_name": "Er. Amit Sharma",
        "designation": "Assistant Engineer (Street Light Operations)",
        "demo_email": "powergrid.lighting.faults@gmail.com"
    },
    "Central Grievance Cell (Municipal Authority)": {
        "dept_id": "GOV-DEPT-HQ-00",
        "officer_name": "Chief Municipal Nodal Officer",
        "designation": "Director (Grievance Redressal)",
        "demo_email": "cmo.civic.escalation@gmail.com"
    }
}

def send_officer_dispatch_email(dept_name, ticket_id, priority, description, location, map_url, media_filename):
    """Sends immediate official notification email to the specific department officer."""
    officer_info = DEPARTMENT_OFFICERS.get(dept_name, DEPARTMENT_OFFICERS["Central Grievance Cell (Municipal Authority)"])
    
    # In test mode, route to your email; otherwise route to department officer demo email
    target_email = MY_TEST_EMAIL if TESTING_MODE_OVERRIDE_TO_MY_EMAIL and MY_TEST_EMAIL else officer_info["demo_email"]
    officer_title = f"{officer_info['officer_name']} ({officer_info['designation']})"
    dept_id = officer_info["dept_id"]

    subject = f"🚨 [FIELD ACTION DIRECTIVE: {priority}] Ticket #{ticket_id} Assigned to {dept_name}"

    html_content = f"""
    <html>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f8fafc; padding: 20px; color: #0f172a;">
        <div style="max-width: 620px; margin: 0 auto; background: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.06);">
            <div style="background: #0f172a; padding: 22px; color: #ffffff;">
                <span style="background: #ef4444; color: #ffffff; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;">DEPARTMENT DISPATCH ALERT</span>
                <h3 style="margin: 8px 0 2px 0;">CIVIC AI DISPATCH ENGINE</h3>
                <small style="color: #94a3b8;">Government of India • Municipal Redressal Cell</small>
            </div>
            <div style="padding: 24px;">
                <p><strong>To Assigned Officer:</strong> {officer_title}</p>
                <p><strong>Official Department Inbox:</strong> <code>{officer_info['demo_email']}</code></p>
                <p>Aapke concerned department ke jurisdiction me citizen complaint auto-triage hokar ground verification ke liye assign ki gayi hai:</p>
                
                <table style="width: 100%; border-collapse: collapse; margin: 20px 0; background: #f8fafc; border-radius: 8px; overflow: hidden;">
                    <tr>
                        <td style="padding: 10px 14px; border-bottom: 1px solid #e2e8f0; font-weight: bold; color: #64748b; font-size: 13px;">Docket Ticket ID:</td>
                        <td style="padding: 10px 14px; border-bottom: 1px solid #e2e8f0; color: #2563eb; font-weight: bold; font-family: monospace;">{ticket_id}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px 14px; border-bottom: 1px solid #e2e8f0; font-weight: bold; color: #64748b; font-size: 13px;">Department Code:</td>
                        <td style="padding: 10px 14px; border-bottom: 1px solid #e2e8f0; font-weight: 600;">{dept_id} ({dept_name})</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px 14px; border-bottom: 1px solid #e2e8f0; font-weight: bold; color: #64748b; font-size: 13px;">AI Priority:</td>
                        <td style="padding: 10px 14px; border-bottom: 1px solid #e2e8f0; font-weight: bold; color: {'#dc2626' if priority=='HIGH' else '#d97706'};">{priority} PRIORITY</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px 14px; border-bottom: 1px solid #e2e8f0; font-weight: bold; color: #64748b; font-size: 13px;">Ground Location:</td>
                        <td style="padding: 10px 14px; border-bottom: 1px solid #e2e8f0; font-weight: 600;">{location}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px 14px; border-bottom: 1px solid #e2e8f0; font-weight: bold; color: #64748b; font-size: 13px;">Issue Description:</td>
                        <td style="padding: 10px 14px; border-bottom: 1px solid #e2e8f0;">{description}</td>
                    </tr>
                </table>

                {f'<div style="text-align: center; margin: 25px 0;"><a href="{map_url}" style="background: #2563eb; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 14px; display: inline-block;">📍 Pinpoint Spot on Google Maps &rarr;</a></div>' if map_url else ''}

                <div style="background: #fef2f2; border-left: 4px solid #ef4444; padding: 14px; border-radius: 4px; margin-top: 20px;">
                    <p style="margin: 0; font-size: 13px; color: #991b1b;"><strong>Executive Directive:</strong> Kripya field team ko spot inspection par bhejein. Karyawahi poori hone ke baad officer portal par <em>Work Resolution Proof</em> upload karke ticket close karein.</p>
                </div>
            </div>
            <div style="background: #f1f5f9; padding: 14px; text-align: center; font-size: 11px; color: #64748b;">
                Department Officer Automated Router • CivicAI System
            </div>
        </div>
    </body>
    </html>
    """

    if not SENDER_EMAIL or "your_actual_gmail" in SENDER_EMAIL or not SENDER_PASSWORD or "your_16" in SENDER_PASSWORD:
        print("\n" + "="*70)
        print(f"📧 [OFFICER DISPATCH LOG]")
        print(f"TO OFFICER: {officer_title}")
        print(f"DEPARTMENT DEMO EMAIL: {officer_info['demo_email']}")
        print(f"DELIVERY TARGET: {target_email}")
        print(f"SEVERITY: {priority} | TICKET: {ticket_id}")
        print(f"LOCATION: {location}")
        print("="*70 + "\n")
        return True

    try:
        msg = MIMEMultipart()
        msg['From'] = f"CivicAI Officer Dispatch <{SENDER_EMAIL}>"
        msg['To'] = target_email
        msg['Subject'] = subject
        msg.attach(MIMEText(html_content, 'html'))

        if media_filename:
            file_path = os.path.join(CITIZEN_FOLDER, media_filename)
            if os.path.exists(file_path):
                with open(file_path, "rb") as attachment:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f"attachment; filename={media_filename}")
                msg.attach(part)

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, target_email, msg.as_string())
        server.quit()
        print(f"✅ Real Email Dispatched to Officer: {officer_title} at {target_email}!")
        return True
    except Exception as e:
        print(f"⚠️ Email dispatch failed: {e}")
        return False

def get_media_type(filename):
    if not filename: return None
    ext = os.path.splitext(filename)[1].lower()
    return 'video' if ext in VIDEO_EXTENSIONS else 'image'

def get_media_url(filename):
    if not filename: return None
    if os.path.exists(os.path.join(CITIZEN_FOLDER, filename)): return f"/static/uploads/citizen_evidence/{filename}"
    if os.path.exists(os.path.join(WORK_FOLDER, filename)): return f"/static/uploads/work_proof/{filename}"
    if os.path.exists(os.path.join(UPLOAD_FOLDER, filename)): return f"/static/uploads/{filename}"
    return None

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS officers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gov_id TEXT UNIQUE,
            full_name TEXT,
            department TEXT,
            username TEXT UNIQUE,
            password TEXT
        )
    ''')
    cursor.execute("SELECT COUNT(*) FROM officers")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO officers (gov_id, full_name, department, username, password) VALUES (?, ?, ?, ?, ?)",
                       ("GOV-OFFICER-7890", "Chief Municipal Officer", "Central Grievance Cell (Municipal Authority)", "admin", "password123"))

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT,
            gov_dept_id TEXT,
            description TEXT,
            priority TEXT,
            department TEXT,
            media_name TEXT,
            media_type TEXT,
            status TEXT,
            created_at TEXT,
            resolution_media TEXT,
            resolution_media_type TEXT,
            reject_reason TEXT,
            location TEXT,
            map_url TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deleted_complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT,
            gov_dept_id TEXT,
            description TEXT,
            department TEXT,
            deleted_by TEXT,
            delete_reason TEXT,
            deleted_at TEXT,
            deleted_epoch REAL
        )
    ''')

    for col in ['gov_dept_id TEXT', 'media_name TEXT', 'media_type TEXT', 'resolution_media TEXT', 'resolution_media_type TEXT', 'reject_reason TEXT', 'image_name TEXT', 'resolution_image TEXT', 'location TEXT', 'map_url TEXT']:
        try: cursor.execute(f"ALTER TABLE complaints ADD COLUMN {col}")
        except sqlite3.OperationalError: pass

    for col in ['gov_id TEXT']:
        try: cursor.execute(f"ALTER TABLE officers ADD COLUMN {col}")
        except sqlite3.OperationalError: pass

    conn.commit()
    conn.close()

init_db()

def purge_expired_deleted_records():
    one_week_ago_epoch = time.time() - (7 * 24 * 60 * 60)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM deleted_complaints WHERE deleted_epoch IS NOT NULL AND deleted_epoch < ?", (one_week_ago_epoch,))
    conn.commit()
    conn.close()

def get_complaint_count():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM complaints")
    count = cursor.fetchone()[0]
    conn.close()
    return count

@app.route('/')
def home():
    total_count = get_complaint_count()
    return render_template('index.html', total_count=total_count)

# --- Citizen Grievance Submission + Automated Department Officer Email ---
@app.route('/analyze', methods=['POST'])
def analyze():
    complaint_text = request.form.get('complaint', '')
    media_file = request.files.get('damage_media')
    chosen_dept = request.form.get('department', 'auto')
    incident_date = request.form.get('incident_date', '')
    location_text = request.form.get('location', '').strip()
    lat = request.form.get('latitude', '').strip()
    lng = request.form.get('longitude', '').strip()

    if lat and lng:
        map_url = f"https://www.google.com/maps?q={lat},{lng}"
    elif location_text:
        map_url = f"https://www.google.com/maps/search/{location_text.replace(' ', '+')}+India"
    else:
        map_url = ""

    priority = "LOW"
    saved_media_name = None
    media_type = None

    if media_file and media_file.filename != '':
        filename = secure_filename(f"citizen_{datetime.now().strftime('%Y%m%d%H%M%S')}_{media_file.filename}")
        save_path = os.path.join(CITIZEN_FOLDER, filename)
        media_file.save(save_path)
        saved_media_name = filename
        media_type = get_media_type(filename)
        priority = analyze_damage(save_path, text=complaint_text)
    else:
        priority = analyze_damage("", text=complaint_text)

    if chosen_dept and chosen_dept != 'auto':
        department = chosen_dept
    else:
        department = assign_department(complaint_text)

    officer_data = DEPARTMENT_OFFICERS.get(department, DEPARTMENT_OFFICERS["Central Grievance Cell (Municipal Authority)"])
    gov_dept_id = officer_data["dept_id"]
    assigned_officer_title = f"{officer_data['officer_name']} ({officer_data['designation']})"
    assigned_officer_email = officer_data["demo_email"]

    ticket_id = f"GOV-CIVIC-{random.randint(10000, 99999)}"
    time_now = datetime.now().strftime("%I:%M %p")

    if incident_date:
        try:
            dt_obj = datetime.strptime(incident_date, "%Y-%m-%d")
            timestamp = dt_obj.strftime(f"%A, %d %b %Y • {time_now}")
        except ValueError:
            timestamp = datetime.now().strftime(f"%A, %d %b %Y • {time_now}")
    else:
        timestamp = datetime.now().strftime(f"%A, %d %b %Y • {time_now}")

    status = "Pending"

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO complaints (ticket_id, gov_dept_id, description, priority, department, media_name, media_type, status, created_at, resolution_media, resolution_media_type, reject_reason, location, map_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (ticket_id, gov_dept_id, complaint_text, priority, department, saved_media_name, media_type, status, timestamp, None, None, None, location_text, map_url))
    conn.commit()
    conn.close()

    # 🚀 Direct Email to the Department's Responsible Officer
    send_officer_dispatch_email(department, ticket_id, priority, complaint_text, location_text, map_url, saved_media_name)

    total_count = get_complaint_count()

    return render_template(
        'receipt.html',
        ticket_id=ticket_id,
        gov_dept_id=gov_dept_id,
        officer_title=assigned_officer_title,
        officer_email=assigned_officer_email,
        complaint=complaint_text,
        priority=priority,
        department=department,
        status=status,
        timestamp=timestamp,
        location=location_text,
        map_url=map_url,
        media_name=saved_media_name,
        media_url=get_media_url(saved_media_name),
        media_type=media_type,
        total_count=total_count
    )

# --- Officer Auth Routes ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        gov_id = request.form.get('gov_id', '').strip().upper()
        full_name = request.form.get('full_name', '').strip()
        department = request.form.get('department', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not gov_id or not full_name or not username or not password:
            error = "Sabhi fields bharna anivarya hai!"
        else:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO officers (gov_id, full_name, department, username, password) VALUES (?, ?, ?, ?, ?)",
                               (gov_id, full_name, department, username, password))
                conn.commit()
                conn.close()
                return redirect('/login?registered=1')
            except sqlite3.IntegrityError:
                error = "Yeh Govt ID ya Username pehle se registered hai!"
                conn.close()

    return render_template('register.html', error=error)

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    registered = request.args.get('registered')
    if request.method == 'POST':
        login_input = request.form.get('username', '').strip()
        pwd = request.form.get('password', '').strip()

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT gov_id, full_name, department FROM officers WHERE (username = ? OR gov_id = ?) AND password = ?", 
                       (login_input, login_input.upper(), pwd))
        officer = cursor.fetchone()
        conn.close()

        if officer:
            session['admin_logged'] = True
            session['officer_gov_id'] = officer[0]
            session['officer_name'] = officer[1]
            session['officer_dept'] = officer[2]
            return redirect('/admin')
        else:
            error = "Amaniya Government ID ya Password!"

    return render_template('login.html', error=error, registered=registered)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# --- Officer Dashboard ---
@app.route('/admin')
def admin_portal():
    if not session.get('admin_logged'):
        return redirect('/login')

    purge_expired_deleted_records()

    filter_date = request.args.get('date', '').strip()
    filter_dept = request.args.get('dept', '').strip()
    sort_by = request.args.get('sort', 'newest').strip()

    officer_dept = session.get('officer_dept', '')
    officer_gov_id = session.get('officer_gov_id', '')

    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT DISTINCT department FROM complaints WHERE department IS NOT NULL AND department != '' ORDER BY department ASC")
    all_depts = [r['department'] for r in cursor.fetchall()]

    query = "SELECT * FROM complaints WHERE 1=1"
    params = []

    # Filter by user dropdown first; if not, and officer is department-specific, filter by department
    if filter_dept:
        query += " AND department = ?"
        params.append(filter_dept)
    elif officer_dept and officer_dept not in ["Central Grievance Cell (Municipal Authority)", "General Administration", "HQ"]:
        query += " AND department = ?"
        params.append(officer_dept)

    if filter_date:
        try:
            dt_obj = datetime.strptime(filter_date, "%Y-%m-%d")
            std_format = dt_obj.strftime("%d %b %Y")
            query += " AND created_at LIKE ?"
            params.append(f"%{std_format}%")
        except ValueError:
            pass

    if sort_by == 'oldest': query += " ORDER BY id ASC"
    elif sort_by == 'dept_asc': query += " ORDER BY department ASC, id DESC"
    elif sort_by == 'priority': query += " ORDER BY CASE priority WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 WHEN 'LOW' THEN 3 ELSE 4 END ASC, id DESC"
    else: query += " ORDER BY id DESC"

    cursor.execute(query, tuple(params))
    raw_complaints = cursor.fetchall()

    complaints = []
    for row in raw_complaints:
        keys = row.keys()
        c_media = row['media_name'] if 'media_name' in keys and row['media_name'] else (row['image_name'] if 'image_name' in keys and row['image_name'] else None)
        c_type = row['media_type'] if 'media_type' in keys and row['media_type'] else get_media_type(c_media)

        w_media = row['resolution_media'] if 'resolution_media' in keys and row['resolution_media'] else (row['resolution_image'] if 'resolution_image' in keys and row['resolution_image'] else None)
        w_type = row['resolution_media_type'] if 'resolution_media_type' in keys and row['resolution_media_type'] else get_media_type(w_media)

        raw_time = row['created_at'] if 'created_at' in keys and row['created_at'] else ""
        parts = raw_time.split('•')
        date_part = parts[0].strip() if len(parts) > 0 else raw_time
        time_part = parts[1].strip() if len(parts) > 1 else ""

        loc = row['location'] if 'location' in keys and row['location'] else "Not Specified"
        m_url = row['map_url'] if 'map_url' in keys and row['map_url'] else ""
        
        dept_data = DEPARTMENT_OFFICERS.get(row['department'], DEPARTMENT_OFFICERS["Central Grievance Cell (Municipal Authority)"])
        g_id = row['gov_dept_id'] if 'gov_dept_id' in keys and row['gov_dept_id'] else dept_data["dept_id"]

        complaints.append({
            'id': row['id'],
            'ticket_id': row['ticket_id'],
            'gov_dept_id': g_id,
            'description': row['description'],
            'priority': row['priority'],
            'department': row['department'],
            'status': row['status'],
            'location': loc,
            'map_url': m_url,
            'date_part': date_part,
            'time_part': time_part,
            'citizen_media': c_media,
            'citizen_url': get_media_url(c_media),
            'citizen_type': c_type,
            'work_media': w_media,
            'work_url': get_media_url(w_media),
            'work_type': w_type
        })

    # Summary metrics
    if officer_dept and officer_dept not in ["Central Grievance Cell (Municipal Authority)", "General Administration", "HQ"]:
        cursor.execute("SELECT COUNT(*) FROM complaints WHERE department = ?", (officer_dept,))
        total = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM complaints WHERE status = 'Pending' AND department = ?", (officer_dept,))
        pending = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM complaints WHERE status = 'Resolved' AND department = ?", (officer_dept,))
        resolved = cursor.fetchone()[0]
    else:
        cursor.execute("SELECT COUNT(*) FROM complaints")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM complaints WHERE status = 'Pending'")
        pending = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM complaints WHERE status = 'Resolved'")
        resolved = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM deleted_complaints")
    deleted_count = cursor.fetchone()[0]

    cursor.execute("SELECT * FROM deleted_complaints ORDER BY id DESC")
    deleted_logs = cursor.fetchall()
    conn.close()

    return render_template(
        'admin.html',
        complaints=complaints,
        departments=all_depts,
        total=total,
        pending=pending,
        resolved=resolved,
        deleted_count=deleted_count,
        deleted_logs=deleted_logs,
        filter_date=filter_date,
        filter_dept=filter_dept,
        sort_by=sort_by,
        officer_name=session.get('officer_name'),
        officer_dept=officer_dept,
        officer_gov_id=officer_gov_id
    )

# --- Dedicated Work Proof Upload Page ---
@app.route('/resolve/<ticket_id>')
def resolve_page(ticket_id):
    if not session.get('admin_logged'):
        return redirect('/login')

    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM complaints WHERE ticket_id = ?", (ticket_id,))
    ticket = cursor.fetchone()
    conn.close()

    if not ticket:
        return redirect('/admin')

    keys = ticket.keys()
    c_media = ticket['media_name'] if 'media_name' in keys and ticket['media_name'] else (ticket['image_name'] if 'image_name' in keys and ticket['image_name'] else None)
    c_type = ticket['media_type'] if 'media_type' in keys and ticket['media_type'] else get_media_type(c_media)
    dept_data = DEPARTMENT_OFFICERS.get(ticket['department'], DEPARTMENT_OFFICERS["Central Grievance Cell (Municipal Authority)"])
    g_id = ticket['gov_dept_id'] if 'gov_dept_id' in keys and ticket['gov_dept_id'] else dept_data["dept_id"]

    ticket_data = {
        'ticket_id': ticket['ticket_id'],
        'gov_dept_id': g_id,
        'description': ticket['description'],
        'department': ticket['department'],
        'priority': ticket['priority'],
        'location': ticket['location'] if 'location' in keys and ticket['location'] else "Not Specified",
        'map_url': ticket['map_url'] if 'map_url' in keys and ticket['map_url'] else "",
        'created_at': ticket['created_at'],
        'citizen_media': c_media,
        'citizen_url': get_media_url(c_media),
        'citizen_type': c_type
    }

    return render_template('resolve.html', ticket=ticket_data)

# --- Work Proof Upload Action ---
@app.route('/resolve_ticket/<ticket_id>', methods=['POST'])
def resolve_ticket(ticket_id):
    if not session.get('admin_logged'):
        return redirect('/login')

    proof_file = request.files.get('proof_media')
    saved_proof_name = None
    proof_type = None

    if proof_file and proof_file.filename != '':
        filename = secure_filename(f"work_{ticket_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{proof_file.filename}")
        save_path = os.path.join(WORK_FOLDER, filename)
        proof_file.save(save_path)
        saved_proof_name = filename
        proof_type = get_media_type(filename)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:
        cursor.execute("UPDATE complaints SET status = 'Resolved', resolution_media = ?, resolution_media_type = ? WHERE ticket_id = ?",
                       (saved_proof_name, proof_type, ticket_id))
    except sqlite3.OperationalError: pass

    try:
        cursor.execute("UPDATE complaints SET status = 'Resolved', resolution_image = ? WHERE ticket_id = ?",
                       (saved_proof_name, ticket_id))
    except sqlite3.OperationalError: pass

    conn.commit()
    conn.close()

    return redirect('/admin')

# --- Deny & Delete Action ---
@app.route('/deny_ticket/<ticket_id>', methods=['POST'])
def deny_ticket(ticket_id):
    if not session.get('admin_logged'):
        return redirect('/login')

    reason_category = request.form.get('delete_reason', 'Fake Upload')
    custom_comment = request.form.get('custom_comment', '').strip()
    final_reason = reason_category + (f" - {custom_comment}" if custom_comment else "")

    officer_name = f"{session.get('officer_name')} ({session.get('officer_gov_id', 'OFFICIAL')})"
    deleted_at = datetime.now().strftime("%A, %d %b %Y • %I:%M %p")
    deleted_epoch = time.time()

    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM complaints WHERE ticket_id = ?", (ticket_id,))
    row = cursor.fetchone()

    if row:
        keys = row.keys()
        dept_data = DEPARTMENT_OFFICERS.get(row['department'], DEPARTMENT_OFFICERS["Central Grievance Cell (Municipal Authority)"])
        g_id = row['gov_dept_id'] if 'gov_dept_id' in keys else dept_data["dept_id"]
        cursor.execute('''
            INSERT INTO deleted_complaints (ticket_id, gov_dept_id, description, department, deleted_by, delete_reason, deleted_at, deleted_epoch)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (ticket_id, g_id, row['description'], row['department'], officer_name, final_reason, deleted_at, deleted_epoch))

        for col in ['media_name', 'image_name', 'resolution_media', 'resolution_image']:
            if col in keys and row[col]:
                fname = row[col]
                for folder in [CITIZEN_FOLDER, WORK_FOLDER, UPLOAD_FOLDER]:
                    fpath = os.path.join(folder, fname)
                    if os.path.exists(fpath):
                        try: os.remove(fpath)
                        except OSError: pass

    cursor.execute("DELETE FROM complaints WHERE ticket_id = ?", (ticket_id,))
    conn.commit()
    conn.close()

    return redirect('/admin')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)