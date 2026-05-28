"""
geocodeaza_acum.py — Script standalone geocodare firme furnizoare Pantelimon
==============================================================================
Folosește:
  - ANAF v9 API (gratuit, fără API key) pentru adrese firme
  - Nominatim / OpenStreetMap (gratuit) pentru coordonate lat/lng
  - SQLite cache (geocoding_cache.db) cu TTL 180 zile

Nu rulează scraping SEAP. Citește contracte.json local și produce firme_geocoded.json.

Rulare: py geocodeaza_acum.py
"""

import json
import os
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

import requests

# Forteaza UTF-8 pe Windows (evita UnicodeEncodeError cu emoji)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

REPO_DIR   = os.path.dirname(os.path.abspath(__file__))
CONTRACTE  = os.path.join(REPO_DIR, "contracte.json")
GEO_OUT    = os.path.join(REPO_DIR, "firme_geocoded.json")
CACHE_DB   = os.path.join(REPO_DIR, "geocoding_cache.db")
INDEX_JSON = os.path.join(REPO_DIR, "furnizori", "index.html")  # fallback

USER_AGENT     = "transparenta-pantelimon-bot (contact: contact@transparenta-pantelimon.eu)"
ANAF_URL       = "https://webservicesp.anaf.ro/api/PlatitorTvaRest/v9/tva"
NOMINATIM_URL  = "https://nominatim.openstreetmap.org/search"
RATE_LIMIT     = 1.2   # secunde — respectă Nominatim policy

# ── Cache SQLite ──────────────────────────────────────────────────────────────

