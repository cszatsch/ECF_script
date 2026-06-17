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
    "Partenaire;TVA intracom_xx0;SIRET_xx1;SIREN_xx2\r\n"
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


def test_routing_is_country_agnostic():
    # Le routage dépend du dernier caractère du code, pas du code pays :
    # DE0/DE1/DE2 vont dans les mêmes colonnes que FR0/FR1/FR2.
    data = (
        "Partenaire;Catégorie;Nº ID fiscale\n"
        "30000001;DE0;DE123456789\n"
        "30000001;DE1;1,1E+13\n"
        "30000001;DE2;111\n"
    )
    lines = converter.convert(data).strip().split("\r\n")
    assert lines[0] == "Partenaire;TVA intracom_xx0;SIRET_xx1;SIREN_xx2"
    assert lines[1] == "30000001;DE123456789;1,1E+13;111"


def test_partial_partner_leaves_blanks():
    # Un partenaire avec une seule valeur (ici un SIRET) : les autres colonnes
    # restent vides, mais le schéma (3 colonnes) est conservé.
    data = "Partenaire;Catégorie;Nº ID fiscale\n20000070;FR1;ABC\n"
    lines = converter.convert(data).strip().split("\r\n")
    assert lines[0] == "Partenaire;TVA intracom_xx0;SIRET_xx1;SIREN_xx2"
    assert lines[1] == "20000070;;ABC;"


def test_default_column_catches_other_digits():
    # Règle par défaut : un code se terminant par un chiffre autre que 1/2
    # (ex. 3) alimente TVA intracom_xx0, sans créer de colonne supplémentaire.
    data = "Partenaire;Catégorie;Nº ID fiscale\n20000071;FR3;XYZ\n"
    lines = converter.convert(data).strip().split("\r\n")
    assert lines[0] == "Partenaire;TVA intracom_xx0;SIRET_xx1;SIREN_xx2"
    assert lines[1] == "20000071;XYZ;;"


def test_default_column_zero_has_priority():
    # FR0 et FR3 pointent tous deux vers TVA intracom_xx0 : la valeur du code
    # se terminant par 0 l'emporte, quel que soit l'ordre des lignes.
    data_zero_first = (
        "Partenaire;Catégorie;Nº ID fiscale\n"
        "20000072;FR0;VALEUR_ZERO\n"
        "20000072;FR3;VALEUR_TROIS\n"
    )
    data_three_first = (
        "Partenaire;Catégorie;Nº ID fiscale\n"
        "20000072;FR3;VALEUR_TROIS\n"
        "20000072;FR0;VALEUR_ZERO\n"
    )
    for data in (data_zero_first, data_three_first):
        line = converter.convert(data).strip().split("\r\n")[1]
        assert line == "20000072;VALEUR_ZERO;;"


def test_default_column_without_zero_keeps_first():
    # Sans code se terminant par 0, la première valeur par défaut est gardée.
    data = (
        "Partenaire;Catégorie;Nº ID fiscale\n"
        "20000073;FR3;PREMIER\n"
        "20000073;FR4;SECOND\n"
    )
    line = converter.convert(data).strip().split("\r\n")[1]
    assert line == "20000073;PREMIER;;"


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
