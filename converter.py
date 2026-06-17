"""Conversion (pivot) d'un CSV de fiches fiscales partenaires.

Le fichier d'ENTRÉE contient une ligne par couple (Partenaire, Catégorie) :

    Partenaire ; Catégorie ; Nº ID fiscale
    20000068   ; FR0       ; FR55389036427
    20000068   ; FR1       ; 3,89036E+13
    20000068   ; FR2       ; 389036427
    ...

Le code de la colonne « Catégorie » a la forme [xx][n] : deux lettres (code
pays, ex. FR) suivies d'un chiffre. Seul ce dernier caractère détermine la
colonne de destination, indépendamment du pays :

    se termine par 1            -> SIRET_xx1
    se termine par 2            -> SIREN_xx2
    se termine par 0 (ou autre) -> TVA intracom_xx0   (destination par défaut)

Tout code ne se terminant pas par 1 ou 2 (0, 3, 4, 5…) alimente la colonne
par défaut « TVA intracom_xx0 ». Si un même partenaire possède plusieurs
codes pointant vers cette colonne (ex. FR0 et FR3), la valeur du code se
terminant par 0 est retenue ; les autres (3, 4, 5…) sont ignorées. À défaut
de code se terminant par 0, la première valeur par défaut rencontrée est
conservée.

Le fichier de SORTIE regroupe (pivot) une ligne par Partenaire :

    Partenaire ; TVA intracom_xx0 ; SIRET_xx1   ; SIREN_xx2
    20000068   ; FR55389036427    ; 3,89036E+13 ; 389036427

Le séparateur (« ; » ou tabulation) et l'encodage sont détectés
automatiquement. Les valeurs sont recopiées telles quelles : une valeur
comme « 3,89036E+13 » est préservée à l'identique (aucune conversion
numérique). Les colonnes sans valeur pour un partenaire restent vides.

Ce module est utilisable :
  * en bibliothèque  : ``convert(text)`` / ``convert_bytes(data)``
  * en ligne de commande : ``python converter.py entree.csv sortie.csv``
"""

from __future__ import annotations

import csv
import io
import unicodedata

# Correspondance « clé de colonne » -> en-tête de colonne. La clé est :
#   "1" si le code catégorie se termine par 1, "2" s'il se termine par 2,
#   "0" dans tous les autres cas (destination par défaut).
# L'ordre des clés fixe l'ordre des colonnes en sortie. Pour adapter l'outil
# (autres libellés), modifiez ce dictionnaire.
DEFAULT_COLUMN_LABELS = {
    "0": "TVA intracom_xx0",
    "1": "SIRET_xx1",
    "2": "SIREN_xx2",
}

# Séparateurs testés, par ordre de priorité en cas d'égalité.
CANDIDATE_DELIMITERS = [";", "\t", ","]

# Encodages testés à la lecture (cas courants des exports FR / Excel).
CANDIDATE_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")


def _strip_accents(text: str) -> str:
    """Supprime les accents pour comparer les en-têtes de façon souple."""
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


def _normalize(text: str) -> str:
    return _strip_accents(text or "").strip().lower()


def detect_delimiter(header_line: str) -> str:
    """Devine le séparateur à partir de la ligne d'en-tête.

    On compte les séparateurs candidats sur l'en-tête uniquement : les
    valeurs (qui peuvent contenir une virgule décimale, ex. « 3,89036E+13 »)
    ne faussent donc pas la détection.
    """
    best = CANDIDATE_DELIMITERS[0]
    best_count = -1
    for delimiter in CANDIDATE_DELIMITERS:
        count = header_line.count(delimiter)
        if count > best_count:
            best_count = count
            best = delimiter
    return best


def decode_bytes(data: bytes) -> str:
    """Décode des octets en testant les encodages courants."""
    for encoding in CANDIDATE_ENCODINGS:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    # latin-1 accepte tous les octets ; filet de sécurité.
    return data.decode("latin-1", errors="replace")


