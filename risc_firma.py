"""
risc_firma.py — Detector indicatori de risc pentru firme furnizoare
====================================================================

Extrage date financiare publice de la Ministerul Finanțelor (mfinante.gov.ro)
și calculează indicatori factuali de risc (nu concluzii juridice).

Utilizare:
    from risc_firma import fetch_firma_anaf, evaluate_shell_risk, get_risk_panel_html

    profil = fetch_firma_anaf('12345678', 'transparenta-pantelimon-bot (contact: office@valisblue.com)')
    flags  = evaluate_shell_risk(profil, contract_date='2025-03-01', contract_value=500_000)

Rate limiting: 1.2s între request-uri. Respectă robots.txt al mfinante.gov.ro.
Cache: SQLite local (firme_cache.db), TTL 30 zile.

ATENȚIE: Datele ANAF au decalaj 6-12 luni față de realitate.
"""

import json
import os
import re
import sqlite3
import time
from datetime import datetime, timedelta

CONTACT_EMAIL_DEFAULT = 'transparenta-pantelimon-bot (contact: office@valisblue.com)'
TTL_DAYS = 30
CACHE_FILE = 'firme_cache.db'
REQUEST_DELAY = 1.2   # secunde între request-uri (rate limiting)

# ──────────────────────────────────────────────────────────────────────────────
# Cache SQLite
# ──────────────────────────────────────────────────────────────────────────────

