import os
import sqlite3
from flask import Flask, jsonify, redirect, request, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, static_folder=".")

# Base de données intégrée pour s'adapter parfaitement au plan gratuit Render
DB_NAME = "hotel_royal_gratuit.db"


def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS utilisateurs (
                role TEXT PRIMARY KEY, password_hash TEXT
            )
        """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS stock (
                article TEXT PRIMARY KEY, quantite INTEGER, prix_achat REAL, prix_vente REAL
            )
        """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ventes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article TEXT, quantite INTEGER, total REAL, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS depenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                motif TEXT, montant REAL, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS credits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom_client TEXT, motif TEXT, montant REAL, statut TEXT DEFAULT 'En attente', date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chambres (
                numero TEXT PRIMARY KEY, statut TEXT, type TEXT
            )
        """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS salaires (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mois_annee TEXT, statut_reception TEXT DEFAULT 'Confirmé', date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Insertion des accès par défaut
        cursor.execute("SELECT COUNT(*) FROM utilisateurs")
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "INSERT INTO utilisateurs VALUES ('patron', ?)",
                (generate_password_hash("patron123"),),
            )
            cursor.execute(
                "INSERT INTO utilisateurs VALUES ('gerant', ?)",
                (generate_password_hash("gerant123"),),
            )

        # Insertion du stock initial
        cursor.execute("SELECT COUNT(*) FROM stock")
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "INSERT INTO stock VALUES ('Chambre Standard', 15, 12000, 30000)"
            )
            cursor.execute(
                "INSERT INTO stock VALUES ('Chambre VIP', 5, 25000, 75000)"
            )
            cursor.execute(
                "INSERT INTO stock VALUES ('Boisson Royale', 100, 2000, 4000)"
            )

            for i in range(101, 106):
                cursor.execute(
                    f"INSERT INTO chambres VALUES ('{i}', 'Libre', 'Standard')"
                )
            for i in range(201, 204):
                cursor.execute(
                    f"INSERT INTO chambres VALUES ('{i}', 'Libre', 'VIP')"
                )
        conn.commit()


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    role = data.get("role")
    password = data.get("password")

    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT password_hash FROM utilisateurs WHERE role = ?", (role,)
        )
        res = cursor.fetchone()
        if res and check_password_hash(res[0], password):
            return jsonify({"statut": "success", "role": role})
    return jsonify({"erreur": "Mot de passe incorrect"}), 401


@app.route("/api/modifier_password", methods=["POST"])
def modifier_password():
    data = request.json
    role_cible = data.get("role_cible")
    nouveau_password = data.get("nouveau_password")

    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        hashed = generate_password_hash(nouveau_password)
        cursor.execute(
            "UPDATE utilisateurs SET password_hash = ? WHERE role = ?",
            (hashed, role_cible),
        )
        conn.commit()
    return jsonify({"statut": "success"})


@app.route("/api/donnees_completes", methods=["GET"])
def get_donnees():
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM stock")
        stocks = [dict(r) for r in cursor.fetchall()]

        cursor.execute(
            "SELECT id, article, quantite, total, datetime(date, 'localtime') as dt FROM ventes ORDER BY id DESC"
        )
        ventes = [dict(r) for r in cursor.fetchall()]

        cursor.execute(
            "SELECT id, motif, montant, datetime(date, 'localtime') as dt FROM depenses ORDER BY id DESC"
        )
        depenses = [dict(r) for r in cursor.fetchall()]

        cursor.execute(
            "SELECT id, nom_client, motif, montant, statut, datetime(date, 'localtime') as dt FROM credits ORDER BY id DESC"
        )
        credits = [dict(r) for r in cursor.fetchall()]

        cursor.execute("SELECT * FROM chambres ORDER BY numero ASC")
        chambres = [dict(r) for r in cursor.fetchall()]

        cursor.execute(
            "SELECT id, mois_annee, datetime(date, 'localtime') as dt FROM salaires ORDER BY id DESC"
        )
        salaires = [dict(r) for r in cursor.fetchall()]

    return jsonify(
        {
            "stocks": stocks,
            "ventes": ventes,
            "depenses": depenses,
            "credits": credits,
            "chambres": chambres,
            "salaires": salaires,
        }
    )


@app.route("/api/action", methods=["POST"])
def executer_action():
    data = request.json
    action = data.get("action")

    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()

        if action == "vente":
            article = data.get("article")
            qte = int(data.get("quantite", 1))
            cursor.execute(
                "SELECT quantite, prix_vente FROM stock WHERE article = ?",
                (article,),
            )
            res = cursor.fetchone()

            # Extraction sécurisée des éléments du tuple SQLite (0 = Quantité, 1 = Prix Vente)
            if res and res[0] >= qte:
                prix_de_vente = res[1]
                total = qte * prix_de_vente
                cursor.execute(
                    "UPDATE stock SET quantite = quantite - ? WHERE article = ?",
                    (qte, article),
                )
                cursor.execute(
                    "INSERT INTO ventes (article, quantite, total) VALUES (?, ?, ?)",
                    (article, qte, total),
                )
            else:
                return jsonify({"erreur": "Stock insuffisant"}), 400

        elif action == "depense":
            cursor.execute(
                "INSERT INTO depenses (motif, montant) VALUES (?, ?)",
                (data.get("motif"), float(data.get("montant"))),
            )

        elif action == "credit":
            cursor.execute(
                "INSERT INTO credits (nom_client, motif, montant, statut) VALUES (?, ?, ?, 'En attente')",
                (
                    data.get("nom_client"),
                    data.get("motif"),
                    float(data.get("montant")),
                ),
            )

        elif action == "rembourser":
            cursor.execute(
                "UPDATE credits SET statut = 'Remboursé' WHERE id = ?",
                (int(data.get("id")),),
            )

        elif action == "chambre_statut":
            cursor.execute(
                "UPDATE chambres SET statut = ? WHERE numero = ?",
                (data.get("statut"), data.get("numero")),
            )

        elif action == "salaire":
            cursor.execute(
                "INSERT INTO salaires (mois_annee) VALUES (?)",
                (data.get("mois_annee"),),
            )

        elif action == "ajouter_stock":
            cursor.execute(
                "INSERT OR REPLACE INTO stock VALUES (?, ?, ?, ?)",
                (
                    data.get("article"),
                    int(data.get("quantite")),
                    float(data.get("prix_achat")),
                    float(data.get("prix_vente")),
                ),
            )

        elif action == "supprimer_stock":
            cursor.execute(
                "DELETE FROM stock WHERE article = ?", (data.get("article"),)
            )

        conn.commit()
    return jsonify({"statut": "success"})


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000)
