"""
genereaza_analiza_ai.py — Analiză AI săptămânală via Google Gemini (gratuit)
===========================================================================
Generează 3 module de analiză bazate pe datele deja colectate:
  Modul 1 — Briefing săptămânal (text investigativ ~400 cuvinte)
  Modul 2 — Scor AI + evaluare per firmă (top 20 după risc)
  Modul 3 — Detector conexiuni ascunse (pattern-uri temporale, grupuri firme)

Output: analiza_ai.json (consumat de monitor_pantelimon.py la generarea HTML)

Configurare (o singură dată):
  - Creează cont gratuit pe https://aistudio.google.com/
  - Generează API key (gratuit, fără card de credit)
  - Adaugă în GitHub Secrets: GEMINI_API_KEY
  - Sau local: export GEMINI_API_KEY="..."

Limite gratuite Gemini 2.0 Flash:
  1,500,000 tokens/zi | 15 requests/minut | $0 cost

Utilizare:
  python genereaza_analiza_ai.py                    # citește raport.json local
  python genereaza_analiza_ai.py --input raport.json # explicit
"""

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from collections import defaultdict

# ── Configurare ───────────────────────────────────────────────────────────────

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL   = "gemini-2.0-flash"
GEMINI_URL     = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

INPUT_FILES = [
    "raport.json",           # output principal monitor_pantelimon.py
    "stare_anterioara.json", # flags detectate anterior
    "cache_firme.json",      # date ANAF/openapi per firmă
]

OUTPUT_FILE = "analiza_ai.json"

TOP_FIRME_N = 20  # câte firme analizăm în Modul 2

# ── Helpers ───────────────────────────────────────────────────────────────────

def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def gemini_call(prompt: str, max_tokens: int = 2048) -> str:
    """Apelează Gemini API și returnează textul generat."""
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY lipsă. Setează variabila de mediu sau GitHub Secret."
        )

    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": 0.3,  # mai factual, mai puțin creativ
        },
    }).encode("utf-8")

    url = f"{GEMINI_URL}?key={GEMINI_API_KEY}"
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini HTTP {e.code}: {body[:300]}")


def fmt_ron(v: float) -> str:
    if v >= 1_000_000:
        return f"{v/1_000_000:.2f} mil. RON"
    if v >= 1_000:
        return f"{v/1_000:.0f}K RON"
    return f"{v:.0f} RON"


# ── Încărcare date ─────────────────────────────────────────────────────────────

def load_data() -> dict:
    """Încarcă toate datele disponibile local."""
    data = {}

    # raport.json — output principal (contracte + flags)
    for fname in ["raport.json", "stare_anterioara.json"]:
        path = Path(fname)
        if path.exists():
            try:
                data[fname] = json.loads(path.read_text(encoding="utf-8"))
                log(f"  Încărcat {fname} ({path.stat().st_size // 1024}KB)")
            except Exception as e:
                log(f"  ⚠ Nu am putut citi {fname}: {e}")

    # cache_firme.json — date per firmă
    cache_path = Path("cache_firme.json")
    if cache_path.exists():
        try:
            data["firme"] = json.loads(cache_path.read_text(encoding="utf-8"))
            log(f"  Încărcat cache_firme.json ({len(data['firme'])} firme)")
        except Exception as e:
            log(f"  ⚠ cache_firme.json: {e}")

    return data


