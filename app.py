import os
import random
import sqlite3
import time
from datetime import datetime
from flask import Flask, render_template, request, redirect, session
from werkzeug.utils import secure_filename
from ai_engine import analyze_damage, assign_department

app = Flask(__name__)
app.secret_key = 'civic_master_portal_key_2026'

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
CITIZEN_FOLDER = os.path.join(UPLOAD_FOLDER, 'citizen_evidence')
WORK_FOLDER = os.path.join(UPLOAD_FOLDER, 'work_proof')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CITIZEN_FOLDER, exist_ok=True)
os.makedirs(WORK_FOLDER, exist_ok=True)

DB_NAME = "civic_records.db"
VIDEO_EXTENSIONS = ('.mp4', '.mov', '.avi', '.mkv', '.webm')

def get_media_type(filename):
    if not filename:
        return None
    ext = os.path.splitext(filename)[1].lower()
    return 'video' if ext in VIDEO_EXTENSIONS else 'image'

def get_media_url(filename):
    if not filename:
        return None
    if os.path.exists(os.path.join(CITIZEN_FOLDER, filename)):
        return f"/static/uploads/citizen_evidence/{filename}"
    if os.path.exists(os.path.join(WORK_FOLDER, filename)):
        return f"/static/uploads/work_proof/{filename}"
    if os.path.exists(os.path.join(UPLOAD_FOLDER, filename)):
        return f"/static/uploads/{filename}"
    return None

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 1. Officers Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS officers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT,
            department TEXT,
            username TEXT UNIQUE,
            password TEXT
        )
    ''')
    cursor.execute("SELECT COUNT(*) FROM officers")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO officers (full_name, department, username, password) VALUES (?, ?, ?, ?)",
                       ("Chief Municipal Officer", "General Administration", "admin", "password123"))

    # 2. Active Complaints Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT,
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

    # 3. Deleted Complaints Table (with deleted_epoch for 1-week auto-cleanup)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deleted_complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT,
            description TEXT,
            department TEXT,
            deleted_by TEXT,
            delete_reason TEXT,
            deleted_at TEXT,
            deleted_epoch REAL
        )
    ''')

    for col in ['media_name TEXT', 'media_type TEXT', 'resolution_media TEXT', 'resolution_media_type TEXT', 'reject_reason TEXT', 'image_name TEXT', 'resolution_image TEXT', 'location TEXT', 'map_url TEXT']:
        try:
            cursor.execute(f"ALTER TABLE complaints ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass

    try:
        cursor.execute("ALTER TABLE deleted_complaints ADD COLUMN deleted_epoch REAL")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

init_db()

# --- 1-Week (7 Days) Auto Purge Routine ---
def purge_expired_deleted_records():
    """Automatically deletes records from deleted_complaints older than 7 days (604,800 seconds)."""
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

# --- Citizen Grievance Submission ---
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
        INSERT INTO complaints (ticket_id, description, priority, department, media_name, media_type, status, created_at, resolution_media, resolution_media_type, reject_reason, location, map_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (ticket_id, complaint_text, priority, department, saved_media_name, media_type, status, timestamp, None, None, None, location_text, map_url))
    conn.commit()
    conn.close()

    total_count = get_complaint_count()

    return render_template(
        'dashboard.html',
        ticket_id=ticket_id,
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
        full_name = request.form.get('full_name', '').strip()
        department = request.form.get('department', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not full_name or not username or not password:
            error = "Sabhi fields bharna zaroori hai!"
        else:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO officers (full_name, department, username, password) VALUES (?, ?, ?, ?)",
                               (full_name, department, username, password))
                conn.commit()
                conn.close()
                return redirect('/login?registered=1')
            except sqlite3.IntegrityError:
                error = "Yeh Username pehle se maujood hai! Naya chunein."
                conn.close()

    return render_template('register.html', error=error)

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    registered = request.args.get('registered')
    if request.method == 'POST':
        user = request.form.get('username', '').strip()
        pwd = request.form.get('password', '').strip()

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT full_name, department FROM officers WHERE username = ? AND password = ?", (user, pwd))
        officer = cursor.fetchone()
        conn.close()

        if officer:
            session['admin_logged'] = True
            session['officer_name'] = officer[0]
            session['officer_dept'] = officer[1]
            return redirect('/admin')
        else:
            error = "Galat Username ya Password!"

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

    # Run 1-week auto cleanup on every dashboard access
    purge_expired_deleted_records()

    filter_date = request.args.get('date', '').strip()
    filter_dept = request.args.get('dept', '').strip()
    sort_by = request.args.get('sort', 'newest').strip()

    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT DISTINCT department FROM complaints WHERE department IS NOT NULL AND department != '' ORDER BY department ASC")
    all_depts = [r['department'] for r in cursor.fetchall()]

    query = "SELECT * FROM complaints WHERE 1=1"
    params = []

    if filter_date:
        try:
            dt_obj = datetime.strptime(filter_date, "%Y-%m-%d")
            std_format = dt_obj.strftime("%d %b %Y")
            query += " AND created_at LIKE ?"
            params.append(f"%{std_format}%")
        except ValueError:
            pass

    if filter_dept:
        query += " AND department = ?"
        params.append(filter_dept)

    if sort_by == 'oldest':
        query += " ORDER BY id ASC"
    elif sort_by == 'dept_asc':
        query += " ORDER BY department ASC, id DESC"
    elif sort_by == 'dept_desc':
        query += " ORDER BY department DESC, id DESC"
    elif sort_by == 'priority':
        query += " ORDER BY CASE priority WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 WHEN 'LOW' THEN 3 ELSE 4 END ASC, id DESC"
    else:
        query += " ORDER BY id DESC"

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

        complaints.append({
            'id': row['id'],
            'ticket_id': row['ticket_id'],
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
        officer_dept=session.get('officer_dept')
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

    ticket_data = {
        'ticket_id': ticket['ticket_id'],
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
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("UPDATE complaints SET status = 'Resolved', resolution_image = ? WHERE ticket_id = ?",
                       (saved_proof_name, ticket_id))
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

    return redirect('/admin')

# --- Deny & Delete with Epoch Timestamp Log (Auto-deletes in 1 Week) ---
@app.route('/deny_ticket/<ticket_id>', methods=['POST'])
def deny_ticket(ticket_id):
    if not session.get('admin_logged'):
        return redirect('/login')

    reason_category = request.form.get('delete_reason', 'Fake Upload')
    custom_comment = request.form.get('custom_comment', '').strip()
    
    final_reason = reason_category
    if custom_comment:
        final_reason += f" - {custom_comment}"

    officer_name = session.get('officer_name', 'Authorized Officer')
    deleted_at = datetime.now().strftime("%A, %d %b %Y • %I:%M %p")
    deleted_epoch = time.time()  # Store current epoch timestamp for auto-deletion

    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM complaints WHERE ticket_id = ?", (ticket_id,))
    row = cursor.fetchone()

    if row:
        keys = row.keys()
        cursor.execute('''
            INSERT INTO deleted_complaints (ticket_id, description, department, deleted_by, delete_reason, deleted_at, deleted_epoch)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (ticket_id, row['description'], row['department'], officer_name, final_reason, deleted_at, deleted_epoch))

        for col in ['media_name', 'image_name', 'resolution_media', 'resolution_image']:
            if col in keys and row[col]:
                fname = row[col]
                for folder in [CITIZEN_FOLDER, WORK_FOLDER, UPLOAD_FOLDER]:
                    fpath = os.path.join(folder, fname)
                    if os.path.exists(fpath):
                        try:
                            os.remove(fpath)
                        except OSError:
                            pass

    cursor.execute("DELETE FROM complaints WHERE ticket_id = ?", (ticket_id,))
    conn.commit()
    conn.close()

    return redirect('/admin')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)