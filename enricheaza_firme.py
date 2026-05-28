#!/usr/bin/env python3
"""
enricheaza_firme.py — Îmbogățire indicatori financiari în raport_transparenta.html
====================================================================================

Citește datele existente din <script id="risc-firma-data">, fetchează date financiare
de la mfinante.gov.ro pentru fiecare firmă (via risc_firma.py cu cache SQLite),
evaluează indicatorii de risc shell (ZERO_ANGAJATI, CIFRA_AFACERI_ZERO etc.) și
actualizează JSON-ul embedded în HTML.

Rulare:
    python enricheaza_firme.py

Efect:
  - raport_transparenta.html actualizat pe disk cu flaguri financiare adăugate
  - firme_cache.db populat (TTL 30 zile, nu se re-fetchează)

ATENȚIE:
  - Rate limiting: 1.2s/firmă — pentru 93 firme = ~2 min
  - NU modifică altceva în HTML (contracte, nereguli, etc.)
  - User-Agent: transparenta-pantelimon-bot (contact: contact@transparenta-pantelimon.eu)
"""
import sys
import json
import re
import os
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HTML_FILE    = 'raport_transparenta.html'
CACHE_FILE   = 'firme_cache.db'
# Setați NO_MFINANTE=1 sau --no-mfinante pentru a sări fetch-ul mfinante
# (util când URL-ul e 404 sau în CI fără acces la internet)
NO_MFINANTE  = '--no-mfinante' in sys.argv or os.environ.get('NO_MFINANTE') == '1'

try:
    from risc_firma import fetch_firma_anaf, evaluate_shell_risk
except ImportError:
    print('[EROARE] risc_firma.py nu a fost găsit în director. Oprire.')
    sys.exit(1)

# ── 1. Citim HTML-ul existent ──────────────────────────────────────────────
if not os.path.exists(HTML_FILE):
    print(f'[EROARE] {HTML_FILE} nu există. Oprire.')
    sys.exit(1)

content = open(HTML_FILE, encoding='utf-8').read()

# ── 2. Extragem blocul risc-firma-data ────────────────────────────────────
m = re.search(
    r'(<script\s+id="risc-firma-data"[^>]*>)(.*?)(</script>)',
    content, re.DOTALL
)
if not m:
    print('[EROARE] Blocul risc-firma-data nu a fost găsit în HTML.')
    sys.exit(1)

tag_open  = m.group(1)
json_str  = m.group(2).strip()
tag_close = m.group(3)

try:
    risc_data = json.loads(json_str)
except json.JSONDecodeError as e:
    print(f'[EROARE] JSON invalid în risc-firma-data: {e}')
    sys.exit(1)

print(f'[OK] Încărcat {len(risc_data)} firme din risc-firma-data.')

# ── 2b. Populăm CUI-urile lipsă din firme_geocoded.json ──────────────────
# Cele 92/93 firme fără CUI în risc-firma-data pot fi cross-referenced
# cu firme_geocoded.json care are CIF-ul din ANAF v9.
GEOCODED_FILE = 'firme_geocoded.json'
if os.path.exists(GEOCODED_FILE):
    try:
        geocoded = json.load(open(GEOCODED_FILE, encoding='utf-8'))
        # Index după name (uppercase)
        geo_by_name = {g['name'].upper().strip(): g['cif'] for g in geocoded if g.get('cif')}
        # Index fuzzy: primele 15 caractere
        geo_by_prefix = {}
        for name, cif in geo_by_name.items():
            prefix = name[:15]
            geo_by_prefix.setdefault(prefix, []).append((name, cif))

        cui_filled = 0
        for furn_name, rd in risc_data.items():
            if rd.get('cui'):
                continue
            name_up = furn_name.upper().strip()
            # Exact match
            if name_up in geo_by_name:
                rd['cui'] = geo_by_name[name_up]
                cui_filled += 1
                continue
            # Prefix match (first 15 chars)
            prefix = name_up[:15]
            candidates = geo_by_prefix.get(prefix, [])
            if len(candidates) == 1:
                rd['cui'] = candidates[0][1]
                cui_filled += 1

        print(f'[OK] CUI-uri completate din firme_geocoded.json: {cui_filled}')
        total_with_cui = sum(1 for rd in risc_data.values() if rd.get('cui'))
        print(f'     Firme cu CUI acum: {total_with_cui}/{len(risc_data)}')
    except Exception as e:
        print(f'[WARN] Eroare la citire firme_geocoded.json: {e}')

