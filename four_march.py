"""Application web Flask : jointure (clé PARTNER) de trois exports CSV.

Lancement :

    pip install -r requirements.txt
    python four_march.py

puis ouvrir http://127.0.0.1:5001 dans un navigateur.

(Le convertisseur de fiches fiscales, lui, est servi par ``app.py`` sur le
port 5000 ; les deux applications sont indépendantes.)
"""

from __future__ import annotations

import io

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from four_march_join import join_bytes

MAX_UPLOAD_MB = 100

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
app.secret_key = "four-march-local"


@app.route("/", methods=["GET"])
def index():
    return render_template("four_march.html")


@app.route("/join", methods=["POST"])
def join_route():
    fournisseur = request.files.get("fournisseur")
    taxnum = request.files.get("taxnum")
    zgess1 = request.files.get("zgess1")

    libelles = (
        ("FOURNISSEUR", fournisseur),
        ("TVA (TAXNUM)", taxnum),
        ("ZGESS1", zgess1),
    )
    manquants = [nom for nom, f in libelles if f is None or f.filename == ""]
    if manquants:
        flash("Fichier(s) manquant(s) : " + ", ".join(manquants) + ".")
        return redirect(url_for("index"))

    try:
        result = join_bytes(
            fournisseur.read(),
            [taxnum.read(), zgess1.read()],
        )
    except ValueError as exc:
        flash(f"Jointure impossible : {exc}.")
        return redirect(url_for("index"))
    except Exception as exc:  # garde-fou : pas de 500 brute
        flash(f"Erreur inattendue lors de la jointure : {exc}")
        return redirect(url_for("index"))

    return send_file(
        io.BytesIO(result),
        mimetype="text/csv",
        as_attachment=True,
        download_name="four_march_resultat.csv",
    )


@app.errorhandler(413)
def too_large(_error):
    flash(f"Fichiers trop volumineux (maximum {MAX_UPLOAD_MB} Mo au total).")
    return redirect(url_for("index")), 413


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5001)
