"""
Monitor Transparență Bugetară — Primăria Pantelimon
====================================================
Script de monitorizare automată: trage date din SEAP și transparenta.eu,
detectează red flags și generează raport HTML + alertă email opțională.

Utilizare:
    python monitor_pantelimon.py          # rulează analiza și generează raportul
    python monitor_pantelimon.py --email  # rulează și trimite email dacă sunt flags noi

Dependențe: pip install requests beautifulsoup4
"""

import json
import os
import smtplib
import sys
import time
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ==============================================================================
# CONFIGURARE — EDITEAZĂ ACESTE VALORI
# ==============================================================================

CONFIG = {
    # Identificatori Primăria Pantelimon
    "cui": "4420759",
    "nume_entitate": "Orașul Pantelimon",
    "judet": "Ilfov",

    # Praguri legale achiziție publică (RON, conform Legii 98/2016 actualizate)
    "prag_servicii_furnizare": 130_000,   # sub acest prag → cumpărare directă
    "prag_lucrari": 500_000,              # sub acest prag → procedură simplificată
    "marja_fragmentare_pct": 0.97,        # dacă valoarea e >97% din prag → suspect

    # Câte luni în urmă căutăm contracte
    "luni_analiza": 12,

    # Fișiere locale
    "fisier_stare": "stare_anterioara.json",   # pentru a detecta items noi
    "fisier_raport": "raport_transparenta.html",

    # Email (opțional — lasă gol dacă nu vrei alerte email)
    "email_from": "",          # ex: "monitorizare.pantelimon@gmail.com"
    "email_to": "",            # ex: "office@valisblue.com"
    "email_smtp": "smtp.gmail.com",
    "email_port": 587,
    "email_parola": "",        # recomandăm App Password Google, nu parola reală
}

# ==============================================================================
# SURSE DE DATE
# ==============================================================================

SEAP_BASE = "https://www.e-licitatie.ro/api-pub"
TRANSPARENTA_BASE = "https://transparenta.eu"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MonitorCivic/1.0; civic transparency)",
    "Accept": "application/json, text/html",
    "Content-Type": "application/json",
}

# ==============================================================================
# 1. DATE BUGET DIN TRANSPARENTA.EU
# ==============================================================================

def fetch_budget_transparenta(cui: str) -> dict:
    """
    Extrage datele financiare din transparenta.eu (sursă: ANAF/MF).
    Returnează dict cu venituri, cheltuieli, evoluție YoY.
    """
    print(f"  [transparenta.eu] Fetchuiesc date buget pentru CUI {cui}...")
    url = f"{TRANSPARENTA_BASE}/entities/{cui}"

    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")

        # Extragem din meta description: "Venituri X mil. RON, Cheltuieli Y mil. RON..."
        meta_desc = ""
        for tag in soup.find_all("meta"):
            if tag.get("name") == "description" or tag.get("property") == "og:description":
                meta_desc = tag.get("content", "")
                break

        # Parse simplu din description
        result = {
            "sursa": "transparenta.eu / ANAF",
            "url": url,
            "descriere_bruta": meta_desc,
            "an": datetime.now().year,
            "venituri_mil_ron": None,
            "cheltuieli_mil_ron": None,
            "balanta_mil_ron": None,
        }

        # Extragem valorile numerice din description
        import re
        numere = re.findall(r"[\d,\.]+\s*mil\.?\s*RON", meta_desc)
        if len(numere) >= 2:
            def parse_ron(s):
                s = s.replace("mil.", "").replace("RON", "").replace("\xa0", "").strip()
                s = s.replace(",", ".")
                return float(s)
            result["venituri_mil_ron"] = parse_ron(numere[0])
            result["cheltuieli_mil_ron"] = parse_ron(numere[1])
            if len(numere) >= 3:
                result["balanta_mil_ron"] = parse_ron(numere[2])

        # Extragem și YoY din pagina HTML
        yoy_patterns = re.findall(r"([+-][\d,\.]+%)\s*YoY", r.text)
        result["yoy_venituri"] = yoy_patterns[0] if len(yoy_patterns) > 0 else "N/A"
        result["yoy_cheltuieli"] = yoy_patterns[1] if len(yoy_patterns) > 1 else "N/A"

        print(f"    ✓ Venituri: {result['venituri_mil_ron']} mil. RON  |  Cheltuieli: {result['cheltuieli_mil_ron']} mil. RON")
        return result

    except Exception as e:
        print(f"    ✗ Eroare transparenta.eu: {e}")
        return {"eroare": str(e), "sursa": "transparenta.eu"}


# ==============================================================================
# 2. DATE CONTRACTE DIN SEAP (e-licitatie.ro)
# ==============================================================================

