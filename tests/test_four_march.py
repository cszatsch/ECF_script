"""Tests de la jointure four_march (lancer : ``pytest``)."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import four_march_join as fm  # noqa: E402

# Fichier de base (FOURNISSEUR) : double en-tête, clé alphanumérique (BPC001)
# et un partenaire sans enrichissement (30000000).
FOURNISSEUR = (
    "PARTNER;BU_GROUP;NAME_ORG1\n"
    "Partenaire;Regroupement;Nom 1\n"
    "20000068;G1;Alpha\n"
    "BPC001;S100;Beta\n"
    "30000000;G2;Gamma\n"
).encode("utf-8")

# TAXNUM : double en-tête, libellé FR partiel (seule la 1re colonne a un libellé).
TAXNUM = (
    "PARTNER;TVA intracom_xx0;SIREN_xx2\n"
    "Partenaire;Nº ID fiscale;\n"
    "20000068;FR55;389\n"
    "BPC001;FR20;582\n"
).encode("utf-8")

# ZGESS1 : pas de 2e en-tête, et un doublon de clé (BPC001).
ZGESS1 = (
    "PARTNER;TYPE;IDNUMBER\n"
    "20000068;ZGESS1;1017\n"
    "BPC001;ZGESS1;998\n"
    "BPC001;ZGESS1;999\n"
).encode("utf-8")


def _result_lines():
    text = fm.join(FOURNISSEUR, [TAXNUM, ZGESS1])
    return text.split("\r\n")


def test_technical_header():
    assert _result_lines()[0] == (
        "PARTNER;BU_GROUP;NAME_ORG1;TVA intracom_xx0;SIREN_xx2;TYPE;IDNUMBER"
    )


def test_french_header_reproduced_with_blanks():
    # PARTNER->Partenaire, BU_GROUP->Regroupement, NAME_ORG1->Nom 1,
    # TVA->Nº ID fiscale, SIREN/TYPE/IDNUMBER sans libellé -> vides.
    assert _result_lines()[1] == "Partenaire;Regroupement;Nom 1;Nº ID fiscale;;;"


def test_left_join_keeps_all_base_partners():
    lines = _result_lines()
    # 2 lignes d'en-tête + 3 partenaires de base
    keys = [ln.split(";")[0] for ln in lines if ln]
    assert keys == ["PARTNER", "Partenaire", "20000068", "BPC001", "30000000"]


def test_enrichment_values_joined():
    lines = _result_lines()
    assert lines[2] == "20000068;G1;Alpha;FR55;389;ZGESS1;1017"


def test_alphanumeric_key_and_duplicate_first_wins():
    # BPC001 (clé alphanumérique) ; le doublon ZGESS1 garde la 1re valeur (998).
    line = next(ln for ln in _result_lines() if ln.startswith("BPC001"))
    assert line == "BPC001;S100;Beta;FR20;582;ZGESS1;998"


def test_unmatched_partner_has_blanks():
    # 30000000 n'est ni dans TAXNUM ni dans ZGESS1 -> 4 colonnes vides.
    line = next(ln for ln in _result_lines() if ln.startswith("30000000"))
    assert line == "30000000;G2;Gamma;;;;"


def test_without_french_header():
    lines = fm.join(FOURNISSEUR, [TAXNUM, ZGESS1],
                    include_french_header=False).split("\r\n")
    assert lines[0].startswith("PARTNER;")
    assert lines[1].startswith("20000068;")  # pas de ligne de libellés FR


def test_join_bytes_has_bom():
    out = fm.join_bytes(FOURNISSEUR, [TAXNUM, ZGESS1])
    assert out.startswith(b"\xef\xbb\xbf")


def test_empty_base_raises():
    with pytest.raises(ValueError):
        fm.join(b"", [TAXNUM, ZGESS1])
