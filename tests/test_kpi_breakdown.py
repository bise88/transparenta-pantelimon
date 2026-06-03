"""
tests/test_kpi_breakdown.py
===========================
Teste pentru _categorizeaza_contracte_breakdown() și _LUCR_KEYWORDS.
Acoperă: clasificare, deduplicare Rev.X, an-filter, edge-cases.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from monitor_pantelimon import _categorizeaza_contracte_breakdown, _LUCR_KEYWORDS


# ── Fixtures ────────────────────────────────────────────────────────────────

def _c(titlu, valoare, cui='12345', data='2026-03-01'):
    return {'titlu': titlu, 'valoare': valoare, 'cui': cui, 'data': data}


# ── Teste clasificare ────────────────────────────────────────────────────────

class TestClasificareLucrari:
    def test_lucrari_keyword_reparatii(self):
        contracte = [_c('Servicii de reparatii cladire (Rev.2)', 50000)]
        bkd = _categorizeaza_contracte_breakdown(contracte, 2026)
        assert bkd['lucr_n'] == 1
        assert bkd['srv_n'] == 0

    def test_lucrari_keyword_constructi(self):
        contracte = [_c('Constructie canal pluvial', 200000)]
        bkd = _categorizeaza_contracte_breakdown(contracte, 2026)
        assert bkd['lucr_n'] == 1

    def test_lucrari_keyword_reabilitare(self):
        contracte = [_c('Reabilitare drum comunal DC4', 300000)]
        bkd = _categorizeaza_contracte_breakdown(contracte, 2026)
        assert bkd['lucr_n'] == 1

    def test_lucrari_keyword_modernizare(self):
        contracte = [_c('Modernizare parc central Pantelimon', 150000)]
        bkd = _categorizeaza_contracte_breakdown(contracte, 2026)
        assert bkd['lucr_n'] == 1

    def test_servicii_curatenie(self):
        contracte = [_c('Servicii de curatenie sediu primarie', 48000)]
        bkd = _categorizeaza_contracte_breakdown(contracte, 2026)
        assert bkd['srv_n'] == 1
        assert bkd['lucr_n'] == 0

    def test_servicii_furnizare(self):
        contracte = [_c('Furnizare materiale birotice', 12000)]
        bkd = _categorizeaza_contracte_breakdown(contracte, 2026)
        assert bkd['srv_n'] == 1

    def test_servicii_consultanta(self):
        contracte = [_c('Consultanta juridica primarie', 24000)]
        bkd = _categorizeaza_contracte_breakdown(contracte, 2026)
        assert bkd['srv_n'] == 1

    def test_mixed_categorie_separata(self):
        """Contracte mixte clasificate independent."""
        contracte = [
            _c('Lucrari de amenajare parc', 100000, cui='111'),
            _c('Servicii de paza obiectiv', 60000, cui='222'),
        ]
        bkd = _categorizeaza_contracte_breakdown(contracte, 2026)
        assert bkd['lucr_n'] == 1
        assert bkd['srv_n'] == 1
        assert bkd['total'] == 160000


# ── Teste deduplicare ────────────────────────────────────────────────────────

class TestDeduplicareRevX:
    def test_rev2_pastreaza_maxim(self):
        """Rev.2 cu valoare mai mare înlocuiește contractul original."""
        contracte = [
            _c('Servicii curatenie (Rev.1)', 45000),
            _c('Servicii curatenie (Rev.2)', 50000),
        ]
        bkd = _categorizeaza_contracte_breakdown(contracte, 2026)
        assert bkd['srv_n'] == 1
        assert bkd['srv_total'] == 50000

    def test_rev_firme_diferite_nu_se_merge(self):
        """Același titlu, firme diferite = 2 contracte distincte."""
        contracte = [
            _c('Servicii IT', 30000, cui='AAA'),
            _c('Servicii IT', 30000, cui='BBB'),
        ]
        bkd = _categorizeaza_contracte_breakdown(contracte, 2026)
        assert bkd['srv_n'] == 2
        assert bkd['srv_total'] == 60000

    def test_rev_case_insensitive(self):
        """(REV.2) uppercase tratat la fel."""
        contracte = [
            _c('Reparatii acoperis (REV.2)', 80000),
            _c('Reparatii acoperis (Rev.1)', 70000),
        ]
        bkd = _categorizeaza_contracte_breakdown(contracte, 2026)
        assert bkd['lucr_n'] == 1
        assert bkd['lucr_total'] == 80000


# ── Teste filtru an ──────────────────────────────────────────────────────────

class TestFiltruAn:
    def test_filtreaza_alt_an(self):
        """Contracte din 2025 nu apar în breakdownul 2026."""
        contracte = [
            _c('Servicii consultanta', 20000, data='2025-06-15'),
            _c('Lucrari consolidare', 500000, data='2026-02-20'),
        ]
        bkd = _categorizeaza_contracte_breakdown(contracte, 2026)
        assert bkd['n'] == 1
        assert bkd['lucr_n'] == 1

    def test_an_gol_skip(self):
        """Contracte fără dată sunt ignorate."""
        contracte = [_c('Servicii IT', 10000, data='')]
        bkd = _categorizeaza_contracte_breakdown(contracte, 2026)
        assert bkd['n'] == 0

    def test_toate_zero_fara_contracte(self):
        """Lista goală returnează zerouri corecte."""
        bkd = _categorizeaza_contracte_breakdown([], 2026)
        assert bkd['n'] == 0
        assert bkd['total'] == 0.0
        assert bkd['medie'] == 0


# ── Teste matematică ─────────────────────────────────────────────────────────

class TestMatematica:
    def test_total_suma_categorii(self):
        """total == lucr_total + srv_total."""
        contracte = [
            _c('Reparatii fatada', 100000, cui='A'),
            _c('Servicii web', 20000, cui='B'),
            _c('Amenajare gradina', 30000, cui='C'),
        ]
        bkd = _categorizeaza_contracte_breakdown(contracte, 2026)
        assert bkd['total'] == bkd['lucr_total'] + bkd['srv_total']

    def test_n_suma_categorii(self):
        """n == lucr_n + srv_n."""
        contracte = [
            _c('Constructie gard', 50000, cui='X'),
            _c('Servicii copiere', 5000, cui='Y'),
        ]
        bkd = _categorizeaza_contracte_breakdown(contracte, 2026)
        assert bkd['n'] == bkd['lucr_n'] + bkd['srv_n']

    def test_medie_corecta(self):
        """medie == total / n."""
        contracte = [
            _c('Servicii A', 10000, cui='A'),
            _c('Servicii B', 30000, cui='B'),
        ]
        bkd = _categorizeaza_contracte_breakdown(contracte, 2026)
        assert bkd['medie'] == 20000.0

    def test_keywords_lista_populata(self):
        """_LUCR_KEYWORDS nu e goală și conține elemente cunoscute."""
        assert len(_LUCR_KEYWORDS) >= 5
        assert 'reparatii' in _LUCR_KEYWORDS
        assert 'reabilitare' in _LUCR_KEYWORDS
        assert 'constructi' in _LUCR_KEYWORDS