def extrage_date_relevante(data: dict) -> dict:
    """
    Construiește un rezumat compact al datelor pentru a minimiza tokens.
    Gemini primește esența, nu fișierele brute.
    """
    raport = data.get("raport.json", {})
    stare  = data.get("stare_anterioara.json", {})
    firme  = data.get("firme", {})

    flags      = raport.get("flags", [])
    contracte  = raport.get("contracte", [])
    statistici = raport.get("statistici", {})
    buget      = raport.get("buget", {})
    data_gen   = raport.get("data_generare", datetime.now().strftime("%Y-%m-%d"))
    flags_noi  = stare.get("flags_noi_count", 0)

    # Rezumat flags per tip și severitate
    flags_summary = defaultdict(lambda: {"CRITIC": 0, "MAJOR": 0, "MEDIU": 0})
    for f in flags:
        flags_summary[f.get("tip", "NECUNOSCUT")][f.get("severitate", "MEDIU")] += 1

    # Top firme după număr de flags
    flags_per_firma = defaultdict(list)
    valoare_per_firma = defaultdict(float)
    for f in flags:
        furn = f.get("furnizor", "")
        if furn:
            flags_per_firma[furn].append(f)
            valoare_per_firma[furn] += f.get("valoare", 0) or 0

    top_firme = sorted(
        flags_per_firma.items(),
        key=lambda x: (len(x[1]), valoare_per_firma[x[0]]),
        reverse=True,
    )[:TOP_FIRME_N]

    # Adresele firmelor (pentru detecție conexiuni)
    adrese_firme = {}
    for cui, info in firme.items():
        adresa = info.get("adresa") or info.get("address") or ""
        if adresa:
            adrese_firme[cui] = adresa

    # Pattern-uri temporale: contracte per lună
    contracte_per_luna = defaultdict(float)
    contracte_per_furnizor_luna = defaultdict(lambda: defaultdict(list))
    for c in contracte:
        data_c = c.get("data_publicare", "")[:7]  # YYYY-MM
        if data_c:
            contracte_per_luna[data_c] += c.get("valoare_ron", 0)
            furn = c.get("castigator", "")
            if furn:
                contracte_per_furnizor_luna[furn][data_c].append(c)

    # Firme cu contracte în aceeași lună (posibile grupuri coordonate)
    luni_active_per_firma = {
        furn: list(luni.keys())
        for furn, luni in contracte_per_furnizor_luna.items()
        if len(luni) > 0
    }

    return {
        "data_generare": data_gen,
        "flags_noi": flags_noi,
        "statistici": {
            "total_flags": len(flags),
            "critic": sum(1 for f in flags if f.get("severitate") == "CRITIC"),
            "major":  sum(1 for f in flags if f.get("severitate") == "MAJOR"),
            "mediu":  sum(1 for f in flags if f.get("severitate") == "MEDIU"),
            "total_contracte": len(contracte),
            "valoare_totala": sum(c.get("valoare_ron", 0) for c in contracte),
            "hcl_extraordinare_pct": statistici.get("hcl", {}).get("pct_extraordinare", 0),
        },
        "buget": {
            "venituri": buget.get("venituri_mil_ron"),
            "cheltuieli": buget.get("cheltuieli_mil_ron"),
        },
        "flags_per_tip": {k: dict(v) for k, v in flags_summary.items()},
        "top_firme": [
            {
                "nume": furn,
                "nr_flags": len(fflags),
                "valoare_totala": valoare_per_firma[furn],
                "tipuri_flags": list({f["tip"] for f in fflags}),
                "cel_mai_grav": max(fflags, key=lambda f: {"CRITIC": 3, "MAJOR": 2, "MEDIU": 1}.get(f.get("severitate","MEDIU"), 1)),
            }
            for furn, fflags in top_firme
        ],
        "contracte_per_luna": dict(sorted(contracte_per_luna.items())),
        "adrese_firme": adrese_firme,
        "luni_active_per_firma": {k: v for k, v in luni_active_per_firma.items() if len(v) >= 2},
    }


# ── Modul 1: Briefing săptămânal ─────────────────────────────────────────────