def fetch_contracts_seap(cui: str, luni: int = 12) -> list:
    """
    Caută contractele atribuite de Primăria Pantelimon în SEAP
    în ultimele `luni` luni. Returnează lista de contracte.
    """
    print(f"  [SEAP] Caut contracte pentru CUI {cui} (ultimele {luni} luni)...")

    data_start = (datetime.now() - timedelta(days=luni * 30)).strftime("%Y-%m-%d")
    data_end = datetime.now().strftime("%Y-%m-%d")

    # Endpoint pentru anunțuri de atribuire (contracte finalizate)
    url = f"{SEAP_BASE}/NoticeSearch/GetList"

    payload = {
        "caNoticeStateCode": None,
        "cpvCodeId": None,
        "contractingAuthority": cui,
        "contractingAuthorityFiscalNumber": cui,
        "noticeStateCode": None,
        "publicationDateStart": data_start,
        "publicationDateEnd": data_end,
        "pageSize": 100,
        "pageIndex": 0,
        "sortField": "publicationDate",
        "sortDirection": "desc",
    }

    contracte = []

    try:
        r = requests.post(url, json=payload, headers=HEADERS, timeout=30)
        r.raise_for_status()
        data = r.json()

        items = data.get("items", data.get("list", data.get("data", [])))
        print(f"    ✓ Găsite {len(items)} înregistrări în anunțuri de atribuire")

        for item in items:
            contract = {
                "id": item.get("caNoticeId") or item.get("id", ""),
                "numar": item.get("noticeNo", ""),
                "titlu": item.get("contractTitle", item.get("title", "Fără titlu")),
                "valoare_ron": float(item.get("contractValue", item.get("estimatedValue", 0)) or 0),
                "moneda": item.get("currencyCode", "RON"),
                "tip_procedura": item.get("procedureTypeName", item.get("procedureType", "")),
                "data_publicare": item.get("publicationDate", "")[:10] if item.get("publicationDate") else "",
                "castigator": item.get("winnerName", item.get("winner", {}).get("name", "Necunoscut")),
                "castigator_cui": item.get("winnerFiscalNumber", ""),
                "nr_ofertanti": int(item.get("numberOfOffers", item.get("nbTendersReceived", 1)) or 1),
                "sursa": "SEAP-atribuire",
            }
            contracte.append(contract)

    except requests.exceptions.HTTPError as e:
        print(f"    ⚠ Anunțuri atribuire: HTTP {e.response.status_code} - încerc endpoint alternativ")

    # Fallback: endpoint alternativ pentru contracte
    if not contracte:
        url2 = f"{SEAP_BASE}/C_PUBLIC_CANotice/GetCANoticeContracts"
        payload2 = {
            "contractingAuthorityCode": cui,
            "pageSize": 100,
            "pageIndex": 0,
        }
        try:
            r2 = requests.post(url2, json=payload2, headers=HEADERS, timeout=30)
            if r2.status_code == 200:
                data2 = r2.json()
                items2 = data2.get("items", data2.get("list", []))
                print(f"    ✓ Fallback: găsite {len(items2)} contracte")
                for item in items2:
                    contracte.append({
                        "id": item.get("caNoticeId", ""),
                        "numar": item.get("contractNo", ""),
                        "titlu": item.get("contractTitle", ""),
                        "valoare_ron": float(item.get("contractValue", 0) or 0),
                        "moneda": "RON",
                        "tip_procedura": item.get("procedureType", ""),
                        "data_publicare": (item.get("contractDate") or "")[:10],
                        "castigator": item.get("winnerTitle", ""),
                        "castigator_cui": item.get("winnerFiscalNumber", ""),
                        "nr_ofertanti": 1,
                        "sursa": "SEAP-contracte",
                    })
        except Exception as e2:
            print(f"    ✗ Fallback eșuat: {e2}")

    # Dacă tot nu avem date, generăm date demonstrative cu avertisment
    if not contracte:
        print("    ⚠ Nu s-au putut obține date live SEAP - folosim date demonstrative")
        contracte = _date_demonstrative_seap()

    return contracte


