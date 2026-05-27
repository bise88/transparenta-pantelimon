"""
tests/test_pnrr.py
§3.3 proiecte.pnrr.gov.ro — teste unitare

Toate testele mockuiesc rețeaua → rulează offline.
"""
import json
import os
import sys
import sqlite3
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from monitor_pantelimon import fetch_pnrr_projects


# ── Mock helpers ──────────────────────────────────────────────────────────────

PNRR_RESPONSE_JSON = json.dumps([
    {
        "titlu": "Reabilitare termica blocuri Pantelimon",
        "cod": "PNRR-C5-I2-001",
        "valoare_ron": 4_500_000,
        "status": "in_implementare",
        "program": "PNRR Componenta 5",
        "beneficiar": "Primaria Pantelimon",
        "link": "https://proiecte.pnrr.gov.ro/proiect/001",
    },
    {
        "titlu": "Digitalizare servicii publice",
        "cod": "PNRR-C7-I1-002",
        "valoare_ron": 1_200_000,
        "status": "finalizat",
        "program": "PNRR Componenta 7",
        "beneficiar": "Primaria Pantelimon",
        "link": "https://proiecte.pnrr.gov.ro/proiect/002",
    },
]).encode()

PNRR_RESPONSE_EMPTY = json.dumps([]).encode()

HTML_PNRR_GOALA = b"<html><body><p>Nu exista proiecte.</p></body></html>"


def _mock_resp(body: bytes):
    m = MagicMock()
    m.read.return_value = body
    m.__enter__ = lambda s: s
    m.__exit__ = MagicMock(return_value=False)
    return m


# ── §3.3 fetch_pnrr_projects ──────────────────────────────────────────────────

class TestFetchPnrrProjects:

    def test_returneaza_lista(self, tmp_path):
        """Funcția returnează o listă."""
        cache_db = str(tmp_path / "pnrr.db")
        out_json = tmp_path / "pnrr_projects.json"

        import builtins
        orig = builtins.open
        def po(path, *a, **kw):
            return orig(str(out_json), *a, **kw) if "pnrr_projects" in str(path) else orig(path, *a, **kw)

        with patch("urllib.request.urlopen", return_value=_mock_resp(PNRR_RESPONSE_JSON)), \
             patch("builtins.open", side_effect=po):
            rez = fetch_pnrr_projects("4420759", cache_db=cache_db)

        assert isinstance(rez, list)

    def test_raspuns_cu_proiecte(self, tmp_path):
        """Proiectele sunt returnate cu câmpuri normalizate."""
        cache_db = str(tmp_path / "pnrr.db")
        out_json = tmp_path / "pnrr_projects.json"

        import builtins
        orig = builtins.open
        def po(path, *a, **kw):
            return orig(str(out_json), *a, **kw) if "pnrr_projects" in str(path) else orig(path, *a, **kw)

        with patch("urllib.request.urlopen", return_value=_mock_resp(PNRR_RESPONSE_JSON)), \
             patch("builtins.open", side_effect=po):
            rez = fetch_pnrr_projects("4420759", cache_db=cache_db)

        assert len(rez) >= 1
        # Câmpuri normalizate
        for p in rez:
            assert "titlu" in p
            assert "extras_la" in p

    def test_raspuns_gol_returneaza_lista_goala(self, tmp_path):
        """API fără proiecte → []."""
        cache_db = str(tmp_path / "pnrr.db")
        out_json = tmp_path / "pnrr_projects.json"

        import builtins
        orig = builtins.open
        def po(path, *a, **kw):
            return orig(str(out_json), *a, **kw) if "pnrr_projects" in str(path) else orig(path, *a, **kw)

        with patch("urllib.request.urlopen", return_value=_mock_resp(PNRR_RESPONSE_EMPTY)), \
             patch("builtins.open", side_effect=po):
            rez = fetch_pnrr_projects("4420759", cache_db=cache_db)

        assert rez == []

    def test_eroare_retea_returneaza_lista_goala(self, tmp_path):
        """Eroare rețea → [] fără excepție."""
        cache_db = str(tmp_path / "pnrr.db")
        out_json = tmp_path / "pnrr_projects.json"

        import builtins
        orig = builtins.open
        def po(path, *a, **kw):
            return orig(str(out_json), *a, **kw) if "pnrr_projects" in str(path) else orig(path, *a, **kw)

        with patch("urllib.request.urlopen", side_effect=OSError("timeout")), \
             patch("builtins.open", side_effect=po):
            rez = fetch_pnrr_projects("4420759", cache_db=cache_db)

        assert rez == []

    def test_cache_sqlite_creat(self, tmp_path):
        """Cache SQLite cu tabela pnrr_projects creat după primul fetch."""
        cache_db = str(tmp_path / "pnrr.db")
        out_json = tmp_path / "pnrr_projects.json"

        import builtins
        orig = builtins.open
        def po(path, *a, **kw):
            return orig(str(out_json), *a, **kw) if "pnrr_projects" in str(path) else orig(path, *a, **kw)

        with patch("urllib.request.urlopen", return_value=_mock_resp(PNRR_RESPONSE_EMPTY)), \
             patch("builtins.open", side_effect=po):
            fetch_pnrr_projects("4420759", cache_db=cache_db)

        assert os.path.exists(cache_db)
        conn = sqlite3.connect(cache_db)
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        conn.close()
        assert "pnrr_projects" in tables

    def test_cache_hit_nu_face_request(self, tmp_path):
        """Cache valid → nu face request HTTP."""
        cache_db = str(tmp_path / "pnrr.db")
        out_json = tmp_path / "pnrr_projects.json"

        # Populăm cache manual
        conn = sqlite3.connect(cache_db)
        conn.execute(
            "CREATE TABLE pnrr_projects (cache_key TEXT PRIMARY KEY, extras_la TEXT, date_json TEXT)"
        )
        conn.execute("INSERT INTO pnrr_projects VALUES (?,?,?)",
                     ("pnrr_4420759", datetime.now().isoformat(),
                      json.dumps([{"titlu": "test", "cod": "T1", "valoare_ron": 0,
                                   "status": "", "program": "", "beneficiar": "",
                                   "link": "", "extras_la": "2026-01-01"}])))
        conn.commit()
        conn.close()

        import builtins
        orig = builtins.open
        def po(path, *a, **kw):
            return orig(str(out_json), *a, **kw) if "pnrr_projects" in str(path) else orig(path, *a, **kw)

        with patch("urllib.request.urlopen") as mock_url, \
             patch("builtins.open", side_effect=po):
            fetch_pnrr_projects("4420759", cache_db=cache_db)

        mock_url.assert_not_called()

    def test_scrie_json_output(self, tmp_path):
        """Scrie pnrr_projects.json pe disc."""
        cache_db = str(tmp_path / "pnrr.db")
        out_json = tmp_path / "pnrr_projects.json"

        import builtins
        orig = builtins.open
        def po(path, *a, **kw):
            return orig(str(out_json), *a, **kw) if "pnrr_projects" in str(path) else orig(path, *a, **kw)

        with patch("urllib.request.urlopen", return_value=_mock_resp(PNRR_RESPONSE_JSON)), \
             patch("builtins.open", side_effect=po):
            fetch_pnrr_projects("4420759", cache_db=cache_db)

        assert out_json.exists()
        data = json.loads(out_json.read_text(encoding="utf-8"))
        assert isinstance(data, list)
