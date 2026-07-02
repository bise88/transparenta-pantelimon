"""
tests/test_cache_ttl.py
Centralizare TTL cache (config.py) + cache nou pentru surse care nu aveau
niciunul: SEAP contracte, HCL, ANAF v9.

Toate testele mockuiesc rețeaua → rulează offline.
"""
import json
import os
import sqlite3
import sys
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from monitor_pantelimon import fetch_contracts_seap, fetch_hcl_metadata, _get_firme_anaf_batch


# ── config.py — valori centralizate ─────────────────────────────────────────

class TestConfigTtl:

    def test_valori_ajustate(self):
        assert config.TTL_SEAP_CONTRACTE_DAYS == 7
        assert config.TTL_HCL_DAYS == 7
        assert config.TTL_CURTEA_CONTURI_DAYS == 90
        assert config.TTL_MOL_DAYS == 14
        assert config.TTL_NOMINATIM_DAYS == 365
        assert config.TTL_ANAF_V9_DAYS == 365
        assert config.TTL_FIRME_FINANCIAR_REFRESH_DAYS == 365

    def test_valori_neschimbate(self):
        assert config.TTL_MFINANTE_DAYS == 30
        assert config.TTL_ANI_DAYS == 30
        assert config.TTL_TED_DAYS == 7
        assert config.TTL_PNRR_DAYS == 7
        assert config.TTL_ONRC_DAYS == 30
        assert config.TTL_PRESA_DAYS == 7


# ── fetch_contracts_seap — cache nou (7 zile) ───────────────────────────────

class TestFetchContractsSeapCache:

    def test_cache_sqlite_creat(self, tmp_path):
        cache_db = str(tmp_path / "seap.db")
        with patch("monitor_pantelimon.requests.get", side_effect=OSError("timeout")):
            fetch_contracts_seap("4420759", cache_db=cache_db)

        assert os.path.exists(cache_db)
        conn = sqlite3.connect(cache_db)
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        conn.close()
        assert "seap_contracte" in tables

    def test_cache_hit_nu_face_request(self, tmp_path):
        cache_db = str(tmp_path / "seap.db")
        with patch("monitor_pantelimon.requests.get", side_effect=OSError("timeout")):
            fetch_contracts_seap("4420759", cache_db=cache_db)

        with patch("monitor_pantelimon.requests.get") as mock_get:
            contracte, debug = fetch_contracts_seap("4420759", cache_db=cache_db)

        mock_get.assert_not_called()
        assert isinstance(contracte, list)


# ── fetch_hcl_metadata — cache nou (7 zile) ─────────────────────────────────

class TestFetchHclMetadataCache:

    def test_cache_sqlite_creat(self, tmp_path):
        cache_db = str(tmp_path / "hcl.db")
        with patch("monitor_pantelimon.requests.get", side_effect=OSError("timeout")):
            fetch_hcl_metadata("https://www.primariapantelimon.ro/hotarari-2025/", cache_db=cache_db)

        assert os.path.exists(cache_db)
        conn = sqlite3.connect(cache_db)
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        conn.close()
        assert "hcl_metadata" in tables

    def test_cache_hit_nu_face_request(self, tmp_path):
        cache_db = str(tmp_path / "hcl.db")
        url = "https://www.primariapantelimon.ro/hotarari-2025/"
        with patch("monitor_pantelimon.requests.get", side_effect=OSError("timeout")):
            fetch_hcl_metadata(url, cache_db=cache_db)

        with patch("monitor_pantelimon.requests.get") as mock_get:
            rezultat = fetch_hcl_metadata(url, cache_db=cache_db)

        mock_get.assert_not_called()
        assert rezultat == []


# ── _get_firme_anaf_batch — cache nou (365 zile) ────────────────────────────

ANAF_RESPONSE_OK = {
    "found": [
        {
            "date_generale": {
                "cui": 12345678,
                "denumire": "FIRMA TEST SRL",
                "data_infiintare": "2015-03-01",
                "stare_inregistrare": "VALID",
                "nrRegCom": "J40/1234/2015",
            },
            "stare_inactiv": {"statusInactivi": False},
        }
    ]
}


def _mock_anaf_response():
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = ANAF_RESPONSE_OK
    return resp


class TestGetFirmeAnafBatchCache:

    def test_cache_json_populat(self, tmp_path):
        fisier_cache = str(tmp_path / "cache_firme.json")
        with patch("monitor_pantelimon.requests.post", return_value=_mock_anaf_response()):
            rezultat = _get_firme_anaf_batch(["12345678"], fisier_cache=fisier_cache)

        assert "12345678" in rezultat
        with open(fisier_cache, encoding="utf-8") as f:
            cache = json.load(f)
        assert "_anaf_v9_data" in cache
        assert "12345678" in cache["_anaf_v9_data"]

    def test_cache_hit_nu_face_request(self, tmp_path):
        fisier_cache = str(tmp_path / "cache_firme.json")
        with patch("monitor_pantelimon.requests.post", return_value=_mock_anaf_response()):
            _get_firme_anaf_batch(["12345678"], fisier_cache=fisier_cache)

        with patch("monitor_pantelimon.requests.post") as mock_post:
            rezultat = _get_firme_anaf_batch(["12345678"], fisier_cache=fisier_cache)

        mock_post.assert_not_called()
        assert rezultat["12345678"]["denumire"] == "FIRMA TEST SRL"
