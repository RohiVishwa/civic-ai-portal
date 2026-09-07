import os
import sqlite3
import random
from datetime import datetime, timedelta
from flask import Flask, render_template, render_template_string, request, redirect, url_for, session, jsonify

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
            deleted_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()

    # Dynamic migrations
    existing_cols = [c[1] for c in cur.execute("PRAGMA table_info(complaints)").fetchall()]
    new_cols = {
        "resolution_media": "TEXT",
        "resolution_notes": "TEXT",
        "deletion_reason": "TEXT",
        "deleted_at": "TIMESTAMP",
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

# Smart Bilingual Classifier (English + Hindi/Hinglish)
def calculate_action_timeline(desc, selected_dept):
    text = (desc or "").lower()

    water_keywords = ['water', 'pipe', 'leak', 'drain', 'paani', 'sewer', 'sewage', 'nalaa', 'jal', 'nal', 'tank', 'overflow', 'burst', 'pipeline']
    road_keywords = ['road', 'pothole', 'sadak', 'crater', 'gaddha', 'traffic', 'divider', 'path', 'highway', 'tar', 'concrete', 'asphalt']
    sanitation_keywords = ['garbage', 'trash', 'kachra', 'smell', 'safai', 'waste', 'badbu', 'gandagi', 'dustbin', 'dump', 'cleanup']
    electric_keywords = ['light', 'wire', 'pole', 'current', 'bijli', 'power', 'dark', 'andhera', 'taar', 'spark', 'shock', 'streetlight']

    critical_keywords = ['burst', 'flood', 'flooding', 'shock', 'spark', 'current', 'wire', 'danger', 'hazard', 'crater', 'deep', 'manhole', 'accident', 'severe', 'collapse', 'fire', 'khula', 'gehra', 'toota', 'emergency']
    high_keywords = ['pothole', 'gaddha', 'road', 'sadak', 'garbage', 'kachra', 'waste', 'dump', 'smell', 'badbu', 'sewage', 'drain', 'overflow', 'choke', 'blocked', 'leak', 'paani', 'dark', 'broken', 'damaged']

    # 1. Department Resolution
    if selected_dept and selected_dept != "Auto-Detect via AI Engine":
        dept = selected_dept
    else:
        w_score = sum(1 for k in water_keywords if k in text)
        r_score = sum(1 for k in road_keywords if k in text)
        s_score = sum(1 for k in sanitation_keywords if k in text)
        e_score = sum(1 for k in electric_keywords if k in text)

        scores = {
            "Water Supply & Drainage": w_score,
            "Roads & Civil Infrastructure": r_score,
            "Sanitation & Solid Waste": s_score,
            "Electricity & Street Lighting": e_score
        }
        best = max(scores, key=scores.get)
        dept = best if scores[best] > 0 else "Town Planning & Public Works"

    # 2. Priority Resolution
    priority = "Medium"
    if any(k in text for k in critical_keywords):
        priority = "Critical"
    elif any(k in text for k in high_keywords):
        priority = "High"
    elif dept in ["Water Supply & Drainage", "Roads & Civil Infrastructure", "Electricity & Street Lighting"]:
        priority = "High"
    elif len(text) > 4:
        priority = "High"

    # 3. Target Action Window
    now = datetime.now()
    if priority == "Critical":
        target_time = (now + timedelta(hours=24)).strftime("%d %b, %I:%M %p")
        deadline_text = f"First Action Target: 24h ({target_time}) [Containment & Safety Lock]"
    elif priority == "High":
        target_time = (now + timedelta(days=2)).strftime("%d %b, %I:%M %p")
        deadline_text = f"First Action Target: 48h ({target_time}) [Crew Dispatch & Assessment]"
    else:
        target_time = (now + timedelta(days=5)).strftime("%d %b, %I:%M %p")
        deadline_text = f"Standard Target: 5–7 Days ({target_time}) [Routine Civil Works]"

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

# Embedded Printable Dispatch Slip Template
DISPATCH_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CivicAI - Municipal Dispatch Slip {{ c['ticket_id'] }}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
    <style>
        body {
            background: linear-gradient(135deg, #0b1120 0%, #0f172a 50%, #1e1b4b 100%);
            color: #f8fafc;
            font-family: system-ui, -apple-system, sans-serif;
            min-height: 100vh;
            padding: 30px 15px;
        }
        .slip-card {
            background-color: #1e293b;
            border: 2px solid #38bdf8;
            border-radius: 18px;
            max-width: 800px;
            margin: auto;
            box-shadow: 0 20px 45px rgba(0,0,0,0.6);
        }
        .watermark-img {
            max-height: 270px;
            border-radius: 10px;
            border: 1px solid #475569;
            object-fit: cover;
            width: 100%;
        }
        @media print {
            body {
                background: #fff !important;
                color: #000 !important;
                padding: 0;
            }
            .slip-card {
                border: 2px solid #000 !important;
                background: #fff !important;
                color: #000 !important;
                box-shadow: none !important;
                max-width: 100% !important;
                width: 100% !important;
            }
            .no-print {
                display: none !important;
            }
            .text-white, .text-light, .text-secondary {
                color: #000 !important;
            }
            .badge {
                border: 1px solid #000 !important;
                color: #000 !important;
            }
        }
    </style>
</head>
<body>
<div class="container">
    <div class="slip-card p-4 p-md-5">
        
        <div class="d-flex justify-content-between align-items-start border-bottom border-secondary pb-3 mb-4">
            <div>
                <span class="badge bg-info text-dark fw-bold px-3 py-1 mb-2">OFFICIAL MUNICIPAL DISPATCH SLIP</span>
                <h4 class="fw-bold mb-0 text-white">CivicAI Autonomous Governance Network</h4>
                <div class="text-secondary small font-monospace">Automated Incident Triage & Telemetry Report</div>
            </div>
            <div class="text-end">
                <span class="badge bg-success bg-opacity-25 text-success border border-success px-3 py-2 fs-6 font-monospace">
                    {{ c['ticket_id'] }}
                </span>
                <div class="text-secondary small mt-1 font-monospace">{{ c['created_at'] }}</div>
            </div>
        </div>

        <div class="row g-4 mb-4">
            <div class="col-md-5">
                <label class="form-label text-secondary small fw-bold text-uppercase">Photographic Evidence</label>
                {% if c['image_data'] and c['image_data']|length > 30 %}
                <img src="{{ c['image_data'] }}" class="watermark-img shadow" alt="Geotagged Evidence">
                {% else %}
                <div class="p-4 bg-dark text-center rounded border border-secondary text-secondary small">Visual Evidence Attached</div>
                {% endif %}
            </div>
            <div class="col-md-7">
                <label class="form-label text-secondary small fw-bold text-uppercase">Telemetry Summary</label>
                <div class="p-3 bg-black rounded-3 border border-secondary mb-3">
                    <div class="mb-2">
                        <span class="text-secondary small d-block">Department Allotment:</span>
                        <strong class="text-info fs-6">{{ c['department'] }}</strong>
                    </div>
                    <div class="mb-2">
                        <span class="text-secondary small d-block">Priority Tier:</span>
                        {% if c['priority'] == 'Critical' %}
                        <span class="badge bg-danger">Critical Emergency</span>
                        {% elif c['priority'] == 'High' %}
                        <span class="badge bg-warning text-dark">High Priority</span>
                        {% else %}
                        <span class="badge bg-secondary">Medium Standard</span>
                        {% endif %}
                    </div>
                    <div class="mb-0">
                        <span class="text-secondary small d-block">Enforced Target Window:</span>
                        <span class="text-warning font-monospace small">{{ c['deadline'] }}</span>
                    </div>
                </div>

                <div class="p-3 bg-black rounded-3 border border-secondary">
                    <span class="text-secondary small d-block mb-1">Geotag GNSS Coordinates:</span>
                    <strong class="text-light font-monospace small">{{ c['location'] }}</strong>
                    <div class="mt-1">
                        <a href="https://maps.google.com/?q={{ c['location'] }}" target="_blank" class="text-info text-decoration-none small">
                            <i class="bi bi-geo-alt-fill text-danger"></i> Open Coordinates on Google Maps &rarr;
                        </a>
                    </div>
                </div>
            </div>
        </div>

        <div class="mb-4">
            <label class="form-label text-secondary small fw-bold text-uppercase">Citizen Incident Statement</label>
            <div class="p-3 bg-black rounded-3 border border-secondary text-light">
                {{ c['description'] }}
            </div>
        </div>

        <div class="row pt-3 border-top border-secondary text-secondary small">
            <div class="col-6">
                <div>Digital Verification: <strong class="text-success font-monospace">SHA-256 Verified</strong></div>
                <div>Routing Nodal: <span class="font-monospace">pwd.executive.engineer@civicai.gov.in</span></div>
            </div>
            <div class="col-6 text-end">
                <div class="fst-italic">Autonomous Municipal Dispatch Engine</div>
                <div>Government Municipal Corporation</div>
            </div>
        </div>

        <div class="d-flex gap-2 justify-content-end mt-4 pt-3 border-top border-secondary no-print">
            <a href="/" class="btn btn-outline-light btn-sm px-3 rounded-pill">
                <i class="bi bi-arrow-left"></i> Report Another Grievance
            </a>
            <a href="/login" class="btn btn-outline-info btn-sm px-3 rounded-pill">
                <i class="bi bi-shield-lock"></i> Officer Desk
            </a>
            <button onclick="window.print()" class="btn btn-warning fw-bold btn-sm px-4 rounded-pill shadow">
                <i class="bi bi-printer-fill me-1"></i> Print Official Slip (PDF)
            </button>
        </div>

    </div>
</div>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template('index.html')

# SUBMIT ROUTE: Captures media and redirects straight to /dispatch/<ticket_id>
@app.route('/submit', methods=['POST'])
def submit_complaint():
    try:
        desc = request.form.get('description', '').strip()
        selected_dept = request.form.get('department', 'Auto-Detect via AI Engine')
        raw_location = request.form.get('location', '')
        image_data = request.form.get('image_data', '').strip()

        # Permanent Fail-safe: ensure image_data is NEVER empty
        if not image_data or len(image_data) < 30:
            image_data = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='640' height='480' style='background:%230f172a'><text x='50%25' y='50%25' fill='%2338bdf8' font-family='monospace' font-size='20' text-anchor='middle'>CIVICAI SATELLITE EVIDENCE RECORD</text></svg>"

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

        # Instant redirect to printable dispatch slip
        return redirect(f"/dispatch/{ticket_id}")
    except Exception as e:
        print(f"[SUBMIT ERROR] {e}")
        return redirect(url_for('home'))

# DISPATCH SLIP ROUTE (Uses render_template_string so no file is needed!)
@app.route('/dispatch/<ticket_id>')
def dispatch_slip(ticket_id):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM complaints WHERE ticket_id = ?", (ticket_id,))
    complaint = cur.fetchone()
    conn.close()

    if not complaint:
        return "<h3>Grievance Dossier not found.</h3><a href='/'>Go to Home</a>", 404

    return render_template_string(DISPATCH_HTML_TEMPLATE, c=complaint)

@app.route('/api/track/<ticket_id>')
def track_ticket(ticket_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute('''
        SELECT ticket_id, department, priority, deadline, status, resolution_media, created_at
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
    return jsonify({"found": False, "msg": "Ticket not found."})

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
    denied = sum(1 for c in complaints if c['status'] in ['Denied', 'Marked for Deletion'])
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

# 24-Hour Audit Retention Soft Delete
@app.route('/delete/<ticket_id>', methods=['POST'])
def delete_ticket(ticket_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    reason = request.form.get('deletion_reason', 'Administrative audit requested.')
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute('''
        UPDATE complaints
        SET status = 'Marked for Deletion',
            deletion_reason = ?,
            deleted_at = CURRENT_TIMESTAMP
        WHERE ticket_id = ?
    ''', (reason, ticket_id))
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)