def _date_demonstrative_seap() -> list:
    """Date demonstrative pentru când API-ul SEAP nu răspunde."""
    return [
        {"id": "demo1", "numar": "2025-001", "titlu": "Lucrări reabilitare str. Principală",
         "valoare_ron": 1_240_000, "moneda": "RON", "tip_procedura": "Negociere fără publicare prealabilă",
         "data_publicare": "2025-03-15", "castigator": "SC CONSTRUCT RAPID SRL",
         "castigator_cui": "12345678", "nr_ofertanti": 1, "sursa": "DEMO"},
        {"id": "demo2", "numar": "2025-002", "titlu": "Furnizare materiale construcții lot 1",
         "valoare_ron": 128_500, "moneda": "RON", "tip_procedura": "Cumpărare directă",
         "data_publicare": "2025-04-02", "castigator": "SC MATERIALE BUILD SRL",
         "castigator_cui": "87654321", "nr_ofertanti": 1, "sursa": "DEMO"},
        {"id": "demo3", "numar": "2025-003", "titlu": "Furnizare materiale construcții lot 2",
         "valoare_ron": 127_800, "moneda": "RON", "tip_procedura": "Cumpărare directă",
         "data_publicare": "2025-04-09", "castigator": "SC MATERIALE BUILD SRL",
         "castigator_cui": "87654321", "nr_ofertanti": 1, "sursa": "DEMO"},
        {"id": "demo4", "numar": "2025-004", "titlu": "Servicii salubrizare stradală",
         "valoare_ron": 680_000, "moneda": "RON", "tip_procedura": "Licitație deschisă",
         "data_publicare": "2025-02-10", "castigator": "SC SALUBRITATE ILFOV SRL",
         "castigator_cui": "11223344", "nr_ofertanti": 2, "sursa": "DEMO"},
        {"id": "demo5", "numar": "2025-005", "titlu": "Servicii pază și securitate sediu",
         "valoare_ron": 96_000, "moneda": "RON", "tip_procedura": "Procedură simplificată",
         "data_publicare": "2025-01-20", "castigator": "SC PAZA TOTAL SRL",
         "castigator_cui": "55667788", "nr_ofertanti": 1, "sursa": "DEMO"},
        {"id": "demo6", "numar": "2025-006", "titlu": "Lucrări reabilitare str. Secundară",
         "valoare_ron": 1_180_000, "moneda": "RON", "tip_procedura": "Negociere fără publicare prealabilă",
         "data_publicare": "2025-03-22", "castigator": "SC CONSTRUCT RAPID SRL",
         "castigator_cui": "12345678", "nr_ofertanti": 1, "sursa": "DEMO"},
        {"id": "demo7", "numar": "2025-007", "titlu": "Servicii IT infrastructură",
         "valoare_ron": 45_000, "moneda": "RON", "tip_procedura": "Cumpărare directă",
         "data_publicare": "2025-05-01", "castigator": "SC DIGITAL SOLUTIONS SRL",
         "castigator_cui": "99001122", "nr_ofertanti": 1, "sursa": "DEMO"},
        {"id": "demo8", "numar": "2025-008", "titlu": "Amenajare spații verzi",
         "valoare_ron": 38_200, "moneda": "RON", "tip_procedura": "Cumpărare directă",
         "data_publicare": "2025-04-18", "castigator": "SC GREEN PARK SRL",
         "castigator_cui": "33445566", "nr_ofertanti": 1, "sursa": "DEMO"},
    ]


# ==============================================================================
# 3. ALGORITMI DE DETECȚIE RED FLAGS
# ==============================================================================

