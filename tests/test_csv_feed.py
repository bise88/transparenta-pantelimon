"""
tests/test_csv_feed.py
PR #36 — teste unitare pentru genereaza_contracte_csv() si genereaza_feed_atom().
Nu fac scraping / I/O real (zero network).
"""
import csv
import io
import os
import sys
from datetime import datetime, timezone

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from monitor_pantelimon import genereaza_contracte_csv, genereaza_feed_atom


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CONTRACTE_SAMPLE = [
    {
        "id": "achizitie-directa-2025-100001",
        "titlu": "Servicii curatenie sediu primarie",
        "valoare": 45000,
        "data": "2025-03-15",
        "tip": "achizitie-directa",
        "firma": "CLEAN SERV SRL",
        "cui": "RO11111111",
        "ofertanti": 1,
    },
    {
        "id": "achizitie-directa-2025-100002",
        "titlu": "Lucrari reparatii drumuri",
        "valoare": 129500,
        "data": "2025-04-20",
        "tip": "achizitie-directa",
        "firma": "DRUM CONSTRUCT SA",
        "cui": "RO22222222",
        "ofertanti": 0,
    },
    {
        "id": "licitatie-2025-100003",
        "titlu": "Furnizare combustibil 2025",
        "valoare": 350000,
        "data": "2025-01-10",
        "tip": "licitatie-deschisa",
        "firma": "PETROM DISTRIB SRL",
        "cui": "RO33333333",
        "ofertanti": 3,
    },
]

NEREGULI_SAMPLE = [
    {
        "titlu": "Achizitie directa peste prag",
        "severitate": "CRITIC",
        "furnizor": "MIDAS ROAD SRL",
        "valoare": 880000,
        "descriere": "Contract individual depaseste pragul de 130.000 RON.",
        "data": "2025-04-03",
    },
    {
        "titlu": "Concentrare furnizor >80%",
        "severitate": "CRITIC",
        "furnizor": "ALA EXPERT SRL",
        "valoare": 500000,
        "descriere": "Top-1 furnizor detine >80% din totalul contractelor.",
        "data": "2025-07-29",
    },
    {
        "titlu": "Fragmentare artificiala",
        "severitate": "MAJOR",
        "furnizor": "SANTIA SRL",
        "valoare": 260000,
        "descriere": "3 contracte similare sub prag intr-un interval de 30 zile.",
        "data": "2025-06-01",
    },
]


# ===========================================================================
# TestGenereazaContracteCsv
# ===========================================================================

class TestGenereazaContracteCsv:

    def test_returneaza_string(self):
        """genereaza_contracte_csv returneaza un string non-gol."""
        result = genereaza_contracte_csv(CONTRACTE_SAMPLE)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_header_prezent(self):
        """Prima linie este headerul CSV cu toate campurile."""
        result = genereaza_contracte_csv(CONTRACTE_SAMPLE)
        reader = csv.reader(io.StringIO(result))
        header = next(reader)
        assert "id" in header
        assert "titlu" in header
        assert "valoare" in header
        assert "data" in header
        assert "tip" in header
        assert "firma" in header
        assert "cui" in header
        assert "ofertanti" in header

    def test_numar_randuri(self):
        """Numarul de randuri = len(contracte) + 1 (header)."""
        result = genereaza_contracte_csv(CONTRACTE_SAMPLE)
        lines = [l for l in result.split("\n") if l.strip()]
        assert len(lines) == len(CONTRACTE_SAMPLE) + 1

    def test_valori_corecte(self):
        """Datele din primul contract apar corect in CSV."""
        result = genereaza_contracte_csv(CONTRACTE_SAMPLE)
        reader = csv.DictReader(io.StringIO(result))
        rows = list(reader)
        assert rows[0]["id"] == "achizitie-directa-2025-100001"
        assert rows[0]["firma"] == "CLEAN SERV SRL"
        assert rows[0]["cui"] == "RO11111111"
        assert rows[0]["valoare"] == "45000"

    def test_toate_randurile_prezente(self):
        """Toate contractele apar in CSV."""
        result = genereaza_contracte_csv(CONTRACTE_SAMPLE)
        assert "CLEAN SERV SRL" in result
        assert "DRUM CONSTRUCT SA" in result
        assert "PETROM DISTRIB SRL" in result

    def test_lista_goala(self):
        """Lista goala produce doar headerul."""
        result = genereaza_contracte_csv([])
        reader = csv.reader(io.StringIO(result))
        header = next(reader)
        assert len(header) >= 8
        rows = list(reader)
        assert len([r for r in rows if any(r)]) == 0

    def test_valori_none_tratate(self):
        """Campurile None nu crapa exportul — devin string gol."""
        contracte = [{
            "id": "x-001",
            "titlu": "Test",
            "valoare": None,
            "data": None,
            "tip": None,
            "firma": None,
            "cui": None,
            "ofertanti": None,
        }]
        result = genereaza_contracte_csv(contracte)
        assert isinstance(result, str)
        reader = csv.DictReader(io.StringIO(result))
        row = next(reader)
        assert row["valoare"] == ""
        assert row["firma"] == ""

    def test_caractere_speciale_escapate(self):
        """Titluri cu virgule/ghilimele sunt escapate corect in CSV."""
        contracte = [{
            "id": "x-002",
            "titlu": 'Servicii "IT", configurare',
            "valoare": 10000,
            "data": "2025-01-01",
            "tip": "ad",
            "firma": "FIRMA, SRL",
            "cui": "RO99",
            "ofertanti": 1,
        }]
        result = genereaza_contracte_csv(contracte)
        reader = csv.DictReader(io.StringIO(result))
        row = next(reader)
        assert row["titlu"] == 'Servicii "IT", configurare'
        assert row["firma"] == "FIRMA, SRL"

    def test_fisier_contracte_csv_exista(self):
        """contracte.csv exista in repo (placeholder pentru monitor)."""
        csv_path = os.path.join(REPO_ROOT, "contracte.csv")
        assert os.path.exists(csv_path)

    def test_fisier_contracte_csv_are_header(self):
        """contracte.csv contine cel putin headerul."""
        csv_path = os.path.join(REPO_ROOT, "contracte.csv")
        with open(csv_path, encoding="utf-8") as f:
            content = f.read()
        assert "id" in content
        assert "firma" in content


