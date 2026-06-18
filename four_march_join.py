"""Jointure (sur la clé PARTNER) de trois exports CSV de partenaires.

Contexte : on dispose de trois exports SAP partageant la colonne clé
``PARTNER`` :

  * FOURNISSEUR (BUT000)        — table de référence (tous les partenaires) ;
  * TAXNUM (DFKKBPTAXNUM)       — numéros fiscaux (TVA/SIRET/SIREN) ;
  * ZGESS1 (BUT0ID)             — identifiant ZGESS1 (TYPE, IDNUMBER).

La jointure est un *left join* sur FOURNISSEUR : on conserve **tous** les
partenaires du fichier de base et on ajoute les colonnes des autres fichiers
quand le PARTNER correspond (cellules vides sinon).

Particularités gérées :

  * Les exports ont une 1re ligne d'en-tête « technique » (PARTNER, BU_GROUP…)
    et parfois une 2e ligne de libellés français (Partenaire, Regroupement…).
    Cette 2e ligne est détectée, ignorée comme donnée, et reproduite en sortie.
  * La clé PARTNER peut être alphanumérique (ex. BP001B, BPC001).
  * Si un partenaire apparaît plusieurs fois dans un fichier, la première
    occurrence est conservée.
  * Séparateur (« ; » ou tabulation) et encodage détectés automatiquement
    (réutilise :mod:`converter`). Sortie en UTF-8 + BOM, compatible Excel.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass

from converter import decode_bytes, detect_delimiter

KEY = "PARTNER"

# Valeurs de la colonne clé qui désignent une ligne d'en-tête (et non une
# donnée) : sert à repérer la 2e ligne d'en-tête « libellés français ».
_KEY_ALIASES = {"partner", "partenaire"}


@dataclass
class _Source:
    """Représentation d'un fichier source analysé."""

    header: list[str]                 # noms techniques des colonnes
    french: dict[str, str]            # nom technique -> libellé FR (peut être vide)
    key_idx: int                      # index de la colonne clé
    other_idx: list[int]              # index des colonnes hors clé
    other_cols: list[str]             # noms techniques des colonnes hors clé
    by_key: dict[str, list[str]]      # clé -> ligne (1re occurrence)
    order: list[str]                  # clés dans l'ordre d'apparition
    delimiter: str


def _parse(data: bytes, key: str) -> _Source:
    """Analyse un fichier CSV (octets) en une structure :class:`_Source`."""
    text = decode_bytes(data)
    first_line = next((ln for ln in text.splitlines() if ln.strip()), "")
    if not first_line:
        raise ValueError("un fichier est vide")
    delimiter = detect_delimiter(first_line)

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = [r for r in reader if any(c.strip() for c in r)]
    if not rows:
        raise ValueError("un fichier est vide")

    header = [c.strip() for c in rows[0]]
    aliases = _KEY_ALIASES | {key.lower()}
    key_idx = next(
        (i for i, c in enumerate(header) if c.lower() in aliases),
        0,
    )

    data_rows = rows[1:]

    # 2e ligne d'en-tête (libellés FR) : sa cellule clé est un libellé connu.
    french: dict[str, str] = {}
    if data_rows:
        first = data_rows[0]
        first_key = first[key_idx].strip().lower() if key_idx < len(first) else ""
        if first_key in aliases:
            french = {
                header[i]: (first[i].strip() if i < len(first) else "")
                for i in range(len(header))
            }
            data_rows = data_rows[1:]

    other_idx = [i for i in range(len(header)) if i != key_idx]
    other_cols = [header[i] for i in other_idx]

    by_key: dict[str, list[str]] = {}
    order: list[str] = []
    for row in data_rows:
        k = row[key_idx].strip() if key_idx < len(row) else ""
        if not k:
            continue
        if k not in by_key:           # 1re occurrence conservée
            by_key[k] = row
            order.append(k)

    return _Source(header, french, key_idx, other_idx, other_cols,
                   by_key, order, delimiter)


def join(
    base_data: bytes,
    enrich_data: list[bytes],
    key: str = KEY,
    include_french_header: bool = True,
) -> str:
    """Effectue la jointure et renvoie le CSV résultat (str).

    :param base_data: contenu du fichier de base (left join), ex. FOURNISSEUR.
    :param enrich_data: contenus des fichiers d'enrichissement, dans l'ordre
                        des colonnes voulu en sortie.
    :param key: nom de la colonne clé (par défaut « PARTNER »).
    :param include_french_header: si vrai, ajoute la 2e ligne d'en-tête
                                   (libellés français) en sortie.
    :raises ValueError: si un fichier est vide.
    """
    base = _parse(base_data, key)
    enrich = [_parse(d, key) for d in enrich_data]

    # En-tête technique : clé + colonnes de la base + colonnes des enrichissements.
    tech = [base.header[base.key_idx]] + base.other_cols
    for src in enrich:
        tech += src.other_cols

    # En-tête « libellés français » (vide quand non disponible).
    french = [base.french.get(base.header[base.key_idx], "")]
    french += [base.french.get(c, "") for c in base.other_cols]
    for src in enrich:
        french += [src.french.get(c, "") for c in src.other_cols]

    def get(row: list[str], idx: int) -> str:
        return row[idx] if idx < len(row) else ""

    out = io.StringIO()
    writer = csv.writer(out, delimiter=base.delimiter, lineterminator="\r\n")
    writer.writerow(tech)
    if include_french_header:
        writer.writerow(french)

    for k in base.order:
        base_row = base.by_key[k]
        line = [k] + [get(base_row, i) for i in base.other_idx]
        for src in enrich:
            src_row = src.by_key.get(k)
            if src_row is None:
                line += [""] * len(src.other_idx)
            else:
                line += [get(src_row, i) for i in src.other_idx]
        writer.writerow(line)

    return out.getvalue()


def join_bytes(
    base_data: bytes,
    enrich_data: list[bytes],
    key: str = KEY,
    include_french_header: bool = True,
) -> bytes:
    """Comme :func:`join`, mais renvoie des octets encodés UTF-8 + BOM."""
    result = join(base_data, enrich_data, key, include_french_header)
    return result.encode("utf-8-sig")
