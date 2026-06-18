"""Tests de la jointure four_iban (lancer : ``pytest``)."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import four_iban_join as fi  # noqa: E402

# BUT0K (pilote) : double en-tête ; 20000099 n'a pas d'IBAN dans TIBAN.
BUT0K = (
    "PARTNER;BKVID;BANKS;BANKL;BANKN;BKONT;KOINH\n"
    "Partenaire;Coord. banc.;Pays/rég. bque;Clé bancaire;Compte bancaire;Clé R.I.B.;Titulaire cpte\n"
    "20000068;1;FR;3000300691;20628259;22;SAS ATLANTIS\n"
    "20000069;1;FR;3000205681;0000066502R;95;SARL FRESNOTEL\n"
    "20000099;1;FR;9999999999;0000000000;99;SARL SANS IBAN\n"
).encode("utf-8")

TIBAN = (
    "BANKS;BANKL;BANKN;BKONT;IBAN;ERDAT;TABKEY\n"
    "Pays/Rég. bnque;Clé bancaire;Compte bancaire;Clé R.I.B.;IBAN;Créé le;Origine IBAN : clé\n"
    "FR;3000300691;20628259;22;FR76IBAN68;08/05/2026;A1\n"
    "FR;3000205681;0000066502R;95;FR76IBAN69;10/05/2026;A2\n"
).encode("utf-8")


def _lines():
    return [ln for ln in fi.join(BUT0K, TIBAN).split("\r\n") if ln]


def test_technical_header():
    assert _lines()[0] == (
        "PARTNER;BKVID;BANKS;BANKL;BANKN;BKONT;KOINH;IBAN;ERDAT;TABKEY"
    )


def test_french_header_reproduced():
    assert _lines()[1] == (
        "Partenaire;Coord. banc.;Pays/rég. bque;Clé bancaire;Compte bancaire;"
        "Clé R.I.B.;Titulaire cpte;IBAN;Créé le;Origine IBAN : clé"
    )


def test_composite_key_match_adds_iban():
    assert _lines()[2] == (
        "20000068;1;FR;3000300691;20628259;22;SAS ATLANTIS;FR76IBAN68;08/05/2026;A1"
    )


def test_key_columns_not_duplicated():
    # BANKS/BANKL/BANKN/BKONT n'apparaissent qu'une fois (pas de doublon TIBAN).
    header = _lines()[0].split(";")
    assert header.count("BANKS") == 1
    assert header.count("BKONT") == 1


def test_driver_keeps_all_rows():
    keys = [ln.split(";")[0] for ln in _lines()[2:]]
    assert keys == ["20000068", "20000069", "20000099"]


def test_unmatched_has_blank_iban():
    line = next(ln for ln in _lines() if ln.startswith("20000099"))
    # IBAN, ERDAT, TABKEY vides -> la ligne se termine par trois champs vides.
    assert line == "20000099;1;FR;9999999999;0000000000;99;SARL SANS IBAN;;;"


def test_without_french_header():
    lines = fi.join(BUT0K, TIBAN, include_french_header=False).split("\r\n")
    assert lines[0].startswith("PARTNER;")
    assert lines[1].startswith("20000068;")


def test_join_bytes_has_bom():
    assert fi.join_bytes(BUT0K, TIBAN).startswith(b"\xef\xbb\xbf")


def test_missing_key_column_raises():
    bad = "PARTNER;BANKS;IBAN\nPartenaire;Pays;IBAN\n20000068;FR;X\n".encode("utf-8")
    with pytest.raises(ValueError):
        fi.join(BUT0K, bad)  # TIBAN sans BANKL/BANKN/BKONT


def test_empty_file_raises():
    with pytest.raises(ValueError):
        fi.join(b"", TIBAN)
