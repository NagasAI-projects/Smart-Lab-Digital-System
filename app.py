import os
import csv
import io
import sqlite3
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, Response, g
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.environ.get("LAB_DB_PATH", os.path.join(BASE_DIR, "smart_lab.db"))
app = Flask(__name__)
app.secret_key = os.environ.get("LAB_SECRET_KEY", "change-this-secret-before-deployment")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

BRANCHES = ["CSE", "Data Science", "AI & ML", "Cyber Security", "ECE", "EEE", "Mechanical", "Civil", "Other"]
YEARS = ["1st Year", "2nd Year", "3rd Year", "4th Year"]
PURPOSES = ["Programming Practice", "Lab Experiment", "Project Work", "Assignment", "Research", "Other"]

def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH, timeout=15)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.execute("PRAGMA journal_mode = WAL")
    return g.db

@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript("""
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pin TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        branch TEXT NOT NULL,
        year TEXT NOT NULL,
        section TEXT DEFAULT '',
        active INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS systems (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        lab_name TEXT NOT NULL DEFAULT 'Computer Lab 1',
        active INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS visits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL REFERENCES students(id),
        system_id INTEGER NOT NULL REFERENCES systems(id),
        lab_name TEXT NOT NULL,
        purpose TEXT NOT NULL,
        check_in TEXT NOT NULL,
        check_out TEXT DEFAULT NULL
    );
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_visits_checkin ON visits(check_in);
    CREATE INDEX IF NOT EXISTS idx_visits_student ON visits(student_id);
    """)
    # Safe demo records: replace with approved college data only after permission.
    if db.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 0:
        db.executemany("INSERT INTO students(pin,name,branch,year,section) VALUES(?,?,?,?,?)", [
            ("DS001", "Demo Student One", "Data Science", "2nd Year", "A"),
            ("CS001", "Demo Student Two", "CSE", "1st Year", "A"),
            ("AI001", "Demo Student Three", "AI & ML", "3rd Year", "B"),
            ("EC001", "Demo Student Four", "ECE", "2nd Year", "A"),
        ])
    if db.execute("SELECT COUNT(*) FROM systems").fetchone()[0] == 0:
        db.executemany("INSERT INTO systems(code,lab_name) VALUES(?,?)", [
            (f"PC-{i:02d}", "Computer Lab 1") for i in range(1, 31)
        ])
        db.executemany("INSERT INTO systems(code,lab_name) VALUES(?,?)", [
            (f"DSLAB-{i:02d}", "Data Science Lab") for i in range(1, 6)
        ])
    if db.execute("SELECT COUNT(*) FROM admins").fetchone()[0] == 0:
        username = os.environ.get("LAB_ADMIN_USER", "admin")
        password = os.environ.get("LAB_ADMIN_PASSWORD", "ChangeMe123!")
        db.execute("INSERT INTO admins(username,password_hash) VALUES(?,?)",
                   (username, generate_password_hash(password)))
    db.commit()
    db.close()

def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_id"):
            flash("Please sign in to the admin dashboard.", "warning")
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)
    return wrapped

def get_active_visit(student_id):
    return get_db().execute("""
        SELECT v.*, s.pin, s.name, s.branch, s.year, sy.code AS system_code
        FROM visits v JOIN students s ON s.id=v.student_id
        JOIN systems sy ON sy.id=v.system_id
        WHERE v.student_id=? AND v.check_out IS NULL ORDER BY v.id DESC LIMIT 1
    """, (student_id,)).fetchone()

@app.route("/")
def index():
    db = get_db()
    systems = db.execute("SELECT * FROM systems WHERE active=1 ORDER BY lab_name, code").fetchall()
    return render_template("index.html", branches=BRANCHES, years=YEARS, purposes=PURPOSES, systems=systems)

@app.route("/api/student/<pin>")
def student_lookup(pin):
    student = get_db().execute("SELECT pin,name,branch,year,section FROM students WHERE pin=? AND active=1",
                               (pin.strip().upper(),)).fetchone()
    if not student:
        return {"ok": False, "message": "PIN not found. Please check with lab faculty."}, 404
    return {"ok": True, "student": dict(student)}

@app.post("/check-in")
def check_in():
    db = get_db()
    pin = request.form.get("pin", "").strip().upper()
    system_code = request.form.get("system_code", "").strip().upper()
    purpose = request.form.get("purpose", "").strip()
    student = db.execute("SELECT * FROM students WHERE pin=? AND active=1", (pin,)).fetchone()
    system = db.execute("SELECT * FROM systems WHERE code=? AND active=1", (system_code,)).fetchone()
    if not student:
        flash("Student PIN was not found. Use an approved student PIN.", "danger")
        return redirect(url_for("index"))
    if not system:
        flash("Please choose a valid lab computer.", "danger")
        return redirect(url_for("index"))
    if purpose not in PURPOSES:
        flash("Please choose a valid purpose.", "danger")
        return redirect(url_for("index"))
    active = get_active_visit(student["id"])
    if active:
        flash(f"{student['name']} already has an active visit on {active['system_code']}. Check out first.", "warning")
        return redirect(url_for("index"))
    occupied = db.execute("SELECT id FROM visits WHERE system_id=? AND check_out IS NULL", (system["id"],)).fetchone()
    if occupied:
        flash(f"{system_code} is currently marked as occupied. Choose an available system.", "warning")
        return redirect(url_for("index"))
    db.execute("INSERT INTO visits(student_id,system_id,lab_name,purpose,check_in) VALUES(?,?,?,?,?)",
               (student["id"], system["id"], system["lab_name"], purpose, now_iso()))
    db.commit()
    flash(f"Check-in successful for {student['name']} on {system_code}.", "success")
    return redirect(url_for("index"))

