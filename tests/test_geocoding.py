"""
tests/test_geocoding.py
§3.6  — teste unitare pentru geocodeaza_firme() din monitor_pantelimon.py

Toate testele mockuiesc rețeaua (Nominatim) și SQLite → rulează offline.
Izolare fișiere: monkeypatch.chdir(tmp_path) → orice scriere relativă
("firme_geocoded.json") merge în tmp_path, nu în root-ul proiectului.
"""
import json
import os
import sys
import sqlite3
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from monitor_pantelimon import geocodeaza_firme


# ── Helpers ──────────────────────────────────────────────────────────────────

FIRME_OPENAPI_SAMPLE = {
    "1234567": {
        "adresa":            "Str. Victoriei 1",
        "judet":             "Ilfov",
        "_nume":             "FIRMA TEST SRL",
        "radiata":           False,
        "numar_reg_com":     "J23/123/2020",
        "stare":             "ACTIV",
        "ultima_declaratie": "",
        "recom_url":         "",
        "sursa":             "openapi.ro",
        "data_cache":        datetime.now().isoformat(),
    }
}

CUI_VALORI    = {"1234567": 850_000}
CUI_CONTRACTE = {"1234567": 5}
INDEX_FURNIZORI = [
    {"nume": "FIRMA TEST SRL", "slug": "firma-test-srl", "count": 5, "valoare": 850_000}
]


def _nominatim_ok(*args, **kwargs):
    """Simulează un răspuns Nominatim valid."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps([
        {"lat": "44.4268", "lon": "26.1025", "display_name": "Pantelimon, Ilfov, România"}
    ]).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def _nominatim_empty(*args, **kwargs):
    """Simulează răspuns Nominatim fără rezultate."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = b"[]"
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def _nominatim_error(*args, **kwargs):
    raise OSError("network error")


# ── Teste de bază ─────────────────────────────────────────────────────────────

