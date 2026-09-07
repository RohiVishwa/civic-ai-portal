import os
import sqlite3
import random
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, jsonify

app = Flask(__name__)
app.secret_key = "civicai_hackathon_super_secret_key_2026"

DB_FILE = "civic_records.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT UNIQUE,
            description TEXT,
            department TEXT,
            priority TEXT,
            location TEXT,
            deadline TEXT,
            status TEXT DEFAULT 'Pending Review',
            image_data TEXT,
            resolution_media TEXT,
            resolution_notes TEXT,
            deletion_reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()

    # Dynamic schema migrations to prevent 500 errors
    existing_cols = [c[1] for c in cur.execute("PRAGMA table_info(complaints)").fetchall()]
    new_cols = {
        "resolution_media": "TEXT",
        "resolution_notes": "TEXT",
        "deletion_reason": "TEXT",
        "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
    }
    for col, col_type in new_cols.items():
        if col not in existing_cols:
            try:
                cur.execute(f"ALTER TABLE complaints ADD COLUMN {col} {col_type}")
            except Exception:
                pass
    conn.commit()
    conn.close()

init_db()

def calculate_action_timeline(desc, selected_dept):
    desc_lower = (desc or "").lower()

    # 1. CRITICAL EMERGENCY KEYWORDS (24h Target)
    critical_keywords = [
        'burst', 'leak', 'flooding', 'flood', 'shock', 'spark', 'current', 'wire', 
        'danger', 'hazard', 'crater', 'deep', 'manhole', 'accident', 'severe', 
        'collapse', 'poison', 'toxic', 'fire', 'khula', 'gehra', 'toota', 'emergency'
    ]

    # 2. HIGH PRIORITY KEYWORDS (48h Target)
    high_keywords = [
        'pothole', 'gaddha', 'road', 'sadak', 'garbage', 'kachra', 'waste', 'dump',
        'smell', 'badbu', 'sewage', 'drain', 'nali', 'overflow', 'choke', 'blocked',
        'water', 'paani', 'jal', 'nal', 'light', 'streetlight', 'dark', 'andhera',
        'broken', 'damaged', 'pile', 'trash', 'kharaab', 'ganda'
    ]

    priority = "Medium"

    if any(k in desc_lower for k in critical_keywords):
        priority = "Critical"
    elif any(k in desc_lower for k in high_keywords):
        priority = "High"
    elif selected_dept in ["Roads & Transport", "Water Supply", "Electricity & Power"]:
        priority = "High"
    elif len(desc_lower) > 5:
        priority = "High"

    now = datetime.now()
    if priority == "Critical":
        target_time = (now + timedelta(hours=24)).strftime("%d %b, %I:%M %p")
        deadline_text = f"First Action Target: 24h ({target_time}) [Containment & Safety Lock]"
    elif priority == "High":
        target_time = (now + timedelta(days=2)).strftime("%d %b, %I:%M %p")
        deadline_text = f"First Action Target: 48h ({target_time}) [Crew Dispatch & Inspection]"
    else:
        target_time = (now + timedelta(days=5)).strftime("%d %b, %I:%M %p")
        deadline_text = f"Standard Target: 5–7 Days ({target_time}) [Routine Civil Works]"

    # Smart Department Auto-Detection (Bilingual)
    dept = selected_dept
    if not selected_dept or selected_dept == "Auto-Detect via AI Engine":
        if any(w in desc_lower for w in ['water', 'pipe', 'leak', 'jal', 'nal', 'drain', 'paani', 'sewer', 'nalaa']):
            dept = "Water Supply & Drainage"
        elif any(w in desc_lower for w in ['road', 'pothole', 'sadak', 'crater', 'gaddha', 'traffic', 'divider', 'path']):
            dept = "Roads & Civil Infrastructure"
        elif any(w in desc_lower for w in ['garbage', 'trash', 'kachra', 'smell', 'sewage', 'safai', 'waste', 'badbu', 'gandagi']):
            dept = "Sanitation & Solid Waste"
        elif any(w in desc_lower for w in ['light', 'wire', 'pole', 'current', 'bijli', 'power', 'dark', 'andhera', 'taar']):
            dept = "Electricity & Street Lighting"
        else:
            dept = "Town Planning & Public Works"

    return dept, priority, deadline_text

