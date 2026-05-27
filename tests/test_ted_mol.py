"""
tests/test_ted_mol.py
§3.4 TED Europa + §3.5 MOL primărie — teste unitare

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
from monitor_pantelimon import search_ted_for_buyer, fetch_mol_primarie


# ── Mock helpers ──────────────────────────────────────────────────────────────

TED_RESPONSE_OK = json.dumps({
    "notices": [
        {
            "notice-id": "2026/S 001-000001",
            "short-description": "Reabilitare drum comunal Pantelimon",
            "publication-date": "2026-01-15",
            "estimated-value-setting": {"amount": 650000},
            "procedure-type": "open",
        },
        {
            "notice-id": "2026/S 001-000002",
            "short-description": "Servicii IT administrație publică",
            "publication-date": "2026-02-20",
            "estimated-value-setting": {"amount": 120000},
            "procedure-type": "restricted",
        },
    ]
}).encode()

TED_RESPONSE_EMPTY = json.dumps({"notices": []}).encode()

HTML_MOL_CU_RECTIFICARI = """
<html><body>
  <ul>
    <li><a href="/mol/hcl-47-2025.pdf">HCL 47/2025 rectificare buget 2.300.000 RON</a></li>
    <li><a href="/mol/hcl-51-2025.pdf">HCL 51/2025 aprobare buget local 2026</a></li>
    <li><a href="/mol/informatii-publice.html">Informații publice</a></li>
  </ul>
