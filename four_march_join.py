"""Jointure (sur la clé PARTNER) de trois exports CSV de partenaires.

Contexte : trois exports SAP partagent la colonne clé ``PARTNER`` :

  * FOURNISSEUR (BUT000)   — données fournisseurs (raison sociale, etc.) ;
  * TAXNUM (DFKKBPTAXNUM)  — numéros fiscaux (TVA/SIRET/SIREN) ;
  * ZGESS1 (BUT0ID)        — identifiant ZGESS1 (TYPE, IDNUMBER).

La jointure est **pilotée par le fichier ZGESS1** : on ne conserve que les
lignes dont le ``PARTNER`` est présent dans ZGESS1. Les partenaires des autres
fichiers absents de ZGESS1 sont ignorés (drop). Le résultat comporte une ligne
par ligne de ZGESS1, enrichie des colonnes de FOURNISSEUR et de TAXNUM lorsque
le ``PARTNER`` correspond (cellules vides sinon).

Plus généralement, :func:`join` reçoit une liste de fichiers (dans l'ordre des
colonnes voulu en sortie) et l'indice du fichier « pilote » (``driver_index``)
dont les lignes déterminent celles conservées.

Particularités gérées :

  * Double en-tête des exports (noms techniques + libellés français) : la 2e
    ligne est détectée, ignorée comme donnée, et reproduite en sortie.
  * Clé PARTNER alphanumérique (ex. BP001B, BPC001).
  * Doublons : dans le fichier pilote, chaque ligne produit une ligne en
    sortie ; dans les fichiers d'enrichissement, la 1re occurrence est utilisée.
  * Séparateur / encodage détectés (réutilise :mod:`converter`). Sortie en
    UTF-8 + BOM, compatible Excel.
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
    by_key: dict[str, list[str]]      # clé -> ligne (1re occurrence), pour recherche
    data_rows: list[list[str]]        # toutes les lignes de données, dans l'ordre
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

    rest = rows[1:]

    # 2e ligne d'en-tête (libellés FR) : sa cellule clé est un libellé connu.
    french: dict[str, str] = {}
    if rest:
        first = rest[0]
        first_key = first[key_idx].strip().lower() if key_idx < len(first) else ""
        if first_key in aliases:
            french = {
                header[i]: (first[i].strip() if i < len(first) else "")
                for i in range(len(header))
            }
            rest = rest[1:]

    other_idx = [i for i in range(len(header)) if i != key_idx]
    other_cols = [header[i] for i in other_idx]

    data_rows: list[list[str]] = []
    by_key: dict[str, list[str]] = {}
    for row in rest:
        k = row[key_idx].strip() if key_idx < len(row) else ""
        if not k:
            continue
        data_rows.append(row)
        if k not in by_key:           # 1re occurrence conservée (recherche)
            by_key[k] = row

    return _Source(header, french, key_idx, other_idx, other_cols,
                   by_key, data_rows, delimiter)


def join(
    sources: list[bytes],
    driver_index: int,
    key: str = KEY,
    include_french_header: bool = True,
) -> str:
    """Effectue la jointure et renvoie le CSV résultat (str).

    :param sources: contenus des fichiers, **dans l'ordre des colonnes** voulu
                    en sortie (la clé apparaît une seule fois, en tête).
    :param driver_index: indice, dans ``sources``, du fichier « pilote » dont
                         les lignes déterminent celles conservées (les PARTNER
                         absents de ce fichier sont ignorés).
    :param key: nom de la colonne clé (par défaut « PARTNER »).
    :param include_french_header: si vrai, ajoute la 2e ligne d'en-tête
                                   (libellés français) en sortie.
    :raises ValueError: si un fichier est vide ou ``driver_index`` est invalide.
    """
    if not sources:
        raise ValueError("aucun fichier fourni")
    if not -len(sources) <= driver_index < len(sources):
        raise ValueError("driver_index hors limites")

    parsed = [_parse(d, key) for d in sources]
    driver = parsed[driver_index]

    key_header = parsed[0].header[parsed[0].key_idx]

    # En-tête technique : clé + colonnes (hors clé) de chaque source.
    tech = [key_header]
    for src in parsed:
        tech += src.other_cols

    # En-tête « libellés français » : libellé de la clé = 1er disponible.
    key_french = next(
        (src.french.get(src.header[src.key_idx], "")
         for src in parsed if src.french.get(src.header[src.key_idx], "")),
        "",
    )
    french = [key_french]
    for src in parsed:
        french += [src.french.get(c, "") for c in src.other_cols]

    def get(row: list[str], idx: int) -> str:
        return row[idx] if idx < len(row) else ""

    out = io.StringIO()
    writer = csv.writer(out, delimiter=parsed[0].delimiter, lineterminator="\r\n")
    writer.writerow(tech)
    if include_french_header:
        writer.writerow(french)

    # Une ligne de sortie par ligne du fichier pilote.
    for drow in driver.data_rows:
        k = drow[driver.key_idx].strip() if driver.key_idx < len(drow) else ""
        if not k:
            continue
        line = [k]
        for src in parsed:
            if src is driver:
                line += [get(drow, i) for i in src.other_idx]
            else:
                match = src.by_key.get(k)
                if match is None:
                    line += [""] * len(src.other_idx)
                else:
                    line += [get(match, i) for i in src.other_idx]
        writer.writerow(line)

    return out.getvalue()


def join_bytes(
    sources: list[bytes],
    driver_index: int,
    key: str = KEY,
    include_french_header: bool = True,
) -> bytes:
    """Comme :func:`join`, mais renvoie des octets encodés UTF-8 + BOM."""
    result = join(sources, driver_index, key, include_french_header)
    return result.encode("utf-8-sig")
