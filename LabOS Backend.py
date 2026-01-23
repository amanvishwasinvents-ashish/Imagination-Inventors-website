from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import jwt
import datetime
from functools import wraps

# ---------------- CONFIG ----------------
SECRET_KEY = "CHANGE_THIS_SECRET"
DB_PATH = "lab_os.db"

# Hard-coded users (v0.1)
USERS = {
    "aman": {
        "password": "admin123",  # CHANGE
        "role": "admin"
    },
    "builder1": {
        "password": "builder123",  # CHANGE
        "role": "builder"
    }
}

# ---------------- APP ----------------
app = Flask(__name__)
CORS(app)

# ---------------- DB ----------------
def get_db():
    return sqlite3.connect(DB_PATH)


def init_db():
    db = get_db()
    cur = db.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        description TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS work_units (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER,
        title TEXT,
        description TEXT,
        owner TEXT,
        status TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS updates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        work_unit_id INTEGER,
        user TEXT,
        text TEXT,
        timestamp TEXT
    )
    """)

    db.commit()
    db.close()

# ---------------- AUTH ----------------
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization")
        if not token:
            return jsonify({"error": "Token missing"}), 401
        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            request.user = data
        except Exception:
            return jsonify({"error": "Invalid token"}), 401
        return f(*args, **kwargs)
    return decorated


@app.route("/login", methods=["POST"])
def login():
    data = request.json
    user = USERS.get(data.get("username"))

    if not user or user["password"] != data.get("password"):
        return jsonify({"error": "Invalid credentials"}), 401

    token = jwt.encode({
        "username": data["username"],
        "role": user["role"],
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=8)
    }, SECRET_KEY, algorithm="HS256")

    return jsonify({"token": token, "role": user["role"]})

# ---------------- PROJECTS ----------------
@app.route("/projects", methods=["GET", "POST"])
@token_required
def projects():
    db = get_db()
    cur = db.cursor()

    if request.method == "POST":
        if request.user["role"] != "admin":
            return jsonify({"error": "Forbidden"}), 403
        cur.execute("INSERT INTO projects (name, description) VALUES (?, ?)",
                    (request.json["name"], request.json.get("description", "")))
        db.commit()

    cur.execute("SELECT * FROM projects")
    rows = cur.fetchall()
    db.close()

    return jsonify([{ "id": r[0], "name": r[1], "description": r[2] } for r in rows])

# ---------------- WORK UNITS ----------------
@app.route("/work-units", methods=["GET", "POST"])
@token_required
def work_units():
    db = get_db()
    cur = db.cursor()

    if request.method == "POST":
        if request.user["role"] != "admin":
            return jsonify({"error": "Forbidden"}), 403
        cur.execute("""
            INSERT INTO work_units (project_id, title, description, owner, status)
            VALUES (?, ?, ?, ?, ?)
        """, (
            request.json["project_id"],
            request.json["title"],
            request.json.get("description", ""),
            request.json["owner"],
            "idea"
        ))
        db.commit()

    cur.execute("SELECT * FROM work_units")
    rows = cur.fetchall()
    db.close()

    return jsonify([{
        "id": r[0],
        "project_id": r[1],
        "title": r[2],
        "description": r[3],
        "owner": r[4],
        "status": r[5]
    } for r in rows])

# ---------------- STATUS UPDATE ----------------
@app.route("/work-units/<int:wid>/status", methods=["POST"])
@token_required
def update_status(wid):
    status = request.json["status"]
    user = request.user["username"]

    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT owner FROM work_units WHERE id = ?", (wid,))
    row = cur.fetchone()

    if not row or row[0] != user:
        return jsonify({"error": "Forbidden"}), 403

    cur.execute("UPDATE work_units SET status = ? WHERE id = ?", (status, wid))
    db.commit()
    db.close()

    return jsonify({"success": True})

# ---------------- START ----------------
if __name__ == "__main__":
    init_db()
    app.run(debug=True)
