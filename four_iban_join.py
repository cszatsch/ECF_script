"""Jointure four_iban : rattache l'IBAN à chaque coordonnée bancaire partenaire.

Deux exports SAP sont mis en jointure :

  * BUT0K  — coordonnées bancaires par partenaire :
             PARTNER ; BKVID ; BANKS ; BANKL ; BANKN ; BKONT ; KOINH
  * TIBAN  — table des IBAN :
             BANKS ; BANKL ; BANKN ; BKONT ; IBAN ; ERDAT ; TABKEY

La clé de jointure est **composite** : (BANKS, BANKL, BANKN, BKONT), c'est-à-dire
l'identification du compte bancaire (pays/région, clé banque, compte, clé RIB).

La jointure est **pilotée par BUT0K** : une ligne de sortie par ligne de BUT0K,
enrichie des colonnes propres à TIBAN (IBAN, ERDAT, TABKEY) lorsque la clé
correspond (cellules vides sinon). Les colonnes communes (la clé) ne sont pas
dupliquées : elles proviennent de BUT0K.

Particularités gérées :

  * Double en-tête des exports (noms techniques + libellés français) : la 2e
    ligne est détectée (présence de minuscules), ignorée comme donnée, et
    reproduite en sortie.
  * Si une même clé apparaît plusieurs fois dans TIBAN, la 1re est utilisée.
  * Séparateur / encodage détectés (réutilise :mod:`converter`). Sortie en
    UTF-8 + BOM, compatible Excel.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass

from converter import decode_bytes, detect_delimiter

# Clé de jointure composite par défaut (identification du compte bancaire).
DEFAULT_KEY_COLUMNS = ("BANKS", "BANKL", "BANKN", "BKONT")


@dataclass
class _Source:
    header: list[str]
    french: dict[str, str]          # nom technique -> libellé FR (peut être vide)
    data_rows: list[list[str]]
    delimiter: str


def _is_label_row(row: list[str]) -> bool:
    """Vrai si la ligne ressemble à des libellés (2e en-tête FR).

    Les lignes de données de ces exports SAP sont en majuscules (codes,
    identifiants, raisons sociales) ; la ligne de libellés français contient,
    elle, des minuscules (« Partenaire », « Clé bancaire »…).
    """
    return any(ch.islower() for cell in row for ch in cell)


def _parse(data: bytes) -> _Source:
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
    rest = rows[1:]

    french: dict[str, str] = {}
    if rest and _is_label_row(rest[0]):
        labels = rest[0]
        french = {
            header[i]: (labels[i].strip() if i < len(labels) else "")
            for i in range(len(header))
        }
        rest = rest[1:]

    return _Source(header, french, rest, delimiter)


def _key_indices(header: list[str], key_columns: tuple[str, ...]) -> list[int]:
    lower = [c.lower() for c in header]
    indices = []
    for name in key_columns:
        try:
            indices.append(lower.index(name.lower()))
        except ValueError:
            raise ValueError(f"colonne clé « {name} » absente d'un fichier")
    return indices


def join(
    driver_data: bytes,
    lookup_data: bytes,
    key_columns: tuple[str, ...] = DEFAULT_KEY_COLUMNS,
    include_french_header: bool = True,
) -> str:
    """Effectue la jointure et renvoie le CSV résultat (str).

    :param driver_data: fichier pilote (BUT0K), dont chaque ligne est conservée.
    :param lookup_data: fichier consulté (TIBAN), source des colonnes ajoutées.
    :param key_columns: noms des colonnes formant la clé composite.
    :param include_french_header: ajoute la 2e ligne d'en-tête (libellés FR).
    :raises ValueError: fichier vide ou colonne clé manquante.
    """
    driver = _parse(driver_data)
    lookup = _parse(lookup_data)

    d_key_idx = _key_indices(driver.header, key_columns)
    l_key_idx = _key_indices(lookup.header, key_columns)
    l_key_set = set(l_key_idx)

    # Colonnes de TIBAN à ajouter = celles qui ne font pas partie de la clé.
    l_extra_idx = [i for i in range(len(lookup.header)) if i not in l_key_set]
    l_extra_cols = [lookup.header[i] for i in l_extra_idx]

    def composite(row: list[str], idxs: list[int]) -> tuple[str, ...]:
        return tuple(row[i].strip() if i < len(row) else "" for i in idxs)

    # Index TIBAN : clé composite -> ligne (1re occurrence).
    by_key: dict[tuple[str, ...], list[str]] = {}
    for row in lookup.data_rows:
        k = composite(row, l_key_idx)
        if k not in by_key:
            by_key[k] = row

    # En-têtes de sortie : colonnes de BUT0K + colonnes propres de TIBAN.
    tech = list(driver.header) + l_extra_cols
    french = [driver.french.get(c, "") for c in driver.header]
    french += [lookup.french.get(c, "") for c in l_extra_cols]

    def get(row: list[str], idx: int) -> str:
        return row[idx] if idx < len(row) else ""

    out = io.StringIO()
    writer = csv.writer(out, delimiter=driver.delimiter, lineterminator="\r\n")
    writer.writerow(tech)
    if include_french_header:
        writer.writerow(french)

    for drow in driver.data_rows:
        driver_part = [get(drow, i) for i in range(len(driver.header))]
        match = by_key.get(composite(drow, d_key_idx))
        if match is None:
            extra = [""] * len(l_extra_idx)
        else:
            extra = [get(match, i) for i in l_extra_idx]
        writer.writerow(driver_part + extra)

    return out.getvalue()


def join_bytes(
    driver_data: bytes,
    lookup_data: bytes,
    key_columns: tuple[str, ...] = DEFAULT_KEY_COLUMNS,
    include_french_header: bool = True,
) -> bytes:
    """Comme :func:`join`, mais renvoie des octets encodés UTF-8 + BOM."""
    result = join(driver_data, lookup_data, key_columns, include_french_header)
    return result.encode("utf-8-sig")
