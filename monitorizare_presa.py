#!/usr/bin/env python3
"""
monitorizare_presa.py — Monitorizare automată mențiuni presă pentru firmele din raport
=======================================================================================

Caută mențiuni de presă cu cuvinte-cheie de risc pentru fiecare firmă cu CUI
din risc-firma-data. Surse: Google News RSS + Context.ro RSS.

Output:  mentiuni_presa_auto.json
         {CUI: {nume, total, mentiuni[{title,link,source,pub_date,matched_keyword}], fetched_at}}

Cache:   .cache_presa.sqlite  (TTL 7 zile, per (CUI, sursă))
Rate:    1.2s între requests
User-Agent: transparenta-pantelimon-bot (contact: contact@transparenta-pantelimon.eu)

Utilizare:
  python monitorizare_presa.py                    # rulare completă
  python monitorizare_presa.py --dry-run          # afișează query-urile fără fetch
  python monitorizare_presa.py --firma "FIRMA X"  # o singură firmă
"""
import sys
import os
import json
import re
import sqlite3
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

from config import TTL_PRESA_DAYS

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ── Configurare ────────────────────────────────────────────────────────────────

USER_AGENT  = 'transparenta-pantelimon-bot (contact: contact@transparenta-pantelimon.eu)'
CACHE_DB    = Path(__file__).parent / '.cache_presa.sqlite'
CACHE_TTL_DAYS = TTL_PRESA_DAYS   # mai scurt decât cache geocodare; presa e dinamică
RATE_LIMIT_S   = 1.2        # secunde între requests
MAX_MENTIUNI_PER_FIRMA = 20 # per sursă RSS
HTML_FILE   = Path(__file__).parent / 'raport_transparenta.html'
OUTPUT_FILE = Path(__file__).parent / 'mentiuni_presa_auto.json'

# Surse RSS — format: (label_afișat, url_template_cu_{query})
# {query} e înlocuit cu urllib.parse.quote(query_text)
RSS_SOURCES = [
    (
        'Google News RO',
        'https://news.google.com/rss/search?q={query}&hl=ro&gl=RO&ceid=RO:ro',
    ),
    (
        'Context.ro',
        'https://www.context.ro/?s={query_raw}&feed=rss2',
    ),
]

# ── Cuvinte-cheie de risc ──────────────────────────────────────────────────────
KEYWORDS_RISC = [
    'anchet',        # anchetă, anchetați, anchetare
    'corup',         # corupție, corupt, corupți
    'urmar',         # urmărire, urmărit
    'condamna',
    'sanctiona',     # sancționate, sancționar
    'dosar penal',
    'mita',          # mită, mit-
    'spaga',         # șpagă
    'conflict intere',
    'audit',
    'curtea de conturi',
    'denunt',        # denunț, denunțare
    'abuz',
    'frauda',        # fraudă, fraudă fiscală
    'evaziune',
    'spalare bani',  # spălare de bani
    'DNA',
    'ANI ',          # cu spațiu — evită "ANIF", "ANIVERS" etc.
    'DIICOT',
    'ANAF',
    'ANAP',
]

# Anti-fals-pozitive — dacă oricare apare în titlu, articolul e ignorat
NEGATIVE_KEYWORDS = [
    'fotbal',   'meci',      'sport',   'campionat',
    'film',     'muzica',    'concert', 'festival',
    'reteta',   'gastrono',  'mancare', 'restaurant',
    'vedeta',   'celebrity', 'showbiz',
    'horoscop', 'vreme',     'meteo',
]

# ── Cache SQLite ───────────────────────────────────────────────────────────────

def _init_db(db_path: Path = CACHE_DB) -> sqlite3.Connection:
    db = sqlite3.connect(str(db_path))
    db.execute("""
        CREATE TABLE IF NOT EXISTS query_cache (
            cache_key  TEXT PRIMARY KEY,
            firma      TEXT,
            cui        TEXT,
            sursa      TEXT,
            response   TEXT,
            fetched_at TEXT
        )
    """)
    db.commit()
    return db


def _cache_get(db: sqlite3.Connection, key: str):
    row = db.execute(
        "SELECT response, fetched_at FROM query_cache WHERE cache_key = ?", (key,)
    ).fetchone()
    if not row:
        return None
    try:
        fetched = datetime.fromisoformat(row[1])
    except (ValueError, TypeError):
        return None
    if datetime.now() - fetched > timedelta(days=CACHE_TTL_DAYS):
        return None
    return json.loads(row[0])


def _cache_set(db: sqlite3.Connection, key: str, firma: str, cui: str,
               sursa: str, data: list) -> None:
    db.execute(
        "INSERT OR REPLACE INTO query_cache VALUES (?, ?, ?, ?, ?, ?)",
        (key, firma, cui, sursa, json.dumps(data, ensure_ascii=False),
         datetime.now().isoformat()),
    )
    db.commit()


# ── Fetch RSS ──────────────────────────────────────────────────────────────────