</body></html>
""".encode()

HTML_MOL_GOALA = b"<html><body><p>Nu exista documente.</p></body></html>"


def _mock_resp(body: bytes):
    m = MagicMock()
    m.read.return_value = body
    m.__enter__ = lambda s: s
    m.__exit__ = MagicMock(return_value=False)
    return m


# ── §3.4 TED Europa ───────────────────────────────────────────────────────────

class TestSearchTedForBuyer:

    def test_returneaza_lista(self, tmp_path):
        """Funcția returnează o listă."""
        cache_db = str(tmp_path / "ted.db")
        out_json = tmp_path / "ted_notices.json"

        import builtins
        orig = builtins.open
        def po(path, *a, **kw):
            return orig(str(out_json), *a, **kw) if "ted_notices" in str(path) else orig(path, *a, **kw)

        with patch("urllib.request.urlopen", return_value=_mock_resp(TED_RESPONSE_OK)), \
             patch("builtins.open", side_effect=po):
            rez = search_ted_for_buyer("4420759", year=2026, cache_db=cache_db)

        assert isinstance(rez, list)

    def test_filtreaza_dupa_an(self, tmp_path):
        """Numai anunțurile din anul specificat sunt returnate."""
        cache_db = str(tmp_path / "ted.db")
        out_json = tmp_path / "ted_notices.json"

        import builtins
        orig = builtins.open
        def po(path, *a, **kw):
            return orig(str(out_json), *a, **kw) if "ted_notices" in str(path) else orig(path, *a, **kw)

        with patch("urllib.request.urlopen", return_value=_mock_resp(TED_RESPONSE_OK)), \
             patch("builtins.open", side_effect=po):
            rez = search_ted_for_buyer("4420759", year=2026, cache_db=cache_db)

        for notice in rez:
            if notice.get("publication_date"):
                assert "2026" in notice["publication_date"]

    def test_raspuns_gol_returneaza_lista_goala(self, tmp_path):
        """API fără rezultate → []."""
        cache_db = str(tmp_path / "ted.db")
        out_json = tmp_path / "ted_notices.json"

        import builtins
        orig = builtins.open
        def po(path, *a, **kw):
            return orig(str(out_json), *a, **kw) if "ted_notices" in str(path) else orig(path, *a, **kw)

        with patch("urllib.request.urlopen", return_value=_mock_resp(TED_RESPONSE_EMPTY)), \
             patch("builtins.open", side_effect=po):
            rez = search_ted_for_buyer("4420759", year=2026, cache_db=cache_db)

        assert rez == []

    def test_eroare_retea_returneaza_lista_goala(self, tmp_path):
        """Eroare rețea → [] fără excepție."""
        cache_db = str(tmp_path / "ted.db")
        out_json = tmp_path / "ted_notices.json"

        import builtins
        orig = builtins.open
        def po(path, *a, **kw):
            return orig(str(out_json), *a, **kw) if "ted_notices" in str(path) else orig(path, *a, **kw)

        with patch("urllib.request.urlopen", side_effect=OSError("timeout")), \
             patch("builtins.open", side_effect=po):
            rez = search_ted_for_buyer("4420759", year=2026, cache_db=cache_db)

        assert rez == []

    def test_cache_sqlite_creat(self, tmp_path):
        """Cache SQLite creat după primul fetch."""
        cache_db = str(tmp_path / "ted.db")
        out_json = tmp_path / "ted_notices.json"

        import builtins
        orig = builtins.open
        def po(path, *a, **kw):
            return orig(str(out_json), *a, **kw) if "ted_notices" in str(path) else orig(path, *a, **kw)

        with patch("urllib.request.urlopen", return_value=_mock_resp(TED_RESPONSE_EMPTY)), \
             patch("builtins.open", side_effect=po):
            search_ted_for_buyer("4420759", year=2026, cache_db=cache_db)

        assert os.path.exists(cache_db)
        conn = sqlite3.connect(cache_db)
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        conn.close()
        assert "ted_notices" in tables

    def test_cache_hit_nu_face_request(self, tmp_path):
        """Cache valid → nu face request HTTP."""
        cache_db = str(tmp_path / "ted.db")
        out_json = tmp_path / "ted_notices.json"

        conn = sqlite3.connect(cache_db)
        conn.execute("CREATE TABLE ted_notices (cache_key TEXT PRIMARY KEY, extras_la TEXT, date_json TEXT)")
        conn.execute("INSERT INTO ted_notices VALUES (?,?,?)",
                     ("4420759_2026", datetime.now().isoformat(), json.dumps([{"notice_id": "test"}])))
        conn.commit()
        conn.close()

        import builtins
        orig = builtins.open
        def po(path, *a, **kw):
            return orig(str(out_json), *a, **kw) if "ted_notices" in str(path) else orig(path, *a, **kw)

        with patch("urllib.request.urlopen") as mock_url, \
             patch("builtins.open", side_effect=po):
            search_ted_for_buyer("4420759", year=2026, cache_db=cache_db)

        mock_url.assert_not_called()


# ── §3.5 MOL primărie ─────────────────────────────────────────────────────────

class TestFetchMolPrimarie:

    def test_returneaza_lista(self, tmp_path):
        """Funcția returnează o listă."""
        cache_db = str(tmp_path / "mol.db")
        out_json = tmp_path / "mol_primarie.json"

        import builtins
        orig = builtins.open
        def po(path, *a, **kw):
            return orig(str(out_json), *a, **kw) if "mol_primarie" in str(path) else orig(path, *a, **kw)

        with patch("urllib.request.urlopen", return_value=_mock_resp(HTML_MOL_CU_RECTIFICARI)), \
             patch("builtins.open", side_effect=po):
            rez = fetch_mol_primarie(cache_db=cache_db)

        assert isinstance(rez, list)

    def test_filtreaza_documente_relevante(self, tmp_path):
        """Returnează doar documentele bugetare (HCL/rectificare/aprobare)."""
        cache_db = str(tmp_path / "mol.db")
        out_json = tmp_path / "mol_primarie.json"

        import builtins
        orig = builtins.open
        def po(path, *a, **kw):
            return orig(str(out_json), *a, **kw) if "mol_primarie" in str(path) else orig(path, *a, **kw)

        with patch("urllib.request.urlopen", return_value=_mock_resp(HTML_MOL_CU_RECTIFICARI)), \
             patch("builtins.open", side_effect=po):
            rez = fetch_mol_primarie(cache_db=cache_db)

        # "Informații publice" nu trebuie să apară
        for r in rez:
            assert "informații publice" not in r.get("titlu", "").lower()

    def test_fara_date_returneaza_lista_goala(self, tmp_path):
        """Pagina fără documente relevante → []."""
        cache_db = str(tmp_path / "mol.db")
        out_json = tmp_path / "mol_primarie.json"

        import builtins
        orig = builtins.open
        def po(path, *a, **kw):
            return orig(str(out_json), *a, **kw) if "mol_primarie" in str(path) else orig(path, *a, **kw)

        with patch("urllib.request.urlopen", return_value=_mock_resp(HTML_MOL_GOALA)), \
             patch("builtins.open", side_effect=po):
            rez = fetch_mol_primarie(cache_db=cache_db)

        assert rez == []

    def test_eroare_retea_returneaza_lista_goala(self, tmp_path):
        """Eroare rețea → []."""
        cache_db = str(tmp_path / "mol.db")
        out_json = tmp_path / "mol_primarie.json"

        import builtins
        orig = builtins.open
        def po(path, *a, **kw):
            return orig(str(out_json), *a, **kw) if "mol_primarie" in str(path) else orig(path, *a, **kw)

        with patch("urllib.request.urlopen", side_effect=OSError("timeout")), \
             patch("builtins.open", side_effect=po):
            rez = fetch_mol_primarie(cache_db=cache_db)

        assert rez == []

    def test_cache_sqlite_creat(self, tmp_path):
        """Cache SQLite creat corect."""
        cache_db = str(tmp_path / "mol.db")
        out_json = tmp_path / "mol_primarie.json"

        import builtins
        orig = builtins.open
        def po(path, *a, **kw):
            return orig(str(out_json), *a, **kw) if "mol_primarie" in str(path) else orig(path, *a, **kw)

        with patch("urllib.request.urlopen", return_value=_mock_resp(HTML_MOL_GOALA)), \
             patch("builtins.open", side_effect=po):
            fetch_mol_primarie(cache_db=cache_db)

        assert os.path.exists(cache_db)
        conn = sqlite3.connect(cache_db)
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        conn.close()
        assert "mol_entries" in tables