def genereaza_briefing(rezumat: dict) -> dict:
    """Generează un briefing investigativ săptămânal în română."""
    log("  [Modul 1] Generez briefing săptămânal...")

    top3 = rezumat["top_firme"][:3]
    top3_text = "\n".join(
        f"  - {f['nume']}: {f['nr_flags']} flags ({', '.join(f['tipuri_flags'][:3])}), "
        f"valoare totală {fmt_ron(f['valoare_totala'])}"
        for f in top3
    )

    s = rezumat["statistici"]
    prompt = f"""Ești un jurnalist de investigație specializat în achiziții publice din România.
Scrie un briefing investigativ CONCIS (maximum 350 cuvinte) în limba română, pe baza datelor de mai jos.

DATE ANALIZĂ — Primăria Pantelimon, {rezumat['data_generare']}:
- Total red flags detectate: {s['total_flags']} ({s['critic']} CRITIC, {s['major']} MAJOR, {s['mediu']} MEDIU)
- Flags noi față de săptămâna trecută: {rezumat['flags_noi']}
- Contracte analizate: {s['total_contracte']} ({fmt_ron(s['valoare_totala'])})
- Ședințe CL extraordinare: {s['hcl_extraordinare_pct']}% din total

TOP 3 FIRME CU CEL MAI MARE RISC:
{top3_text}

INSTRUCȚIUNI:
1. Începe cu cel mai îngrijorător finding specific (nu generic)
2. Menționează firmele și valorile concrete
3. Explică DE CE e îngrijorător (context legal simplu)
4. Dacă există flags noi, evidențiază-le
5. Încheie cu o recomandare concretă cetățenilor (ce pot face)
6. Ton: factual, neutru, informativ — NU dramatic, NU speculativ
7. Format: paragraf continuu, NU liste cu bullet points
8. OBLIGATORIU: adaugă disclaimer la final (italic): "Analiză generată automat pe baza datelor publice. Necesită verificare umană înainte de utilizare."

Scrie DOAR briefing-ul, fără titlu și fără introducere."""

    text = gemini_call(prompt, max_tokens=1024)

    return {
        "text": text,
        "data": rezumat["data_generare"],
        "statistici_rezumat": {
            "total_flags": s["total_flags"],
            "flags_noi": rezumat["flags_noi"],
            "top_firma": top3[0]["nume"] if top3 else "N/A",
        },
    }


# ── Modul 2: Scor AI per firmă ────────────────────────────────────────────────

def genereaza_scoruri_firme(rezumat: dict) -> list:
    """Generează evaluare AI pentru top N firme cu risc ridicat."""
    log(f"  [Modul 2] Generez scoruri AI pentru {len(rezumat['top_firme'])} firme...")

    rezultate = []

    for i, firma in enumerate(rezumat["top_firme"]):
        log(f"    ({i+1}/{len(rezumat['top_firme'])}) {firma['nume'][:40]}...")

        cel_mai_grav = firma.get("cel_mai_grav", {})

        prompt = f"""Ești expert în achiziții publice românești (Legea 98/2016).
Evaluează riscul asociat firmei de mai jos în maxim 3 propoziții clare în română.

FIRMĂ: {firma['nume']}
NR. FLAGS DETECTATE: {firma['nr_flags']}
TIPURI NEREGULI: {', '.join(firma['tipuri_flags'])}
VALOARE TOTALĂ CONTRACTE IMPLICATE: {fmt_ron(firma['valoare_totala'])}
CEL MAI GRAV INCIDENT: {cel_mai_grav.get('titlu', 'N/A')} — {cel_mai_grav.get('descriere', '')[:200]}

INSTRUCȚIUNI:
- Propoziție 1: Ce pattern de risc prezintă firma (concret, cu valori)
- Propoziție 2: Ce risc legal specific implică (articol de lege dacă relevant)
- Propoziție 3: Ce acțiune recomandați (ANAP, Curtea de Conturi, sau "monitorizare continuă")
- Nivel risc final: RIDICAT / MEDIU / SCĂZUT (o singură linie la final)
- Format: Propoziție1. Propoziție2. Propoziție3.\nNivel risc: RIDICAT/MEDIU/SCĂZUT
- NU repeta numele firmei la fiecare propoziție
- NU adăuga titlu sau introducere"""

        try:
            text = gemini_call(prompt, max_tokens=512)

            # Extrage nivelul risc din ultima linie
            nivel_risc = "MEDIU"
            linii = [l.strip() for l in text.split("\n") if l.strip()]
            for linie in reversed(linii):
                if "nivel risc:" in linie.lower():
                    if "RIDICAT" in linie.upper():
                        nivel_risc = "RIDICAT"
                    elif "SCĂZUT" in linie.upper() or "SCAZUT" in linie.upper():
                        nivel_risc = "SCĂZUT"
                    else:
                        nivel_risc = "MEDIU"
                    text = "\n".join(l for l in linii if "nivel risc:" not in l.lower())
                    break

            rezultate.append({
                "firma": firma["nume"],
                "evaluare": text,
                "nivel_risc": nivel_risc,
                "nr_flags": firma["nr_flags"],
                "valoare": firma["valoare_totala"],
                "tipuri_flags": firma["tipuri_flags"],
            })
        except Exception as e:
            log(f"    ⚠ Eroare Gemini pentru {firma['nume'][:30]}: {e}")
            rezultate.append({
                "firma": firma["nume"],
                "evaluare": "Evaluare indisponibilă temporar.",
                "nivel_risc": "MEDIU",
                "nr_flags": firma["nr_flags"],
                "valoare": firma["valoare_totala"],
                "tipuri_flags": firma["tipuri_flags"],
            })

    return rezultate