# ── 2c. Merge date financiare din firme_financiar.json ───────────────────
# Generat de: python import_financiar_datagov.py
# Conține: { "CUI": { an, cifra_afaceri, nr_salariati } }
FINANCIAR_FILE = 'firme_financiar.json'
fin_flagged = 0
if os.path.exists(FINANCIAR_FILE):
    try:
        financiar = json.load(open(FINANCIAR_FILE, encoding='utf-8'))
        print(f'[OK] firme_financiar.json: {len(financiar)} CUI-uri cu date financiare.')

        # Construim index CUI_str → risc_data entry
        cui_to_furn = {}
        for furn, rd in risc_data.items():
            cui = str(rd.get('cui', '')).lstrip('RO').strip()
            if cui:
                cui_to_furn[cui] = furn

        for cui_str, fin in financiar.items():
            furn = cui_to_furn.get(cui_str)
            if not furn:
                continue
            rd = risc_data[furn]

            # Nu duplicăm dacă flagurile financiare există deja
            existing_tips = {f.get('tip', '') for f in rd.get('flags', [])}
            fin_tips = {'ZERO ANGAJATI','CIFRA AFACERI ZERO','CIFRA AFACERI MULT SUB CONTRACT',
                        'CIFRA AFACERI SUB CONTRACT','FOARTE PUTINI ANGAJATI'}
            if existing_tips & fin_tips:
                continue

            ca  = fin.get('cifra_afaceri')
            sal = fin.get('nr_salariati')
            an  = fin.get('an', '?')

            # Cea mai recentă dată de contract și valoarea maximă (pentru evaluate_shell_risk)
            dates   = [f.get('data', '') for f in rd.get('flags', []) if f.get('data')]
            max_val = max((f.get('valoare', 0) or 0 for f in rd.get('flags', [])), default=0)
            latest_date = max(dates) if dates else f'{an}-12-31'

            # Construim profil_data fals dar compatibil cu evaluate_shell_risk()
            profil_data = {'ani': {str(an): {'cifra_afaceri': ca, 'salariati': sal}}}
            try:
                shell_flags = evaluate_shell_risk(profil_data, latest_date, max_val)
            except Exception:
                shell_flags = []

            if shell_flags:
                fin_flagged += 1
                for sf in shell_flags:
                    tip_display = sf['cod'].replace('_', ' ')
                    rd['flags'].append({
                        'tip':        tip_display,
                        'titlu':      sf.get('descriere', ''),
                        'severitate': sf['severitate'],
                        'valoare':    0,
                        'data':       '',
                    })
                    sev = sf['severitate']
                    if sev == 'CRITIC':   rd['n_critic'] = rd.get('n_critic', 0) + 1
                    elif sev == 'MAJOR':  rd['n_major']  = rd.get('n_major', 0) + 1
                    else:                 rd['n_mediu']  = rd.get('n_mediu', 0) + 1
                rd['scor'] = min(100, rd.get('n_critic',0)*10 + rd.get('n_major',0)*5 + rd.get('n_mediu',0)*2)

        print(f'[OK] Firme cu flaguri noi din firme_financiar.json: {fin_flagged}')

    except Exception as e:
        print(f'[WARN] Eroare la citire firme_financiar.json: {e}')
else:
    print(f'[INFO] {FINANCIAR_FILE} lipsă — rulează import_financiar_datagov.py pentru date ANAF.')

# ── 3. Fetch mfinante + merge flags ───────────────────────────────────────
total_fetched   = 0
total_flagged   = 0
total_cached    = 0

if NO_MFINANTE:
    print('[INFO] --no-mfinante: fetch mfinante.gov.ro sărit (se folosesc doar CUI-uri populate).')

