import os
import sqlite3
from flask import Flask, jsonify, redirect, request, send_from_directory

app = Flask(__name__, static_folder=".")

# Emplacement de la base de données (sécurisé pour Render ou local)
DB_DIR = "/data" if os.path.exists("/data") else "."
DB_NAME = os.path.join(DB_DIR, "hotel_stock.db")


def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS stock (
                article TEXT PRIMARY KEY, quantite INTEGER
            )
        """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ventes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article TEXT, quantite INTEGER, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )
        # Remplissage initial si vide
        cursor.execute("SELECT COUNT(*) FROM stock")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO stock VALUES ('Chambre Standard', 20)")
            cursor.execute("INSERT INTO stock VALUES ('Chambre VIP', 5)")
            cursor.execute("INSERT INTO stock VALUES ('Boisson Royale', 100)")
        conn.commit()


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/api/data", methods=["GET"])
def get_data():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT article, quantite FROM stock")
        stocks = {row[0]: row[1] for row in cursor.fetchall()}
        cursor.execute(
            "SELECT article, quantite, datetime(date, 'localtime') FROM ventes ORDER BY id DESC LIMIT 10"
        )
        ventes = [
            {"article": row[0], "quantite": row[1], "date": row[2]}
            for row in cursor.fetchall()
        ]
    return jsonify({"stocks": stocks, "ventes": ventes})


@app.route("/api/vendre", methods=["POST"])
def vendre():
    data = request.json
    article = data.get("article")
    quantite = int(data.get("quantite", 1))

    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT quantite FROM stock WHERE article = ?", (article,)
        )
        res = cursor.fetchone()
        if res and res[0] >= quantite:
            nouveau_stock = res[0] - quantite
            cursor.execute(
                "UPDATE stock SET quantite = ? WHERE article = ?",
                (nouveau_stock, article),
            )
            cursor.execute(
                "INSERT INTO ventes (article, quantite) VALUES (?, ?)",
                (article, quantite),
            )
            conn.commit()
            return jsonify({"statut": "succès"}), 200
        return jsonify({"erreur": "Stock insuffisant"}), 400


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000)
