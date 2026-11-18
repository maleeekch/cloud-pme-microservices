import os
import sqlite3
from flask import Flask, jsonify, request

app = Flask(__name__)
DB = os.getenv("DB_PATH", "/data/catalogue.db")


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    with get_db() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS products ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "name TEXT NOT NULL, price REAL NOT NULL, stock INTEGER NOT NULL)"
        )
        if conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO products (name, price, stock) VALUES (?, ?, ?)",
                [
                    ("Savon d'Alep", 12.5, 40),
                    ("Huile d'argan", 35.0, 15),
                    ("Huile essentielle de lavande", 22.0, 0),
                    ("Crème de karité", 18.0, 25),
                ],
            )


@app.route("/")
def home():
    return jsonify(service="catalogue", status="ok")


@app.route("/products", methods=["GET"])
def list_products():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM products").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/products/<int:product_id>", methods=["GET"])
def get_product(product_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if row is None:
        return jsonify(error="Produit introuvable"), 404
    return jsonify(dict(row))


@app.route("/products", methods=["POST"])
def add_product():
    data = request.get_json(silent=True) or {}
    if not all(k in data for k in ("name", "price", "stock")):
        return jsonify(error="name, price et stock sont obligatoires"), 400
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO products (name, price, stock) VALUES (?, ?, ?)",
            (data["name"], data["price"], data["stock"]),
        )
    return jsonify(id=cur.lastrowid, **data), 201


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)