@app.post("/check-out")
def check_out():
    db = get_db()
    pin = request.form.get("pin", "").strip().upper()
    student = db.execute("SELECT * FROM students WHERE pin=? AND active=1", (pin,)).fetchone()
    if not student:
        flash("Student PIN was not found.", "danger")
        return redirect(url_for("index"))
    active = get_active_visit(student["id"])
    if not active:
        flash("No active visit found for this PIN.", "warning")
        return redirect(url_for("index"))
    db.execute("UPDATE visits SET check_out=? WHERE id=?", (now_iso(), active["id"]))
    db.commit()
    flash(f"Check-out successful for {student['name']} from {active['system_code']}.", "success")
    return redirect(url_for("index"))

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        admin = get_db().execute("SELECT * FROM admins WHERE username=?", (username,)).fetchone()
        if admin and check_password_hash(admin["password_hash"], password):
            session.clear()
            session["admin_id"] = admin["id"]
            session["admin_username"] = admin["username"]
            return redirect(url_for("dashboard"))
        flash("Incorrect username or password.", "danger")
    return render_template("login.html")

@app.post("/admin/logout")
def admin_logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("index"))

@app.route("/admin")
@admin_required
def dashboard():
    db = get_db()
    date_filter = request.args.get("date", datetime.now().date().isoformat())
    branch_filter = request.args.get("branch", "")
    year_filter = request.args.get("year", "")
    lab_filter = request.args.get("lab", "")
    q = request.args.get("q", "").strip()
    conditions = ["date(v.check_in)=?"]
    params = [date_filter]
    if branch_filter:
        conditions.append("s.branch=?"); params.append(branch_filter)
    if year_filter:
        conditions.append("s.year=?"); params.append(year_filter)
    if lab_filter:
        conditions.append("v.lab_name=?"); params.append(lab_filter)
    if q:
        conditions.append("(s.name LIKE ? OR s.pin LIKE ? OR sy.code LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
    where = " AND ".join(conditions)
    visits = db.execute(f"""
        SELECT v.*, s.pin,s.name,s.branch,s.year,s.section,sy.code AS system_code,
        CASE WHEN v.check_out IS NULL THEN 'Inside' ELSE 'Checked out' END AS status
        FROM visits v JOIN students s ON s.id=v.student_id
        JOIN systems sy ON sy.id=v.system_id WHERE {where}
        ORDER BY v.check_in DESC
    """, params).fetchall()
    total = db.execute("SELECT COUNT(*) FROM visits WHERE date(check_in)=?", (date_filter,)).fetchone()[0]
    inside = db.execute("SELECT COUNT(*) FROM visits WHERE date(check_in)=? AND check_out IS NULL", (date_filter,)).fetchone()[0]
    systems_total = db.execute("SELECT COUNT(*) FROM systems WHERE active=1").fetchone()[0]
    occupied = db.execute("SELECT COUNT(DISTINCT system_id) FROM visits WHERE check_out IS NULL").fetchone()[0]
    labs = db.execute("SELECT DISTINCT lab_name FROM systems WHERE active=1 ORDER BY lab_name").fetchall()
    # Simple hourly analytics for the selected date.
    hourly_rows = db.execute("""
        SELECT strftime('%H', check_in) AS hour, COUNT(*) AS total
        FROM visits WHERE date(check_in)=? GROUP BY hour ORDER BY hour
    """, (date_filter,)).fetchall()
    hourly = {int(r["hour"]): r["total"] for r in hourly_rows}
    return render_template("dashboard.html", visits=visits, total=total, inside=inside,
        systems_total=systems_total, occupied=occupied, date_filter=date_filter,
        branch_filter=branch_filter, year_filter=year_filter, lab_filter=lab_filter, q=q,
        branches=BRANCHES, years=YEARS, labs=labs,
        hours=[f"{h:02d}:00" for h in range(7, 20)],
        hour_values=[hourly.get(h, 0) for h in range(7, 20)])

@app.route("/admin/export.csv")
@admin_required
def export_csv():
    date_filter = request.args.get("date", datetime.now().date().isoformat())
    db = get_db()
    rows = db.execute("""
        SELECT s.pin,s.name,s.branch,s.year,s.section,v.lab_name,sy.code AS system_code,
        v.purpose,v.check_in,v.check_out
        FROM visits v JOIN students s ON s.id=v.student_id
        JOIN systems sy ON sy.id=v.system_id
        WHERE date(v.check_in)=? ORDER BY v.check_in DESC
    """, (date_filter,)).fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["PIN", "Name", "Branch", "Year", "Section", "Lab", "System", "Purpose", "Check-in", "Check-out"])
    for row in rows:
        writer.writerow([row[k] or "" for k in row.keys()])
    return Response("\ufeff" + output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=lab-visits-{date_filter}.csv"})

@app.route("/health")
def health():
    return {"status": "ok", "service": "Smart Lab Digital Registration"}
init_db()

if __name__ == "__main__":
    print("Smart Lab app starting.")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
