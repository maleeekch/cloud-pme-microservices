import os
import sqlite3
from datetime import datetime

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)
DB = os.getenv("DB_PATH", "/data/commandes.db")
CATALOGUE_URL = os.getenv("CATALOGUE_URL", "http://catalogue:8000")
NOTIFICATIONS_URL = os.getenv("NOTIFICATIONS_URL", "http://notifications:8000")


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    with get_db() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS orders ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "product_id INTEGER NOT NULL, product_name TEXT NOT NULL, "
            "quantity INTEGER NOT NULL, total REAL NOT NULL, "
            "customer_email TEXT NOT NULL, created_at TEXT NOT NULL)"
        )


@app.route("/")
def home():
    return jsonify(service="commandes", status="ok")


@app.route("/orders", methods=["POST"])
def create_order():
    data = request.get_json(silent=True) or {}
    if not all(k in data for k in ("product_id", "quantity", "customer_email")):
        return jsonify(error="product_id, quantity et customer_email sont obligatoires"), 400
    if not isinstance(data["quantity"], int) or data["quantity"] < 1:
        return jsonify(error="quantity doit etre un entier positif"), 400

    # 1) Appel au service Catalogue
    try:
        r = requests.get(f"{CATALOGUE_URL}/products/{data['product_id']}", timeout=5)
    except requests.exceptions.RequestException:
        return jsonify(error="Service Catalogue indisponible"), 503
    if r.status_code == 404:
        return jsonify(error="Produit introuvable"), 404
    if r.status_code != 200:
        return jsonify(error="Erreur du service Catalogue"), 502
    product = r.json()

    # 2) Verification du stock
    if product["stock"] < data["quantity"]:
        return jsonify(error="Stock insuffisant", stock_disponible=product["stock"]), 409

    # 3) Enregistrement de la commande (base propre au service)
    total = round(product["price"] * data["quantity"], 2)
    created_at = datetime.now().isoformat(timespec="seconds")
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO orders (product_id, product_name, quantity, total, customer_email, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (product["id"], product["name"], data["quantity"], total, data["customer_email"], created_at),
        )
    order = {
        "id": cur.lastrowid,
        "product_id": product["id"],
        "product_name": product["name"],
        "quantity": data["quantity"],
        "total": total,
        "customer_email": data["customer_email"],
        "created_at": created_at,
    }

    # 4) Notification (si le service est en panne, la commande reste valide)
    try:
        n = requests.post(
            f"{NOTIFICATIONS_URL}/notify",
            json={"to": order["customer_email"], "order_id": order["id"], "total": total},
            timeout=3,
        )
        notification = "envoyee" if n.status_code == 200 else "echec"
    except requests.exceptions.RequestException:
        notification = "indisponible"

    return jsonify(order=order, notification=notification), 201


@app.route("/orders", methods=["GET"])
def list_orders():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/orders/<int:order_id>", methods=["GET"])
def get_order(order_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if row is None:
        return jsonify(error="Commande introuvable"), 404
    return jsonify(dict(row))


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)