#!/usr/bin/env python3
"""
analizeaza_retele.py — Detectare relații între firmele monitorizate
====================================================================

Detectează firme legate prin adresă fiscală comună, folosind datele din
firme_geocoded.json (adrese ANAF v9).

Categorii de relații:
  ADRESA_COMUNA — aceeași adresă normalizată (stradă + număr + localitate)

Output:
  retele_firme.json — noduri (firme) + edges (relații)

Utilizare:
  python analizeaza_retele.py
  python analizeaza_retele.py --input firme_geocoded.json --output retele_firme.json
"""
import sys
import os
import json
import re
import argparse
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

GEO_FILE    = Path(__file__).parent / 'firme_geocoded.json'
OUTPUT_FILE = Path(__file__).parent / 'retele_firme.json'

# ── Normalizare adresă ─────────────────────────────────────────────────────────

# Prefixe juridico-geografice de eliminat din adresă (case-insensitive)
_PREFIXE = re.compile(
    r'\b(judet|jud|municipiul|municipiu|mun|oras|ors|orasul|com|comuna|sat|'
    r'sector|sect|str|strada|stradela|strd|bld|blvd|sos|soseaua|'
    r'calea|cal|aleea|alee|intr|intrarea|bd|piata|p-ta|'
    r'nr|no|bloc|bl|scara|sc|etaj|et|apart|ap|camera|cam|'
    r'cl[aă]dire|cl[aă]d|birou|of|oficiu)\b\.?',
    re.IGNORECASE | re.UNICODE,
)

# Diacritice română → ascii
_DIACR = str.maketrans(
    'ăâîșşțţĂÂÎȘŞȚŢ',
    'aaissttAAISST T'.replace(' ', '')
)

# Caractere non-alfanumerice (mai puțin spații)
_PUNCT = re.compile(r'[^\w\s]')
# Spații multiple
_SPACES = re.compile(r'\s+')


def _norm_adresa(raw: str) -> str:
    """
    Normalizează o adresă ANAF pentru matching fuzzy.

    Pipeline:
      1. Lowercase
      2. Transliterate diacritice → ascii
      3. Elimină prefixe juridice (JUD., STR., NR., BL. etc.)
      4. Elimină punctuație
      5. Colapsează spații
      6. Trimm

    Returnează string normalizat sau '' dacă adresa e prea scurtă.
    """
    if not raw:
        return ''
    s = raw.lower()
    s = s.translate(_DIACR)
    s = _PREFIXE.sub(' ', s)
    s = _PUNCT.sub(' ', s)
    s = _SPACES.sub(' ', s).strip()
    # Adresele prea scurte (<10 chars) sunt prea generice pentru matching fiabil
    return s if len(s) >= 10 else ''


def _adresa_key(norm: str, max_words: int = 6) -> str:
    """
    Cheie de grupare din adresa normalizată.
    Folosim primele min(max_words, len(words)) cuvinte: localitate + stradă + număr.
    Luăm MIN dintre max_words și numărul efectiv de cuvinte pentru a evita false
    negative când o adresă scurtă apare ca prefix al uneia mai lungi.

    6 cuvinte acoperă: [județ] [localitate] [stradă_cuvant1] [stradă_cuvant2] [număr]
    """
    words = norm.split()
    n = min(max_words, len(words))
    return ' '.join(words[:n])


# ── Detecție relații ──────────────────────────────────────────────────────────

def detect_adrese_comune(firme: list, min_chars: int = 10) -> list:
    """
    Găsește perechi de firme cu aceeași adresă fiscală normalizată.

    Args:
        firme:     lista de dict-uri din firme_geocoded.json
        min_chars: lungime minimă a adresei normalizate (filtrare adr. generice)

    Returns:
        Lista de edge-uri: [{tip, firme[cui1,cui2], nume[n1,n2], adresa, severitate}]
    """
    by_key: dict = defaultdict(list)

    for f in firme:
        raw_adr = f.get('adresa_fiscala') or f.get('adresa') or ''
        norm    = _norm_adresa(raw_adr)
        if not norm or len(norm) < min_chars:
            continue
        key = _adresa_key(norm)
        if not key:
            continue
        cui  = str(f.get('cif') or f.get('cui') or '').strip()
        nume = (f.get('name') or f.get('denumire') or '').strip()
        if not cui or not nume:
            continue
        by_key[key].append({'cui': cui, 'nume': nume, 'adresa': raw_adr})

    edges: list = []
    for key, lista in by_key.items():
        if len(lista) < 2:
            continue
        # Generăm toate perechile (n*(n-1)/2)
        for i, f1 in enumerate(lista):
            for f2 in lista[i + 1:]:
                if f1['cui'] == f2['cui']:
                    continue  # aceeași firmă, CUI duplicat în geocoded
                edges.append({
                    'tip':       'ADRESA_COMUNA',
                    'firme':     [f1['cui'], f2['cui']],
                    'nume':      [f1['nume'], f2['nume']],
                    'adresa':    f1['adresa'],
                    'adresa_norm': key,
                    'severitate': 'MEDIU',
                    'descriere': (
                        f'{f1["nume"]} și {f2["nume"]} au aceeași adresă fiscală '
                        f'înregistrată la ANAF. Poate indica legătură de business sau '
                        f'sediu de companii. Verificare manuală recomandată.'
                    ),
                })
    return edges