def analizeaza_red_flags(contracte: list, config: dict) -> list:
    """
    Rulează toți algoritmii de detecție pe lista de contracte.
    Returnează o listă de red flags găsite.
    """
    print("  [Analiză] Rulând algoritmi de detecție red flags...")
    flags = []

    prag_s = config["prag_servicii_furnizare"]
    prag_l = config["prag_lucrari"]
    marja = config["marja_fragmentare_pct"]

    # ── Algoritm 1: Contracte cu un singur ofertant ──────────────────────────
    for c in contracte:
        if c["nr_ofertanti"] == 1 and c["valoare_ron"] > 20_000:
            severitate = "MAJOR" if c["valoare_ron"] > 200_000 else "MEDIU"
            flags.append({
                "tip": "OFERTANT_UNIC",
                "severitate": severitate,
                "titlu": "Un singur ofertant",
                "descriere": f'Contractul "{c["titlu"][:60]}..." ({_fmt_ron(c["valoare_ron"])}) '
                             f'a fost atribuit fără competiție reală.',
                "contract_id": c["id"],
                "contract_numar": c["numar"],
                "valoare": c["valoare_ron"],
                "furnizor": c["castigator"],
                "data": c["data_publicare"],
                "tip_procedura": c["tip_procedura"],
            })

    # ── Algoritm 2: Valoare aproape de prag (fragmentare suspectă) ───────────
    for c in contracte:
        v = c["valoare_ron"]
        if v > 0:
            for prag, tip_prag in [(prag_s, "servicii/furnizare"), (prag_l, "lucrări")]:
                if prag * marja < v <= prag:
                    flags.append({
                        "tip": "APROAPE_DE_PRAG",
                        "severitate": "MAJOR",
                        "titlu": "Valoare suspectă aproape de prag",
                        "descriere": (f'Contract {tip_prag} cu valoare {_fmt_ron(v)}, '
                                     f'cu {_fmt_ron(prag - v)} sub pragul de licitație ({_fmt_ron(prag)}). '
                                     f'Posibilă evitare deliberată a procedurii competitive.'),
                        "contract_id": c["id"],
                        "contract_numar": c["numar"],
                        "valoare": v,
                        "furnizor": c["castigator"],
                        "data": c["data_publicare"],
                        "tip_procedura": c["tip_procedura"],
                    })

    # ── Algoritm 3: Fragmentare (același furnizor, titluri similare, interval scurt) ─
    from collections import defaultdict
    pe_furnizor = defaultdict(list)
    for c in contracte:
        if c["castigator_cui"]:
            pe_furnizor[c["castigator_cui"]].append(c)

    for cui_f, lista in pe_furnizor.items():
        if len(lista) < 2:
            continue
        # Sortăm după dată
        lista_sorted = sorted(lista, key=lambda x: x["data_publicare"])
        for i in range(len(lista_sorted) - 1):
            a, b = lista_sorted[i], lista_sorted[i + 1]
            # Verificăm interval scurt (< 60 zile) și titluri similare
            try:
                da = datetime.strptime(a["data_publicare"], "%Y-%m-%d")
                db = datetime.strptime(b["data_publicare"], "%Y-%m-%d")
                zile_diferenta = abs((db - da).days)
            except ValueError:
                zile_diferenta = 999

            titlu_similar = (
                _similaritate_titlu(a["titlu"], b["titlu"]) > 0.4
                or "lot" in a["titlu"].lower() and "lot" in b["titlu"].lower()
            )
            valoare_combinata = a["valoare_ron"] + b["valoare_ron"]

            if zile_diferenta < 60 and titlu_similar and valoare_combinata > prag_s:
                flags.append({
                    "tip": "FRAGMENTARE",
                    "severitate": "CRITIC",
                    "titlu": "Posibilă fragmentare artificială a contractelor",
                    "descriere": (f'Furnizor "{a["castigator"]}" a primit 2 contracte similare '
                                 f'la interval de {zile_diferenta} zile, valoare combinată '
                                 f'{_fmt_ron(valoare_combinata)} (peste pragul de {_fmt_ron(prag_s)}). '
                                 f'Posibilă încălcare art. 11 din Legea 98/2016.'),
                    "contract_id": f"{a['id']},{b['id']}",
                    "contract_numar": f"{a['numar']} + {b['numar']}",
                    "valoare": valoare_combinata,
                    "furnizor": a["castigator"],
                    "data": a["data_publicare"],
                    "tip_procedura": a["tip_procedura"],
                })

    # ── Algoritm 4: Utilizare excesivă proceduri non-competitive ─────────────
    total = len(contracte)
    if total > 0:
        directe = [c for c in contracte if "direct" in c["tip_procedura"].lower()
                   or "negociere" in c["tip_procedura"].lower()]
        pct_directe = len(directe) / total * 100
        if pct_directe > 40:
            flags.append({
                "tip": "PROCEDURI_NON_COMPETITIVE",
                "severitate": "MAJOR",
                "titlu": "Exces de proceduri non-competitive",
                "descriere": (f'{len(directe)} din {total} contracte ({pct_directe:.0f}%) '
                             f'au fost atribuite prin cumpărare directă sau negociere fără publicare. '
                             f'Media națională recomandată este sub 30%.'),
                "contract_id": "global",
                "contract_numar": "–",
                "valoare": sum(c["valoare_ron"] for c in directe),
                "furnizor": "Multiple",
                "data": datetime.now().strftime("%Y-%m-%d"),
                "tip_procedura": "Multiple",
            })

    # ── Algoritm 5: Furnizori dominanți (monopol de facto) ───────────────────
    valori_pe_furnizor = defaultdict(float)
    for c in contracte:
        valori_pe_furnizor[c["castigator"]] += c["valoare_ron"]

    total_valoare = sum(c["valoare_ron"] for c in contracte)
    if total_valoare > 0:
        for furnizor, valoare in valori_pe_furnizor.items():
            pct = valoare / total_valoare * 100
            if pct > 35 and valoare > 500_000:
                flags.append({
                    "tip": "FURNIZOR_DOMINANT",
                    "severitate": "MEDIU",
                    "titlu": "Furnizor dominant în achizițiile publice",
                    "descriere": (f'"{furnizor}" a primit {pct:.0f}% din totalul contractelor '
                                 f'({_fmt_ron(valoare)} din {_fmt_ron(total_valoare)}). '
                                 f'Concentrare excesivă – risc de conflict de interese sau specificații preferențiale.'),
                    "contract_id": "global",
                    "contract_numar": "–",
                    "valoare": valoare,
                    "furnizor": furnizor,
                    "data": datetime.now().strftime("%Y-%m-%d"),
                    "tip_procedura": "Multiple",
                })

    # Deduplicare (același furnizor poate apărea în mai mulți algoritmi)
    flags_unice = []
    ids_vazute = set()
    for f in flags:
        key = f"{f['tip']}_{f['contract_id']}_{f['furnizor']}"
        if key not in ids_vazute:
            flags_unice.append(f)
            ids_vazute.add(key)

    print(f"    ✓ Detectate {len(flags_unice)} red flags "
          f"({sum(1 for f in flags_unice if f['severitate']=='CRITIC')} CRITIC, "
          f"{sum(1 for f in flags_unice if f['severitate']=='MAJOR')} MAJOR, "
          f"{sum(1 for f in flags_unice if f['severitate']=='MEDIU')} MEDIU)")

    return flags_unice


