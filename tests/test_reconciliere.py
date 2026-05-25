"""
Teste unitare pentru reconciliere_buget_seap() si _suma_seap_dedupata().
Ruleaza cu: py -m pytest tests/test_reconciliere.py -v
Sau fara pytest: py tests/test_reconciliere.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from monitor_pantelimon import reconciliere_buget_seap, _suma_seap_dedupata


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _c(titlu, firma, valoare, data='2025-03-01', cui=None):
    """Fabrica un contract cu schema export (valoare/data/firma/cui)."""
    return {'titlu': titlu, 'firma': firma, 'cui': cui or firma,
            'valoare': valoare, 'data': data}

def _ci(titlu, castigator, valoare_ron, data_publicare='2025-03-01', castigator_cui=None):
    """Fabrica un contract cu schema interna (valoare_ron/data_publicare/castigator)."""
    return {'titlu': titlu, 'castigator': castigator,
            'castigator_cui': castigator_cui or castigator,
            'valoare_ron': valoare_ron, 'data_publicare': data_publicare}


# ---------------------------------------------------------------------------
# Teste _suma_seap_dedupata
# ---------------------------------------------------------------------------

def test_dedup_identice():
    """Doua intrari identice (titlu, firma, valoare) → 1 entry, suma = valoarea unica."""
    contracte = [
        _c('Servicii IT', 'FIRMA_A', 10_000),
        _c('Servicii IT', 'FIRMA_A', 10_000),
    ]
    suma, n = _suma_seap_dedupata(contracte, 2025)
    assert n == 1, f'Asteptat 1 contract unic, got {n}'
    assert suma == 10_000, f'Asteptat 10000, got {suma}'


def test_dedup_rev_keep_max():
    """X (Rev.2) 120, X (Rev.1) 100, X 90 → 1 entry, keep max = 120."""
    contracte = [
        _c('Curatenie strazi (Rev.2)', 'FIRMA_B', 120),
        _c('Curatenie strazi (Rev.1)', 'FIRMA_B', 100),
        _c('Curatenie strazi', 'FIRMA_B', 90),
    ]
    suma, n = _suma_seap_dedupata(contracte, 2025)
    assert n == 1, f'Asteptat 1 contract unic, got {n}'
    assert suma == 120, f'Asteptat 120 (max), got {suma}'


def test_dedup_doua_firme_acelasi_titlu():
    """Doua firme diferite cu acelasi titlu → 2 entries pastrate (nu se deduplicheaza)."""
    contracte = [
        _c('Consultanta juridica', 'FIRMA_C', 50_000),
        _c('Consultanta juridica', 'FIRMA_D', 45_000),
    ]
    suma, n = _suma_seap_dedupata(contracte, 2025)
    assert n == 2, f'Asteptat 2 contracte unice (firme diferite), got {n}'
    assert suma == 95_000, f'Asteptat 95000, got {suma}'


def test_dedup_filtru_an():
    """Contractele din alt an sunt ignorate."""
    contracte = [
        _c('Contract 2024', 'FIRMA_E', 100_000, data='2024-06-01'),
        _c('Contract 2025', 'FIRMA_E', 200_000, data='2025-06-01'),
    ]
    suma, n = _suma_seap_dedupata(contracte, 2025)
    assert n == 1, f'Asteptat 1 contract (doar 2025), got {n}'
    assert suma == 200_000


def test_dedup_schema_interna():
    """Functia accepta si schema interna (valoare_ron, data_publicare, castigator_cui)."""
    contracte = [
        _ci('Reparatii (Rev.2)', 'FIRMA_F', 80_000),
        _ci('Reparatii', 'FIRMA_F', 60_000),
    ]
    suma, n = _suma_seap_dedupata(contracte, 2025)
    assert n == 1
    assert suma == 80_000


def test_dedup_date_murdare_skip():
    """Contractele fara titlu sau firma sunt sarite (date murdare)."""
    contracte = [
        _c('', 'FIRMA_G', 5_000),        # titlu gol
        _c('Contract valid', '', 3_000),  # firma goala
        _c('Contract valid', 'FIRMA_G', 3_000),  # ok
    ]
    suma, n = _suma_seap_dedupata(contracte, 2025)
    assert n == 1
    assert suma == 3_000


def test_dedup_lista_goala():
    """Lista goala → (0.0, 0)."""
    suma, n = _suma_seap_dedupata([], 2025)
    assert suma == 0.0
    assert n == 0


# ---------------------------------------------------------------------------
# Teste reconciliere_buget_seap — edge cases
# ---------------------------------------------------------------------------

def test_reco_total_anaf_zero():
    """total_anaf = 0 → procentele sunt 0, fara ZeroDivisionError."""
    r = reconciliere_buget_seap({}, [], an=2025)
    assert r['procent_vizibil_in_seap'] == 0.0
    assert r['procent_gap'] == 0.0
    assert r['date_inconsistente'] is False


def test_reco_gap_negativ_returnat_zero():
    """Gap negativ (SEAP > ANAF) → gap_neexplicat_ron = 0, date_inconsistente = True."""
    contracte = [_c('Mare contract', 'FIRMA_H', 200_000_000)]
    r = reconciliere_buget_seap({'cheltuieli_total': 100_000_000}, contracte, an=2025)
    assert r['gap_neexplicat_ron'] == 0.0
    assert r['date_inconsistente'] is True


def test_reco_cheltuieli_mil_ron():
    """Cheie cheltuieli_mil_ron (din fetch_budget_transparenta) convertita corect."""
    r = reconciliere_buget_seap({'cheltuieli_mil_ron': 500.0}, [], an=2025)
    assert r['total_anaf_ron'] == 500_000_000.0


def test_reco_gap_pozitiv_consistent():
    """Cand SEAP << ANAF, gap e pozitiv si date_inconsistente = False."""
    contracte = [_c('Contract mic', 'FIRMA_I', 1_000_000)]
    r = reconciliere_buget_seap({'cheltuieli_total': 100_000_000}, contracte, an=2025)
    assert r['gap_neexplicat_ron'] > 0
    assert r['date_inconsistente'] is False
    # verifica formula: ANAF - salarii(45%) - transferuri(15%) - SEAP >= 0
    expected_gap = 100_000_000 - 45_000_000 - 15_000_000 - 1_000_000
    assert abs(r['gap_neexplicat_ron'] - expected_gap) < 1


def test_reco_estimari_default():
    """estimari_default_folosite = True cand buget_anaf nu are cap_salarii."""
    r = reconciliere_buget_seap({'cheltuieli_total': 100_000_000}, [], an=2025)
    assert r['estimari_default_folosite'] is True


def test_reco_estimari_explicite():
    """estimari_default_folosite = False cand cap_salarii e furnizat explicit."""
    r = reconciliere_buget_seap(
        {'cheltuieli_total': 100_000_000, 'cap_salarii': 40_000_000},
        [], an=2025
    )
    assert r['estimari_default_folosite'] is False
    assert r['salarii_estimate_ron'] == 40_000_000.0


def test_reco_nr_contracte_unice_expus():
    """nr_contracte_unice e prezent in payload si reflecta dedup-ul."""
    contracte = [
        _c('Contract A (Rev.2)', 'FIRMA_J', 50_000),
        _c('Contract A', 'FIRMA_J', 40_000),  # acelasi, se deduplicheaza
        _c('Contract B', 'FIRMA_J', 20_000),  # diferit, ramine
    ]
    r = reconciliere_buget_seap({'cheltuieli_total': 500_000_000}, contracte, an=2025)
    assert r['nr_contracte_unice'] == 2, f'Asteptat 2 unice, got {r["nr_contracte_unice"]}'
    assert r['total_seap_ron'] == 70_000.0  # max(50k,40k) + 20k


# ---------------------------------------------------------------------------
# Runner standalone (fara pytest)
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    tests = [
        test_dedup_identice,
        test_dedup_rev_keep_max,
        test_dedup_doua_firme_acelasi_titlu,
        test_dedup_filtru_an,
        test_dedup_schema_interna,
        test_dedup_date_murdare_skip,
        test_dedup_lista_goala,
        test_reco_total_anaf_zero,
        test_reco_gap_negativ_returnat_zero,
        test_reco_cheltuieli_mil_ron,
        test_reco_gap_pozitiv_consistent,
        test_reco_estimari_default,
        test_reco_estimari_explicite,
        test_reco_nr_contracte_unice_expus,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f'  PASS  {t.__name__}')
            passed += 1
        except Exception as e:
            print(f'  FAIL  {t.__name__}: {e}')
            failed += 1
    print(f'\n{passed} passed, {failed} failed')
    sys.exit(1 if failed else 0)
