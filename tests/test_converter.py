"""Tests de la logique de conversion (lancer : ``pytest``)."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import converter  # noqa: E402

INPUT_SEMI = (
    "Partenaire;Catégorie;Nº ID fiscale\n"
    "20000068;FR0;FR55389036427\n"
    "20000068;FR1;3,89036E+13\n"
    "20000068;FR2;389036427\n"
    "20000069;FR0;FR44352689327\n"
    "20000069;FR1;3,52689E+13\n"
    "20000069;FR2;352689327\n"
)

EXPECTED_SEMI = (
    "Partenaire;FR0 - TVA intracom;FR1 - SIRET;FR2 - SIREN\r\n"
    "20000068;FR55389036427;3,89036E+13;389036427\r\n"
    "20000069;FR44352689327;3,52689E+13;352689327\r\n"
)


def test_convert_semicolon():
    assert converter.convert(INPUT_SEMI) == EXPECTED_SEMI


def test_convert_tab():
    tab_input = INPUT_SEMI.replace(";", "\t")
    expected = EXPECTED_SEMI.replace(";", "\t")
    assert converter.convert(tab_input) == expected


def test_detect_delimiter():
    assert converter.detect_delimiter("Partenaire;Catégorie;Nº ID fiscale") == ";"
    assert converter.detect_delimiter("Partenaire\tCatégorie\tNº ID fiscale") == "\t"


def test_preserves_scientific_notation():
    # La virgule décimale ne doit ni casser le parsing ni être modifiée.
    assert "3,89036E+13" in converter.convert(INPUT_SEMI)


def test_missing_categories_leave_blanks():
    # Un partenaire avec seulement FR0 : les colonnes FR1/FR2 restent vides,
    # mais le schéma (3 colonnes de catégories) est conservé.
    data = "Partenaire;Catégorie;Nº ID fiscale\n20000070;FR0;FRXX\n"
    lines = converter.convert(data).strip().split("\r\n")
    assert lines[0] == "Partenaire;FR0 - TVA intracom;FR1 - SIRET;FR2 - SIREN"
    assert lines[1] == "20000070;FRXX;;"


def test_unknown_category_appended():
    data = (
        "Partenaire;Catégorie;Nº ID fiscale\n"
        "20000071;FR0;A\n"
        "20000071;FR9;Z\n"
    )
    header = converter.convert(data).split("\r\n")[0]
    assert header.endswith("FR9")  # catégorie inconnue ajoutée en fin


def test_decode_bytes_cp1252():
    # « Catégorie » encodé en cp1252 doit être lu correctement.
    raw = "Partenaire;Catégorie;Nº ID fiscale\n20000068;FR0;X\n".encode("cp1252")
    assert "Catégorie" in converter.decode_bytes(raw)


def test_convert_bytes_roundtrip_has_bom():
    out = converter.convert_bytes(INPUT_SEMI.encode("utf-8"))
    assert out.startswith(b"\xef\xbb\xbf")  # BOM UTF-8 pour Excel


def test_empty_raises():
    with pytest.raises(ValueError):
        converter.convert("")
    with pytest.raises(ValueError):
        converter.convert("   \n  \n")
