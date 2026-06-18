"""Tests de la jointure four_march (lancer : ``pytest``).

La jointure est pilotée par ZGESS1 : seules les lignes dont le PARTNER figure
dans ZGESS1 sont conservées ; les colonnes restent dans l'ordre
FOURNISSEUR, TVA, ZGESS1.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import four_march_join as fm  # noqa: E402

# FOURNISSEUR : double en-tête ; 30000000 n'est pas dans ZGESS1 -> doit être ignoré.
FOURNISSEUR = (
    "PARTNER;BU_GROUP;NAME_ORG1\n"
    "Partenaire;Regroupement;Nom 1\n"
    "20000068;G1;Alpha\n"
    "BPC001;S100;Beta\n"
    "30000000;G2;Gamma\n"
).encode("utf-8")

# TAXNUM : double en-tête ; 20000069 n'est pas dans ZGESS1 -> doit être ignoré.
TAXNUM = (
    "PARTNER;TVA intracom_xx0;SIREN_xx2\n"
    "Partenaire;Nº ID fiscale;\n"
    "20000068;FR55;389\n"
    "BPC001;FR20;582\n"
    "20000069;FR99;999\n"
).encode("utf-8")

# ZGESS1 (fichier pilote) : pas de 2e en-tête ; BPC001 en double ; 88888888
# absent des deux autres fichiers.
ZGESS1 = (
    "PARTNER;TYPE;IDNUMBER\n"
    "20000068;ZGESS1;1017\n"
    "BPC001;ZGESS1;998\n"
    "BPC001;ZGESS1;999\n"
    "88888888;ZGESS1;7777\n"
).encode("utf-8")

# Ordre des sources = ordre des colonnes ; ZGESS1 (indice 2) pilote les lignes.
SOURCES = [FOURNISSEUR, TAXNUM, ZGESS1]
DRIVER = 2

# 4e fichier (résultat four_iban) : coordonnées bancaires + IBAN par partenaire.
# BPC001 a deux comptes (deux lignes) ; 77777777 n'est pas dans ZGESS1.
BANK = (
    "PARTNER;IBAN\n"
    "Partenaire;IBAN\n"
    "20000068;FR76AAA\n"
    "BPC001;FR76BBB\n"
    "BPC001;FR76CCC\n"
    "77777777;FR76ZZZ\n"
).encode("utf-8")

SOURCES4 = [FOURNISSEUR, TAXNUM, ZGESS1, BANK]


def _lines():
    text = fm.join(SOURCES, driver_index=DRIVER)
    return [ln for ln in text.split("\r\n") if ln]


def test_technical_header():
    assert _lines()[0] == (
        "PARTNER;BU_GROUP;NAME_ORG1;TVA intracom_xx0;SIREN_xx2;TYPE;IDNUMBER"
    )


def test_french_header_reproduced_with_blanks():
    assert _lines()[1] == "Partenaire;Regroupement;Nom 1;Nº ID fiscale;;;"


def test_rows_driven_by_zgess1():
    keys = [ln.split(";")[0] for ln in _lines()[2:]]
    # Ordre de ZGESS1, BPC001 en double conservé.
    assert keys == ["20000068", "BPC001", "BPC001", "88888888"]


def test_orphans_of_other_files_dropped():
    text = fm.join(SOURCES, driver_index=DRIVER)
    # 30000000 (FOURNISSEUR) et 20000069 (TAXNUM) ne sont pas dans ZGESS1.
    assert "30000000" not in text
    assert "20000069" not in text


def test_enrichment_values_joined():
    assert _lines()[2] == "20000068;G1;Alpha;FR55;389;ZGESS1;1017"


def test_zgess1_duplicate_produces_two_rows():
    rows = [ln for ln in _lines() if ln.startswith("BPC001")]
    assert rows == [
        "BPC001;S100;Beta;FR20;582;ZGESS1;998",
        "BPC001;S100;Beta;FR20;582;ZGESS1;999",
    ]


def test_zgess1_partner_absent_from_others_has_blanks():
    line = next(ln for ln in _lines() if ln.startswith("88888888"))
    assert line == "88888888;;;;;ZGESS1;7777"


def test_without_french_header():
    lines = fm.join(SOURCES, driver_index=DRIVER,
                    include_french_header=False).split("\r\n")
    assert lines[0].startswith("PARTNER;")
    assert lines[1].startswith("20000068;")  # pas de ligne de libellés FR


def test_join_bytes_has_bom():
    out = fm.join_bytes(SOURCES, driver_index=DRIVER)
    assert out.startswith(b"\xef\xbb\xbf")


def test_empty_source_raises():
    with pytest.raises(ValueError):
        fm.join([b"", TAXNUM, ZGESS1], driver_index=DRIVER)


def test_invalid_driver_index_raises():
    with pytest.raises(ValueError):
        fm.join(SOURCES, driver_index=5)


# --- Jointure à 4 fichiers (ajout du résultat four_iban) --------------------

def _lines4():
    return [ln for ln in fm.join(SOURCES4, driver_index=DRIVER).split("\r\n") if ln]


def test_four_files_header_appends_bank_column():
    assert _lines4()[0] == (
        "PARTNER;BU_GROUP;NAME_ORG1;TVA intracom_xx0;SIREN_xx2;TYPE;IDNUMBER;IBAN"
    )


def test_four_files_iban_joined():
    assert _lines4()[2] == "20000068;G1;Alpha;FR55;389;ZGESS1;1017;FR76AAA"


def test_four_files_multi_account_first_wins():
    # BPC001 a deux comptes dans le 4e fichier : la 1re occurrence (FR76BBB)
    # est utilisée pour ses deux lignes (doublon ZGESS1).
    rows = [ln for ln in _lines4() if ln.startswith("BPC001")]
    assert rows == [
        "BPC001;S100;Beta;FR20;582;ZGESS1;998;FR76BBB",
        "BPC001;S100;Beta;FR20;582;ZGESS1;999;FR76BBB",
    ]


def test_four_files_bank_orphan_blank():
    # 88888888 (dans ZGESS1) est absent du 4e fichier -> IBAN vide.
    line = next(ln for ln in _lines4() if ln.startswith("88888888"))
    assert line == "88888888;;;;;ZGESS1;7777;"
