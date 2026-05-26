"""
Teste unitare pentru risc_firma.py — evaluate_shell_risk + cache + HTML panel.
Nu fac request-uri de rețea — testează doar logica pură.

Rulare: py tests/test_risc_firma.py
"""
import sys, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from risc_firma import evaluate_shell_risk, get_risk_panel_html, _cache_set, _cache_get


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _firma(ca=None, sal=None, prof=None, year='2024', cif='12345678'):
    ani = {}
    entry = {}
    if ca is not None:   entry['cifra_afaceri'] = ca
    if sal is not None:  entry['salariati'] = sal
    if prof is not None: entry['profit_net'] = prof
    ani[year] = entry
    return {'cif': cif, 'extras_la': '2026-01-01T00:00:00', 'ani': ani}


# ──────────────────────────────────────────────────────────────────────────────
# evaluate_shell_risk
# ──────────────────────────────────────────────────────────────────────────────

def test_zero_ca_este_critic():
    """Cifra de afaceri 0 → CIFRA_AFACERI_ZERO / CRITIC."""
    flags = evaluate_shell_risk(_firma(ca=0, sal=1), '2025-03-01', 500_000)
    coduri = [f['cod'] for f in flags]
    assert 'CIFRA_AFACERI_ZERO' in coduri
    c = next(f for f in flags if f['cod'] == 'CIFRA_AFACERI_ZERO')
    assert c['severitate'] == 'CRITIC'


def test_ca_sub_10_pct_este_major():
    """CA = 4% din valoarea contractului → CIFRA_AFACERI_MULT_SUB_CONTRACT / MAJOR."""
    flags = evaluate_shell_risk(_firma(ca=20_000, sal=5), '2025-03-01', 500_000)
    coduri = [f['cod'] for f in flags]
    assert 'CIFRA_AFACERI_MULT_SUB_CONTRACT' in coduri
    c = next(f for f in flags if f['cod'] == 'CIFRA_AFACERI_MULT_SUB_CONTRACT')
    assert c['severitate'] == 'MAJOR'


def test_ca_intre_10_si_50_pct_este_mediu():
    """CA = 30% din valoarea contractului → CIFRA_AFACERI_SUB_CONTRACT / MEDIU."""
    flags = evaluate_shell_risk(_firma(ca=150_000, sal=10), '2025-03-01', 500_000)
    coduri = [f['cod'] for f in flags]
    assert 'CIFRA_AFACERI_SUB_CONTRACT' in coduri
    c = next(f for f in flags if f['cod'] == 'CIFRA_AFACERI_SUB_CONTRACT')
    assert c['severitate'] == 'MEDIU'


def test_ca_ok_niciun_flag_ca():
    """CA > 50% din contract → niciun flag CA."""
    flags = evaluate_shell_risk(_firma(ca=600_000, sal=20), '2025-03-01', 500_000)
    coduri = [f['cod'] for f in flags]
    assert 'CIFRA_AFACERI_ZERO' not in coduri
    assert 'CIFRA_AFACERI_MULT_SUB_CONTRACT' not in coduri
    assert 'CIFRA_AFACERI_SUB_CONTRACT' not in coduri


def test_zero_angajati_este_major():
    """0 angajați → ZERO_ANGAJATI / MAJOR."""
    flags = evaluate_shell_risk(_firma(ca=1_000_000, sal=0), '2025-03-01', 500_000)
    coduri = [f['cod'] for f in flags]
    assert 'ZERO_ANGAJATI' in coduri
    c = next(f for f in flags if f['cod'] == 'ZERO_ANGAJATI')
    assert c['severitate'] == 'MAJOR'


def test_1_angajat_este_mediu():
    """1 angajat → FOARTE_PUTINI_ANGAJATI / MEDIU."""
    flags = evaluate_shell_risk(_firma(ca=1_000_000, sal=1), '2025-03-01', 500_000)
    coduri = [f['cod'] for f in flags]
    assert 'FOARTE_PUTINI_ANGAJATI' in coduri
    c = next(f for f in flags if f['cod'] == 'FOARTE_PUTINI_ANGAJATI')
    assert c['severitate'] == 'MEDIU'


def test_2_angajati_este_mediu():
    """2 angajați → FOARTE_PUTINI_ANGAJATI / MEDIU."""
    flags = evaluate_shell_risk(_firma(ca=1_000_000, sal=2), '2025-03-01', 500_000)
    coduri = [f['cod'] for f in flags]
    assert 'FOARTE_PUTINI_ANGAJATI' in coduri


def test_3_plus_angajati_niciun_flag_angajati():
    """3+ angajați → niciun flag angajați."""
    flags = evaluate_shell_risk(_firma(ca=1_000_000, sal=3), '2025-03-01', 500_000)
    coduri = [f['cod'] for f in flags]
    assert 'ZERO_ANGAJATI' not in coduri
    assert 'FOARTE_PUTINI_ANGAJATI' not in coduri


def test_firma_fara_date_returneaza_lista_goala():
    """Firmă fără date → []."""
    assert evaluate_shell_risk({}, '2025-03-01', 500_000) == []
    assert evaluate_shell_risk(None, '2025-03-01', 500_000) == []
    assert evaluate_shell_risk({'error': 'timeout', 'ani': {}}, '2025-03-01', 500_000) == []


def test_firma_fara_ani_returneaza_lista_goala():
    """Firmă cu ani={} → []."""
    assert evaluate_shell_risk({'cif': '1', 'ani': {}}, '2025-03-01', 500_000) == []


def test_data_invalida_returneaza_lista_goala():
    """Data contractului invalida → []."""
    flags = evaluate_shell_risk(_firma(ca=0, sal=0), 'invalid-date', 500_000)
    assert flags == []