def _init_cache(db_path: str = CACHE_FILE) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS firme (
            cif         TEXT PRIMARY KEY,
            extras_la   TEXT NOT NULL,
            date_json   TEXT NOT NULL
        )
    ''')
    conn.commit()
    return conn


def _cache_get(cif: str, db_path: str = CACHE_FILE) -> dict | None:
    """Returnează datele din cache dacă există și nu sunt expirate (TTL_DAYS)."""
    try:
        conn = _init_cache(db_path)
        row = conn.execute(
            'SELECT extras_la, date_json FROM firme WHERE cif = ?', (cif,)
        ).fetchone()
        conn.close()
        if not row:
            return None
        extras_la = datetime.fromisoformat(row[0])
        if datetime.now() - extras_la > timedelta(days=TTL_DAYS):
            return None
        return json.loads(row[1])
    except Exception:
        return None


def _cache_set(cif: str, data: dict, db_path: str = CACHE_FILE) -> None:
    """Salvează datele în cache."""
    try:
        conn = _init_cache(db_path)
        conn.execute(
            'INSERT OR REPLACE INTO firme VALUES (?, ?, ?)',
            (cif, datetime.now().isoformat(), json.dumps(data, ensure_ascii=False))
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


# ──────────────────────────────────────────────────────────────────────────────
# Fetch date financiare din mfinante.gov.ro (ANAF — date publice)
# ──────────────────────────────────────────────────────────────────────────────

def fetch_firma_anaf(cif: str, contact_email: str = CONTACT_EMAIL_DEFAULT,
                    db_path: str = CACHE_FILE) -> dict:
    """
    Extrage cifra de afaceri, profit și număr salariați din declarațiile
    financiare publice de pe mfinante.gov.ro (date ANAF gratuite, L544/2001).

    Returnează dict cu câmpurile:
        cif, extras_la, error (optional), ani: {an: {cifra_afaceri, profit, salariati}}

    ATENȚIE: datele au decalaj 6-12 luni față de realitate.
    """
    cif_clean = str(cif).lstrip('RO').strip()

    # ── Cache hit ──
    cached = _cache_get(cif_clean, db_path)
    if cached:
        return cached

    # ── Fetch live ──
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError as e:
        return {'cif': cif_clean, 'error': f'Dependință lipsă: {e}', 'ani': {}}

    url = (
        'https://mfinante.gov.ro/static/10/Anaf/'
        f'Informatii_R/situatii_financiare.html?cui={cif_clean}'
    )
    headers = {
        'User-Agent': f'transparenta-pantelimon-bot (contact: {contact_email})',
        'Accept-Language': 'ro,en-US;q=0.9',
    }

    time.sleep(REQUEST_DELAY)

    try:
        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()
    except Exception as e:
        result = {'cif': cif_clean, 'error': str(e), 'ani': {},
                  'extras_la': datetime.now().isoformat()}
        _cache_set(cif_clean, result, db_path)
        return result

    soup = BeautifulSoup(r.text, 'html.parser')
    data = {'cif': cif_clean, 'extras_la': datetime.now().isoformat(), 'ani': {}}

    # Parsing tabel situații financiare
    # Structura tipică: prima coloană = indicator, restul = ani (desc)
    for table in soup.find_all('table'):
        headers_row = table.find('tr')
        if not headers_row:
            continue
        col_headers = [th.get_text(strip=True)
                       for th in headers_row.find_all(['th', 'td'])]
        years = [h for h in col_headers if re.match(r'20\d{2}', h)]

        for row in table.find_all('tr')[1:]:
            cells = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
            if len(cells) < 2:
                continue
            label = cells[0].lower()
            for i, year in enumerate(years, start=1):
                if i >= len(cells):
                    break
                val_str = cells[i].replace('.', '').replace(',', '.').replace(' ', '').replace('\xa0', '')
                try:
                    val = float(val_str)
                except ValueError:
                    continue
                entry = data['ani'].setdefault(year, {})
                if 'cifr' in label and 'afacer' in label:
                    entry['cifra_afaceri'] = val
                elif 'profit' in label and 'pierdere' not in label and 'net' not in label:
                    entry['profit_brut'] = val
                elif 'profit net' in label:
                    entry['profit_net'] = val
                elif 'salariat' in label or 'angajat' in label:
                    try:
                        entry['salariati'] = int(val)
                    except ValueError:
                        entry['salariati'] = val

    _cache_set(cif_clean, data, db_path)
    return data


# ──────────────────────────────────────────────────────────────────────────────
# Evaluare indicatori de risc (fapte factuale — nu concluzii juridice)
# ──────────────────────────────────────────────────────────────────────────────

def evaluate_shell_risk(firma_data: dict, contract_date: str,
                        contract_value: float) -> list[dict]:
    """
    Compară datele financiare ale firmei cu parametrii contractului.
    Returnează o listă de indicatori factuali de risc (nu etichete subiective).

    Fiecare indicator:
        cod, severitate (CRITIC/MAJOR/MEDIU), descriere

    ATENȚIE: Datele ANAF au decalaj 6-12 luni. Un indicator de risc nu înseamnă
    neapărat o problemă reală — lasă concluzia la latitudinea cititorului.
    """
    if not firma_data or 'error' in firma_data:
        return []
    if not firma_data.get('ani'):
        return []

    flags = []
    try:
        year_contract = int(contract_date[:4])
    except (TypeError, ValueError):
        return []

    year_prev = str(year_contract - 1)
    year_prev2 = str(year_contract - 2)
    ani = firma_data.get('ani', {})

    # Folosim cel mai recent an disponibil anterior contractului
    year_ref = None
    for y in [year_prev, year_prev2]:
        if y in ani:
            year_ref = y
            break

    if year_ref:
        ca   = ani[year_ref].get('cifra_afaceri')
        sal  = ani[year_ref].get('salariati')
        prof = ani[year_ref].get('profit_net') or ani[year_ref].get('profit_brut')

        # ── Cifra de afaceri ──
        if ca == 0:
            flags.append({
                'cod': 'CIFRA_AFACERI_ZERO',
                'severitate': 'CRITIC',
                'descriere': (
                    f'Cifra de afaceri în {year_ref}: 0 RON. '
                    f'Valoare contract: {contract_value:,.0f} RON.'
                ),
            })
        elif ca is not None and contract_value > 0 and ca < contract_value * 0.1:
            flags.append({
                'cod': 'CIFRA_AFACERI_MULT_SUB_CONTRACT',
                'severitate': 'MAJOR',
                'descriere': (
                    f'Cifra de afaceri în {year_ref}: {ca:,.0f} RON '
                    f'(sub 10% din valoarea contractului de {contract_value:,.0f} RON).'
                ),
            })
        elif ca is not None and contract_value > 0 and ca < contract_value * 0.5:
            flags.append({
                'cod': 'CIFRA_AFACERI_SUB_CONTRACT',
                'severitate': 'MEDIU',
                'descriere': (
                    f'Cifra de afaceri în {year_ref}: {ca:,.0f} RON '
                    f'(sub 50% din valoarea contractului de {contract_value:,.0f} RON).'
                ),
            })

        # ── Angajați ──
        if sal == 0:
            flags.append({
                'cod': 'ZERO_ANGAJATI',
                'severitate': 'MAJOR',
                'descriere': f'0 angajați declarați la ANAF pentru {year_ref}.',
            })
        elif sal is not None and sal <= 2:
            flags.append({
                'cod': 'FOARTE_PUTINI_ANGAJATI',
                'severitate': 'MEDIU',
                'descriere': f'{sal} angajat(i) declarați în {year_ref}.',
            })

    return flags


# ──────────────────────────────────────────────────────────────────────────────
# Generator HTML panel „Profil firmă" (pentru raportul HTML)
# ──────────────────────────────────────────────────────────────────────────────

def get_risk_panel_html(cif: str, firma_data: dict,
                        contract_date: str, contract_value: float) -> str:
    """
    Generează un bloc HTML cu datele financiare publice ale firmei și
    indicatorii de risc. Destinat inserției în cardul de nereguă din raport.

    Returnează string HTML gol dacă nu există date.
    """
    if not firma_data or 'error' in firma_data or not firma_data.get('ani'):
        return ''

    flags = evaluate_shell_risk(firma_data, contract_date, contract_value)
    risk_count = len(flags)

    # Alege cel mai recent an cu date
    ani = firma_data.get('ani', {})
    year_display = max(ani.keys()) if ani else '–'
    entry = ani.get(year_display, {})

    ca   = entry.get('cifra_afaceri')
    sal  = entry.get('salariati')
    prof = entry.get('profit_net') or entry.get('profit_brut')
    extras_la = firma_data.get('extras_la', '')[:10]

    def _fmt(v, suffix='RON'):
        if v is None:
            return '–'
        if isinstance(v, float):
            return f'{v:,.0f} {suffix}'
        return f'{v} {suffix}'

    flags_html = ''
    for f in flags:
        sev_col = {'CRITIC': '#991b1b', 'MAJOR': '#b45309', 'MEDIU': '#854d0e'}.get(
            f['severitate'], '#374151')
        flags_html += (
            f'<span style="display:inline-block;margin:.15rem .2rem;padding:.1rem .45rem;'
            f'background:#fef2f2;color:{sev_col};border:1px solid #fca5a5;'
            f'border-radius:4px;font-size:.72rem;font-weight:600">'
            f'⚠ {f["cod"].replace("_"," ")}</span>'
        )

    panel_bg = '#fff7ed' if risk_count > 0 else '#f0fdf4'
    panel_border = '#fed7aa' if risk_count > 0 else '#bbf7d0'

    return f'''<div class="supplier-risk-panel" data-risk-count="{risk_count}"
     style="margin:.75rem 0;padding:.75rem 1rem;background:{panel_bg};
            border:1px solid {panel_border};border-radius:8px;font-size:.85rem">
  <h4 style="margin:0 0 .5rem;font-size:.88rem;color:#374151">
    📇 Date financiare publice (ANAF {year_display})
  </h4>
  <dl style="display:grid;grid-template-columns:max-content 1fr;gap:.2rem .75rem;margin:0">
    <dt style="color:#6b7280">Cifra de afaceri</dt>
    <dd style="margin:0">{_fmt(ca)}</dd>
    <dt style="color:#6b7280">Angajați declarați</dt>
    <dd style="margin:0">{_fmt(sal, '')}</dd>
    <dt style="color:#6b7280">Profit net</dt>
    <dd style="margin:0">{_fmt(prof)}</dd>
  </dl>
  {('<div style="margin-top:.5rem">' + flags_html + '</div>') if flags_html else ''}
  <p style="font-size:.7rem;color:#9ca3af;margin:.5rem 0 0">
    Date publice ANAF/MF — decalaj 6–12 luni. Extrase {extras_la}.
    <a href="https://mfinante.gov.ro/static/10/Anaf/Informatii_R/situatii_financiare.html?cui={cif}"
       target="_blank" rel="noopener" style="color:#6b7280">Sursa ↗</a>
  </p>
</div>'''


# ──────────────────────────────────────────────────────────────────────────────
# Utilitar CLI pentru testare manuală
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print('Utilizare: py risc_firma.py <CIF> [valoare_contract] [data_contract]')
        print('Exemplu:   py risc_firma.py 14922160 500000 2025-03-01')
        sys.exit(1)

    cif_arg = sys.argv[1]
    val_arg = float(sys.argv[2]) if len(sys.argv) > 2 else 100_000.0
    dat_arg = sys.argv[3] if len(sys.argv) > 3 else '2025-01-01'

    print(f'Fetch date ANAF pentru CUI {cif_arg}...')
    profil = fetch_firma_anaf(cif_arg)
    print(f'Date găsite: {json.dumps(profil, ensure_ascii=False, indent=2)}')

    flags = evaluate_shell_risk(profil, dat_arg, val_arg)
    if flags:
        print(f'\n{len(flags)} indicator(i) de risc:')
        for f in flags:
            print(f'  [{f["severitate"]}] {f["cod"]}: {f["descriere"]}')
    else:
        print('\nNiciun indicator de risc detectat (sau date indisponibile).')
