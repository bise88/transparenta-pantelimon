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
import zipfile

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ── URL-uri per an ─────────────────────────────────────────────────────────────
# NOTĂ: fișierele .csv = specificații coloane (mici, câțiva KB)
#        fișierele .txt = date efective bilanțuri (~200MB, comma-delimited, UTF-8)
# Schema TXT confirmată (2024): CUI,CAEN,I1,I2,...,I20
#   I13 = Cifra de afaceri netă
#   I20 = Număr mediu de salariați
URLS = {
    '2024': 'https://data.gov.ro/dataset/d3caacb6-2c08-445e-94e6-8d36d00ab250/resource/f89140dc-20dd-494f-912a-d1a482188885/download/web_bl_bs_sl_an2024.txt',
    '2024-uu': 'https://data.gov.ro/dataset/d3caacb6-2c08-445e-94e6-8d36d00ab250/resource/25098618-f6a5-4610-8c7f-c0bdb801635f/download/web_uu_an2024.txt',
    '2023': 'https://data.gov.ro/dataset/7861a98f-4d5c-4faa-90d4-8e934ebd1782/resource/5ed47b6f-f8a2-4ca8-a272-692aff4fe9e4/download/web_bl_bs_sl_an2023.txt',
    '2023-uu': 'https://data.gov.ro/dataset/7861a98f-4d5c-4faa-90d4-8e934ebd1782/resource/a1c85e04-4a2d-4e0c-bcac-73c5c85d0e30/download/web_uu_an2023.txt',
}

# Delimiter real în fișierele .txt
CSV_DELIMITER = ','

# ── Variante de nume coloană ───────────────────────────────────────────────────
# TXT-ul folosește I1..I20 (coduri indicatori); descrierile sunt în .csv spec.
# I13 = Cifra de afaceri netă  |  I20 = Număr mediu de salariați
COL_CUI_VARIANTS   = {'cui', 'cod fiscal', 'cod_fiscal', 'cod unic'}
COL_CA_VARIANTS    = {'i13', 'cifra de afaceri neta', 'cifra_de_afaceri_neta', 'ca neta', 'ca_neta'}
COL_SAL_VARIANTS   = {'i20', 'numar mediu de salariati', 'numar_mediu_de_salariati', 'salariati', 'nr salariati'}

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
        reader = csv.reader(f, delimiter=CSV_DELIMITER)
        headers_raw = next(reader, [])
        headers_norm = [_norm(h) for h in headers_raw]

        idx_cui = _find_col(headers_norm, COL_CUI_VARIANTS)
        idx_ca  = _find_col(headers_norm, COL_CA_VARIANTS)
        idx_sal = _find_col(headers_norm, COL_SAL_VARIANTS)

        if idx_cui is None:
            print(f'[EROARE] Coloana CUI nu a fost găsită.')
            print(f'         Coloane raw (primele 15): {headers_raw[:15]}')
            print(f'         Coloane normalize (primele 15): {headers_norm[:15]}')
            return
        print(f'[INFO] Coloane detectate: CUI@{idx_cui}, CA@{idx_ca}, Sal@{idx_sal}')
        # Dict mutable folosit ca flag în closure (evită nonlocal)
        _state = {'debug_shown': False}

        for row in reader:
            # Debug: primul rând de date (indiferent de CUI)
            if not _state['debug_shown']:
                _state['debug_shown'] = True
                sample = {headers_raw[i]: row[i] for i in range(min(len(headers_raw), len(row)))}
                cui_sample = sample.get(headers_raw[idx_cui] if idx_cui is not None else '', 'N/A')
                ca_sample  = sample.get(headers_raw[idx_ca]  if idx_ca  is not None else '', 'N/A')
                sal_sample = sample.get(headers_raw[idx_sal] if idx_sal is not None else '', 'N/A')
                print(f'[DEBUG] Primul rând: CUI={cui_sample!r}, CA={ca_sample!r}, Sal={sal_sample!r}')
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

        # ── ZIP? data.gov.ro pune uneori fișierele mari în ZIP ───────────────
        if raw_bytes[:2] == b'PK':
            print('[INFO] Fișier ZIP detectat — extrag primul CSV din arhivă...')
            with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
                csv_names = [n for n in zf.namelist()
                             if n.lower().endswith('.csv') or n.lower().endswith('.txt')]
                if not csv_names:
                    print(f'[EROARE] Niciun CSV/TXT în ZIP. Conținut: {zf.namelist()}')
                    return rezultate
                csv_name = csv_names[0]
                print(f'         Extrag: {csv_name}')
                raw_bytes = zf.read(csv_name)

        # ── Detectare encoding ────────────────────────────────────────────────
        # .txt ANAF 2024 este UTF-8 fara BOM. .csv spec poate fi cp1250.
        if raw_bytes.startswith(b'\xef\xbb\xbf'):
            enc = 'utf-8-sig'
        elif raw_bytes.startswith(b'\xff\xfe') or raw_bytes.startswith(b'\xfe\xff'):
            enc = 'utf-16'
        elif raw_bytes[:20].isascii():
            enc = 'utf-8'  # header ASCII → UTF-8 (standard pentru .txt ANAF 2024)
        else:
            enc = encoding  # cp1250 sau override explicit

        # Decodăm cu fallback cascadat
        text = raw_bytes.decode(enc, errors='replace')
        n_bad = text.count('�')
        if n_bad > 50:
            if enc == 'cp1250':
                print(f'[INFO] {n_bad} caractere stricate — reîncerc cu windows-1250...')
                text = raw_bytes.decode('windows-1250', errors='replace')
            elif enc not in ('utf-8', 'utf-8-sig'):
                print(f'[INFO] {n_bad} caractere stricate cu {enc} — reîncerc utf-8...')
                text = raw_bytes.decode('utf-8', errors='replace')

        _rows(io.StringIO(text))
    else:
        # Fișier local — streaming cu open()
        enc = encoding
        with open(source, encoding=enc, errors='replace') as f:
            _rows(f)

    return rezultate


def main():
    parser = argparse.ArgumentParser(description='Import situații financiare ANAF data.gov.ro')
    parser.add_argument('--an', default='2024', choices=list(URLS.keys()),
                        help='Anul situațiilor financiare (implicit: 2024)')
    parser.add_argument('--fisier', default=None,
                        help='Cale fișier local CSV (sare descărcarea)')
    parser.add_argument('--encoding', default='cp1250',
                        help='Encoding fișier CSV (implicit: cp1250)')
    parser.add_argument('--merge', action='store_true',
                        help=f'Merge în {OUTPUT_JSON} existent (nu suprascrie)')
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

    # ── Merge cu fișier existent (--merge) ───────────────────────────────────
    if args.merge and os.path.exists(OUTPUT_JSON):
        try:
            existing = json.load(open(OUTPUT_JSON, encoding='utf-8'))
            n_before = len(existing)
            existing.update(output)   # new entries win (mai recente)
            output = existing
            print(f'[OK] Merge: {n_before} existente + {len(rezultate)} noi → {len(output)} total')
        except Exception as e:
            print(f'[WARN] Merge eșuat ({e}) — suprascriere.')

    json.dump(output, open(OUTPUT_JSON, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)
    print(f'\n[OK] Scris {OUTPUT_JSON} ({len(output)} firme).')
    print(f'     Pas următor: python enricheaza_firme.py')


if __name__ == '__main__':
    main()
