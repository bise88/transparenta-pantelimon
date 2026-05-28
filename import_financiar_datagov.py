#!/usr/bin/env python3
"""
import_financiar_datagov.py — Import situații financiare ANAF de pe data.gov.ro
================================================================================

Descarcă (streaming) fișierul WEB_BL_BS_SL_AN{AN}.csv de pe data.gov.ro (~200MB),
extrage datele pentru CUI-urile din risc-firma-data, produce `firme_financiar.json`.

Sursa oficială:
  https://data.gov.ro/dataset/situatii_financiare_2024
  Fișier: WEB_BL_BS_SL_AN2024.csv (bilanțuri entități mari + mijlocii + mici)

Schema confirmată (delimiter `;`):
  CUI                       — cod unic identificare
  Cifra de afaceri neta     — CA netă (RON)
  Numar mediu de salariati  — nr. mediu angajați în cursul anului
  + zeci de alte coloane bilanțiere (ignorate)

Utilizare:
  python import_financiar_datagov.py             # an implicit: 2024
  python import_financiar_datagov.py --an 2023   # pentru date din 2023
  python import_financiar_datagov.py --fisier /path/to/local.csv  # fișier local

Output:
  firme_financiar.json — dict { CUI_str: {an, cifra_afaceri, nr_salariati} }
  Comite-l în repo; monitor_pantelimon.py îl va citi la generarea raportului.

ATENȚIE:
  - Descărcare ~200MB → ~30-60s pe conexiune bună
  - Streaming: memorie O(n_CUI) nu O(fișier)
  - Encoding tipic pentru fișiere gov.ro: cp1250 sau utf-8 cu BOM
  - Datele ANAF au decalaj 6-12 luni față de realitate
"""
import sys
import os
import csv
import json
import re
import argparse
import io

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ── URL-uri per an ────────────────────────────────────────────────────────────
URLS = {
    '2024': 'https://data.gov.ro/dataset/d3caacb6-2c08-445e-94e6-8d36d00ab250/resource/b9f399d8-b641-4a23-9de7-a1dd4427b4b0/download/web_bl_bs_sl_an2024.csv',
    '2023': 'https://data.gov.ro/dataset/7861a98f-4d5c-4faa-90d4-8e934ebd1782/resource/2de79441-0db1-468d-9e7e-ebc9b0f3ff17/download/web_bl_bs_sl_an2023.csv',
}

# ── Variante de nume coloană (se schimbă ușor între ediții) ──────────────────
COL_CUI_VARIANTS   = {'cui', 'cod fiscal', 'cod_fiscal', 'cod unic'}
COL_CA_VARIANTS    = {'cifra de afaceri neta', 'cifra_de_afaceri_neta', 'cifra afaceri', 'ca neta'}
COL_SAL_VARIANTS   = {'numar mediu de salariati', 'numar_mediu_de_salariati', 'salariati', 'nr salariati'}

HTML_FILE        = 'raport_transparenta.html'
OUTPUT_JSON      = 'firme_financiar.json'


def _norm(s):
    """Normalizare nume coloană: lowercase, fără diacritice, fără spații duble."""
    s = s.lower().strip()
    for a, b in [('ă','a'),('â','a'),('î','i'),('ș','s'),('ş','s'),('ț','t'),('ţ','t')]:
        s = s.replace(a, b)
    return re.sub(r'\s+', ' ', s)


def _find_col(headers_norm, variants):
    """Returnează indexul primei coloane care se potrivește cu una din variante."""
    for i, h in enumerate(headers_norm):
        if h in variants:
            return i
    # Potrivire parțială dacă exact nu merge
    for i, h in enumerate(headers_norm):
        for v in variants:
            if v in h or h in v:
                return i
    return None


def get_cui_set_from_html(html_file=HTML_FILE):
    """Extrage toate CUI-urile din risc-firma-data JSON embedded în HTML."""
    try:
        content = open(html_file, encoding='utf-8').read()
        m = re.search(r'id="risc-firma-data"[^>]*>(.*?)</script>', content, re.DOTALL)
        if not m:
            return set()
        data = json.loads(m.group(1).strip())
        cuis = set()
        for rd in data.values():
            cui = str(rd.get('cui', '')).lstrip('RO').strip()
            if cui and cui.isdigit():
                cuis.add(int(cui))
        return cuis
    except Exception as e:
        print(f'[WARN] Nu am putut extrage CUI-uri din HTML: {e}')
        return set()


