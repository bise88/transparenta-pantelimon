"""
tests/test_retele_firme.py
===========================
Teste pentru analizeaza_retele.py: normalizare adrese, clustering,
deduplicare CUI, gaseste_firme_legate, construieste_retea, incarca_retea.
"""
import sys
import os
import json
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from analizeaza_retele import (
    _norm_adresa,
    _adresa_key,
    detect_adrese_comune,
    gaseste_firme_legate,
    construieste_retea,
    incarca_retea,
)


# ── Teste _norm_adresa ────────────────────────────────────────────────────────

class TestNormAdresa:
    def test_lowercase(self):
        assert _norm_adresa('STR. VICTORIEI NR.1') == _norm_adresa('str. victoriei nr.1')

    def test_diacritice_remove(self):
        n = _norm_adresa('Str. Grădinarilor Nr. 11, Pantelimon')
        assert 'gradinarilor' in n
        assert 'ă' not in n

    def test_prefix_str_eliminat(self):
        n = _norm_adresa('Str. Victoriei 12')
        assert 'str' not in n.split()

    def test_prefix_jud_eliminat(self):
        n = _norm_adresa('Jud. Ilfov, Com. Pantelimon')
        assert 'jud' not in n.split()
        assert 'com' not in n.split()

    def test_prefix_nr_eliminat(self):
        n = _norm_adresa('Str. Mihai Viteazu Nr. 12, Pantelimon')
        # 'nr' trebuie eliminat ca prefix
        assert 'nr' not in n.split()

    def test_adresa_goala_returneaza_gol(self):
        assert _norm_adresa('') == ''
        assert _norm_adresa(None) == ''

    def test_adresa_prea_scurta_returneaza_gol(self):
        assert _norm_adresa('Str. X') == ''  # < 10 chars after normalization

    def test_spatii_multiple_colapsate(self):
        n = _norm_adresa('Str.   Victoriei    12')
        assert '  ' not in n


# ── Teste _adresa_key ─────────────────────────────────────────────────────────

class TestAdresaKey:
    def test_max_6_words(self):
        n = 'ilfov pantelimon gradinarilor 11 demisol etaj 1 ap 2'
        key = _adresa_key(n, max_words=6)
        assert len(key.split()) <= 6

    def test_adresa_scurta_nu_e_trunchitata(self):
        n = 'ilfov pantelimon gradinarilor 11'
        key = _adresa_key(n, max_words=6)
        assert key == n  # mai puțin de 6 cuvinte → returnează totul

    def test_prefix_comun_produce_aceeasi_cheie(self):
        n1 = 'ilfov pantelimon gradinarilor 11'
        n2 = 'ilfov pantelimon gradinarilor 11 etaj 1 ap 5'
        k1 = _adresa_key(n1, max_words=6)
        k2 = _adresa_key(n2, max_words=6)
        # n1 are 4 cuvinte, n2 are mai multe → keys diferite (n1 mai scurtă)
        # dar cu 4 cuvinte max ambele ar fi egale
        k1_4 = _adresa_key(n1, max_words=4)
        k2_4 = _adresa_key(n2, max_words=4)
        assert k1_4 == k2_4


# ── Teste detect_adrese_comune ────────────────────────────────────────────────

class TestDetectAdreseComunePerechi:
    def _f(self, cif, name, adresa):
        return {'cif': cif, 'name': name, 'adresa': adresa}

    def test_doua_firme_aceeasi_adresa(self):
        firme = [
            self._f('1', 'A SRL', 'Str. Mihai Viteazu Nr. 12, Pantelimon, Ilfov'),
            self._f('2', 'B SRL', 'Str. Mihai Viteazu Nr. 12, Pantelimon, Ilfov'),
        ]
        edges = detect_adrese_comune(firme)
        assert len(edges) == 1
        assert set(edges[0]['firme']) == {'1', '2'}

    def test_adrese_diferite_nicio_relatie(self):
        firme = [
            self._f('1', 'A SRL', 'Str. Victoriei Nr. 1, Bucuresti'),
            self._f('2', 'B SRL', 'Sos. Pantelimon Nr. 100, Ilfov'),
        ]
        edges = detect_adrese_comune(firme)
        assert edges == []

    def test_trei_firme_aceeasi_adresa_3_perechi(self):
        adr = 'Str. Independentei Nr. 5, Pantelimon, Ilfov'
        firme = [
            self._f('1', 'A SRL', adr),
            self._f('2', 'B SRL', adr),
            self._f('3', 'C SRL', adr),
        ]
        edges = detect_adrese_comune(firme)
        assert len(edges) == 3  # C(3,2) = 3 perechi

    def test_cui_duplicat_nu_genereaza_edge(self):
        """Aceeași firmă cu CUI duplicat nu generează edge cu sine."""
        adr = 'Str. Libertatii Nr. 10, Pantelimon'
        firme = [
            self._f('999', 'FIRMA X SRL', adr),
            self._f('999', 'FIRMA X SRL', adr),
        ]
        edges = detect_adrese_comune(firme)
        assert edges == []

    def test_tip_edge_corect(self):
        firme = [
            self._f('1', 'A SRL', 'Str. Gradinarilor Nr. 30, Pantelimon, Ilfov'),
            self._f('2', 'B SRL', 'Str. Gradinarilor Nr. 30, Pantelimon, Ilfov'),
        ]
        edges = detect_adrese_comune(firme)
        assert edges[0]['tip'] == 'ADRESA_COMUNA'
        assert edges[0]['severitate'] == 'MEDIU'

    def test_adresa_prea_scurta_ignorata(self):
        """Adrese sub pragul de lungime nu generează edges."""
        firme = [
            self._f('1', 'A SRL', 'X'),
            self._f('2', 'B SRL', 'X'),
        ]
        edges = detect_adrese_comune(firme)
        assert edges == []

    def test_firma_fara_cui_ignorata(self):
        firme = [
            self._f('', 'A SRL', 'Str. Victoriei Nr. 1, Pantelimon, Ilfov'),
            self._f('2', 'B SRL', 'Str. Victoriei Nr. 1, Pantelimon, Ilfov'),
        ]
        edges = detect_adrese_comune(firme)
        assert edges == []

    def test_firma_fara_nume_ignorata(self):
        firme = [
            self._f('1', '', 'Str. Victoriei Nr. 1, Pantelimon, Ilfov'),
            self._f('2', 'B SRL', 'Str. Victoriei Nr. 1, Pantelimon, Ilfov'),
        ]
        edges = detect_adrese_comune(firme)
        assert edges == []