def _find_columns(header: list[str]) -> tuple[int, int, int]:
    """Retourne les indices (partenaire, catégorie, valeur).

    Recherche par mots-clés (insensible à la casse et aux accents), avec
    repli sur les positions 0 / 1 / 2 si une colonne n'est pas reconnue.
    """
    idx_partner = idx_category = idx_value = None
    for i, col in enumerate(header):
        name = _normalize(col)
        if idx_partner is None and "partenaire" in name:
            idx_partner = i
        elif idx_category is None and "categorie" in name:
            idx_category = i
        elif idx_value is None and ("fiscal" in name or "id" in name):
            idx_value = i
    if idx_partner is None:
        idx_partner = 0
    if idx_category is None:
        idx_category = 1
    if idx_value is None:
        idx_value = 2
    return idx_partner, idx_category, idx_value


def convert(text: str, column_labels: dict[str, str] | None = None) -> str:
    """Transforme le contenu CSV d'entrée et renvoie le CSV de sortie (str).

    :param text: contenu du fichier d'entrée.
    :param column_labels: correspondance clé de colonne -> libellé. Par défaut
                          :data:`DEFAULT_COLUMN_LABELS`.
    :raises ValueError: si le fichier est vide ou le format non reconnu.
    """
    if column_labels is None:
        column_labels = DEFAULT_COLUMN_LABELS

    first_line = next((ln for ln in text.splitlines() if ln.strip()), "")
    if not first_line:
        raise ValueError("Le fichier CSV est vide.")
    delimiter = detect_delimiter(first_line)

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = [r for r in reader if any(cell.strip() for cell in r)]
    if not rows:
        raise ValueError("Le fichier CSV est vide.")

    header = rows[0]
    if len(header) < 2:
        raise ValueError(
            "Format non reconnu : séparateur introuvable. "
            "Utilisez un CSV séparé par « ; » ou par tabulation."
        )
    idx_partner, idx_category, idx_value = _find_columns(header)

    def cell(row: list[str], idx: int) -> str:
        return row[idx].strip() if idx < len(row) else ""

    # {partenaire: {"0"|"1"|"2": valeur}} — l'ordre d'apparition est préservé.
    partners: dict[str, dict[str, str]] = {}
    for row in rows[1:]:
        partner = cell(row, idx_partner)
        if not partner:
            continue
        value = cell(row, idx_value)
        last = cell(row, idx_category)[-1:]  # dernier caractère du code, ou ""
        bucket = partners.setdefault(partner, {})
        if last == "1":
            bucket["1"] = value          # ...1 -> SIRET
        elif last == "2":
            bucket["2"] = value          # ...2 -> SIREN
        elif last == "0" or "0" not in bucket:
            # Cas par défaut (se termine par 0, 3, 4, 5…, ou autre).
            # Le code se terminant par 0 est prioritaire et écrase ; sinon on
            # conserve la première valeur par défaut rencontrée.
            bucket["0"] = value

    # Schéma de sortie stable : toujours les trois colonnes connues.
    ordered_keys = list(column_labels)

    out = io.StringIO()
    writer = csv.writer(out, delimiter=delimiter, lineterminator="\r\n")
    header_out = [header[idx_partner].strip() or "Partenaire"]
    header_out += [column_labels.get(k, k) for k in ordered_keys]
    writer.writerow(header_out)
    for partner, values in partners.items():
        writer.writerow([partner] + [values.get(k, "") for k in ordered_keys])

    return out.getvalue()


def convert_bytes(data: bytes, column_labels: dict[str, str] | None = None) -> bytes:
    """Variante octets -> octets.

    Décode l'entrée (encodage détecté) et renvoie un CSV encodé en UTF-8
    avec BOM (``utf-8-sig``) pour une ouverture correcte des accents dans
    Excel.
    """
    text = decode_bytes(data)
    return convert(text, column_labels).encode("utf-8-sig")


def _main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Convertit (pivote) un CSV de fiches fiscales partenaires."
    )
    parser.add_argument("entree", help="Fichier CSV d'entrée")
    parser.add_argument("sortie", help="Fichier CSV de sortie")
    args = parser.parse_args(argv)

    with open(args.entree, "rb") as fh:
        data = fh.read()
    result = convert_bytes(data)
    with open(args.sortie, "wb") as fh:
        fh.write(result)
    print(f"Converti : {args.entree} -> {args.sortie}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