class TestGeocodeazaFirme:
    """Teste pentru funcția geocodeaza_firme()."""

    def test_returneaza_lista_cu_coordonate(self, tmp_path, monkeypatch):
        """Funcția returnează o listă cu coordonate valide."""
        monkeypatch.chdir(tmp_path)   # toate scrierile relative → tmp_path
        cache_db = str(tmp_path / "geo_test.db")

        with patch("urllib.request.urlopen", side_effect=_nominatim_ok), \
             patch("time.sleep"):
            rezultat = geocodeaza_firme(
                firme_openapi=FIRME_OPENAPI_SAMPLE,
                cui_valori=CUI_VALORI,
                cui_contracte=CUI_CONTRACTE,
                index_furnizori=INDEX_FURNIZORI,
                cache_db=cache_db,
            )

        assert isinstance(rezultat, list)
        assert len(rezultat) == 1
        item = rezultat[0]
        assert item["cif"] == "1234567"
        assert isinstance(item["lat"], float)
        assert isinstance(item["lng"], float)
        assert item["valoare"] == 850_000
        assert item["nr_contracte"] == 5

    def test_geocodare_fara_adresa_skip(self, tmp_path, monkeypatch):
        """Firmele fără adresă sunt omise."""
        monkeypatch.chdir(tmp_path)
        cache_db = str(tmp_path / "geo_test.db")
        firme_no_addr = {
            "9999999": {
                "adresa": "",
                "judet":  "Ilfov",
                "_nume":  "FARA ADRESA SRL",
            }
        }

        rezultat = geocodeaza_firme(
            firme_openapi=firme_no_addr,
            cui_valori={"9999999": 100_000},
            cui_contracte={"9999999": 2},
            index_furnizori=[],
            cache_db=cache_db,
        )
        assert rezultat == []

    def test_geocodare_nominatim_gol_skip(self, tmp_path, monkeypatch):
        """Dacă Nominatim returnează [] → firma nu apare în rezultate."""
        monkeypatch.chdir(tmp_path)
        cache_db = str(tmp_path / "geo_test.db")

        with patch("urllib.request.urlopen", side_effect=_nominatim_empty), \
             patch("time.sleep"):
            rezultat = geocodeaza_firme(
                firme_openapi=FIRME_OPENAPI_SAMPLE,
                cui_valori=CUI_VALORI,
                cui_contracte=CUI_CONTRACTE,
                index_furnizori=INDEX_FURNIZORI,
                cache_db=cache_db,
            )

        assert rezultat == []

    def test_geocodare_eroare_retea_skip(self, tmp_path, monkeypatch):
        """Eroare de rețea la Nominatim → firma nu apare (nu ridică excepție)."""
        monkeypatch.chdir(tmp_path)
        cache_db = str(tmp_path / "geo_test.db")

        with patch("urllib.request.urlopen", side_effect=_nominatim_error), \
             patch("time.sleep"):
            rezultat = geocodeaza_firme(
                firme_openapi=FIRME_OPENAPI_SAMPLE,
                cui_valori=CUI_VALORI,
                cui_contracte=CUI_CONTRACTE,
                index_furnizori=INDEX_FURNIZORI,
                cache_db=cache_db,
            )

        assert rezultat == []

    def test_firme_fara_contracte_skip(self, tmp_path, monkeypatch):
        """Firmele din openapi fără contracte (valoare=0, nr=0) sunt omise."""
        monkeypatch.chdir(tmp_path)
        cache_db = str(tmp_path / "geo_test.db")

        with patch("urllib.request.urlopen", side_effect=_nominatim_ok), \
             patch("time.sleep"):
            rezultat = geocodeaza_firme(
                firme_openapi=FIRME_OPENAPI_SAMPLE,
                cui_valori={},       # nicio valoare
                cui_contracte={},    # niciun contract
                index_furnizori=[],
                cache_db=cache_db,
            )

        assert rezultat == []

    def test_cache_sqlite_creat(self, tmp_path, monkeypatch):
        """Funcția crează fișierul cache SQLite și tabela geocoding."""
        monkeypatch.chdir(tmp_path)
        cache_db = str(tmp_path / "geo_cache.db")

        with patch("urllib.request.urlopen", side_effect=_nominatim_ok), \
             patch("time.sleep"):
            geocodeaza_firme(
                firme_openapi=FIRME_OPENAPI_SAMPLE,
                cui_valori=CUI_VALORI,
                cui_contracte=CUI_CONTRACTE,
                index_furnizori=INDEX_FURNIZORI,
                cache_db=cache_db,
            )

        assert os.path.exists(cache_db)
        conn = sqlite3.connect(cache_db)
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        conn.close()
        assert "geocoding" in tables

    def test_cache_hit_nu_face_request(self, tmp_path, monkeypatch):
        """A doua apelare cu același cache nu mai face request Nominatim."""
        monkeypatch.chdir(tmp_path)
        cache_db = str(tmp_path / "geo_cache.db")

        # Pre-populăm cache-ul manual
        conn = sqlite3.connect(cache_db)
        conn.execute(
            "CREATE TABLE geocoding (adresa TEXT PRIMARY KEY, lat REAL, lng REAL, geocodat_la TEXT)"
        )
        conn.execute(
            "INSERT INTO geocoding VALUES (?,?,?,?)",
            ("Str. Victoriei 1", 44.4268, 26.1025, datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()

        with patch("urllib.request.urlopen", side_effect=_nominatim_ok) as mock_url, \
             patch("time.sleep"):
            geocodeaza_firme(
                firme_openapi=FIRME_OPENAPI_SAMPLE,
                cui_valori=CUI_VALORI,
                cui_contracte=CUI_CONTRACTE,
                index_furnizori=INDEX_FURNIZORI,
                cache_db=cache_db,
            )

        mock_url.assert_not_called()

    def test_firme_openapi_gol_returneaza_lista_goala(self, tmp_path, monkeypatch):
        """Dacă firme_openapi e gol dict, returnează []."""
        monkeypatch.chdir(tmp_path)
        cache_db = str(tmp_path / "geo_cache.db")

        rezultat = geocodeaza_firme(
            firme_openapi={},
            cui_valori={},
            cui_contracte={},
            index_furnizori=[],
            cache_db=cache_db,
        )

        assert rezultat == []
