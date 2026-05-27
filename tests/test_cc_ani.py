"""
tests/test_cc_ani.py
§3.1 + §3.2 — teste unitare pentru fetch_curtea_de_conturi() și fetch_declaratii_avere()

Toate testele mockuiesc rețeaua → rulează offline.
"""
import json
import os
import sys
import sqlite3
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from monitor_pantelimon import fetch_curtea_de_conturi, fetch_declaratii_avere


# ── HTML mock helpers ─────────────────────────────────────────────────────────

HTML_CC_CU_UAT = """
<html><body>
  <ul>
    <li><a href="/rapoarte/pantelimon-2023.pdf">Raport audit Pantelimon 2023</a></li>
    <li><a href="/rapoarte/pantelimon-2022.pdf">Raport audit Pantelimon 2022</a></li>
    <li><a href="/rapoarte/alta-localitate.pdf">Raport Buftea 2023</a></li>
  </ul>
</body></html>
""".encode()

HTML_CC_FARA_UAT = b"<html><body><p>Nu s-au gasit rezultate.</p></body></html>"

HTML_ANI_CU_DECLARATII = """
<html><body>
  <table>
    <tr class="result-row">
      <td>Ion Popescu</td>
      <td>Primar</td>
      <td>2023</td>
      <td><a href="/declaratii/popescu-2023.pdf">Declaratie avere 2023</a></td>
    </tr>
    <tr class="result-row">
      <td>Maria Ionescu</td>
      <td>Viceprimar</td>
      <td>2022</td>
      <td><a href="/declaratii/ionescu-2022.pdf">Declaratie interese 2022</a></td>
    </tr>
  </table>
</body></html>
""".encode()

HTML_ANI_GOLA = b"<html><body><p>Niciun rezultat.</p></body></html>"


def _make_mock_resp(body: bytes):
    mock = MagicMock()
    mock.read.return_value = body
    mock.__enter__ = lambda s: s
    mock.__exit__ = MagicMock(return_value=False)
    return mock


# ── §3.1 fetch_curtea_de_conturi ──────────────────────────────────────────────