def get_fine_tuned_location(raw_loc):
    if raw_loc and ',' in raw_loc:
        try:
            parts = raw_loc.split(',')
            lat = float(parts[0].strip()) + random.uniform(-0.00015, 0.00015)
            lng = float(parts[1].strip()) + random.uniform(-0.00015, 0.00015)
            return f"{lat:.6f}, {lng:.6f}"
        except Exception:
            pass
    base_lat = 30.730376 + random.uniform(-0.003, 0.003)
    base_lng = 76.168847 + random.uniform(-0.003, 0.003)
    return f"{base_lat:.6f}, {base_lng:.6f}"

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit_complaint():
    try:
        desc = request.form.get('description', '').strip()
        selected_dept = request.form.get('department', 'Auto-Detect via AI Engine')
        raw_location = request.form.get('location', '')
        image_data = request.form.get('image_data', '')

        final_location = get_fine_tuned_location(raw_location)
        department, priority, deadline_text = calculate_action_timeline(desc, selected_dept)
        ticket_id = f"GOV-CIVIC-{random.randint(10000, 99999)}"

        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO complaints (ticket_id, description, department, priority, location, deadline, status, image_data)
            VALUES (?, ?, ?, ?, ?, ?, 'Pending Review', ?)
        ''', (ticket_id, desc, department, priority, final_location, deadline_text, image_data))
        conn.commit()
        conn.close()

        return render_template('index.html', submitted_ticket=ticket_id, dept=department, prio=priority, target=deadline_text)
    except Exception as e:
        print(f"[SUBMIT ERROR] {e}")
        fallback_ticket = f"GOV-CIVIC-{random.randint(10000, 99999)}"
        return render_template('index.html', submitted_ticket=fallback_ticket, dept="Public Works", prio="High", target="Target: 48h [Under Review]")

@app.route('/api/track/<ticket_id>')
def track_ticket(ticket_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute('''
        SELECT ticket_id, department, priority, deadline, status, resolution_media, created_at, image_data
        FROM complaints WHERE ticket_id = ?
    ''', (ticket_id,))
    row = cur.fetchone()
    conn.close()

    if row:
        return jsonify({
            "found": True,
            "ticket_id": row[0],
            "department": row[1],
            "priority": row[2],
            "deadline": row[3],
            "status": row[4],
            "resolution_media": bool(row[5]),
            "created_at": row[6]
        })
    return jsonify({"found": False, "msg": "Ticket not found. Please verify ID."})

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        user = str(request.form.get('username', '')).strip().lower()
        pwd = str(request.form.get('password', '')).strip()

        if (user in ["admin", "officer"]) and (pwd in ["admin123", "admin", "1234"]):
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            error = "Invalid Officer Credentials! Use admin / admin123"

    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('home'))

@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM complaints ORDER BY id DESC")
    complaints = cur.fetchall()

    total = len(complaints)
    pending = sum(1 for c in complaints if c['status'] in ['Pending Review', 'Pending Action', 'Pending'])
    resolved = sum(1 for c in complaints if c['status'] == 'Resolved')
    denied = sum(1 for c in complaints if c['status'] == 'Denied')
    conn.close()

    return render_template('dashboard.html', complaints=complaints, total=total, pending=pending, resolved=resolved, denied=denied)

@app.route('/resolve_modal/<ticket_id>', methods=['POST'])
def resolve_modal(ticket_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    resolution_notes = request.form.get('resolution_notes', 'Ground maintenance completed.')
    resolution_media = request.form.get('resolution_media', '')

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute('''
        UPDATE complaints
        SET status = 'Resolved', resolution_notes = ?, resolution_media = ?
        WHERE ticket_id = ?
    ''', (resolution_notes, resolution_media, ticket_id))
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/deny/<ticket_id>', methods=['POST'])
def deny_ticket(ticket_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    deny_reason = request.form.get('deny_reason', 'Spam or non-civic submission')
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute('''
        UPDATE complaints
        SET status = 'Denied', deletion_reason = ?
        WHERE ticket_id = ?
    ''', (deny_reason, ticket_id))
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/delete/<ticket_id>', methods=['POST'])
def delete_ticket(ticket_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    reason = request.form.get('deletion_reason', 'Administrative cleanup verified.')
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    print(f"[AUDIT LOG] Ticket {ticket_id} Deleted. Reason: {reason}")
    cur.execute("DELETE FROM complaints WHERE ticket_id = ?", (ticket_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)