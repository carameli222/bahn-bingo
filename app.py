from flask import Flask, request, redirect, make_response, render_template_string
import sqlite3
import os

app = Flask(__name__)

DB_FILE = "db_bingo.sqlite"


def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS reasons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reason TEXT UNIQUE NOT NULL
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS user_reasons (
        user_id INTEGER,
        reason_id INTEGER,
        PRIMARY KEY(user_id, reason_id)
    )
    """)

    conn.commit()
    conn.close()


init_db()


HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>DB-Bingo</title>

<style>

body{
    font-family: Arial;
    max-width: 1000px;
    margin: 40px auto;
    background:#f5f5f5;
}

.card{
    background:white;
    padding:20px;
    border-radius:10px;
    margin-bottom:20px;
}

input[type=text]{
    width:300px;
    padding:10px;
}

button{
    padding:10px;
    cursor:pointer;
}

.progress-container{
    width:100%;
    background:#ddd;
    border-radius:10px;
    overflow:hidden;
}

.progress-bar{
    height:30px;
    background:#1e88e5;
    color:white;
    text-align:center;
    line-height:30px;
}

table{
    width:100%;
    border-collapse:collapse;
}

th,td{
    border:1px solid #ccc;
    padding:8px;
}

</style>

</head>
<body>

<div class="card">
<h1>🚆 DB-Bingo</h1>
<p>Hallo {{ username }}!</p>
</div>

<div class="card">
<h2>Neuen Verspätungsgrund hinzufügen</h2>

<form method="post" action="/add_reason">
<input name="reason" type="text" required placeholder="z.B. Signalstörung">
<button type="submit">Hinzufügen</button>
</form>
</div>

<div class="card">
<h2>Meine Sammlung</h2>

<form method="post" action="/update_checks">

{% for r in reasons %}

<div>
<input
type="checkbox"
name="reason_ids"
value="{{r['id']}}"
{% if r['checked'] %}checked{% endif %}
>

{{r['reason']}}
</div>

{% endfor %}

<br>

<button type="submit">
Speichern
</button>

</form>
</div>

<div class="card">

<h2>Fortschritt</h2>

<div class="progress-container">
<div class="progress-bar" style="width: {{progress}}%;">
{{progress}} %
</div>
</div>

<p>{{completed}} von {{total}} Gründen erlebt.</p>

</div>

<div class="card">

<h2>Rangliste</h2>

<table>
<tr>
<th>Benutzer</th>
<th>Fortschritt</th>
</tr>

{% for u in leaderboard %}
<tr>
<td>{{u['username']}}</td>
<td>{{u['progress']}} %</td>
</tr>
{% endfor %}

</table>

</div>

</body>
</html>
"""


LOGIN_HTML = """
<!DOCTYPE html>
<html>

<head>
<meta charset="utf-8">
<title>DB-Bingo Login</title>

<style>

body{
font-family:Arial;
max-width:700px;
margin:100px auto;
background:#f5f5f5;
}

.card{
background:white;
padding:30px;
border-radius:10px;
}

input{
padding:10px;
width:300px;
}

button{
padding:10px;
}

</style>

</head>

<body>

<div class="card">

<h1>🚆 DB-Bingo</h1>

<h2>Hi, wer bist du?</h2>

<form method="post">

<input
name="username"
required
placeholder="Dein Name"
>

<button type="submit">
Los geht's
</button>

</form>

</div>

</body>

</html>
"""


@app.route("/", methods=["GET", "POST"])
def login():

    username_cookie = request.cookies.get("username")

    if username_cookie:
        return redirect("/dashboard")

    if request.method == "POST":

        username = request.form["username"].strip()

        if username:

            conn = get_db()

            user = conn.execute(
                "SELECT * FROM users WHERE username=?",
                (username,)
            ).fetchone()

            if not user:
                conn.execute(
                    "INSERT INTO users(username) VALUES(?)",
                    (username,)
                )
                conn.commit()

            conn.close()

            resp = make_response(redirect("/dashboard"))
            resp.set_cookie("username", username, max_age=60*60*24*365)

            return resp

    return LOGIN_HTML


@app.route("/dashboard")
def dashboard():

    username = request.cookies.get("username")

    if not username:
        return redirect("/")

    conn = get_db()

    user = conn.execute(
        "SELECT * FROM users WHERE username=?",
        (username,)
    ).fetchone()

    if user is None:
        resp = make_response(redirect("/"))
        resp.delete_cookie("username")

        conn.close()

        return resp

    all_reasons = conn.execute(
        "SELECT * FROM reasons ORDER BY reason"
    ).fetchall()

    checked_ids = {
        row["reason_id"]
        for row in conn.execute(
            "SELECT reason_id FROM user_reasons WHERE user_id=?",
            (user["id"],)
        ).fetchall()
    }

    reasons = []

    for r in all_reasons:
        reasons.append({
            "id": r["id"],
            "reason": r["reason"],
            "checked": r["id"] in checked_ids
        })

    total = len(all_reasons)
    completed = len(checked_ids)

    progress = 0
    if total > 0:
        progress = round(completed / total * 100)

    users = conn.execute(
        "SELECT * FROM users"
    ).fetchall()

    leaderboard = []

    for u in users:

        count = conn.execute(
            """
            SELECT COUNT(*)
            FROM user_reasons
            WHERE user_id=?
            """,
            (u["id"],)
        ).fetchone()[0]

        percent = 0

        if total > 0:
            percent = round(count / total * 100)

        leaderboard.append({
            "username": u["username"],
            "progress": percent
        })

    leaderboard.sort(
        key=lambda x: x["progress"],
        reverse=True
    )

    conn.close()

    return render_template_string(
        HTML,
        username=username,
        reasons=reasons,
        progress=progress,
        completed=completed,
        total=total,
        leaderboard=leaderboard
    )


@app.route("/add_reason", methods=["POST"])
def add_reason():

    username = request.cookies.get("username")

    if not username:
        return redirect("/")

    reason = request.form["reason"].strip()

    if reason:

        conn = get_db()

        try:
            conn.execute(
                "INSERT INTO reasons(reason) VALUES(?)",
                (reason,)
            )
            conn.commit()

        except:
            pass

        conn.close()

    return redirect("/dashboard")


@app.route("/update_checks", methods=["POST"])
def update_checks():

    username = request.cookies.get("username")

    if not username:
        return redirect("/")

    conn = get_db()

    user = conn.execute(
        "SELECT * FROM users WHERE username=?",
        (username,)
    ).fetchone()

    conn.execute(
        "DELETE FROM user_reasons WHERE user_id=?",
        (user["id"],)
    )

    selected = request.form.getlist("reason_ids")

    for rid in selected:
        conn.execute(
            """
            INSERT OR IGNORE INTO user_reasons
            (user_id, reason_id)
            VALUES (?,?)
            """,
            (user["id"], rid)
        )

    conn.commit()
    conn.close()

    return redirect("/dashboard")


@app.route("/logout")
def logout():

    resp = make_response(redirect("/"))
    resp.delete_cookie("username")
    return resp

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
