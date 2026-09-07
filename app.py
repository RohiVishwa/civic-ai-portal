import os
import uuid
import base64
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, jsonify

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "civicai.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ----------------- DATABASE INITIALIZATION -----------------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
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
    conn.commit()
    conn.close()

init_db()

# ----------------- AI CLASSIFICATION ENGINE -----------------
def classify_grievance(text):
    text_lower = text.lower()
    
    # Priority Detection
    priority = "Medium"
    if any(w in text_lower for w in ["urgent", "danger", "burst", "shock", "fire", "spark", "accident", "overflowing", "deadly", "emergency", "current"]):
        priority = "Critical"
    elif any(w in text_lower for w in ["pothole", "deep", "block", "no water", "dark", "huge", "broken", "gaddha"]):
        priority = "High"

    # Department Auto-Triage
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

# ----------------- ROUTES -----------------
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
    loc = request.form.get('location', '30.730376, 76.168847')
    img_data = request.form.get('image_data', '')

    # AI Department & Priority Triage
    ai_dept, ai_priority = classify_grievance(desc)
    final_dept = ai_dept if dept == "Auto-Detect via AI Engine" else dept

    ticket_num = str(uuid.uuid4().int)[:5]
    ticket_id = f"GOV-CIVIC-{ticket_num}"

    # Handle image saving (compressed base64 data URL)
    saved_filename = ""
    if img_data and "base64," in img_data:
        try:
            header, encoded = img_data.split("base64,", 1)
            file_bytes = base64.b64decode(encoded)
            saved_filename = f"{ticket_id}_{uuid.uuid4().hex[:6]}.jpg"
            file_path = os.path.join(UPLOAD_FOLDER, saved_filename)
            with open(file_path, "wb") as f:
                f.write(file_bytes)
        except Exception as e:
            print("Error decoding base64 image:", e)

    now = datetime.now()
    created_at = now.strftime("%Y-%m-%d %H:%M")

    # Priority-based SLA calculation
    if ai_priority == "Critical":
        sla_hours = 24
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
    """, (ticket_id, desc, final_dept, ai_priority, created_at, deadline, loc, saved_filename))
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
            body {{
                background: linear-gradient(135deg, #0b1120 0%, #0f172a 50%, #1e1b4b 100%);
                color: #f8fafc;
                font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }}
            .res-card {{
                background: #1e293b;
                border: 1px solid #38bdf8;
                border-radius: 20px;
                box-shadow: 0 20px 30px -10px rgba(0, 0, 0, 0.6);
                max-width: 520px;
                width: 100%;
            }}
            .ticket-badge {{
                background: #0f172a;
                border: 1px solid #334155;
            }}
        </style>
    </head>
    <body>
        <div class="res-card p-4 p-md-5 text-center shadow-lg">
            <div class="d-inline-flex align-items-center justify-content-center bg-info bg-opacity-10 text-info rounded-circle mb-3" style="width: 70px; height: 70px;">
                <i class="bi bi-check-circle-fill fs-1 text-info"></i>
            </div>
            
            <h3 class="fw-bold text-white mb-1">Grievance Dispatched</h3>
            <p class="text-secondary small mb-4">AI auto-triage has locked coordinates and routed this issue to the municipal desk.</p>

            <div class="ticket-badge p-3 rounded-3 text-start mb-4">
                <div class="d-flex justify-content-between align-items-center mb-2 pb-2 border-bottom border-secondary">
                    <span class="text-secondary small">Ticket ID:</span>
                    <div>
                        <span class="text-info font-monospace fw-bold me-2" id="ticketIdTxt">{ticket_id}</span>
                        <button class="btn btn-outline-secondary btn-sm py-0 px-2 text-light" onclick="copyTicket()" title="Copy to clipboard">
                            <i class="bi bi-clipboard" id="copyIcon"></i>
                        </button>
                    </div>
                </div>
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <span class="text-secondary small">Department:</span>
                    <span class="fw-semibold text-light">{final_dept}</span>
                </div>
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <span class="text-secondary small">Assigned Priority:</span>
                    <span class="badge bg-{badge_color}">{ai_priority}</span>
                </div>
                <div class="d-flex justify-content-between align-items-center">
                    <span class="text-secondary small">{sla_label}:</span>
                    <span class="font-monospace text-light fw-bold">{deadline}</span>
                </div>
            </div>

            <div class="d-grid gap-2">
                <button onclick="window.print()" class="btn btn-outline-light py-2">
                    <i class="bi bi-printer"></i> Print Acknowledgement Slip
                </button>
                <a href="/" class="btn btn-info fw-bold py-2">
                    <i class="bi bi-arrow-left"></i> Back to Citizen Portal
                </a>
            </div>
        </div>

        <script>
        function copyTicket() {{
            const tid = document.getElementById('ticketIdTxt').innerText;
            navigator.clipboard.writeText(tid).then(() => {{
                const icon = document.getElementById('copyIcon');
                icon.className = 'bi bi-check2 text-success';
                setTimeout(() => {{ icon.className = 'bi bi-clipboard'; }}, 2000);
            }});
        }}
        </script>
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
            SELECT ticket_id, department, priority, status, created_at, deadline, damage_media, resolution_media, location 
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
                "location": row["location"]
            })
        return jsonify({"found": False, "msg": "Ticket ID not found in municipal records."})
    except Exception as e:
        return jsonify({"found": False, "msg": str(e)})

# ----------------- ADMIN DASHBOARD -----------------
@app.route('/admin')
def admin_panel():
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

    return render_template('admin.html', complaints=complaints, total=total, pending=pending, resolved=resolved, denied=denied)

@app.route('/admin/resolve/<int:cid>', methods=['POST'])
def resolve_ticket(cid):
    file = request.files.get('resolution_photo')
    filename = ""
    if file and file.filename != "":
        filename = f"resolved_{cid}_{uuid.uuid4().hex[:6]}.jpg"
        file.save(os.path.join(UPLOAD_FOLDER, filename))

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE complaints SET status = 'Resolved', resolution_media = ? WHERE id = ?", (filename, cid))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/admin/deny/<int:cid>', methods=['POST'])
def deny_ticket(cid):
    reason = request.form.get('denial_reason', 'Spam / Out of Jurisdiction')
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE complaints SET status = 'Denied', denial_reason = ? WHERE id = ?", (reason, cid))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port, debug=True)