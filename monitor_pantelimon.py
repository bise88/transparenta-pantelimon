"""
Monitor Transparență Bugetară — Primăria Pantelimon
====================================================
Script de monitorizare automată: trage date din data.gov.ro (export SEAP oficial)
și transparenta.eu, detectează red flags și generează raport HTML.

Utilizare:
    python monitor_pantelimon.py          # rulează analiza și generează raportul
    python monitor_pantelimon.py --email  # rulează și trimite email dacă sunt flags noi

Dependențe: pip install requests beautifulsoup4 openpyxl
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
    "email_to": "",            # ex: "contact@transparenta-pantelimon.eu"
    "email_smtp": "smtp.gmail.com",
    "email_port": 587,
    "email_parola": "",        # recomandăm App Password Google, nu parola reală
}

# ==============================================================================
# SURSE DE DATE
# ==============================================================================

DATAGOV_BASE = "https://data.gov.ro/api/3/action"
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
# 2. DATE CONTRACTE DIN DATA.GOV.RO (export oficial SEAP trimestrial)
# ==============================================================================

def fetch_contracts_seap(cui: str, luni: int = 12) -> list:
    """
    Descarcă contractele Primăriei Pantelimon din data.gov.ro — exportul oficial
    trimestrial al SEAP publicat de ANAP. Mult mai fiabil decât API-ul direct SEAP.
    Returnează lista standardizată de contracte (licitații + achiziții directe).
    """
    import io
    try:
        import openpyxl
    except ImportError:
        print("    ✗ openpyxl lipsă. Rulează: pip install openpyxl")
        return []

    print(f"  [data.gov.ro] Caut contracte pentru CUI {cui}...")

    an_curent = datetime.now().year
    ani_de_verificat = sorted({an_curent - 1, an_curent})  # ultimii 2 ani
    contracte = []
    surse_ok = 0

    for an in ani_de_verificat:
        package_id = f"achizitii-publice-{an}"
        try:
            r = requests.get(
                f"{DATAGOV_BASE}/package_show?id={package_id}",
                timeout=20, headers=HEADERS
            )
            if r.status_code != 200:
                print(f"    ⚠ Pachet {an} indisponibil (HTTP {r.status_code})")
                continue
            resources = r.json()["result"]["resources"]
        except Exception as e:
            print(f"    ⚠ Nu am putut accesa pachetul {an}: {e}")
            continue

        # Selectăm fișierele relevante: Contracte și Achiziții directe (nu notificări)
        fisiere_relevante = []
        for res in resources:
            name = res.get("name", "").lower()
            url = res.get("url", "")
            if not (url.endswith(".xlsx") or url.endswith(".xls")):
                continue
            este_contracte = "contracte" in name and "modificare" not in name
            este_directe = "direct" in name and "notific" not in name and "atribuire" not in name
            if este_contracte or este_directe:
                tip = "contract" if este_contracte else "achizitie-directa"
                fisiere_relevante.append((tip, url, res.get("name", "")))

        print(f"    → {an}: {len(fisiere_relevante)} fișiere relevante găsite")

        for tip_sursa, url, res_name in fisiere_relevante:
            try:
                # Verificăm dimensiunea fișierului înainte de descărcare
                MAX_FILE_MB = 6
                try:
                    head = requests.head(url, timeout=10, headers=HEADERS, allow_redirects=True)
                    content_len = int(head.headers.get("Content-Length", 0))
                    if content_len > MAX_FILE_MB * 1024 * 1024:
                        print(f"    ⏭ {res_name}: {content_len//1024//1024}MB > {MAX_FILE_MB}MB, sărim")
                        continue
                except Exception:
                    pass  # HEAD eșuat — încercăm oricum

                # Descărcare cu streaming + limită de timp și dimensiune
                resp = requests.get(url, timeout=30, headers=HEADERS, stream=True)
                if resp.status_code != 200:
                    continue

                chunks = []
                downloaded = 0
                LIMIT = MAX_FILE_MB * 1024 * 1024
                for chunk in resp.iter_content(chunk_size=65536):
                    downloaded += len(chunk)
                    if downloaded > LIMIT:
                        print(f"    ⏭ {res_name}: depășit {MAX_FILE_MB}MB în descărcare, sărim")
                        chunks = []
                        break
                    chunks.append(chunk)
                resp.close()

                if not chunks:
                    continue

                file_bytes = b"".join(chunks)
                wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True)
                ws = wb.active
                rows_iter = ws.iter_rows(values_only=True)
                headers_row = next(rows_iter, None)
                if not headers_row:
                    wb.close()
                    continue

                hdrs = [str(h).strip() if h else "" for h in headers_row]

                def col_idx(*names):
                    for name in names:
                        for i, h in enumerate(hdrs):
                            if name.lower() in h.lower():
                                return i
                    return None

                idx_cui_ac   = col_idx("CUI autoritate")
                idx_proc     = col_idx("Tip procedura")
                idx_valoare  = col_idx("Valoare contract", "Valoare achizitie", "Valoare")
                idx_castig   = col_idx("Ofertant castigator", "Furnizor", "Castigator")
                idx_cui_casg = col_idx("CUI ofertant", "CUI furnizor")
                idx_data     = col_idx("Data contract", "Data achizitie", "Data publicare")
                idx_cpv      = col_idx("Denumire CPV", "Denumire produs", "Obiect")
                idx_numar    = col_idx("Numar contract", "Numar achizitie", "ID")

                if idx_cui_ac is None:
                    wb.close()
                    continue

                rand_idx = 0
                for row in rows_iter:
                    rand_idx += 1
                    if not row or not row[idx_cui_ac]:
                        continue
                    if str(row[idx_cui_ac]).strip() != str(cui):
                        continue

                    # Valoare
                    valoare = 0.0
                    if idx_valoare is not None and row[idx_valoare]:
                        try:
                            valoare = float(str(row[idx_valoare]).replace(",", ".").replace(" ", ""))
                        except (ValueError, TypeError):
                            pass

                    # Dată
                    data_str = ""
                    if idx_data is not None and row[idx_data]:
                        d = row[idx_data]
                        try:
                            data_str = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10]
                        except Exception:
                            data_str = str(d)[:10]

                    tip_proc = str(row[idx_proc]).strip() if idx_proc is not None and row[idx_proc] else ""

                    # nr_ofertanti: deducem din tip procedură (nu e în export)
                    nr_ofertanti = 1
                    if any(kw in tip_proc.lower() for kw in ["deschis", "restrâns", "competitiv"]):
                        nr_ofertanti = 2  # cel puțin 2 în proceduri competitive

                    cid = f"{tip_sursa}-{an}-{rand_idx}"
                    contracte.append({
                        "id": cid,
                        "numar": str(row[idx_numar]).strip() if idx_numar is not None and row[idx_numar] else cid,
                        "titlu": str(row[idx_cpv]).strip() if idx_cpv is not None and row[idx_cpv] else "Nespecificat",
                        "valoare_ron": valoare,
                        "moneda": "RON",
                        "tip_procedura": tip_proc,
                        "data_publicare": data_str,
                        "castigator": str(row[idx_castig]).strip() if idx_castig is not None and row[idx_castig] else "Necunoscut",
                        "castigator_cui": str(row[idx_cui_casg]).strip() if idx_cui_casg is not None and row[idx_cui_casg] else "",
                        "nr_ofertanti": nr_ofertanti,
                        "sursa": f"data.gov.ro/{tip_sursa}/{an}",
                    })

                wb.close()
                surse_ok += 1

            except Exception as e:
                print(f"    ⚠ Eroare la {res_name}: {e}")

    print(f"    ✓ Procesate {surse_ok} fișiere. Găsite {len(contracte)} contracte Pantelimon.")

    if not contracte:
        print("    ✗ Nu s-au găsit contracte reale în data.gov.ro.")

    return contracte


# ==============================================================================
# 3. HOTĂRÂRI CONSILIU LOCAL — ANALIZĂ OCR
# ==============================================================================

HCL_URL_2025 = "https://www.primariapantelimon.ro/hotarari-2025/"
HCL_URL_2024 = "https://www.primariapantelimon.ro/hotarari-2024/"

# Cuvinte cheie care indică proceduri de urgență sau potențiale nereguli
HCL_RED_FLAG_KEYWORDS = {
    "urgenta_procedura": [
        "negociere fără publicare", "negociere fara publicare",
        "procedură de urgență", "procedura de urgenta",
        "atribuire directă", "atribuire directa",
        "fără licitație", "fara licitatie",
    ],
    "rectificare_bugetara": [
        "rectificare bugetară", "rectificare bugetara",
        "rectificare a bugetului", "modificare buget",
    ],
    "sedinta_extraordinara": [
        "convocare de îndată", "convocare de indata",
        "ședință extraordinară", "sedinta extraordinara",
    ],
}


def fetch_hcl_metadata(url: str) -> list:
    """Extrage lista de HCL-uri (PDF-uri) de pe pagina primăriei."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
    except Exception as e:
        print(f"    ⚠ Nu am putut accesa {url}: {e}")
        return []

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(r.text, "html.parser")
    results = []
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)
        href = a["href"]
        if not any(kw in (text + href).lower() for kw in ["hcl", "hotarare", "hotărâre", ".pdf"]):
            continue
        if not href.lower().endswith(".pdf"):
            continue
        if not href.startswith("http"):
            href = "https://www.primariapantelimon.ro" + href
        tip = "extraordinara" if "extraordinar" in text.lower() or "extraordinar" in href.lower() else "ordinara"
        results.append({
            "titlu": text[:120],
            "url": href,
            "tip": tip,
            "filename": href.split("/")[-1],
        })
    return results