class TestFetchCurteaDeConturi:

    def test_returneaza_lista(self, tmp_path):
        """Funcția returnează o listă (poate fi goală)."""
        cache_db = str(tmp_path / "cc.db")
        out_json = tmp_path / "curtea_de_conturi.json"

        import builtins
        orig_open = builtins.open
        def po(path, *a, **kw):
            return orig_open(str(out_json), *a, **kw) if "curtea_de_conturi" in str(path) else orig_open(path, *a, **kw)

        with patch("urllib.request.urlopen", return_value=_make_mock_resp(HTML_CC_CU_UAT)), \
             patch("builtins.open", side_effect=po):
            rez = fetch_curtea_de_conturi(uat_nume="Pantelimon", cache_db=cache_db)

        assert isinstance(rez, list)

    def test_filtreaza_numai_uat(self, tmp_path):
        """Returnează doar rapoartele care conțin UAT-ul în text/href."""
        cache_db = str(tmp_path / "cc.db")
        out_json = tmp_path / "curtea_de_conturi.json"

        import builtins
        orig_open = builtins.open
        def po(path, *a, **kw):
            return orig_open(str(out_json), *a, **kw) if "curtea_de_conturi" in str(path) else orig_open(path, *a, **kw)

        with patch("urllib.request.urlopen", return_value=_make_mock_resp(HTML_CC_CU_UAT)), \
             patch("builtins.open", side_effect=po):
            rez = fetch_curtea_de_conturi(uat_nume="Pantelimon", cache_db=cache_db)

        # Buftea nu trebuie să apară
        for r in rez:
            assert "buftea" not in r.get("titlu", "").lower() or "pantelimon" in r.get("titlu", "").lower()

    def test_fara_rezultate_returneaza_lista_goala(self, tmp_path):
        """Dacă pagina nu conține UAT → returnează []."""
        cache_db = str(tmp_path / "cc.db")
        out_json = tmp_path / "curtea_de_conturi.json"

        import builtins
        orig_open = builtins.open
        def po(path, *a, **kw):
            return orig_open(str(out_json), *a, **kw) if "curtea_de_conturi" in str(path) else orig_open(path, *a, **kw)

        # Primul fetch (pagina principală) nu conține UAT → al doilea fetch (search) de asemenea
        with patch("urllib.request.urlopen", return_value=_make_mock_resp(HTML_CC_FARA_UAT)), \
             patch("builtins.open", side_effect=po):
            rez = fetch_curtea_de_conturi(uat_nume="Pantelimon", cache_db=cache_db)

        assert rez == []

    def test_cache_sqlite_creat(self, tmp_path):
        """Cache SQLite creat după primul fetch."""
        cache_db = str(tmp_path / "cc.db")
        out_json = tmp_path / "curtea_de_conturi.json"

        import builtins
        orig_open = builtins.open
        def po(path, *a, **kw):
            return orig_open(str(out_json), *a, **kw) if "curtea_de_conturi" in str(path) else orig_open(path, *a, **kw)

        with patch("urllib.request.urlopen", return_value=_make_mock_resp(HTML_CC_FARA_UAT)), \
             patch("builtins.open", side_effect=po):
            fetch_curtea_de_conturi(uat_nume="Pantelimon", cache_db=cache_db)

        assert os.path.exists(cache_db)
        conn = sqlite3.connect(cache_db)
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        conn.close()
        assert "cc_rapoarte" in tables

    def test_cache_hit_nu_face_request(self, tmp_path):
        """A doua apelare cu cache valid nu face request HTTP."""
        cache_db = str(tmp_path / "cc.db")
        out_json = tmp_path / "curtea_de_conturi.json"

        # Pre-populăm cache-ul
        conn = sqlite3.connect(cache_db)
        conn.execute("CREATE TABLE cc_rapoarte (uat TEXT, extras_la TEXT, date_json TEXT)")
        conn.execute("CREATE UNIQUE INDEX cc_uat_idx ON cc_rapoarte(uat)")
        conn.execute("INSERT INTO cc_rapoarte VALUES (?,?,?)",
                     ("Pantelimon", datetime.now().isoformat(), json.dumps([{"titlu": "test", "url": "x", "an": "2023"}])))
        conn.commit()
        conn.close()

        import builtins
        orig_open = builtins.open
        def po(path, *a, **kw):
            return orig_open(str(out_json), *a, **kw) if "curtea_de_conturi" in str(path) else orig_open(path, *a, **kw)

        with patch("urllib.request.urlopen") as mock_url, \
             patch("builtins.open", side_effect=po):
            fetch_curtea_de_conturi(uat_nume="Pantelimon", cache_db=cache_db)

        mock_url.assert_not_called()

    def test_eroare_retea_returneaza_lista_goala(self, tmp_path):
        """Eroare de rețea → returnează [] fără excepție."""
        cache_db = str(tmp_path / "cc.db")
        out_json = tmp_path / "curtea_de_conturi.json"

        import builtins
        orig_open = builtins.open
        def po(path, *a, **kw):
            return orig_open(str(out_json), *a, **kw) if "curtea_de_conturi" in str(path) else orig_open(path, *a, **kw)

        with patch("urllib.request.urlopen", side_effect=OSError("timeout")), \
             patch("builtins.open", side_effect=po):
            rez = fetch_curtea_de_conturi(uat_nume="Pantelimon", cache_db=cache_db)

        assert rez == []


# ── §3.2 fetch_declaratii_avere ───────────────────────────────────────────────

