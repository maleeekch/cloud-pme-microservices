import os
import sqlite3
from datetime import datetime

from flask import Flask, jsonify, request

app = Flask(__name__)
DB = os.getenv("DB_PATH", "/data/notifications.db")


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    with get_db() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS notifications ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "recipient TEXT NOT NULL, order_id INTEGER NOT NULL, "
            "message TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL)"
        )


@app.route("/")
def home():
    return jsonify(service="notifications", status="ok")


@app.route("/notify", methods=["POST"])
def notify():
    data = request.get_json(silent=True) or {}
    if not all(k in data for k in ("to", "order_id", "total")):
        return jsonify(error="to, order_id et total sont obligatoires"), 400

    message = f"Bonjour, votre commande n°{data['order_id']} d'un montant de {data['total']} TND est confirmee."
    created_at = datetime.now().isoformat(timespec="seconds")

    # Simulation de l'envoi d'un email (visible dans les logs du conteneur)
    print(f"[EMAIL] a: {data['to']} | {message}", flush=True)

    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO notifications (recipient, order_id, message, status, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (data["to"], data["order_id"], message, "envoyee", created_at),
        )
    return jsonify(id=cur.lastrowid, status="envoyee", to=data["to"], message=message), 200


@app.route("/notifications", methods=["GET"])
def list_notifications():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM notifications ORDER BY id DESC").fetchall()
    return jsonify([dict(r) for r in rows])


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)