def stream_parse_csv(source, cui_tinta, an, encoding='cp1250'):
    """
    Parcurge CSV-ul în streaming (O(1) memorie per rând).
    source = path local (str) sau URL (str începând cu http)
    Returnează dict { CUI_int: {an, cifra_afaceri, nr_salariati} }
    """
    rezultate = {}

    def _rows(f):
        reader = csv.reader(f, delimiter=';')
        headers_raw = next(reader, [])
        headers_norm = [_norm(h) for h in headers_raw]

        idx_cui = _find_col(headers_norm, COL_CUI_VARIANTS)
        idx_ca  = _find_col(headers_norm, COL_CA_VARIANTS)
        idx_sal = _find_col(headers_norm, COL_SAL_VARIANTS)

        if idx_cui is None:
            print(f'[EROARE] Coloana CUI nu a fost găsită. Coloane disponibile: {headers_raw[:10]}')
            return
        print(f'[INFO] Coloane detectate: CUI@{idx_cui}, CA@{idx_ca}, Sal@{idx_sal}')

        for row in reader:
            try:
                cui_raw = row[idx_cui].strip().lstrip('RO').strip()
                if not cui_raw.isdigit():
                    continue
                cui = int(cui_raw)
            except (IndexError, ValueError):
                continue

            if cui not in cui_tinta:
                continue

            ca  = None
            sal = None
            try:
                if idx_ca is not None and idx_ca < len(row):
                    v = row[idx_ca].strip().replace('.', '').replace(',', '.')
                    if v: ca = float(v)
            except ValueError:
                pass
            try:
                if idx_sal is not None and idx_sal < len(row):
                    v = row[idx_sal].strip().replace('.', '').replace(',', '.')
                    if v: sal = int(float(v))
            except ValueError:
                pass

            rezultate[cui] = {'an': an, 'cifra_afaceri': ca, 'nr_salariati': sal}

            if len(rezultate) >= len(cui_tinta):
                print(f'[OK] Toate {len(cui_tinta)} CUI-uri găsite. Oprire timpurie.')
                return

    if source.startswith('http'):
        import urllib.request
        print(f'[INFO] Descărcare streaming: {source}')
        req = urllib.request.Request(
            source,
            headers={'User-Agent': 'transparenta-pantelimon-bot (contact: contact@transparenta-pantelimon.eu)'}
        )
        downloaded = 0
        with urllib.request.urlopen(req, timeout=120) as resp:
            # Citim în blocuri, construim stream text
            chunks = []
            while True:
                chunk = resp.read(65536)  # 64KB pe rând
                if not chunk:
                    break
                chunks.append(chunk)
                downloaded += len(chunk)
                if downloaded % (10 * 1024 * 1024) < 65536:
                    print(f'  ... {downloaded // (1024*1024)} MB descărcați')
            raw_bytes = b''.join(chunks)
        print(f'[OK] Descărcat {len(raw_bytes) // (1024*1024)} MB')

        # Detectăm encoding: BOM UTF-8 sau fallback cp1250
        if raw_bytes.startswith(b'\xef\xbb\xbf'):
            enc = 'utf-8-sig'
        else:
            enc = encoding

        text = raw_bytes.decode(enc, errors='replace')
        _rows(io.StringIO(text))
    else:
        # Fișier local — streaming cu open()
        enc = encoding
        with open(source, encoding=enc, errors='replace') as f:
            _rows(f)

    return rezultate


def main():
    parser = argparse.ArgumentParser(description='Import situații financiare ANAF data.gov.ro')
    parser.add_argument('--an', default='2024', choices=URLS.keys(),
                        help='Anul situațiilor financiare (implicit: 2024)')
    parser.add_argument('--fisier', default=None,
                        help='Cale fișier local CSV (sare descărcarea)')
    parser.add_argument('--encoding', default='cp1250',
                        help='Encoding fișier CSV (implicit: cp1250)')
    args = parser.parse_args()

    # 1. Extragem CUI-urile țintă
    print(f'[1/3] Extrag CUI-uri din {HTML_FILE}...')
    cui_tinta = get_cui_set_from_html()
    if not cui_tinta:
        print('[EROARE] Nu am găsit CUI-uri în risc-firma-data. Verifică că HTML-ul există.')
        sys.exit(1)
    print(f'      {len(cui_tinta)} CUI-uri de căutat.')

    # 2. Parsăm CSV-ul (streaming)
    source = args.fisier or URLS.get(args.an)
    if not source:
        print(f'[EROARE] URL necunoscut pentru an={args.an}')
        sys.exit(1)

    print(f'[2/3] Parsare CSV an={args.an}: {source[:80]}...')
    rezultate = stream_parse_csv(source, cui_tinta, args.an, args.encoding)

    print(f'\n[3/3] Rezultate: {len(rezultate)}/{len(cui_tinta)} CUI-uri găsite.')
    for cui, d in sorted(rezultate.items()):
        sal_str = str(d["nr_salariati"]) if d["nr_salariati"] is not None else 'N/A'
        ca_str  = f'{d["cifra_afaceri"]:,.0f}' if d["cifra_afaceri"] is not None else 'N/A'
        print(f'  {cui}: salariati={sal_str}, CA={ca_str} RON')

    if not rezultate:
        print('[WARN] Niciun CUI găsit. Posibile cauze:')
        print('       - Encoding greșit: încearcă --encoding utf-8')
        print('       - Coloane diferite față de schema așteptată')
        print('       - CUI-urile din raport nu sunt în fișierul de bilanțuri')
        sys.exit(0)

    # Convertim cheile în string pentru JSON (JSON nu permite int keys)
    output = {str(k): v for k, v in rezultate.items()}
    json.dump(output, open(OUTPUT_JSON, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)
    print(f'\n[OK] Scris {OUTPUT_JSON} ({len(output)} firme).')
    print(f'     Pas următor: python enricheaza_firme.py --sursa-financiara {OUTPUT_JSON}')


if __name__ == '__main__':
    main()