# ── Modul 3: Detector conexiuni ascunse ─────────────────────────────────────

def detecteaza_conexiuni(rezumat: dict) -> dict:
    """Detectează pattern-uri temporale și grupuri de firme coordonate."""
    log("  [Modul 3] Detectez conexiuni ascunse...")

    # Construim contextul pentru AI
    luni_active = rezumat.get("luni_active_per_firma", {})

    # Găsim firme cu activitate sincronizată (aceleași luni)
    luni_to_firme = defaultdict(list)
    for firma, luni in luni_active.items():
        for luna in luni:
            luni_to_firme[luna].append(firma)

    # Luni cu multiple firme active simultan (>3 firme diferite)
    luni_aglomerate = {
        luna: firme
        for luna, firme in luni_to_firme.items()
        if len(firme) > 3
    }

    # Firme cu adrese similare (potențial grup)
    adrese = rezumat.get("adrese_firme", {})
    adrese_text = "\n".join(
        f"  {cui}: {adr}"
        for cui, adr in list(adrese.items())[:30]  # max 30 firme
    ) if adrese else "  (date adrese indisponibile)"

    # Text activitate lunară
    luni_text = "\n".join(
        f"  {luna}: {len(firme)} firme active simultan ({', '.join(firme[:4])}{'...' if len(firme)>4 else ''})"
        for luna, firme in sorted(luni_aglomerate.items())[-6:]  # ultimele 6 luni relevante
    ) if luni_aglomerate else "  (nu s-au detectat concentrări lunare semnificative)"

    top_firme_text = "\n".join(
        f"  {f['nume']}: {f['nr_flags']} flags, {fmt_ron(f['valoare_totala'])}"
        for f in rezumat["top_firme"][:10]
    )

    prompt = f"""Ești analist de date specializat în detectarea corupției în achiziții publice din România.
Analizează datele de mai jos și identifică pattern-uri îngrijorătoare de conexiuni între firme.

DATE PRIMĂRIA PANTELIMON:

TOP 10 FIRME CU RISC (după număr flags):
{top_firme_text}

ACTIVITATE LUNARĂ CONCENTRATĂ (luni cu >3 firme active simultan):
{luni_text}

ADRESE FIRME (primele 30):
{adrese_text}

SARCINĂ:
1. Identifică maxim 3 pattern-uri concrete îngrijorătoare:
   - Firme cu activitate sincronizată în aceeași perioadă
   - Posibile grupuri de firme (adrese comune, tipare similare)
   - Concentrări temporale suspecte de contracte

2. Pentru fiecare pattern:
   - Descrie concret ce ai observat (cu names de firme și date)
   - Explică de ce e îngrijorător
   - Indică ce informații suplimentare ar confirma sau infirma

FORMAT RĂSPUNS (JSON strict, fără text în afara JSON):
{{
  "pattern_detectate": [
    {{
      "titlu": "...",
      "descriere": "...(2-3 propoziții)...",
      "firme_implicate": ["Firma A", "Firma B"],
      "nivel_incredere": "RIDICAT/MEDIU/SCĂZUT",
      "actiune_recomandata": "..."
    }}
  ],
  "concluzie_generala": "...(1 propoziție)...",
  "disclaimer": "Pattern-uri detectate automat. Necesită verificare manuală."
}}"""

    try:
        text = gemini_call(prompt, max_tokens=1024)

        # Extrage JSON-ul din răspuns
        text_clean = text.strip()
        if "```json" in text_clean:
            text_clean = text_clean.split("```json")[1].split("```")[0].strip()
        elif "```" in text_clean:
            text_clean = text_clean.split("```")[1].strip()

        result = json.loads(text_clean)
        result["data"] = rezumat["data_generare"]
        return result

    except json.JSONDecodeError:
        log("  ⚠ Răspuns Modul 3 nu e JSON valid — salvez ca text")
        return {
            "pattern_detectate": [],
            "concluzie_generala": text if 'text' in dir() else "Analiză indisponibilă.",
            "disclaimer": "Pattern-uri detectate automat. Necesită verificare manuală.",
            "data": rezumat["data_generare"],
            "eroare": "raspuns_non_json",
        }
    except Exception as e:
        log(f"  ⚠ Eroare Modul 3: {e}")
        return {
            "pattern_detectate": [],
            "concluzie_generala": "Analiză indisponibilă temporar.",
            "disclaimer": "Pattern-uri detectate automat. Necesită verificare manuală.",
            "data": rezumat["data_generare"],
            "eroare": str(e),
        }