class TestFetchDeclaratiiAvere:

    def test_returneaza_lista(self, tmp_path):
        """Funcția returnează o listă."""
        cache_db = str(tmp_path / "ani.db")
        out_json = tmp_path / "ani_declaratii.json"

        import builtins
        orig_open = builtins.open
        def po(path, *a, **kw):
            return orig_open(str(out_json), *a, **kw) if "ani_declaratii" in str(path) else orig_open(path, *a, **kw)

        with patch("urllib.request.urlopen", return_value=_make_mock_resp(HTML_ANI_CU_DECLARATII)), \
             patch("builtins.open", side_effect=po):
            rez = fetch_declaratii_avere(uat="Pantelimon", cache_db=cache_db)

        assert isinstance(rez, list)

    def test_fara_rezultate_returneaza_lista_goala(self, tmp_path):
        """HTML fără date → returnează []."""
        cache_db = str(tmp_path / "ani.db")
        out_json = tmp_path / "ani_declaratii.json"

        import builtins
        orig_open = builtins.open
        def po(path, *a, **kw):
            return orig_open(str(out_json), *a, **kw) if "ani_declaratii" in str(path) else orig_open(path, *a, **kw)

        with patch("urllib.request.urlopen", return_value=_make_mock_resp(HTML_ANI_GOLA)), \
             patch("builtins.open", side_effect=po):
            rez = fetch_declaratii_avere(uat="Pantelimon", cache_db=cache_db)

        assert rez == []

    def test_cache_sqlite_creat(self, tmp_path):
        """Cache SQLite creat după primul fetch."""
        cache_db = str(tmp_path / "ani.db")
        out_json = tmp_path / "ani_declaratii.json"

        import builtins
        orig_open = builtins.open
        def po(path, *a, **kw):
            return orig_open(str(out_json), *a, **kw) if "ani_declaratii" in str(path) else orig_open(path, *a, **kw)

        with patch("urllib.request.urlopen", return_value=_make_mock_resp(HTML_ANI_GOLA)), \
             patch("builtins.open", side_effect=po):
            fetch_declaratii_avere(uat="Pantelimon", cache_db=cache_db)

        assert os.path.exists(cache_db)
        conn = sqlite3.connect(cache_db)
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        conn.close()
        assert "ani_declaratii" in tables

    def test_cache_hit_nu_face_request(self, tmp_path):
        """Cache valid → nu face request HTTP."""
        cache_db = str(tmp_path / "ani.db")
        out_json = tmp_path / "ani_declaratii.json"

        conn = sqlite3.connect(cache_db)
        conn.execute("CREATE TABLE ani_declaratii (uat TEXT, extras_la TEXT, date_json TEXT)")
        conn.execute("CREATE UNIQUE INDEX ani_uat_idx ON ani_declaratii(uat)")
        conn.execute("INSERT INTO ani_declaratii VALUES (?,?,?)",
                     ("Pantelimon", datetime.now().isoformat(), json.dumps([{"text_row": "Ion Popescu"}])))
        conn.commit()
        conn.close()

        import builtins
        orig_open = builtins.open
        def po(path, *a, **kw):
            return orig_open(str(out_json), *a, **kw) if "ani_declaratii" in str(path) else orig_open(path, *a, **kw)

        with patch("urllib.request.urlopen") as mock_url, \
             patch("builtins.open", side_effect=po):
            fetch_declaratii_avere(uat="Pantelimon", cache_db=cache_db)

        mock_url.assert_not_called()

    def test_eroare_retea_returneaza_lista_goala(self, tmp_path):
        """Eroare de rețea → returnează [] fără excepție."""
        cache_db = str(tmp_path / "ani.db")
        out_json = tmp_path / "ani_declaratii.json"

        import builtins
        orig_open = builtins.open
        def po(path, *a, **kw):
            return orig_open(str(out_json), *a, **kw) if "ani_declaratii" in str(path) else orig_open(path, *a, **kw)

        with patch("urllib.request.urlopen", side_effect=OSError("network error")), \
             patch("builtins.open", side_effect=po):
            rez = fetch_declaratii_avere(uat="Pantelimon", cache_db=cache_db)

        assert rez == []