def _fmt_ron(valoare: float) -> str:
    """Formatează o sumă în RON pentru afișare."""
    if valoare >= 1_000_000:
        return f"{valoare/1_000_000:.2f} mil. RON"
    elif valoare >= 1_000:
        return f"{valoare/1_000:.0f}K RON"
    return f"{valoare:.0f} RON"


def _similaritate_titlu(a: str, b: str) -> float:
    """Similaritate simplă între două titluri (Jaccard pe cuvinte)."""
    wa = set(a.lower().split())
    wb = set(b.lower().split())
    if not wa or not wb:
        return 0
    return len(wa & wb) / len(wa | wb)


# ==============================================================================
# 4. TRACKING STARE (detectare flags NOI față de rularea anterioară)
# ==============================================================================

def incarca_stare_anterioara(fisier: str) -> dict:
    """Încarcă starea din rularea anterioară."""
    if Path(fisier).exists():
        with open(fisier, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"flags_anterioare": [], "data_ultima_rulare": None, "contracte_vazute": []}


def salveaza_stare(fisier: str, flags: list, contracte: list):
    """Salvează starea curentă pentru comparație viitoare."""
    stare = {
        "flags_anterioare": [f["contract_id"] + "_" + f["tip"] for f in flags],
        "contracte_vazute": [c["id"] for c in contracte],
        "data_ultima_rulare": datetime.now().isoformat(),
        "total_flags": len(flags),
    }
    with open(fisier, "w", encoding="utf-8") as f:
        json.dump(stare, f, ensure_ascii=False, indent=2)
    print(f"  [Stare] Salvat în {fisier}")


def detecteaza_flags_noi(flags_curente: list, stare_anterioara: dict) -> list:
    """Returnează doar flags-urile care nu existau la ultima rulare."""
    ids_anterioare = set(stare_anterioara.get("flags_anterioare", []))
    noi = [f for f in flags_curente
           if (f["contract_id"] + "_" + f["tip"]) not in ids_anterioare]
    return noi


# ==============================================================================
# 5. GENERARE RAPORT HTML
# ==============================================================================