# ===========================================================================
# TestGenereazaFeedAtom
# ===========================================================================

class TestGenereazaFeedAtom:

    def _parse_feed(self, xml_str):
        """Returneaza continutul raw ca string (fara xml parser)."""
        return xml_str

    def test_returneaza_string(self):
        """genereaza_feed_atom returneaza un string non-gol."""
        result = genereaza_feed_atom(NEREGULI_SAMPLE, datetime(2026, 5, 27, 12, 0, 0))
        assert isinstance(result, str)
        assert len(result) > 0

    def test_declaration_xml(self):
        """Feed-ul incepe cu declaratia XML."""
        result = genereaza_feed_atom(NEREGULI_SAMPLE, datetime(2026, 5, 27))
        assert result.startswith('<?xml version="1.0" encoding="UTF-8"?>')

    def test_namespace_atom(self):
        """Feed-ul contine namespace-ul Atom."""
        result = genereaza_feed_atom(NEREGULI_SAMPLE, datetime(2026, 5, 27))
        assert 'xmlns="http://www.w3.org/2005/Atom"' in result

    def test_title_prezent(self):
        """Feed-ul contine titlul proiectului."""
        result = genereaza_feed_atom(NEREGULI_SAMPLE, datetime(2026, 5, 27))
        assert "Transparen" in result  # diacritice variaza
        assert "Pantelimon" in result

    def test_entries_prezente(self):
        """Feed-ul contine tag-uri <entry> pentru nereguli."""
        result = genereaza_feed_atom(NEREGULI_SAMPLE, datetime(2026, 5, 27))
        assert "<entry>" in result
        assert result.count("<entry>") == len(NEREGULI_SAMPLE)

    def test_severitate_in_titlu_entry(self):
        """Severitatea apare in titlul fiecarei intrari."""
        result = genereaza_feed_atom(NEREGULI_SAMPLE, datetime(2026, 5, 27))
        assert "[CRITIC]" in result
        assert "[MAJOR]" in result

    def test_sortare_critic_primul(self):
        """Intrarea CRITIC apare inaintea MAJOR in feed."""
        result = genereaza_feed_atom(NEREGULI_SAMPLE, datetime(2026, 5, 27))
        idx_critic = result.index("[CRITIC]")
        idx_major = result.index("[MAJOR]")
        assert idx_critic < idx_major

    def test_lista_goala_nu_crapa(self):
        """Lista goala de nereguli produce feed valid fara <entry>."""
        result = genereaza_feed_atom([], datetime(2026, 5, 27))
        assert isinstance(result, str)
        assert "<entry>" not in result
        assert "<feed" in result

    def test_link_spre_raport(self):
        """Feed-ul contine link spre raport_transparenta.html."""
        result = genereaza_feed_atom(NEREGULI_SAMPLE, datetime(2026, 5, 27))
        assert "raport_transparenta.html" in result

    def test_url_base_aprindemlumina(self):
        """Feed-ul foloseste domeniul aprindemlumina.eu."""
        result = genereaza_feed_atom(NEREGULI_SAMPLE, datetime(2026, 5, 27))
        assert "aprindemlumina.eu" in result

    def test_timezone_aware_data(self):
        """Accepta datetime cu timezone."""
        dt = datetime(2026, 5, 27, 10, 0, 0, tzinfo=timezone.utc)
        result = genereaza_feed_atom(NEREGULI_SAMPLE, dt)
        assert isinstance(result, str)
        assert "<feed" in result

    def test_xss_escape_titlu(self):
        """Titlurile cu caractere HTML speciale sunt escapate."""
        nereguli_xss = [{
            "titlu": "<script>alert('xss')</script>",
            "severitate": "CRITIC",
            "furnizor": "FIRMA & CO",
            "valoare": 100000,
            "descriere": "Test XSS <b>bold</b>",
            "data": "2025-01-01",
        }]
        result = genereaza_feed_atom(nereguli_xss, datetime(2026, 5, 27))
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_max_20_entries(self):
        """Feed-ul include maxim 20 nereguli indiferent de input."""
        nereguli_multe = [
            {"titlu": f"Neregula {i}", "severitate": "MEDIU",
             "furnizor": f"Firma {i}", "valoare": i * 1000,
             "descriere": "", "data": "2025-01-01"}
            for i in range(50)
        ]
        result = genereaza_feed_atom(nereguli_multe, datetime(2026, 5, 27))
        assert result.count("<entry>") == 20