def _fetch_rss(url: str, timeout: int = 15) -> str | None:
    """Descarcă RSS și returnează textul XML sau None la eroare."""
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        # Detectare encoding din declaration XML
        enc = 'utf-8'
        if raw.startswith(b'\xef\xbb\xbf'):
            enc = 'utf-8-sig'
        elif b'encoding=' in raw[:200]:
            m = re.search(rb'encoding=["\']([^"\']+)["\']', raw[:200])
            if m:
                enc = m.group(1).decode('ascii', errors='replace')
        return raw.decode(enc, errors='replace')
    except Exception as e:
        print(f'    [WARN] fetch error {url[:60]}: {e}')
        return None


def _parse_rss_items(xml_text: str, firma_lower: str,
                     max_items: int = MAX_MENTIUNI_PER_FIRMA) -> list:
    """
    Parsează RSS XML și returnează itemele relevante pentru firmă.
    Fiecare item trecut de filtre: {title, link, source, pub_date, matched_keyword}.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    items = []
    for item in root.findall('.//item')[:max_items * 3]:   # citim mai mulți, filtrăm
        title   = (item.findtext('title') or '').strip()
        link    = (item.findtext('link')  or '').strip()
        pub_date = (item.findtext('pubDate') or '').strip()
        src_el  = item.find('source')
        source  = src_el.text.strip() if src_el is not None and src_el.text else ''

        title_lower = title.lower()

        # 1. Titlul trebuie să conțină (o parte din) numele firmei
        #    Acceptăm și dacă primul cuvânt semnificativ apare (evitam fals-neg pe abrevieri)
        firma_words = [w for w in firma_lower.split() if len(w) >= 4
                       and w not in ('srl', 'sra', 'sa', 'snc', 'pfa', 'ii',
                                     'cons', 'grup', 'serv', 'sist')]
        if firma_words:
            if not any(fw in title_lower for fw in firma_words):
                continue

        # 2. Cel puțin un cuvânt-cheie de risc în titlu
        matched = None
        for kw in KEYWORDS_RISC:
            if kw.lower() in title_lower:
                matched = kw
                break
        if not matched:
            continue

        # 3. Filtrare fals-pozitive
        if any(neg.lower() in title_lower for neg in NEGATIVE_KEYWORDS):
            continue

        items.append({
            'title':           title,
            'link':            link,
            'source':          source,
            'pub_date':        pub_date,
            'matched_keyword': matched,
        })
        if len(items) >= max_items:
            break

    return items


def cauta_mentiuni_firma(db: sqlite3.Connection, firma_nume: str, cui: str,
                          dry_run: bool = False) -> list:
    """
    Caută mențiuni de risc pentru o firmă în toate sursele RSS configurate.
    Rezultat combinat, deduplicat pe `link`. Cache TTL 7 zile.
    """
    firma_lower = firma_nume.lower()
    # Curăță sufixe juridice din query pentru precizie mai bună
    firma_query = re.sub(
        r'\b(srl|sa|sra|snc|pfa|ii|sas|ra|rn|regie autonoma)\b\.?',
        '', firma_lower, flags=re.IGNORECASE
    ).strip(' ,.-')

    if dry_run:
        print(f'    [DRY] query: "{firma_query}"')
        return []

    toate_mentiunile: list = []
    seen_links: set = set()

    for sursa_label, url_tmpl in RSS_SOURCES:
        cache_key = f'{cui}|{sursa_label}|{firma_query}'.lower()
        cached = _cache_get(db, cache_key)
        if cached is not None:
            print(f'    [CACHE] {sursa_label}')
            for m in cached:
                if m['link'] not in seen_links:
                    toate_mentiunile.append(m)
                    seen_links.add(m['link'])
            continue

        # Build URL
        if '{query_raw}' in url_tmpl:
            url = url_tmpl.replace('{query_raw}', urllib.parse.quote(firma_query))
        else:
            # Google News: combină firma cu OR de keywords
            kw_or = ' OR '.join(f'"{k}"' for k in KEYWORDS_RISC[:8])
            full_query = f'"{firma_query}" ({kw_or})'
            url = url_tmpl.replace('{query}', urllib.parse.quote(full_query))

        print(f'    [FETCH] {sursa_label} → {url[:80]}')
        xml_text = _fetch_rss(url)
        time.sleep(RATE_LIMIT_S)

        mentiuni_sursa: list = []
        if xml_text:
            mentiuni_sursa = _parse_rss_items(xml_text, firma_lower)

        _cache_set(db, cache_key, firma_nume, cui, sursa_label, mentiuni_sursa)

        for m in mentiuni_sursa:
            if m['link'] not in seen_links:
                toate_mentiunile.append(m)
                seen_links.add(m['link'])

    return toate_mentiunile


# ── Helpers publici folosiți de monitor_pantelimon.py ─────────────────────────

def incarca_mentiuni_presa_auto(output_file: Path = OUTPUT_FILE) -> dict:
    """
    Citește mentiuni_presa_auto.json și returnează dict {cui: {...}}.
    Returnează {} dacă fișierul lipsește sau e corupt.
    """
    if not output_file.exists():
        return {}
    try:
        return json.loads(output_file.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError):
        return {}


def evalueaza_flag_presa(mentiuni_firma: dict) -> dict | None:
    """
    Evaluează dacă o firmă merită flagul MENTIUNI_PRESA_RISCANTE.

    Severitate:
      1-2 mențiuni → MEDIU
      3+  mențiuni → MAJOR

    Returnează dict de flag sau None dacă nu e cazul.
    """
    if not mentiuni_firma:
        return None
    total = mentiuni_firma.get('total', 0)
    if total == 0:
        return None
    severitate = 'MAJOR' if total >= 3 else 'MEDIU'
    top5 = mentiuni_firma.get('mentiuni', [])[:5]
    kwds = list({m['matched_keyword'] for m in top5 if m.get('matched_keyword')})
    titlu = (
        f'{total} mențiune(i) în presă cu cuvinte-cheie de risc'
        + (f' ({", ".join(kwds[:3])})' if kwds else '')
    )
    return {
        'tip':       'MENTIUNI PRESA RISCANTE',
        'cod':       'MENTIUNI_PRESA_RISCANTE',
        'titlu':     titlu,
        'severitate': severitate,
        'descriere': (
            'Articole de presă conțin cuvinte ca anchetă, ANAF, urmărire, sancțiune etc. '
            'asociate cu numele firmei. Verificare manuală recomandată — pot fi fals-pozitive.'
        ),
        'mentiuni':  top5,
        'sursa':     'monitorizare_presa.py',
        'data':      mentiuni_firma.get('fetched_at', '')[:10],
    }


# ── Main ───────────────────────────────────────────────────────────────────────

def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description='Monitorizare presă automată firme')
    parser.add_argument('--dry-run', action='store_true',
                        help='Afișează query-urile fără a face fetch real')
    parser.add_argument('--firma', default=None,
                        help='Procesează o singură firmă (nume parțial, case-insensitive)')
    parser.add_argument('--cache-db', default=str(CACHE_DB),
                        help=f'Cale SQLite cache (default: {CACHE_DB})')
    parser.add_argument('--output', default=str(OUTPUT_FILE),
                        help=f'Output JSON (default: {OUTPUT_FILE})')
    args = parser.parse_args(argv)

    # 1. Citire firme din risc-firma-data
    if not HTML_FILE.exists():
        print(f'[ERR] {HTML_FILE} lipsă')
        sys.exit(1)

    content = HTML_FILE.read_text(encoding='utf-8')
    m = re.search(r'id="risc-firma-data"[^>]*>(.*?)</script>', content, re.DOTALL)
    if not m:
        print('[ERR] risc-firma-data lipsă în HTML')
        sys.exit(1)

    risc_data = json.loads(m.group(1).strip())
    firme = [
        (nume, re.sub(r'^[Rr][Oo]\s*', '', str(d.get('cui', '')).strip()).replace(' ', ''))
        for nume, d in risc_data.items()
        if re.sub(r'^[Rr][Oo]\s*', '', str(d.get('cui', '')).strip()).replace(' ', '').isdigit()
    ]

    if args.firma:
        filtru = args.firma.lower()
        firme = [(n, c) for n, c in firme if filtru in n.lower()]
        if not firme:
            print(f'[ERR] Nicio firmă găsită pentru filtrul "{args.firma}"')
            sys.exit(1)

    print(f'[INFO] {len(firme)} firme cu CUI de procesat')

    db = _init_db(Path(args.cache_db))
    output_path = Path(args.output)

    # 2. Încarcă output existent (merge)
    output: dict = {}
    if output_path.exists():
        try:
            output = json.loads(output_path.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError):
            pass

    # 3. Procesare firme
    n_hits = 0
    for i, (nume, cui) in enumerate(firme, 1):
        print(f'\n[{i}/{len(firme)}] {nume} ({cui})')
        mentiuni = cauta_mentiuni_firma(db, nume, cui, dry_run=args.dry_run)

        if mentiuni:
            output[cui] = {
                'nume':       nume,
                'cui':        cui,
                'mentiuni':   mentiuni,
                'total':      len(mentiuni),
                'fetched_at': datetime.now().isoformat(),
            }
            n_hits += 1
            print(f'  → {len(mentiuni)} mențiuni găsite')
        elif not args.dry_run:
            # Păstrăm înregistrarea în output chiar dacă nu s-au găsit mențiuni
            # (pentru a nu re-fetcha la fiecare rulare)
            output.setdefault(cui, {
                'nume': nume, 'cui': cui,
                'mentiuni': [], 'total': 0,
                'fetched_at': datetime.now().isoformat(),
            })

    if not args.dry_run:
        output_path.write_text(
            json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8'
        )
        print(f'\n[OK] {n_hits}/{len(firme)} firme cu mențiuni → {output_path.name}')
        print(f'     {len(output)} firme total în output.')
    else:
        print(f'\n[DRY-RUN] Nu s-a scris niciun fișier.')


if __name__ == '__main__':
    main()