def ocr_pdf_prima_pagina(url: str, max_pages: int = 3) -> str:
    """
    Descarcă PDF-ul și aplică OCR pe primele max_pages pagini.
    Returnează textul extras (poate fi gol dacă OCR eșuează).
    Necesită: tesseract-ocr, tesseract-ocr-ron, poppler-utils instalate pe sistem.
    """
    try:
        import pytesseract
        from pdf2image import convert_from_bytes
    except ImportError:
        return ""

    try:
        r = requests.get(url, headers=HEADERS, timeout=40)
        if r.status_code != 200:
            return ""
        images = convert_from_bytes(r.content, first_page=1, last_page=max_pages, dpi=200)
        text_total = ""
        for img in images:
            text_total += pytesseract.image_to_string(img, lang="ron+eng") + "\n"
        return text_total.lower()
    except Exception as e:
        print(f"      ⚠ OCR eșuat: {e}")
        return ""


def analizeaza_hcl(stare_anterioara: dict) -> dict:
    """
    Analizează hotărârile Consiliului Local:
    1. Metadata (fără OCR): rata ședințelor extraordinare
    2. OCR (doar HCL-uri noi față de rularea anterioară): caută cuvinte cheie red flag

    Returnează dict cu statistici și lista de red flags HCL.
    """
    print("  [HCL] Analizez hotărârile Consiliului Local...")

    ocr_disponibil = False
    try:
        import pytesseract
        from pdf2image import convert_from_bytes
        ocr_disponibil = True
        print("    ✓ OCR disponibil (tesseract)")
    except ImportError:
        print("    ⚠ OCR indisponibil — analiză doar din metadata/nume fișiere")

    hcl_list = []
    for url in [HCL_URL_2025, HCL_URL_2024]:
        found = fetch_hcl_metadata(url)
        hcl_list.extend(found)
        print(f"    → {url.split('/')[-2]}: {len(found)} HCL-uri găsite")

    if not hcl_list:
        print("    ✗ Nu s-au putut obține HCL-urile.")
        return {"flags": [], "statistici": {}, "hcl_list": []}

    total = len(hcl_list)
    extraordinare = [h for h in hcl_list if h["tip"] == "extraordinara"]
    ordinare = [h for h in hcl_list if h["tip"] == "ordinara"]
    pct_extra = round(len(extraordinare) / total * 100) if total else 0

    print(f"    → Total: {total} HCL | Ordinare: {len(ordinare)} | Extraordinare: {len(extraordinare)} ({pct_extra}%)")

    flags_hcl = []

    # FLAG 1: Rată ridicată de ședințe extraordinare
    if pct_extra > 25:
        flags_hcl.append({
            "tip": "sedinte_extraordinare_excesive",
            "severitate": "MAJOR" if pct_extra < 40 else "CRITIC",
            "titlu": f"Rată ridicată de ședințe extraordinare: {pct_extra}%",
            "descriere": (
                f"Din {total} ședințe de Consiliu Local analizate, {len(extraordinare)} ({pct_extra}%) "
                f"sunt 'extraordinare cu convocare de îndată'. Norma legală implică urgențe reale — "
                f"o rată peste 25% sugerează că procedura de urgență este folosită sistematic "
                f"pentru a ocoli consultarea publică obligatorie (Legea 52/2003)."
            ),
            "contract_id": "HCL-META-001",
            "valoare": 0,
            "furnizor": "Consiliul Local Pantelimon",
            "data": datetime.now().strftime("%Y-%m-%d"),
            "tip_procedura": "Sedinta CL extraordinara",
        })

    # FLAG 2: OCR pe HCL-urile noi
    if ocr_disponibil:
        hcl_vazute = set(stare_anterioara.get("hcl_urls_vazute", []))
        hcl_noi = [h for h in hcl_list if h["url"] not in hcl_vazute]
        print(f"    → OCR: {len(hcl_noi)} HCL-uri noi de procesat")

        for hcl in hcl_noi[:10]:  # max 10 per rulare pentru a nu depăși timeout
            print(f"      OCR: {hcl['titlu'][:60]}...")
            text = ocr_pdf_prima_pagina(hcl["url"], max_pages=2)
            if not text:
                continue

            for tip_flag, keywords in HCL_RED_FLAG_KEYWORDS.items():
                for kw in keywords:
                    if kw in text:
                        flags_hcl.append({
                            "tip": f"hcl_{tip_flag}",
                            "severitate": "MAJOR",
                            "titlu": f"HCL: {tip_flag.replace('_', ' ').title()} detectat",
                            "descriere": (
                                f"Cuvânt cheie '{kw}' detectat în: {hcl['titlu']}. "
                                f"Verificați documentul pentru detalii."
                            ),
                            "contract_id": hcl["filename"],
                            "valoare": 0,
                            "furnizor": "Consiliul Local Pantelimon",
                            "data": datetime.now().strftime("%Y-%m-%d"),
                            "tip_procedura": hcl["tip"],
                        })
                        break

    statistici = {
        "total_hcl": total,
        "ordinare": len(ordinare),
        "extraordinare": len(extraordinare),
        "pct_extraordinare": pct_extra,
        "ocr_disponibil": ocr_disponibil,
    }

    print(f"    ✓ Analiză HCL finalizată. Red flags HCL: {len(flags_hcl)}")
    return {"flags": flags_hcl, "statistici": statistici, "hcl_list": hcl_list}