for furn_name, rd in risc_data.items():
    if NO_MFINANTE:
        break  # skip all mfinante calls
    cui = rd.get('cui', '').lstrip('RO').strip()
    if not cui:
        continue

    # Cea mai recentă dată de contract și valoarea maximă
    dates = [f.get('data', '') for f in rd.get('flags', []) if f.get('data')]
    latest_date = max(dates) if dates else ''
    max_val = max((f.get('valoare', 0) or 0 for f in rd.get('flags', [])), default=0)

    if not latest_date:
        continue

    # Verificăm dacă există deja flaguri financiare (evităm duplicarea la re-rulare)
    existing_tips = {f.get('tip', '') for f in rd.get('flags', [])}
    financial_tips = {'ZERO ANGAJATI', 'CIFRA AFACERI ZERO', 'CIFRA AFACERI MULT SUB CONTRACT',
                      'CIFRA AFACERI SUB CONTRACT', 'FOARTE PUTINI ANGAJATI'}
    if existing_tips & financial_tips:
        total_cached += 1
        continue  # deja enriched

    print(f'  [{cui}] {furn_name[:50]}...', end=' ', flush=True)
    profil = fetch_firma_anaf(cui, db_path=CACHE_FILE)
    total_fetched += 1

    if 'error' in profil and not profil.get('ani'):
        print(f'eroare: {profil["error"]}')
        continue

    ani = profil.get('ani', {})
    if not ani:
        print('fără date financiare')
        continue

    shell_flags = evaluate_shell_risk(profil, latest_date, max_val)
    if shell_flags:
        total_flagged += 1
        print(f'{len(shell_flags)} flag(uri): {[sf["cod"] for sf in shell_flags]}')
        for sf in shell_flags:
            tip_display = sf['cod'].replace('_', ' ')
            rd['flags'].append({
                'tip':       tip_display,
                'titlu':     sf.get('descriere', ''),
                'severitate': sf['severitate'],
                'valoare':   0,
                'data':      '',
            })
            sev = sf['severitate']
            if sev == 'CRITIC':   rd['n_critic'] = rd.get('n_critic', 0) + 1
            elif sev == 'MAJOR':  rd['n_major']  = rd.get('n_major', 0) + 1
            else:                 rd['n_mediu']  = rd.get('n_mediu', 0) + 1
        # Recalculează scor
        rd['scor'] = min(100, rd.get('n_critic', 0)*10 + rd.get('n_major', 0)*5 + rd.get('n_mediu', 0)*2)
    else:
        print('fără indicatori de risc financiar')

print()
print(f'[OK] Fetch: {total_fetched}, deja cached/enriched: {total_cached}, cu noi flaguri: {total_flagged}')

# ── 4. Patch HTML — înlocuim JSON-ul din tag ──────────────────────────────
new_json = json.dumps(risc_data, ensure_ascii=False, separators=(',', ':'))
new_block = f'{tag_open}{new_json}{tag_close}'

# Înlocuim blocul original cu cel actualizat (match exact prin re.sub)
content_new = re.sub(
    r'<script\s+id="risc-firma-data"[^>]*>.*?</script>',
    lambda _: new_block,
    content,
    count=1,
    flags=re.DOTALL
)

if content_new == content:
    print('[WARN] Nicio modificare în HTML. Poate tot e ok sau blocul nu a fost găsit.')
else:
    open(HTML_FILE, 'w', encoding='utf-8').write(content_new)
    print(f'[OK] {HTML_FILE} actualizat cu {total_flagged} firme cu indicatori financiari noi.')

# ── 5. Statistici rezumat ─────────────────────────────────────────────────
zero_sal = zero_ca = any_risk = 0
for rd in risc_data.values():
    tips = ' '.join(f.get('tip', '').upper() for f in rd.get('flags', []))
    if 'ZERO ANGAJATI' in tips or 'PUTINI ANGAJATI' in tips:
        zero_sal += 1
    if 'CIFRA AFACERI ZERO' in tips or 'CIFRA AFACERI MULT SUB' in tips:
        zero_ca += 1
    if rd.get('scor', 0) > 0:
        any_risk += 1

print()
print(f'Chip-uri estimate după enrichment:')
print(f'  👥 0 angajați  (zero-sal):  {zero_sal} firme')
print(f'  📉 CA = 0 RON  (zero-ca):   {zero_ca} firme')
print(f'  ⚠️  Orice risc (any-risk):  {any_risk} firme')