# ── Teste gaseste_firme_legate ────────────────────────────────────────────────

class TestGasesteFirmeLegate:
    def _retea(self, edges):
        return {'edges': edges, 'nodes': []}

    def _edge(self, cui1, n1, cui2, n2, tip='ADRESA_COMUNA'):
        return {
            'tip':   tip,
            'firme': [cui1, cui2],
            'nume':  [n1, n2],
            'adresa': 'test',
            'descriere': '',
        }

    def test_gaseste_firma_legata(self):
        retea = self._retea([self._edge('1', 'A SRL', '2', 'B SRL')])
        legate = gaseste_firme_legate('1', retea)
        assert len(legate) == 1
        assert legate[0]['cui_legat'] == '2'
        assert legate[0]['nume_legat'] == 'B SRL'

    def test_gaseste_din_pozitia_2(self):
        retea = self._retea([self._edge('1', 'A SRL', '2', 'B SRL')])
        legate = gaseste_firme_legate('2', retea)
        assert len(legate) == 1
        assert legate[0]['cui_legat'] == '1'
        assert legate[0]['nume_legat'] == 'A SRL'

    def test_firma_fara_relatie_returneaza_gol(self):
        retea = self._retea([self._edge('1', 'A', '2', 'B')])
        legate = gaseste_firme_legate('999', retea)
        assert legate == []

    def test_retea_goala_returneaza_gol(self):
        assert gaseste_firme_legate('1', {}) == []
        assert gaseste_firme_legate('1', {'edges': []}) == []


# ── Teste construieste_retea ──────────────────────────────────────────────────

class TestConstruiesteRetea:
    def _f(self, cif, name, adresa, lat=44.4, lng=26.1):
        return {'cif': cif, 'name': name, 'adresa': adresa, 'lat': lat, 'lng': lng,
                'valoare': 100000, 'nr_contracte': 5}

    def test_structura_output(self):
        firme = [self._f('1', 'A SRL', 'Str. Victoriei Nr. 1, Pantelimon, Ilfov')]
        retea = construieste_retea(firme)
        assert 'nodes' in retea
        assert 'edges' in retea
        assert 'stats' in retea

    def test_stats_noduri_corecte(self):
        firme = [
            self._f('1', 'A SRL', 'Str. X Nr. 1, Pantelimon, Ilfov'),
            self._f('2', 'B SRL', 'Str. Y Nr. 2, Bucuresti'),
        ]
        retea = construieste_retea(firme)
        assert retea['stats']['total_noduri'] == 2

    def test_lista_goala(self):
        retea = construieste_retea([])
        assert retea['nodes'] == []
        assert retea['edges'] == []


# ── Teste incarca_retea ───────────────────────────────────────────────────────

class TestIncarcaRetea:
    def test_fisier_lipsa(self, tmp_path):
        result = incarca_retea(tmp_path / 'nonexistent.json')
        assert result == {}

    def test_fisier_corupt(self, tmp_path):
        p = tmp_path / 'bad.json'
        p.write_text('NOT JSON', encoding='utf-8')
        assert incarca_retea(p) == {}

    def test_fisier_valid(self, tmp_path):
        data = {'nodes': [], 'edges': [], 'stats': {'total_noduri': 0}}
        p = tmp_path / 'retele_firme.json'
        p.write_text(json.dumps(data), encoding='utf-8')
        result = incarca_retea(p)
        assert 'nodes' in result