# ==============================================================================
# 4. ALGORITMI DE DETECȚIE RED FLAGS (contracte SEAP)
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


def salveaza_stare(fisier: str, flags: list, contracte: list, hcl_list: list = None):
    """Salvează starea curentă pentru comparație viitoare."""
    stare = {
        "flags_anterioare": [f["contract_id"] + "_" + f["tip"] for f in flags],
        "contracte_vazute": [c["id"] for c in contracte],
        "hcl_urls_vazute": [h["url"] for h in (hcl_list or [])],
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
            <span>📋 {f.get('contract_id', f.get('contract_numar', '–')) or '–'}</span>
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
    {sum(1 for f in flags if f['severitate']=='CRITIC')} CRITIC · {sum(1 for f in flags if f['severitate']=='MAJOR')} MAJOR · {sum(1 for f in flags if f['severitate']=='MEDIU')} MEDIU</p>
  {nota_demo_msg}
  {flags_html if flags_html else '<div style="background:#E8F5E9;border-left:4px solid #27AE60;padding:14px 18px;border-radius:0 8px 8px 0"><span style="color:#27AE60;font-weight:700">✅ Niciun red flag detectat în această perioadă.</span></div>'}

  <!-- HCL STATISTICI -->
  <h2 style="color:#00427A;margin:28px 0 8px">📋 Hotărâri Consiliu Local</h2>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:20px">
    <div style="background:#fff;border-radius:10px;padding:16px;border-top:4px solid #0070C0;box-shadow:0 1px 4px rgba(0,0,0,.08)">
      <div style="font-size:28px;font-weight:800;color:#0070C0">{config.get('_hcl_total',0)}</div>
      <div style="font-size:11px;color:#777;text-transform:uppercase">HCL Total analizate</div>
    </div>
    <div style="background:#fff;border-radius:10px;padding:16px;border-top:4px solid #27AE60;box-shadow:0 1px 4px rgba(0,0,0,.08)">
      <div style="font-size:28px;font-weight:800;color:#27AE60">{config.get('_hcl_ordinare',0)}</div>
      <div style="font-size:11px;color:#777;text-transform:uppercase">Ședințe ordinare</div>
    </div>
    <div style="background:#fff;border-radius:10px;padding:16px;border-top:4px solid {'#C0392B' if config.get('_hcl_pct',0)>25 else '#E67E22'};box-shadow:0 1px 4px rgba(0,0,0,.08)">
      <div style="font-size:28px;font-weight:800;color:{'#C0392B' if config.get('_hcl_pct',0)>25 else '#E67E22'}">{config.get('_hcl_extraordinare',0)}</div>
      <div style="font-size:11px;color:#777;text-transform:uppercase">Extraordinare cu convocare de îndată ({config.get('_hcl_pct',0)}%)</div>
    </div>
    <div style="background:#fff;border-radius:10px;padding:16px;border-top:4px solid #8E44AD;box-shadow:0 1px 4px rgba(0,0,0,.08)">
      <div style="font-size:12px;font-weight:700;color:#8E44AD">{'✅ OCR activ' if config.get('_hcl_ocr') else '⚠️ Doar metadata'}</div>
      <div style="font-size:11px;color:#777;text-transform:uppercase;margin-top:4px">Mod analiză HCL</div>
    </div>
  </div>

  <!-- STATISTICI ACHIZITII -->
  <h2 style="color:#00427A;margin:28px 0 8px">📊 Statistici Achiziții</h2>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-bottom:20px">
    <div style="background:#fff;border-radius:10px;padding:16px;border-top:4px solid #0070C0;box-shadow:0 1px 4px rgba(0,0,0,.08)">
      <div style="font-size:28px;font-weight:800;color:#0070C0">{len(contracte)}</div>
      <div style="font-size:11px;color:#777;text-transform:uppercase">Contracte totale</div>
    </div>
    <div style="background:#fff;border-radius:10px;padding:16px;border-top:4px solid #C0392B;box-shadow:0 1px 4px rgba(0,0,0,.08)">
      <div style="font-size:28px;font-weight:800;color:#C0392B">{len(directe)}</div>
      <div style="font-size:11px;color:#777;text-transform:uppercase">Cumpărare directă / negociere</div>
    </div>
    <div style="background:#fff;border-radius:10px;padding:16px;border-top:4px solid #E67E22;box-shadow:0 1px 4px rgba(0,0,0,.08)">
      <div style="font-size:28px;font-weight:800;color:#E67E22">{len(unic_ofertant)}</div>
      <div style="font-size:11px;color:#777;text-transform:uppercase">Un singur ofertant</div>
    </div>
    <div style="background:#fff;border-radius:10px;padding:16px;border-top:4px solid #27AE60;box-shadow:0 1px 4px rgba(0,0,0,.08)">
      <div style="font-size:28px;font-weight:800;color:#27AE60">{_fmt_ron(total_val)}</div>
      <div style="font-size:11px;color:#777;text-transform:uppercase">Valoare totală</div>
    </div>
  </div>

  <!-- LISTA CONTRACTE -->
  <h2 style="color:#00427A;margin:28px 0 8px">📄 Lista contracte analizate (primele 20)</h2>
  <div style="overflow-x:auto">
  <table>
    <thead><tr>
      <th>Titlu contract</th><th>Valoare</th><th>Tip procedură</th>
      <th>Ofertanți</th><th>Câștigător</th><th>Data</th>
    </tr></thead>
    <tbody>{contracte_html if contracte_html else '<tr><td colspan="6" style="text-align:center;padding:20px;color:#777">Nu există contracte de afișat</td></tr>'}</tbody>
  </table>
  </div>

</div>

<footer style="background:#00427A;color:rgba(255,255,255,.7);text-align:center;padding:16px;font-size:12px;margin-top:40px">
  <p>Surse date: <a href="https://transparenta.eu/entities/{config['cui']}" target="_blank" style="color:#FFD000">transparenta.eu</a> (ANAF/MF) &nbsp;·&nbsp;
     <a href="https://www.e-licitatie.ro/pub" target="_blank" style="color:#FFD000">e-licitatie.ro (SEAP)</a> &nbsp;·&nbsp;
     <a href="https://www.primariapantelimon.ro" target="_blank" style="color:#FFD000">primariapantelimon.ro</a></p>
  <p style="margin-top:6px;font-size:11px;opacity:.7">
    Raport generat automat de <strong>monitor_pantelimon.py</strong> &nbsp;·&nbsp;
    Inițiativă cetățenească independentă &nbsp;·&nbsp;
    Datele sunt extrase exclusiv din surse publice oficiale.
  </p>
</footer>
</body>
</html>"""
    return html


# ==============================================================================
# 6. TRIMITERE EMAIL ALERTĂ
# ==============================================================================

def trimite_email_alerta(flags_noi: list, raport_html: str, config: dict):
    """Trimite email de alertă dacă există red flags noi."""
    if not config.get("email_from") or not config.get("email_to"):
        print("  [Email] Emailul nu e configurat — se sare.")
        return

    subiect = f"🚩 {len(flags_noi)} red flag(uri) noi — Transparență Pantelimon {datetime.now().strftime('%d.%m.%Y')}"

    flags_text = "\n".join([
        f"[{f['severitate']}] {f['titlu']}\n  → {f['descriere'][:200]}"
        for f in flags_noi[:5]
    ])

    body_text = f"""
Monitor Transparență Bugetară — Pantelimon
==========================================

{len(flags_noi)} red flag(uri) noi detectate față de ultima rulare:

{flags_text}

Raport complet: https://bise88.github.io/transparenta-pantelimon/raport_transparenta.html

---
Inițiativă cetățenească independentă · Date din surse publice oficiale.
"""
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
        print(f"  [Email] ✓ Trimis la {config['email_to']}")
    except Exception as e:
        print(f"  [Email] ✗ Eroare: {e}")


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
    print("\n[1/6] Fetchuiesc date bugetare...")
    budget = fetch_budget_transparenta(CONFIG["cui"])

    # 2. Contracte din data.gov.ro
    print("\n[2/6] Fetchuiesc contracte din data.gov.ro...")
    contracte = fetch_contracts_seap(CONFIG["cui"], CONFIG["luni_analiza"])

    # 3. Hotărâri Consiliu Local
    print("\n[3/6] Analizez hotărârile Consiliului Local...")
    stare_ant = incarca_stare_anterioara(CONFIG["fisier_stare"])
    rezultat_hcl = analizeaza_hcl(stare_ant)
    flags_hcl = rezultat_hcl["flags"]
    statistici_hcl = rezultat_hcl["statistici"]

    # Pasăm statisticile HCL în CONFIG pentru template
    CONFIG["_hcl_total"] = statistici_hcl.get("total_hcl", 0)
    CONFIG["_hcl_ordinare"] = statistici_hcl.get("ordinare", 0)
    CONFIG["_hcl_extraordinare"] = statistici_hcl.get("extraordinare", 0)
    CONFIG["_hcl_pct"] = statistici_hcl.get("pct_extraordinare", 0)
    CONFIG["_hcl_ocr"] = statistici_hcl.get("ocr_rezumat", "")

    # 4. Red flags
    print("\n[4/6] Analizez red flags...")
    flags_contracte = analizeaza_red_flags(contracte, CONFIG)
    toate_flags = flags_contracte + flags_hcl

    # 5. Raport HTML
    print("\n[5/6] Generez raport HTML...")
    raport_html = genereaza_raport_html(budget, contracte, toate_flags, stare_ant)
    with open(CONFIG["fisier_raport"], "w", encoding="utf-8") as f:
        f.write(raport_html)
    print(f"  ✓ Raport salvat: {CONFIG['fisier_raport']}")

    # 6. Salvare stare
    print("\n[6/6] Salvez starea...")
    hcl_urls_noi = rezultat_hcl.get("hcl_urls", [])
    salveaza_stare(contracte, toate_flags, stare_ant, hcl_urls_noi)
    print(f"  ✓ Stare salvata: {CONFIG['fisier_stare']}")

    if trimite_email and toate_flags:
        flags_noi = [f for f in toate_flags
                     if f.get("titlu") not in
                     [x.get("titlu") for x in stare_ant.get("flags_anterioare", [])]]
        if flags_noi:
            trimite_email_alerta(toate_flags, budget, CONFIG)

    print(f"\n{'='*60}")
    print(f"  FINALIZAT -- {len(toate_flags)} flags, {len(contracte)} contracte analizate")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