# ── Build output ──────────────────────────────────────────────────────────────

def construieste_retea(firme: list) -> dict:
    """
    Construiește graful complet: noduri + edges ADRESA_COMUNA.

    Returns:
        dict cu 'nodes', 'edges', 'stats', 'generated_at'
    """
    edges_adresa = detect_adrese_comune(firme)

    # CUI-uri implicate în cel puțin o relație
    cui_in_retea = set()
    for e in edges_adresa:
        cui_in_retea.update(e['firme'])

    # Noduri: toate firmele din firme_geocoded (nu doar cele cu relații)
    nodes: list = []
    for f in firme:
        cui  = str(f.get('cif') or f.get('cui') or '').strip()
        nume = (f.get('name') or f.get('denumire') or '').strip()
        if not cui or not nume:
            continue
        nodes.append({
            'id':           cui,
            'label':        nume,
            'cui':          cui,
            'adresa':       f.get('adresa_fiscala') or f.get('adresa') or '',
            'lat':          f.get('lat'),
            'lng':          f.get('lng') or f.get('lon'),
            'valoare':      f.get('valoare', 0),
            'nr_contracte': f.get('nr_contracte', 0),
            'in_retea':     cui in cui_in_retea,
        })

    return {
        'nodes':      nodes,
        'edges':      edges_adresa,
        'stats': {
            'total_noduri':         len(nodes),
            'noduri_in_retea':      len(cui_in_retea),
            'edges_adresa_comuna':  len(edges_adresa),
            'total_edges':          len(edges_adresa),
        },
    }


def gaseste_firme_legate(cui: str, retea: dict) -> list:
    """
    Returnează lista firmelor legate prin orice tip de relație cu firma `cui`.
    Folosit de genereaza_pagina_furnizor() din monitor_pantelimon.py.

    Returns:
        Lista de dict {cui_legat, nume_legat, tip, adresa, descriere}
    """
    rezultate: list = []
    for edge in retea.get('edges', []):
        firme = edge.get('firme', [])
        if cui not in firme:
            continue
        idx_alt = 1 - firme.index(cui)   # indexul celuilalt
        if idx_alt < 0 or idx_alt >= len(firme):
            continue
        cui_alt  = firme[idx_alt]
        nume_alt = edge.get('nume', ['', ''])[idx_alt]
        rezultate.append({
            'cui_legat':   cui_alt,
            'nume_legat':  nume_alt,
            'tip':         edge.get('tip', ''),
            'adresa':      edge.get('adresa', ''),
            'descriere':   edge.get('descriere', ''),
        })
    return rezultate


def incarca_retea(output_file: Path = OUTPUT_FILE) -> dict:
    """Citește retele_firme.json; returnează dict gol la eroare."""
    if not output_file.exists():
        return {}
    try:
        return json.loads(output_file.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError):
        return {}


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Analiză rețele firme')
    parser.add_argument('--input',  default=str(GEO_FILE),    help='firme_geocoded.json')
    parser.add_argument('--output', default=str(OUTPUT_FILE), help='retele_firme.json')
    args = parser.parse_args()

    geo_path = Path(args.input)
    if not geo_path.exists():
        print(f'[ERR] {geo_path} lipsă — rulează mai întâi geocodeaza_acum.py')
        sys.exit(1)

    firme = json.loads(geo_path.read_text(encoding='utf-8'))
    print(f'[INFO] {len(firme)} firme geocodate')

    retea = construieste_retea(firme)

    stats = retea['stats']
    print(f'[OK] Noduri: {stats["total_noduri"]} | '
          f'În rețea: {stats["noduri_in_retea"]} | '
          f'Edges adresă comună: {stats["edges_adresa_comuna"]}')

    if retea['edges']:
        print('\nRelații detectate:')
        for e in retea['edges']:
            n1, n2 = e['nume'][0][:35], e['nume'][1][:35]
            print(f'  {e["tip"]:20} {n1!r} ↔ {n2!r}')

    import datetime
    retea['generated_at'] = datetime.datetime.now().isoformat()

    out_path = Path(args.output)
    out_path.write_text(
        json.dumps(retea, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    print(f'\n[OK] Scris → {out_path.name}')
    print('     Pas următor: deschide retele.html în browser')


if __name__ == '__main__':
    main()