# ── Generare widget HTML ──────────────────────────────────────────────────────

def genereaza_widget_html(analiza: dict) -> str:
    """Generează fragmentul HTML pentru widgetul AI din raport."""
    briefing = analiza.get("briefing", {})
    conexiuni = analiza.get("conexiuni", {})
    scoruri   = analiza.get("scoruri_firme", [])

    data_str    = briefing.get("data", datetime.now().strftime("%Y-%m-%d"))
    text_brief  = briefing.get("text", "Analiză în curs de generare...")
    # Scurtăm textul pentru widget (primele ~300 caractere)
    text_scurt  = text_brief[:300].rsplit(" ", 1)[0] + "..." if len(text_brief) > 300 else text_brief

    # Pattern-uri detectate
    patterns    = conexiuni.get("pattern_detectate", [])
    concluzie   = conexiuni.get("concluzie_generala", "")

    # Firme cu risc ridicat
    firme_ridicate = [s for s in scoruri if s.get("nivel_risc") == "RIDICAT"]

    patterns_html = ""
    for p in patterns[:3]:
        culoare = {"RIDICAT": "#C0392B", "MEDIU": "#E67E22", "SCĂZUT": "#27AE60"}.get(
            p.get("nivel_incredere", "MEDIU"), "#E67E22"
        )
        patterns_html += f"""
        <div style="border-left:3px solid {culoare};padding:8px 12px;margin-bottom:10px;background:#fafafa;border-radius:0 6px 6px 0">
          <div style="font-weight:700;font-size:13px;color:{culoare}">{p.get('titlu','')}</div>
          <div style="font-size:12px;color:#444;margin-top:4px">{p.get('descriere','')[:200]}</div>
          {'<div style="font-size:11px;color:#666;margin-top:4px">Firme: ' + ', '.join(p.get('firme_implicate',[])[:3]) + '</div>' if p.get('firme_implicate') else ''}
        </div>"""

    firme_html = ""
    for s in firme_ridicate[:5]:
        firme_html += f"""
        <div style="display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid #f0f0f0">
          <span style="background:#C0392B;color:#fff;font-size:10px;font-weight:700;padding:2px 6px;border-radius:4px;white-space:nowrap">RIDICAT</span>
          <span style="font-size:12px;font-weight:600">{s['firma'][:45]}</span>
          <span style="font-size:11px;color:#777;margin-left:auto">{s['nr_flags']} flags · {fmt_ron(s['valoare'])}</span>
        </div>"""

    widget = f"""<!-- WIDGET AI ANALIZA — generat automat {data_str} -->
<div id="ai-analiza" style="background:#fff;border-radius:12px;border:2px solid #7B2FBE;box-shadow:0 2px 12px rgba(123,47,190,0.12);margin:28px 0;overflow:hidden">
  <!-- Header -->
  <div style="background:linear-gradient(135deg,#7B2FBE,#9B59B6);color:#fff;padding:14px 20px;display:flex;align-items:center;gap:10px">
    <span style="font-size:20px">🤖</span>
    <div>
      <div style="font-weight:800;font-size:15px">Analiză AI — Gemini</div>
      <div style="font-size:11px;opacity:.8">Actualizat {data_str} · bazat pe date publice SEAP + ANAF</div>
    </div>
    <div style="margin-left:auto;background:rgba(255,255,255,.2);border-radius:6px;padding:4px 10px;font-size:11px">gratuit · open-source</div>
  </div>

  <!-- Tabs -->
  <div style="display:flex;border-bottom:2px solid #f0f0f0">
    <button onclick="aiTab('briefing')" id="tab-briefing"
      style="flex:1;padding:10px;font-size:12px;font-weight:600;border:none;cursor:pointer;background:#7B2FBE;color:#fff">
      📋 Briefing Săptămânal
    </button>
    <button onclick="aiTab('conexiuni')" id="tab-conexiuni"
      style="flex:1;padding:10px;font-size:12px;font-weight:600;border:none;cursor:pointer;background:#f5f5f5;color:#444">
      🔗 Conexiuni Detectate
    </button>
    <button onclick="aiTab('firme')" id="tab-firme"
      style="flex:1;padding:10px;font-size:12px;font-weight:600;border:none;cursor:pointer;background:#f5f5f5;color:#444">
      🏢 Firme Risc Ridicat
    </button>
  </div>

  <!-- Tab: Briefing -->
  <div id="ai-briefing" style="padding:20px;display:block">
    <p style="font-size:14px;line-height:1.7;color:#333;margin:0 0 12px">{text_scurt}</p>
    {'<details style="margin-top:8px"><summary style="cursor:pointer;color:#7B2FBE;font-size:13px;font-weight:600">Citește analiza completă ▾</summary><p style="font-size:13px;line-height:1.7;color:#555;margin-top:10px;padding:12px;background:#f9f5ff;border-radius:8px">' + text_brief + '</p></details>' if len(text_brief) > 300 else ''}
    {('<div style="margin-top:12px;padding:10px;background:#f9f5ff;border-radius:8px;font-size:12px;color:#555">' + concluzie + '</div>') if concluzie else ''}
  </div>

  <!-- Tab: Conexiuni -->
  <div id="ai-conexiuni" style="padding:20px;display:none">
    {patterns_html if patterns_html else '<p style="color:#777;font-size:13px">Nu s-au detectat pattern-uri semnificative în această perioadă.</p>'}
    <div style="font-size:11px;color:#999;margin-top:12px;font-style:italic">{conexiuni.get('disclaimer','')}</div>
  </div>

  <!-- Tab: Firme -->
  <div id="ai-firme" style="padding:20px;display:none">
    {firme_html if firme_html else '<p style="color:#777;font-size:13px">Nu s-au identificat firme cu risc ridicat în această perioadă.</p>'}
    <div style="font-size:11px;color:#999;margin-top:12px;font-style:italic">
      Evaluări generate automat pe baza algoritmilor de detecție. Necesită verificare umană.
    </div>
  </div>
</div>

<script>
function aiTab(tab) {{
  ['briefing','conexiuni','firme'].forEach(function(t) {{
    document.getElementById('ai-' + t).style.display = t === tab ? 'block' : 'none';
    var btn = document.getElementById('tab-' + t);
    btn.style.background = t === tab ? '#7B2FBE' : '#f5f5f5';
    btn.style.color = t === tab ? '#fff' : '#444';
  }});
}}
</script>
<!-- END WIDGET AI -->"""

    return widget


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log("=== Analiză AI — Gemini 2.0 Flash (gratuit) ===")

    if not GEMINI_API_KEY:
        log("EROARE: GEMINI_API_KEY nu e setat.")
        log("  → Obține key gratuit: https://aistudio.google.com/")
        log("  → Setează: export GEMINI_API_KEY='AIza...'")
        log("  → Sau adaugă în GitHub Secrets ca GEMINI_API_KEY")
        sys.exit(1)

    # 1. Încarcă datele
    log("1. Încarc datele existente...")
    data = load_data()

    if not data.get("raport.json"):
        log("EROARE: raport.json lipsă. Rulează mai întâi monitor_pantelimon.py")
        sys.exit(1)

    # 2. Extrage rezumat compact
    log("2. Extrag rezumat compact...")
    rezumat = extrage_date_relevante(data)
    log(f"   → {rezumat['statistici']['total_flags']} flags, "
        f"{rezumat['statistici']['total_contracte']} contracte, "
        f"{len(rezumat['top_firme'])} firme în analiză")

    # 3. Modul 1 — Briefing
    log("3. Modul 1 — Briefing săptămânal...")
    briefing = genereaza_briefing(rezumat)
    log(f"   → {len(briefing['text'])} caractere generate")

    # 4. Modul 2 — Scoruri firme
    log(f"4. Modul 2 — Scoruri AI ({len(rezumat['top_firme'])} firme)...")
    scoruri = genereaza_scoruri_firme(rezumat)
    risc_ridicat = sum(1 for s in scoruri if s.get("nivel_risc") == "RIDICAT")
    log(f"   → {len(scoruri)} firme evaluate, {risc_ridicat} cu risc RIDICAT")

    # 5. Modul 3 — Conexiuni
    log("5. Modul 3 — Detector conexiuni ascunse...")
    conexiuni = detecteaza_conexiuni(rezumat)
    log(f"   → {len(conexiuni.get('pattern_detectate', []))} pattern-uri detectate")

    # 6. Asamblare rezultat final
    analiza = {
        "data_generare": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "model_folosit": GEMINI_MODEL,
        "cost_estimat": "$0 (Gemini Free Tier)",
        "briefing": briefing,
        "scoruri_firme": scoruri,
        "conexiuni": conexiuni,
    }

    # 7. Generare widget HTML
    log("6. Generez widget HTML...")
    analiza["widget_html"] = genereaza_widget_html(analiza)

    # 8. Salvare
    output_path = Path(OUTPUT_FILE)
    output_path.write_text(json.dumps(analiza, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"7. Salvat: {OUTPUT_FILE} ({output_path.stat().st_size // 1024}KB)")

    # Rezumat final
    log("")
    log("=== GATA ===")
    log(f"   Briefing: {len(briefing['text'])} caractere")
    log(f"   Firme evaluate: {len(scoruri)} ({risc_ridicat} risc RIDICAT)")
    log(f"   Pattern-uri conexiuni: {len(conexiuni.get('pattern_detectate', []))}")
    log(f"   Widget HTML: {len(analiza['widget_html'])} caractere")
    log("")
    log("Pasul următor: monitor_pantelimon.py va citi analiza_ai.json")
    log("  și va insera widgetul în raport_transparenta.html automat.")


if __name__ == "__main__":
    main()
