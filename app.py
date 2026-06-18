"""Application web Flask regroupant les deux outils CSV.

Une page d'accueil propose deux outils partageant la même application :

  * Convertisseur de fiches fiscales (pivot)   ->  /convertisseur
  * Jointure « four_march » de trois exports   ->  /jointure

Lancement :

    pip install -r requirements.txt
    python app.py

puis ouvrir http://127.0.0.1:5000 et choisir un outil.

Les logiques métier vivent dans des modules séparés et restent réutilisables
en bibliothèque ou en CLI :
  * ``converter.py``        (conversion / pivot)
  * ``four_march_join.py``  (jointure)
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
from four_march_join import join_bytes

MAX_UPLOAD_MB = 100

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
app.secret_key = "ecf-script-local"


@app.route("/")
def home():
    return render_template("home.html")


# --- Outil 1 : convertisseur de fiches fiscales -----------------------------

@app.route("/convertisseur", methods=["GET"])
def converter_page():
    return render_template("index.html")


@app.route("/convertisseur/convertir", methods=["POST"])
def converter_convert():
    file = request.files.get("fichier")
    if file is None or file.filename == "":
        flash("Aucun fichier sélectionné.")
        return redirect(url_for("converter_page"))

    try:
        result = convert_bytes(file.read())
    except ValueError as exc:
        flash(f"Conversion impossible : {exc}")
        return redirect(url_for("converter_page"))
    except Exception as exc:  # garde-fou : pas de 500 brute
        flash(f"Erreur inattendue lors de la conversion : {exc}")
        return redirect(url_for("converter_page"))

    base = file.filename.rsplit(".", 1)[0] or "sortie"
    return send_file(
        io.BytesIO(result),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"{base}_converti.csv",
    )


# --- Outil 2 : jointure four_march ------------------------------------------

@app.route("/jointure", methods=["GET"])
def join_page():
    return render_template("four_march.html")


@app.route("/jointure/joindre", methods=["POST"])
def join_run():
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
        return redirect(url_for("join_page"))

    try:
        result = join_bytes(
            fournisseur.read(),
            [taxnum.read(), zgess1.read()],
        )
    except ValueError as exc:
        flash(f"Jointure impossible : {exc}.")
        return redirect(url_for("join_page"))
    except Exception as exc:  # garde-fou : pas de 500 brute
        flash(f"Erreur inattendue lors de la jointure : {exc}")
        return redirect(url_for("join_page"))

    return send_file(
        io.BytesIO(result),
        mimetype="text/csv",
        as_attachment=True,
        download_name="four_march_resultat.csv",
    )


@app.errorhandler(413)
def too_large(_error):
    flash(f"Fichier(s) trop volumineux (maximum {MAX_UPLOAD_MB} Mo).")
    return redirect(url_for("home")), 413


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