def _init_cache(db):
    conn = sqlite3.connect(db)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS geocoding (
            adresa TEXT PRIMARY KEY, lat REAL, lng REAL, geocodat_la TEXT
        )
    """)
    conn.commit()
    return conn


def _cache_get(conn, adresa, ttl=180):
    row = conn.execute(
        "SELECT lat, lng, geocodat_la FROM geocoding WHERE adresa=?", (adresa,)
    ).fetchone()
    if not row:
        return None
    lat, lng, ts = row
    if ts:
        try:
            if datetime.now() - datetime.fromisoformat(ts) < timedelta(days=ttl):
                return (lat, lng)
        except ValueError:
            pass
    return None


def _cache_set(conn, adresa, lat, lng):
    conn.execute(
        "INSERT OR REPLACE INTO geocoding (adresa,lat,lng,geocodat_la) VALUES (?,?,?,?)",
        (adresa, lat, lng, datetime.now().isoformat())
    )
    conn.commit()


# ── ANAF v9 batch ─────────────────────────────────────────────────────────────

def fetch_anaf_batch(cui_list):
    """Returnează dict CUI -> {denumire, adresa, stare} via ANAF v9 (gratuit)."""
    result = {}
    # Normalizare CUI (int, fără prefix RO)
    cui_int_map = {}
    for raw in cui_list:
        clean = str(raw).strip().upper().lstrip("RO")
        try:
            ci = int(clean)
            cui_int_map[ci] = str(raw).strip()
        except ValueError:
            continue

    today = datetime.now().strftime("%Y-%m-%d")
    BATCH = 499

    cui_ints = list(cui_int_map.keys())
    total = len(cui_ints)
    gasit = 0

    for i in range(0, total, BATCH):
        batch = cui_ints[i:i + BATCH]
        payload = [{"cui": c, "data": today} for c in batch]
        try:
            r = requests.post(
                ANAF_URL, json=payload, timeout=25,
                headers={"Content-Type": "application/json", "User-Agent": USER_AGENT}
            )
            if r.status_code != 200:
                print(f"  ⚠  ANAF v9 HTTP {r.status_code} — batch {i//BATCH+1}")
                continue
            data = r.json()
        except Exception as e:
            print(f"  ⚠  ANAF batch {i//BATCH+1} eroare: {e}")
            continue

        for item in data.get("found", []):
            dg  = item.get("date_generale", {})
            ci  = dg.get("cui")   # ANAF v9: CUI este in date_generale, nu la nivel top
            if not ci:
                continue
            orig = cui_int_map.get(ci, str(ci))
            adresa = (dg.get("adresa") or "").strip()
            result[orig] = {
                "denumire": (dg.get("denumire") or "").strip(),
                "adresa":   adresa,
                "stare":    (dg.get("stare_inregistrare") or "").strip(),
                "nrRegCom": (dg.get("nrRegCom") or "").strip(),
            }
            if adresa:
                gasit += 1

    print(f"  ANAF: {gasit}/{total} firme cu adresă")
    return result


# ── Nominatim geocoding ───────────────────────────────────────────────────────

def simplify_anaf_address(adresa):
    """Extrage localitate + judet din adresa ANAF verbosa pentru Nominatim."""
    import re
    parts = [p.strip() for p in adresa.split(",")]
    judet, localitate, sector = "", "", ""
    for p in parts:
        pu = p.upper()
        if pu.startswith("JUD."):
            judet = re.sub(r"^JUD\.\s*", "", p, flags=re.IGNORECASE).strip()
        elif "BUCURE" in pu:
            localitate = "Bucuresti"
        elif re.match(r"^SECTOR\s+\d+", pu, re.IGNORECASE):
            sector = re.sub(r"^SECTOR\s*", "Sector ", p, flags=re.IGNORECASE).strip()
        elif re.match(r"^(MUN\.|MUNICIPIUL|ORAS|SAT|ORŞ\.|ORS\.)\s*", pu):
            loc = re.sub(r"^(MUN\.|MUNICIPIUL|ORAS|SAT|ORŞ\.\s*|ORS\.)\s*", "", p, flags=re.IGNORECASE).strip()
            loc = loc.split()[0] if loc else loc
            if loc:
                localitate = loc
        elif re.match(r"^(STR|SOS|BD|BDUL|CAL\.|CALEA|NR|BL|SC|AP|ET|ALEEA|INTRAREA)", pu):
            break  # am ajuns la strada, oprim
    parts_q = []
    if localitate == "Bucuresti" and sector:
        parts_q.append(sector)
    if localitate:
        parts_q.append(localitate)
    if judet and judet.upper() not in (localitate.upper() if localitate else ""):
        parts_q.append(judet)
    if not parts_q:
        # fallback: primele 2 parti curatate de prefixe
        for p in adresa.split(",")[:2]:
            p2 = re.sub(r"^(JUD\.|MUNICIPIUL|ORAS|MUN\.|SAT|ORŞ\.|ORS\.)\s*", "", p, flags=re.IGNORECASE).strip()
            if p2:
                parts_q.append(p2)
    return ", ".join(parts_q) if parts_q else adresa[:50]


def nominatim_geocode(adresa):
    """Returnează (lat, lng) sau (None, None). Simplifică adresa ANAF înainte de query."""
    adresa_query = simplify_anaf_address(adresa)
    query = urllib.parse.urlencode({"q": adresa_query + ", Romania", "format": "json", "limit": "1"})
    url   = f"{NOMINATIM_URL}?{query}"
    req   = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        pass
    return None, None


# ── Slugify ───────────────────────────────────────────────────────────────────

def slugify(text):
    import unicodedata, re
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:80]


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Geocodare firme furnizoare — ANAF v9 + Nominatim")
    print("=" * 60)

    # 1. Citim contracte.json
    with open(CONTRACTE, encoding="utf-8") as f:
        contracte = json.load(f)

    # 2. Agregăm valori și nr. contracte per CUI
    cui_valori    = {}
    cui_contracte = {}
    cui_nume      = {}
    for c in contracte:
        cui  = (c.get("cui") or "").strip()
        if not cui:
            continue
        val  = float(c.get("valoare") or 0)
        nume = (c.get("firma") or "").strip()
        cui_valori[cui]    = cui_valori.get(cui, 0) + val
        cui_contracte[cui] = cui_contracte.get(cui, 0) + 1
        if nume and cui not in cui_nume:
            cui_nume[cui] = nume

    cui_list = list(cui_valori.keys())
    print(f"\n📋 {len(cui_list)} CUI-uri unice din {len(contracte)} contracte")

    # 3. Fetch ANAF adrese
    print("\n🏢 Interoghez ANAF v9 pentru adrese...")
    firme_anaf = fetch_anaf_batch(cui_list)

    # 4. Geocodare Nominatim cu cache
    print("\n🗺  Geocodez via Nominatim (cu cache SQLite 180 zile)...")
    conn      = _init_cache(CACHE_DB)
    rezultate = []
    ultima_req = 0.0

    cu_adresa = [(cui, firme_anaf[cui]) for cui in cui_list if cui in firme_anaf and firme_anaf[cui].get("adresa")]
    fara_adresa = len(cui_list) - len(cu_adresa)

    print(f"  {len(cu_adresa)} firme cu adresă / {fara_adresa} fără adresă (skip)")

    geocodate = 0
    din_cache = 0
    nereusite = 0

    for idx, (cui, info) in enumerate(cu_adresa, 1):
        adresa = info["adresa"]
        # Curăță adresa pentru query mai bun
        adresa_query = adresa

        cached = _cache_get(conn, adresa_query)
        if cached:
            lat, lng = cached
            din_cache += 1
        else:
            # Rate limiting Nominatim (1 req/sec policy)
            elapsed = time.time() - ultima_req
            if elapsed < RATE_LIMIT:
                time.sleep(RATE_LIMIT - elapsed)
            lat, lng = nominatim_geocode(adresa_query)
            ultima_req = time.time()
            if lat is not None:  # Salvam in cache doar succesele
                _cache_set(conn, adresa_query, lat, lng)

            if lat is not None:
                geocodate += 1
                loc_query = simplify_anaf_address(adresa)
                print(f"  [{idx}/{len(cu_adresa)}] OK {info['denumire'][:35]:35s} ({loc_query[:25]}) -> {lat:.4f},{lng:.4f}")
            else:
                nereusite += 1
                loc_query = simplify_anaf_address(adresa)
                print(f"  [{idx}/{len(cu_adresa)}] !! {info['denumire'][:35]:35s} ({loc_query[:25]}) geocodare esuata")

        if lat is None or lng is None:
            continue

        # Nume firmă: ANAF > contracte
        name = info.get("denumire") or cui_nume.get(cui) or cui
        slug = slugify(name)

        rezultate.append({
            "name":         name,
            "cif":          cui,
            "adresa":       adresa,
            "lat":          round(lat, 6),
            "lng":          round(lng, 6),
            "valoare":      round(cui_valori.get(cui, 0), 2),
            "nr_contracte": cui_contracte.get(cui, 0),
            "slug":         slug,
        })

    conn.close()

    # 5. Scriem firme_geocoded.json
    with open(GEO_OUT, "w", encoding="utf-8") as f:
        json.dump(rezultate, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"✅ firme_geocoded.json scris: {len(rezultate)} firme geocodate")
    print(f"   Cache hit:  {din_cache}")
    print(f"   Geocodate acum: {geocodate}")
    print(f"   Eșuate:     {nereusite}")
    print(f"   Fără adresă: {fara_adresa}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
