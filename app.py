"""Application web Flask : conversion (pivot) de CSV de fiches fiscales.

Lancement :

    pip install -r requirements.txt
    python app.py

puis ouvrir http://127.0.0.1:5000 dans un navigateur.
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

from converter import convert_bytes

MAX_UPLOAD_MB = 10

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
# Clé requise pour les messages flash. Application locale : valeur fixe.
app.secret_key = "ecf-script-local"


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/convert", methods=["POST"])
def convert_route():
    file = request.files.get("fichier")
    if file is None or file.filename == "":
        flash("Aucun fichier sélectionné.")
        return redirect(url_for("index"))

    try:
        result = convert_bytes(file.read())
    except ValueError as exc:
        flash(f"Conversion impossible : {exc}")
        return redirect(url_for("index"))
    except Exception as exc:  # garde-fou : on ne montre jamais une 500 brute
        flash(f"Erreur inattendue lors de la conversion : {exc}")
        return redirect(url_for("index"))

    base = file.filename.rsplit(".", 1)[0] or "sortie"
    out_name = f"{base}_converti.csv"

    return send_file(
        io.BytesIO(result),
        mimetype="text/csv",
        as_attachment=True,
        download_name=out_name,
    )


@app.errorhandler(413)
def too_large(_error):
    flash(f"Fichier trop volumineux (maximum {MAX_UPLOAD_MB} Mo).")
    return redirect(url_for("index")), 413


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
