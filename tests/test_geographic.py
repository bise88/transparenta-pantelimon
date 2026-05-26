"""
Teste unitare pentru detect_geographic_anomaly (§2.5 AUDIT.md).
Nu fac request-uri de rețea — testează doar logica pură.

Rulare: py tests/test_geographic.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from monitor_pantelimon import detect_geographic_anomaly


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _contract(titlu='curatenie birouri', cui='11111111', valoare=50_000, data='2025-03-01'):
    return {
        'titlu': titlu,
        'castigator_cui': cui,
        'castigator': f'FIRMA {cui} SRL',
        'valoare_ron': valoare,
        'data_publicare': data,
        'tip_procedura': 'achizitie-directa',
        'contract_id': f'test-{cui}',
    }


def _firma_openapi(judet='VN'):
    """Simulează datele din firme_openapi (openapi.ro enriched)."""
    return {'judet': judet, 'adresa': f'JUD {judet}, ORAS TEST, STR 1', 'stare': 'ACTIVA'}


# ──────────────────────────────────────────────────────────────────────────────
# Teste de bază
# ──────────────────────────────────────────────────────────────────────────────

def test_firma_din_judet_indepartat_genereaza_flag():
    """Firmă din Vrancea pentru servicii de curățenie → GEOGRAFIE_ANORMALA."""
    contracte = [_contract()]
    firme = {'11111111': _firma_openapi('VN')}
    flags = detect_geographic_anomaly(contracte, firme)
    assert len(flags) == 1
    assert flags[0]['tip'] == 'GEOGRAFIE_ANORMALA'
    assert flags[0]['severitate'] == 'MEDIU'


def test_firma_din_ilfov_nu_genereaza_flag():
    """Firmă din Ilfov pentru servicii de curățenie → niciun flag (județ acceptabil)."""
    contracte = [_contract()]
    firme = {'11111111': _firma_openapi('IF')}
    assert detect_geographic_anomaly(contracte, firme) == []


def test_firma_din_bucuresti_nu_genereaza_flag():
    """Firmă din București (B) → niciun flag (în lista județelor acceptabile)."""
    contracte = [_contract()]
    firme = {'11111111': _firma_openapi('B')}
    assert detect_geographic_anomaly(contracte, firme) == []


def test_firma_din_prahova_nu_genereaza_flag():
    """Firmă din Prahova (PH) → niciun flag (județ limitrof acceptat)."""
    contracte = [_contract()]
    firme = {'11111111': _firma_openapi('PH')}
    assert detect_geographic_anomaly(contracte, firme) == []


def test_serviciu_non_local_nu_genereaza_flag():
    """Contract de software (non-local) de la firmă din Timișoara → niciun flag."""
    contracte = [_contract(titlu='dezvoltare software aplicatie web')]
    firme = {'11111111': _firma_openapi('TM')}
    assert detect_geographic_anomaly(contracte, firme) == []


def test_firma_fara_judet_nu_genereaza_flag():
    """Firmă fără câmpul judet → niciun flag (date incomplete)."""
    contracte = [_contract()]
    firme = {'11111111': {'adresa': 'ADRESA INCOMPLETA', 'stare': 'ACTIVA'}}
    assert detect_geographic_anomaly(contracte, firme) == []


def test_fara_firme_openapi_returneaza_gol():
    """firme_openapi gol → niciun flag (openapi.ro neconfigurat)."""
    contracte = [_contract()]
    assert detect_geographic_anomaly(contracte, {}) == []


def test_fara_contracte_returneaza_gol():
    """Lista de contracte goală → []."""
    assert detect_geographic_anomaly([], {'11111111': _firma_openapi('VN')}) == []


def test_paza_din_cluj_genereaza_flag():
    """Servicii de pază din Cluj → GEOGRAFIE_ANORMALA."""
    contracte = [_contract(titlu='servicii de paza obiective publice')]
    firme = {'11111111': _firma_openapi('CJ')}
    flags = detect_geographic_anomaly(contracte, firme)
    assert len(flags) == 1
    assert 'CJ' in flags[0]['titlu'] or 'CJ' in flags[0]['descriere']


def test_salubrizare_din_timisoara_genereaza_flag():
    """Servicii de salubrizare din Timiș → flag generat."""
    contracte = [_contract(titlu='servicii de salubrizare si colectare deseuri')]
    firme = {'11111111': _firma_openapi('TM')}
    flags = detect_geographic_anomaly(contracte, firme)
    assert len(flags) == 1


def test_deszapezire_din_iasi_genereaza_flag():
    """Servicii de deszăpezire din Iași → flag generat."""
    contracte = [_contract(titlu='deszapezire drumuri publice')]
    firme = {'11111111': _firma_openapi('IS')}
    flags = detect_geographic_anomaly(contracte, firme)
    assert len(flags) == 1


def test_multiple_contracte_mix():
    """Contracte mixte: local OK + remote flag → un singur flag."""
    contracte = [
        _contract(titlu='curatenie', cui='11111111'),
        _contract(titlu='curatenie', cui='22222222'),
    ]
    firme = {
        '11111111': _firma_openapi('IF'),   # local → OK
        '22222222': _firma_openapi('VS'),   # Vaslui → flag
    }
    flags = detect_geographic_anomaly(contracte, firme)
    assert len(flags) == 1
    assert flags[0]['cif_furnizor'] == '22222222'


def test_contract_fara_cui_este_ignorat():
    """Contract fără CUI → ignorat graceful."""
    c = _contract()
    del c['castigator_cui']
    flags = detect_geographic_anomaly([c], {'11111111': _firma_openapi('VN')})
    assert flags == []


def test_flag_contine_judet_in_descriere():
    """Descrierea flag-ului menționează județele."""
    contracte = [_contract(titlu='mentenanta spatii verzi')]
    firme = {'11111111': _firma_openapi('TL')}
    flags = detect_geographic_anomaly(contracte, firme)
    assert len(flags) == 1
    assert 'TL' in flags[0]['titlu'] or 'TL' in flags[0]['descriere']


def test_sortat_dupa_valoare_descrescator():
    """Flagurile sunt sortate descrescător după valoare."""
    contracte = [
        _contract(titlu='curatenie', cui='11111111', valoare=100_000),
        _contract(titlu='curatenie', cui='22222222', valoare=200_000),
    ]
    firme = {
        '11111111': _firma_openapi('MS'),
        '22222222': _firma_openapi('BV'),
    }
    flags = detect_geographic_anomaly(contracte, firme)
    assert len(flags) == 2
    assert flags[0]['valoare'] >= flags[1]['valoare']


def test_gradinarit_iluminat_detectat():
    """'iluminat strazi' este un keyword local."""
    contracte = [_contract(titlu='iluminat stradal si spatii publice')]
    firme = {'11111111': _firma_openapi('MH')}
    flags = detect_geographic_anomaly(contracte, firme)
    assert len(flags) == 1


# ──────────────────────────────────────────────────────────────────────────────
# Runner standalone
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    tests = [
        test_firma_din_judet_indepartat_genereaza_flag,
        test_firma_din_ilfov_nu_genereaza_flag,
        test_firma_din_bucuresti_nu_genereaza_flag,
        test_firma_din_prahova_nu_genereaza_flag,
        test_serviciu_non_local_nu_genereaza_flag,
        test_firma_fara_judet_nu_genereaza_flag,
        test_fara_firme_openapi_returneaza_gol,
        test_fara_contracte_returneaza_gol,
        test_paza_din_cluj_genereaza_flag,
        test_salubrizare_din_timisoara_genereaza_flag,
        test_deszapezire_din_iasi_genereaza_flag,
        test_multiple_contracte_mix,
        test_contract_fara_cui_este_ignorat,
        test_flag_contine_judet_in_descriere,
        test_sortat_dupa_valoare_descrescator,
        test_gradinarit_iluminat_detectat,
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