def genereaza_raport_html(budget: dict, contracte: list, flags: list,
                           flags_noi: list, config: dict) -> str:
    """Generează raportul HTML complet."""

    data_generare = datetime.now().strftime("%d %B %Y, %H:%M")
    total_val = sum(c["valoare_ron"] for c in contracte)
    directe = [c for c in contracte if "direct" in c["tip_procedura"].lower()
               or "negociere" in c["tip_procedura"].lower()]
    unic_ofertant = [c for c in contracte if c["nr_ofertanti"] == 1]

    # Culori severitate
    culori = {"CRITIC": "#C0392B", "MAJOR": "#E67E22", "MEDIU": "#F39C12"}
    emoji_sev = {"CRITIC": "🔴", "MAJOR": "🟠", "MEDIU": "🟡"}

    flags_html = ""
    for f in flags:
        culoare = culori.get(f["severitate"], "#999")
        emoji = emoji_sev.get(f["severitate"], "⚪")
        nou_badge = ' <span style="background:#E8F5E9;color:#2E7D32;font-size:10px;padding:2px 8px;border-radius:10px;font-weight:700">NOU</span>' if f in flags_noi else ""
        flags_html += f"""
        <div style="border-left:4px solid {culoare};background:#fff;padding:14px 18px;
                    border-radius:0 8px 8px 0;margin-bottom:12px;
                    box-shadow:0 1px 3px rgba(0,0,0,0.08)">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
            <span style="font-size:16px">{emoji}</span>
            <strong style="color:{culoare}">[{f['severitate']}]</strong>
            <span style="font-weight:700">{f['titlu']}</span>
            {nou_badge}
          </div>
          <p style="font-size:13px;color:#444;margin:0 0 8px">{f['descriere']}</p>
          <div style="font-size:12px;color:#777;display:flex;gap:16px;flex-wrap:wrap">
            <span>📋 {f['contract_numar'] or '–'}</span>
            <span>💰 {_fmt_ron(f['valoare'])}</span>
            <span>🏢 {f['furnizor']}</span>
            <span>📅 {f['data']}</span>
            <span>⚙️ {f['tip_procedura']}</span>
          </div>
        </div>"""

    contracte_html = ""
    for c in contracte[:20]:  # primele 20
        badge_tip = ("🔴" if "direct" in c["tip_procedura"].lower() or "negociere" in c["tip_procedura"].lower()
                     else "🟢" if "deschis" in c["tip_procedura"].lower() else "🟡")
        badge_ofertanti = f'<span style="color:{"#C0392B" if c["nr_ofertanti"]==1 else "#27AE60"};font-weight:700">{c["nr_ofertanti"]}</span>'
        nota_demo = ' <em style="color:#aaa;font-size:10px">(demo)</em>' if c.get("sursa") == "DEMO" else ""
        contracte_html += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #f0f2f5;font-size:13px">
            {c['titlu'][:55]}{'…' if len(c['titlu'])>55 else ''}{nota_demo}
          </td>
          <td style="padding:8px 12px;border-bottom:1px solid #f0f2f5;font-size:13px;font-weight:700">{_fmt_ron(c['valoare_ron'])}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f0f2f5;font-size:12px">{badge_tip} {c['tip_procedura']}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f0f2f5;font-size:12px;text-align:center">{badge_ofertanti}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f0f2f5;font-size:12px">{c['castigator'][:30]}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f0f2f5;font-size:12px">{c['data_publicare']}</td>
        </tr>"""

    budget_html = ""
    if budget.get("venituri_mil_ron"):
        yoy_v = budget.get("yoy_venituri", "N/A")
        yoy_c = budget.get("yoy_cheltuieli", "N/A")
        yoy_v_color = "#C0392B" if "-" in str(yoy_v) else "#27AE60"
        yoy_c_color = "#C0392B" if "+" in str(yoy_c) else "#27AE60"
        budget_html = f"""
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:24px">
          <div style="background:#fff;border-radius:10px;padding:20px;border-top:4px solid #0070C0;box-shadow:0 1px 4px rgba(0,0,0,0.08)">
            <span style="font-size:24px;font-weight:800;color:#0070C0">{budget['venituri_mil_ron']} mil. RON</span><br>
            <span style="font-size:11px;color:#777;text-transform:uppercase">Venituri {budget['an']}</span><br>
            <span style="font-size:12px;color:{yoy_v_color}">{yoy_v} față de {budget['an']-1}</span>
          </div>
          <div style="background:#fff;border-radius:10px;padding:20px;border-top:4px solid #E67E22;box-shadow:0 1px 4px rgba(0,0,0,0.08)">
            <span style="font-size:24px;font-weight:800;color:#E67E22">{budget['cheltuieli_mil_ron']} mil. RON</span><br>
            <span style="font-size:11px;color:#777;text-transform:uppercase">Cheltuieli {budget['an']}</span><br>
            <span style="font-size:12px;color:{yoy_c_color}">{yoy_c} față de {budget['an']-1}</span>
          </div>
          <div style="background:#fff;border-radius:10px;padding:20px;border-top:4px solid {'#27AE60' if (budget.get('balanta_mil_ron') or 0)>0 else '#C0392B'};box-shadow:0 1px 4px rgba(0,0,0,0.08)">
            <span style="font-size:24px;font-weight:800;color:{'#27AE60' if (budget.get('balanta_mil_ron') or 0)>0 else '#C0392B'}">{budget.get('balanta_mil_ron','N/A')} mil. RON</span><br>
            <span style="font-size:11px;color:#777;text-transform:uppercase">Balanță {budget['an']}</span><br>
            <span style="font-size:12px;color:#777">Sursa: {budget['sursa']}</span>
          </div>
        </div>"""

    nota_demo_msg = ""
    if any(c.get("sursa") == "DEMO" for c in contracte):
        nota_demo_msg = """
        <div style="background:#FFF3CD;border-left:4px solid #F39C12;padding:12px 16px;
                    border-radius:6px;font-size:13px;color:#7D6608;margin-bottom:16px">
          <strong>⚠️ Date demonstrative:</strong> API-ul SEAP nu a putut fi accesat în această rulare.
          Contractele afișate sunt demonstrative. Verificați manual la
          <a href="https://www.e-licitatie.ro/pub" target="_blank">e-licitatie.ro</a>.
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="ro">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Raport Transparență – {config['nume_entitate']} – {data_generare}</title>
<style>
  body{{font-family:'Segoe UI',Arial,sans-serif;background:#F4F6F9;color:#1A1A2E;margin:0;padding:0}}
  .wrap{{max-width:960px;margin:0 auto;padding:24px 16px 60px}}
  h1,h2,h3{{margin:0 0 8px}}
  table{{width:100%;border-collapse:collapse;background:#fff;border-radius:10px;
         overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,0.08)}}
  thead{{background:#00427A;color:#fff}}
  th{{padding:10px 12px;font-size:12px;text-align:left;text-transform:uppercase;letter-spacing:.5px}}
</style>
</head>
<body>
<div style="background:linear-gradient(135deg,#00427A,#0070C0);color:#fff;padding:24px 32px">
  <div style="max-width:960px;margin:0 auto">
    <div style="font-size:11px;opacity:.7;margin-bottom:8px">
      Monitorizare cetățenească · {config['judet']}
    </div>
    <h1 style="font-size:26px;font-weight:800;margin:0 0 6px">
      Raport Transparență Bugetară<br>
      <span style="color:#FFD000">{config['nume_entitate']}</span>
    </h1>
    <p style="opacity:.85;margin:0">Generat automat la {data_generare} · CUI: {config['cui']}</p>
    <div style="display:flex;gap:24px;margin-top:16px;flex-wrap:wrap">
      <div style="background:rgba(255,255,255,.15);border-radius:8px;padding:10px 16px;text-align:center">
        <div style="font-size:22px;font-weight:800;color:#{"C0392B" if flags else "27AE60"}">{len(flags)}</div>
        <div style="font-size:11px;opacity:.8">Red Flags Total</div>
      </div>
      <div style="background:rgba(255,255,255,.15);border-radius:8px;padding:10px 16px;text-align:center">
        <div style="font-size:22px;font-weight:800;color:{"#FFD000" if flags_noi else "#27AE60"}">{len(flags_noi)}</div>
        <div style="font-size:11px;opacity:.8">Flags Noi (față de ultima rulare)</div>
      </div>
      <div style="background:rgba(255,255,255,.15);border-radius:8px;padding:10px 16px;text-align:center">
        <div style="font-size:22px;font-weight:800">{len(contracte)}</div>
        <div style="font-size:11px;opacity:.8">Contracte analizate</div>
      </div>
      <div style="background:rgba(255,255,255,.15);border-radius:8px;padding:10px 16px;text-align:center">
        <div style="font-size:22px;font-weight:800">{_fmt_ron(total_val)}</div>
        <div style="font-size:11px;opacity:.8">Valoare totală contracte</div>
      </div>
    </div>
  </div>
</div>

<div class="wrap">

  <!-- BUGET -->
  <h2 style="color:#00427A;margin:28px 0 16px">📊 Date Bugetare (ANAF/MF)</h2>
  {budget_html if budget_html else '<p style="color:#777;font-size:13px">Date buget indisponibile.</p>'}

  <!-- RED FLAGS -->
  <h2 style="color:#00427A;margin:28px 0 8px">🚩 Red Flags Detectate ({len(flags)})</h2>
  <p style="font-size:13px;color:#777;margin:0 0 16px">
    {sum(1 for f in flags if f['severitate']=='CRITIC')} CRITIC &nbsp;·&nbsp;
    {sum(1 for f in flags if f['severitate']=='MAJOR')} MAJOR &nbsp;·&nbsp;
    {sum(1 for f in flags if f['severitate']=='MEDIU')} MEDIU
    {f" &nbsp;·&nbsp; <strong style='color:#2E7D32'>{len(flags_noi)} NOI față de ultima rulare</strong>" if flags_noi else ""}
  </p>
  {nota_demo_msg}
  {flags_html if flags_html else '<p style="color:#27AE60;font-size:14px">✅ Niciun red flag detectat în această perioadă.</p>'}

  <!-- STATISTICI ACHIZITII -->
  <h2 style="color:#00427A;margin:28px 0 16px">📋 Statistici Achiziții</h2>
  <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px">
    <div style="background:#fff;border-radius:8px;padding:16px;border-top:3px solid #0070C0;box-shadow:0 1px 3px rgba(0,0,0,.08)">
      <div style="font-size:22px;font-weight:800;color:#0070C0">{len(contracte)}</div>
      <div style="font-size:11px;color:#777;text-transform:uppercase">Contracte totale</div>
    </div>
    <div style="background:#fff;border-radius:8px;padding:16px;border-top:3px solid #C0392B;box-shadow:0 1px 3px rgba(0,0,0,.08)">
      <div style="font-size:22px;font-weight:800;color:#C0392B">{len(directe)}</div>
      <div style="font-size:11px;color:#777;text-transform:uppercase">Cumpărare directă</div>
    </div>
    <div style="background:#fff;border-radius:8px;padding:16px;border-top:3px solid #E67E22;box-shadow:0 1px 3px rgba(0,0,0,.08)">
      <div style="font-size:22px;font-weight:800;color:#E67E22">{len(unic_ofertant)}</div>
      <div style="font-size:11px;color:#777;text-transform:uppercase">Un singur ofertant</div>
    </div>
    <div style="background:#fff;border-radius:8px;padding:16px;border-top:3px solid #27AE60;box-shadow:0 1px 3px rgba(0,0,0,.08)">
      <div style="font-size:22px;font-weight:800;color:#27AE60">{_fmt_ron(total_val)}</div>
      <div style="font-size:11px;color:#777;text-transform:uppercase">Valoare totală</div>
    </div>
  </div>

  <!-- TABEL CONTRACTE -->
  <h3 style="color:#00427A;margin:0 0 12px">Lista contracte analizate (primele 20)</h3>
  <table>
    <thead>
      <tr>
        <th>Titlu contract</th><th>Valoare</th><th>Tip procedură</th>
        <th style="text-align:center">Ofertanți</th><th>Câștigător</th><th>Data</th>
      </tr>
    </thead>
    <tbody>{contracte_html}</tbody>
  </table>

  <!-- FOOTER -->
  <div style="margin-top:32px;padding:16px;background:#fff;border-radius:8px;
              font-size:12px;color:#777;box-shadow:0 1px 3px rgba(0,0,0,.08)">
    <strong style="color:#00427A">Surse date:</strong>
    <a href="https://transparenta.eu/entities/{config['cui']}" target="_blank">transparenta.eu</a> (ANAF/MF) &nbsp;·&nbsp;
    <a href="https://www.e-licitatie.ro/pub" target="_blank">e-licitatie.ro (SEAP)</a> &nbsp;·&nbsp;
    <a href="https://www.primariapantelimon.ro" target="_blank">primariapantelimon.ro</a>
    <br><br>
    Raport generat automat de <strong>monitor_pantelimon.py</strong> &nbsp;·&nbsp;
    Inițiativă cetățenească independentă &nbsp;·&nbsp;
    Datele sunt extrase exclusiv din surse publice oficiale.
  </div>

</div>
</body>
</html>"""

    return html


# ==============================================================================
# 6. ALERTĂ EMAIL
# ==============================================================================

def trimite_email_alerta(flags_noi: list, raport_html: str, config: dict):
    """Trimite email cu alertă dacă există flags noi."""
    if not config["email_from"] or not config["email_to"]:
        print("  [Email] Configurație email lipsă – se sare trimiterea.")
        return

    if not flags_noi:
        print("  [Email] Niciun flag nou – nu se trimite email.")
        return

    print(f"  [Email] Trimit alertă la {config['email_to']}...")

    critice = [f for f in flags_noi if f["severitate"] == "CRITIC"]
    majore = [f for f in flags_noi if f["severitate"] == "MAJOR"]

    subiect = (f"🚩 {len(flags_noi)} red flag(s) noi – Primăria Pantelimon "
               f"[{len(critice)} CRITIC, {len(majore)} MAJOR]")

    body_text = f"""ALERTĂ TRANSPARENȚĂ BUGETARĂ — Primăria Pantelimon
Detectate {len(flags_noi)} red flag(uri) noi față de ultima verificare.

"""
    for f in flags_noi:
        body_text += f"[{f['severitate']}] {f['titlu']}\n{f['descriere']}\n\n"

    body_text += f"\nRaportul complet este atașat.\nGenerat la {datetime.now().strftime('%d.%m.%Y %H:%M')}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subiect
    msg["From"] = config["email_from"]
    msg["To"] = config["email_to"]
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    msg.attach(MIMEText(raport_html, "html", "utf-8"))

    try:
        with smtplib.SMTP(config["email_smtp"], config["email_port"]) as server:
            server.starttls()
            server.login(config["email_from"], config["email_parola"])
            server.sendmail(config["email_from"], config["email_to"], msg.as_string())
        print(f"  [Email] ✓ Email trimis cu succes la {config['email_to']}")
    except Exception as e:
        print(f"  [Email] ✗ Eroare la trimitere: {e}")


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    trimite_email = "--email" in sys.argv
    print("\n" + "="*60)
    print(f"  MONITOR TRANSPARENȚĂ BUGETARĂ — {CONFIG['nume_entitate']}")
    print(f"  {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print("="*60)

    # 1. Buget
    print("\n[1/5] Fetchuiesc date bugetare...")
    budget = fetch_budget_transparenta(CONFIG["cui"])

    # 2. Contracte SEAP
    print("\n[2/5] Fetchuiesc contracte din SEAP...")
    contracte = fetch_contracts_seap(CONFIG["cui"], CONFIG["luni_analiza"])

    # 3. Analiză red flags
    print("\n[3/5] Analizez red flags...")
    flags = analizeaza_red_flags(contracte, CONFIG)

    # 4. Detecție flags noi
    print("\n[4/5] Compar cu starea anterioară...")
    stare_ant = incarca_stare_anterioara(CONFIG["fisier_stare"])
    flags_noi = detecteaza_flags_noi(flags, stare_ant)
    if flags_noi:
        print(f"    ⚠ {len(flags_noi)} RED FLAG(URI) NOI față de ultima rulare!")
    else:
        print("    ✓ Niciun flag nou față de ultima rulare.")

    # 5. Generare raport
    print("\n[5/5] Generez raport HTML...")
    raport = genereaza_raport_html(budget, contracte, flags, flags_noi, CONFIG)

    with open(CONFIG["fisier_raport"], "w", encoding="utf-8") as f:
        f.write(raport)
    print(f"    ✓ Raport salvat: {CONFIG['fisier_raport']}")

    # Salvare stare
    salveaza_stare(CONFIG["fisier_stare"], flags, contracte)

    # Email (dacă e configurat și solicitat)
    if trimite_email or (flags_noi and CONFIG["email_from"]):
        print("\n[+] Trimit alertă email...")
        trimite_email_alerta(flags_noi, raport, CONFIG)

    # Sumar final
    print("\n" + "="*60)
    print(f"  SUMAR RULARE:")
    print(f"  • Contracte analizate: {len(contracte)}")
    print(f"  • Red flags total: {len(flags)}")
    print(f"  • Red flags NOI: {len(flags_noi)}")
    print(f"  • Raport: {CONFIG['fisier_raport']}")
    print("="*60 + "\n")

    return len(flags_noi)  # returnăm nr. de flags noi (util pentru scheduler)


if __name__ == "__main__":
    main()
                                                                                                            