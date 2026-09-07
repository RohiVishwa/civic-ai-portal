import os
import uuid
import base64
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, jsonify, session

app = Flask(__name__)
app.secret_key = "civicai_officer_master_secure_production_key"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "civicai.db")

# ----------------- DATABASE SETUP & PERSISTENT INITIALIZATION -----------------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    # Complaints Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT UNIQUE,
            description TEXT,
            department TEXT,
            priority TEXT,
            status TEXT DEFAULT 'Pending',
            created_at TEXT,
            deadline TEXT,
            location TEXT,
            damage_media TEXT,
            resolution_media TEXT,
            denial_reason TEXT
        )
    """)
    
    # Officers Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS officers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            officer_id TEXT UNIQUE,
            department TEXT,
            password TEXT
        )
    """)

    # Default Officer
    cur.execute("SELECT * FROM officers WHERE officer_id = 'officer'")
    if not cur.fetchone():
        cur.execute("""
            INSERT INTO officers (name, officer_id, department, password)
            VALUES ('Chief Municipal Commissioner', 'officer', 'Municipal Administration', 'admin123')
        """)

    # Seed demo complaints if table is completely empty
    cur.execute("SELECT COUNT(*) FROM complaints")
    count = cur.fetchone()[0]
    if count == 0:
        now = datetime.now()
        pipe_svg = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='100' height='100'><rect width='100' height='100' fill='%230284c7'/><circle cx='50' cy='50' r='20' fill='%2338bdf8'/><text x='50' y='85' fill='white' font-size='11' text-anchor='middle' font-family='sans-serif'>Water Pipe</text></svg>"
        pothole_svg = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='100' height='100'><rect width='100' height='100' fill='%23334155'/><ellipse cx='50' cy='50' rx='35' ry='18' fill='%230f172a'/><text x='50' y='85' fill='white' font-size='11' text-anchor='middle' font-family='sans-serif'>Road Crater</text></svg>"
        waste_svg = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='100' height='100'><rect width='100' height='100' fill='%23059669'/><rect x='30' y='30' width='40' height='40' rx='4' fill='%2310b981'/><text x='50' y='85' fill='white' font-size='11' text-anchor='middle' font-family='sans-serif'>Garbage</text></svg>"

        sample_tickets = [
            ("GOV-CIVIC-89102", "Severe pipeline burst near main market chowk. Clean drinking water flooding the road.", "Water Supply", "Critical", "Pending", (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M"), (now + timedelta(hours=22)).strftime("%Y-%m-%d %H:%M"), "30.731100, 76.169500", pipe_svg),
            ("GOV-CIVIC-44219", "Deep crater pothole in the middle of sector road causing accidents at night.", "Roads & Transport", "High", "Pending", (now - timedelta(hours=8)).strftime("%Y-%m-%d %H:%M"), (now + timedelta(days=2)).strftime("%Y-%m-%d %H:%M"), "30.729500, 76.167200", pothole_svg),
            ("GOV-CIVIC-31045", "Street garbage container overflowing with foul smell near school entrance.", "Sanitation & Waste", "Medium", "Pending", (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M"), (now + timedelta(days=6)).strftime("%Y-%m-%d %H:%M"), "30.728900, 76.171000", waste_svg)
        ]
        cur.executemany("""
            INSERT INTO complaints (ticket_id, description, department, priority, status, created_at, deadline, location, damage_media)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, sample_tickets)

    conn.commit()
    conn.close()

init_db()

# ----------------- AI CLASSIFIER -----------------
def classify_grievance(text):
    text_lower = text.lower()
    priority = "Medium"
    if any(w in text_lower for w in ["urgent", "danger", "burst", "shock", "fire", "spark", "accident", "overflowing", "deadly", "emergency", "current"]):
        priority = "Critical"
    elif any(w in text_lower for w in ["pothole", "deep", "block", "no water", "dark", "huge", "broken", "gaddha"]):
        priority = "High"

    if any(w in text_lower for w in ["water", "pipe", "pipeline", "leak", "sewer", "drain", "tank", "paani", "nali"]):
        department = "Water Supply"
    elif any(w in text_lower for w in ["road", "pothole", "street", "traffic", "divider", "footpath", "highway", "gaddha", "sadak"]):
        department = "Roads & Transport"
    elif any(w in text_lower for w in ["garbage", "trash", "waste", "smell", "dustbin", "clean", "dump", "kachra", "safai"]):
        department = "Sanitation & Waste"
    elif any(w in text_lower for w in ["light", "wire", "pole", "electric", "power", "transformer", "blackout", "bijli", "taar"]):
        department = "Electricity & Power"
    else:
        department = "Town Planning"

    return department, priority

# ----------------- CITIZEN ROUTES -----------------
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/submit', methods=['POST', 'GET'])
@app.route('/report', methods=['POST', 'GET'])
def submit_grievance():
    if request.method == 'GET':
        return redirect(url_for('home'))

    desc = request.form.get('description', '').strip()
    dept = request.form.get('department', 'Auto-Detect via AI Engine')
    loc = request.form.get('location', '30.730376, 76.168847').strip()
    img_data = request.form.get('image_data', '').strip()

    ai_dept, ai_priority = classify_grievance(desc)
    final_dept = ai_dept if dept == "Auto-Detect via AI Engine" else dept

    ticket_num = str(uuid.uuid4().int)[:5]
    ticket_id = f"GOV-CIVIC-{ticket_num}"

    now = datetime.now()
    created_at = now.strftime("%Y-%m-%d %H:%M")

    if ai_priority == "Critical":
        sla_label = "24-Hour Emergency SLA"
        deadline = (now + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M")
        badge_color = "danger"
    elif ai_priority == "High":
        sla_label = "3-Day High Priority SLA"
        deadline = (now + timedelta(days=3)).strftime("%Y-%m-%d %H:%M")
        badge_color = "warning text-dark"
    else:
        sla_label = "7-Day Standard SLA"
        deadline = (now + timedelta(days=7)).strftime("%Y-%m-%d %H:%M")
        badge_color = "info text-dark"

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO complaints (ticket_id, description, department, priority, status, created_at, deadline, location, damage_media)
        VALUES (?, ?, ?, ?, 'Pending', ?, ?, ?, ?)
    """, (ticket_id, desc, final_dept, ai_priority, created_at, deadline, loc, img_data))
    conn.commit()
    conn.close()

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Grievance Dispatched | CivicAI</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
        <style>
            body {{ background: #0b1120; color: #f8fafc; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; font-family: sans-serif; }}
            .card-box {{ background: #1e293b; border: 1px solid #38bdf8; border-radius: 18px; max-width: 480px; width: 100%; }}
        </style>
    </head>
    <body>
        <div class="card-box p-4 text-center shadow-lg">
            <div class="d-inline-flex p-3 rounded-circle bg-info bg-opacity-10 text-info mb-3">
                <i class="bi bi-check-circle-fill fs-1 text-info"></i>
            </div>
            <h4 class="fw-bold text-white mb-1">Grievance Dispatched</h4>
            <p class="text-secondary small mb-3">Incident successfully locked and routed to municipal desk.</p>
            
            <div class="bg-dark p-3 rounded-3 text-start mb-3 border border-secondary">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <span class="text-secondary small">Ticket ID:</span>
                    <div>
                        <span class="text-info font-monospace fw-bold me-2">{ticket_id}</span>
                        <button class="btn btn-sm btn-outline-secondary py-0 px-2 text-white" onclick="navigator.clipboard.writeText('{ticket_id}'); alert('Ticket ID Copied!');"><i class="bi bi-clipboard"></i></button>
                    </div>
                </div>
                <div class="d-flex justify-content-between mb-2">
                    <span class="text-secondary small">Department:</span>
                    <span class="text-light fw-semibold">{final_dept}</span>
                </div>
                <div class="d-flex justify-content-between mb-2">
                    <span class="text-secondary small">Priority:</span>
                    <span class="badge bg-{badge_color}">{ai_priority}</span>
                </div>
                <div class="d-flex justify-content-between">
                    <span class="text-secondary small">{sla_label}:</span>
                    <span class="font-monospace text-light fw-bold">{deadline}</span>
                </div>
            </div>

            <div class="d-grid gap-2">
                <button onclick="window.print()" class="btn btn-outline-light"><i class="bi bi-printer"></i> Print Slip</button>
                <a href="/" class="btn btn-info fw-bold"><i class="bi bi-arrow-left"></i> Return Home</a>
            </div>
        </div>
    </body>
    </html>
    """

# ----------------- PUBLIC TRACKING API -----------------
@app.route('/api/track/<ticket_id>', methods=['GET'])
def track_ticket(ticket_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT ticket_id, department, priority, status, created_at, deadline, damage_media, resolution_media, denial_reason, location 
            FROM complaints WHERE ticket_id = ?
        """, (ticket_id.strip(),))
        row = cur.fetchone()
        conn.close()

        if row:
            return jsonify({
                "found": True,
                "ticket_id": row["ticket_id"],
                "department": row["department"],
                "priority": row["priority"],
                "status": row["status"],
                "created_at": row["created_at"],
                "deadline": row["deadline"],
                "damage_media": row["damage_media"],
                "resolution_media": row["resolution_media"],
                "denial_reason": row["denial_reason"],
                "location": row["location"]
            })
        return jsonify({"found": False, "msg": "No ticket found with this ID."})
    except Exception as e:
        return jsonify({"found": False, "msg": str(e)})

# ----------------- OFFICER AUTH -----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        uid = (request.form.get('officer_id') or request.form.get('username') or '').strip().lower()
        pwd = (request.form.get('password') or '').strip()

        if (uid in ["officer", "officer@civic.gov", "admin"]) and (pwd in ["admin123", "civicadmin@2026"]):
            session['officer_logged_in'] = True
            session['officer_name'] = "Chief Officer"
            session['officer_dept'] = "Municipal Administration"
            return redirect(url_for('admin_panel'))
        else:
            error = "Invalid credentials. Use ID: officer | Pass: admin123"

    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ----------------- OFFICER ADMIN PANEL -----------------
@app.route('/admin')
def admin_panel():
    if not session.get('officer_logged_in'):
        return redirect(url_for('login'))

    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM complaints ORDER BY id DESC")
    complaints = cur.fetchall()

    total = len(complaints)
    pending = sum(1 for c in complaints if c["status"] == "Pending")
    resolved = sum(1 for c in complaints if c["status"] == "Resolved")
    denied = sum(1 for c in complaints if c["status"] == "Denied")
    conn.close()

    return render_template('admin.html', 
                           complaints=complaints, 
                           total=total, 
                           pending=pending, 
                           resolved=resolved, 
                           denied=denied,
                           officer_name=session.get('officer_name', 'Chief Officer'),
                           officer_dept=session.get('officer_dept', 'Municipal Administration'))

# ----------------- RESOLVE & DENY ROUTING -----------------
@app.route('/admin/resolve/<path:identifier>', methods=['POST'])
@app.route('/resolve/<path:identifier>', methods=['POST'])
def resolve_ticket(identifier):
    if not session.get('officer_logged_in'):
        return redirect(url_for('login'))

    file = request.files.get('resolution_photo')
    base64_proof = ""
    if file and file.filename != "":
        encoded = base64.b64encode(file.read()).decode('utf-8')
        base64_proof = f"data:image/jpeg;base64,{encoded}"

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        UPDATE complaints 
        SET status = 'Resolved', resolution_media = ? 
        WHERE id = ? OR ticket_id = ?
    """, (base64_proof, identifier, identifier))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/admin/deny/<path:identifier>', methods=['POST'])
@app.route('/deny/<path:identifier>', methods=['POST'])
def deny_ticket(identifier):
    if not session.get('officer_logged_in'):
        return redirect(url_for('login'))

    reason = request.form.get('denial_reason', 'Out of Jurisdiction')
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        UPDATE complaints 
        SET status = 'Denied', denial_reason = ? 
        WHERE id = ? OR ticket_id = ?
    """, (reason, identifier, identifier))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

# ----------------- MANDATORY AUDITED DELETE -----------------
@app.route('/admin/delete/<path:identifier>', methods=['POST'])
@app.route('/delete/<path:identifier>', methods=['POST'])
def delete_ticket(identifier):
    if not session.get('officer_logged_in'):
        return redirect(url_for('login'))

    reason = request.form.get('delete_reason', '').strip()
    if not reason:
        reason = "Deleted without reason"

    print(f"[AUDIT LOG] Officer {session.get('officer_name')} deleted ticket {identifier} | Justification: {reason}")

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DELETE FROM complaints WHERE id = ? OR ticket_id = ?", (identifier, identifier))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port, debug=True)