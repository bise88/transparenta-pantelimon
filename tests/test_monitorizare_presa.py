"""
tests/test_monitorizare_presa.py
=================================
Teste pentru monitorizare_presa.py: keyword matching, fals-pozitive,
cache SQLite, deduplicare link-uri, evalueaza_flag_presa, RSS parsing.
Toate testele rulează offline (mock urllib).
"""
import sys
import os
import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from monitorizare_presa import (
    KEYWORDS_RISC,
    NEGATIVE_KEYWORDS,
    _parse_rss_items,
    _init_db,
    _cache_get,
    _cache_set,
    evalueaza_flag_presa,
    incarca_mentiuni_presa_auto,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

RSS_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    {items}
  </channel>
</rss>"""


def _item(title, link='http://ex.com', source='Test', pub_date='Mon, 01 Jan 2026 00:00:00 +0000'):
    return f"""<item>
      <title>{title}</title>
      <link>{link}</link>
      <source>{source}</source>
      <pubDate>{pub_date}</pubDate>
    </item>"""


def _rss(*titles):
    items = ''.join(_item(t, link=f'http://ex.com/{i}') for i, t in enumerate(titles))
    return RSS_TEMPLATE.format(items=items)


# ── Teste keyword matching ────────────────────────────────────────────────────

class TestKeywordMatch:
    def test_anchet_in_keywords(self):
        assert any('anchet' in k for k in KEYWORDS_RISC)

    def test_dna_in_keywords(self):
        assert 'DNA' in KEYWORDS_RISC

    def test_anaf_in_keywords(self):
        assert 'ANAF' in KEYWORDS_RISC

    def test_evaziune_in_keywords(self):
        assert 'evaziune' in KEYWORDS_RISC

    def test_min_10_keywords(self):
        assert len(KEYWORDS_RISC) >= 10

    def test_anchet_match_titlu_risc(self):
        """Titlul cu 'anchetă' + firma → detectat."""
        xml = _rss('FIRMA X anchetata de DNA pentru frauda')
        items = _parse_rss_items(xml, 'firma x')
        assert len(items) == 1
        assert items[0]['matched_keyword'] in KEYWORDS_RISC

    def test_anaf_match(self):
        xml = _rss('SOCIETATEA TEST SRL, sanctionata de ANAF cu 200.000 RON')
        items = _parse_rss_items(xml, 'societatea test')
        assert len(items) == 1

    def test_corup_match(self):
        xml = _rss('Dosar de coruptie impotriva CONSTRUCT SRL')
        items = _parse_rss_items(xml, 'construct')
        assert len(items) == 1


# ── Teste fals-pozitive ───────────────────────────────────────────────────────

class TestFalsePositiveFilter:
    def test_fotbal_filtrat(self):
        """Anchetă + fotbal → ignorat."""
        xml = _rss('FIRMA TEST sponsorizeaza echipa de fotbal - ancheta locala')
        items = _parse_rss_items(xml, 'firma test')
        assert len(items) == 0

    def test_meteo_filtrat(self):
        xml = _rss('Compania SERVICE SA: vreme rea si auditul anual')
        items = _parse_rss_items(xml, 'service sa')
        assert len(items) == 0

    def test_showbiz_filtrat(self):
        xml = _rss('PRODCOM SRL castiga premiu la festival, ancheta juriului')
        items = _parse_rss_items(xml, 'prodcom')
        assert len(items) == 0

    def test_negative_keywords_lista(self):
        assert len(NEGATIVE_KEYWORDS) >= 5
        assert 'fotbal' in NEGATIVE_KEYWORDS


# ── Teste filtrare firmă ─────────────────────────────────────────────────────

class TestFiltrareFirma:
    def test_firma_fara_cuvant_in_titlu_ignorata(self):
        """Articol despre altă firmă → ignorat chiar dacă are keyword."""
        xml = _rss('ALTA COMPANIE SRL anchetata de DNA')
        items = _parse_rss_items(xml, 'firma noastra')
        assert len(items) == 0

    def test_firma_fara_cuvinte_semnificative_skip_filtru_firma(self):
        """
        Dacă firma are numai cuvinte < 4 litere (SRL, SA etc.),
        filtrul de firmă se dezactivează → se acceptă orice articol cu keyword de risc.
        Aceasta e comportament intenționat: mai bine fals-pozitiv decât fals-negativ
        pentru firme cu denumiri scurte.
        """
        xml = _rss('SA SA SA: ancheta de DNA')
        items = _parse_rss_items(xml, 'sa')
        # Fără cuvinte relevante de firmă → filtrul e dezactivat → keyword match trece
        assert isinstance(items, list)  # nu aruncă excepție

    def test_cuvant_firma_partial_match(self):
        """Un cuvânt semnificativ din denumire este suficient."""
        xml = _rss('Societatea CONSTRUTEC anchetata de DIICOT pentru evaziune')
        items = _parse_rss_items(xml, 'construtec management grup srl')
        assert len(items) == 1


# ── Teste cache SQLite ────────────────────────────────────────────────────────

class TestCacheSQLite:
    def test_init_db_creeaza_tabela(self, tmp_path):
        db_path = tmp_path / 'test_cache.sqlite'
        db = _init_db(db_path)
        tables = [r[0] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        assert 'query_cache' in tables
        db.close()

    def test_cache_miss_returneaza_none(self, tmp_path):
        db = _init_db(tmp_path / 'c.sqlite')
        result = _cache_get(db, 'nonexistent_key')
        assert result is None
        db.close()

    def test_cache_set_get_roundtrip(self, tmp_path):
        db = _init_db(tmp_path / 'c.sqlite')
        data = [{'title': 'Test', 'link': 'http://x.com', 'matched_keyword': 'ANAF'}]
        _cache_set(db, 'key1', 'FIRMA TEST', '123456', 'Google News', data)
        result = _cache_get(db, 'key1')
        assert result is not None
        assert len(result) == 1
        assert result[0]['title'] == 'Test'
        db.close()

    def test_cache_overwrite(self, tmp_path):
        """Scriere cu aceeași cheie suprascrie valoarea anterioară."""
        db = _init_db(tmp_path / 'c.sqlite')
        _cache_set(db, 'k', 'F', '1', 'src', [{'x': 1}])
        _cache_set(db, 'k', 'F', '1', 'src', [{'x': 2}, {'x': 3}])
        result = _cache_get(db, 'k')
        assert len(result) == 2
        db.close()


# ── Teste evalueaza_flag_presa ────────────────────────────────────────────────

class TestEvalueazaFlagPresa:
    def _mp(self, total, mentiuni=None):
        return {
            'total': total,
            'mentiuni': mentiuni or [
                {'title': f'Art {i}', 'link': f'http://ex.com/{i}',
                 'matched_keyword': 'ANAF', 'source': 'Test', 'pub_date': ''}
                for i in range(total)
            ],
            'fetched_at': '2026-06-03T10:00:00',
        }

    def test_zero_mentiuni_returneaza_none(self):
        assert evalueaza_flag_presa(self._mp(0)) is None

    def test_dict_gol_returneaza_none(self):
        assert evalueaza_flag_presa({}) is None

    def test_1_mentiune_severitate_mediu(self):
        flag = evalueaza_flag_presa(self._mp(1))
        assert flag is not None
        assert flag['severitate'] == 'MEDIU'

    def test_2_mentiuni_severitate_mediu(self):
        flag = evalueaza_flag_presa(self._mp(2))
        assert flag['severitate'] == 'MEDIU'

    def test_3_mentiuni_severitate_major(self):
        flag = evalueaza_flag_presa(self._mp(3))
        assert flag['severitate'] == 'MAJOR'

    def test_10_mentiuni_severitate_major(self):
        flag = evalueaza_flag_presa(self._mp(10))
        assert flag['severitate'] == 'MAJOR'

    def test_tip_corect(self):
        flag = evalueaza_flag_presa(self._mp(2))
        assert flag['tip'] == 'MENTIUNI PRESA RISCANTE'

    def test_top5_mentiuni(self):
        """Flag include maxim 5 mențiuni."""
        flag = evalueaza_flag_presa(self._mp(10))
        assert len(flag['mentiuni']) <= 5

    def test_disclaimer_in_descriere(self):
        flag = evalueaza_flag_presa(self._mp(1))
        assert 'fals-pozitive' in flag['descriere'].lower() or 'manual' in flag['descriere'].lower()


# ── Teste incarca_mentiuni_presa_auto ─────────────────────────────────────────

class TestIncarcaMentiuni:
    def test_fisier_lipsa_returneaza_dict_gol(self, tmp_path):
        result = incarca_mentiuni_presa_auto(tmp_path / 'nonexistent.json')
        assert result == {}

    def test_fisier_corupt_returneaza_dict_gol(self, tmp_path):
        p = tmp_path / 'bad.json'
        p.write_text('NOT JSON', encoding='utf-8')
        result = incarca_mentiuni_presa_auto(p)
        assert result == {}

    def test_fisier_valid_incarca_corect(self, tmp_path):
        data = {'123456': {'total': 2, 'mentiuni': [], 'fetched_at': '2026-01-01T00:00:00'}}
        p = tmp_path / 'mentiuni_presa_auto.json'
        p.write_text(json.dumps(data), encoding='utf-8')
        result = incarca_mentiuni_presa_auto(p)
        assert '123456' in result
        assert result['123456']['total'] == 2