def test_foloseste_an_anterior_contractului():
    """Se folosesc datele din anul anterior contractului (2024 pentru contract 2025)."""
    # Firma are date in 2024 si 2023; contractul e din 2025 → se foloseste 2024
    firma = {
        'cif': '1',
        'extras_la': '2026-01-01',
        'ani': {
            '2024': {'cifra_afaceri': 0, 'salariati': 0},
            '2023': {'cifra_afaceri': 1_000_000, 'salariati': 50},
        },
    }
    flags = evaluate_shell_risk(firma, '2025-06-01', 500_000)
    coduri = [f['cod'] for f in flags]
    # Trebuie sa foloseasca 2024 (0 CA, 0 angajati) nu 2023
    assert 'CIFRA_AFACERI_ZERO' in coduri
    assert 'ZERO_ANGAJATI' in coduri


def test_fallback_la_an_anterior2_daca_lipseste_an1():
    """Dacă lipsesc date din an-1, se folosesc datele din an-2."""
    firma = {
        'cif': '1',
        'extras_la': '2026-01-01',
        'ani': {
            '2023': {'cifra_afaceri': 0, 'salariati': 0},
            # 2024 lipseste
        },
    }
    flags = evaluate_shell_risk(firma, '2025-06-01', 500_000)
    coduri = [f['cod'] for f in flags]
    assert 'CIFRA_AFACERI_ZERO' in coduri


def test_multiple_flags_simultan():
    """CA = 0 și 0 angajați → ambele flag-uri prezente."""
    flags = evaluate_shell_risk(_firma(ca=0, sal=0), '2025-03-01', 500_000)
    coduri = [f['cod'] for f in flags]
    assert 'CIFRA_AFACERI_ZERO' in coduri
    assert 'ZERO_ANGAJATI' in coduri
    assert len(flags) == 2


# ──────────────────────────────────────────────────────────────────────────────
# Cache SQLite
# ──────────────────────────────────────────────────────────────────────────────

def test_cache_round_trip():
    """Set + get pe cache temporar returnează datele corecte."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    try:
        data = {'cif': '99999999', 'ani': {'2024': {'cifra_afaceri': 500_000}}}
        _cache_set('99999999', data, db_path)
        result = _cache_get('99999999', db_path)
        assert result is not None
        assert result['ani']['2024']['cifra_afaceri'] == 500_000
    finally:
        os.unlink(db_path)


def test_cache_miss_returneaza_none():
    """CIF inexistent în cache → None."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    try:
        assert _cache_get('00000000', db_path) is None
    finally:
        os.unlink(db_path)


# ──────────────────────────────────────────────────────────────────────────────
# get_risk_panel_html
# ──────────────────────────────────────────────────────────────────────────────

def test_panel_html_cu_flags():
    """Panel HTML conține codurile flag-urilor când există riscuri."""
    firma = _firma(ca=0, sal=0)
    html = get_risk_panel_html('12345678', firma, '2025-03-01', 500_000)
    assert 'supplier-risk-panel' in html
    assert 'CIFRA AFACERI ZERO' in html or 'CIFRA_AFACERI_ZERO' in html
    assert 'ZERO ANGAJATI' in html or 'ZERO_ANGAJATI' in html


def test_panel_html_fara_date_returneaza_gol():
    """Panel HTML gol când nu există date."""
    assert get_risk_panel_html('12345678', {}, '2025-03-01', 500_000) == ''
    assert get_risk_panel_html('12345678', None, '2025-03-01', 500_000) == ''
    assert get_risk_panel_html('12345678', {'error': 'x', 'ani': {}}, '2025-03-01', 0) == ''


def test_panel_html_fara_flags_fundal_verde():
    """Panel HTML fără riscuri are data-risk-count=0."""
    firma = _firma(ca=1_000_000, sal=50)
    html = get_risk_panel_html('12345678', firma, '2025-03-01', 100_000)
    assert 'data-risk-count="0"' in html


def test_panel_html_contine_an_date():
    """Panel HTML afișează anul datelor financiare."""
    firma = _firma(ca=500_000, sal=10, year='2024')
    html = get_risk_panel_html('12345678', firma, '2025-03-01', 100_000)
    assert '2024' in html


# ──────────────────────────────────────────────────────────────────────────────
# Runner standalone
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    tests = [
        test_zero_ca_este_critic,
        test_ca_sub_10_pct_este_major,
        test_ca_intre_10_si_50_pct_este_mediu,
        test_ca_ok_niciun_flag_ca,
        test_zero_angajati_este_major,
        test_1_angajat_este_mediu,
        test_2_angajati_este_mediu,
        test_3_plus_angajati_niciun_flag_angajati,
        test_firma_fara_date_returneaza_lista_goala,
        test_firma_fara_ani_returneaza_lista_goala,
        test_data_invalida_returneaza_lista_goala,
        test_foloseste_an_anterior_contractului,
        test_fallback_la_an_anterior2_daca_lipseste_an1,
        test_multiple_flags_simultan,
        test_cache_round_trip,
        test_cache_miss_returneaza_none,
        test_panel_html_cu_flags,
        test_panel_html_fara_date_returneaza_gol,
        test_panel_html_fara_flags_fundal_verde,
        test_panel_html_contine_an_date,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f'  PASS  {t.__name__}')
            passed += 1
        except Exception as e:
            print(f'  FAIL  {t.__name__}: {e}')
            import traceback; traceback.print_exc()
            failed += 1
    print(f'\n{passed} passed, {failed} failed')
    sys.exit(1 if failed else 0)
