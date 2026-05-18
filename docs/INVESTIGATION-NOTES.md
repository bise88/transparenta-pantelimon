# Faza 0 — Raport de investigare cod și structură date

> Generat: Mai 2025 | Autor: Claude Code (sesiune autonomă Bloc 1)
> Scop: răspunde la toate întrebările din IMPROVEMENTS.md §Faza 0 înainte de orice modificare.

---

## 1. monitor_pantelimon.py — Structura codului

### 1.1 Funcția care generează HTML-ul

**Funcție:** `genereaza_raport_html(budget, contracte, flags, hcl_data, data_generare, flags_noi)`

- Locație: secțiunea 5 (`# == 5. GENERARE RAPORT HTML ==`), linia ~806
- Template: **f-string Python** (un singur f-string gigant de ~480 de linii)
- Generează `raport_transparenta.html` (scris în `main()` cu `open(..., "w")`)
- Nu folosește Jinja2, Mako sau altă librărie de template-uri

### 1.2 Cum sunt stocate neregulile intern

Neregulile sunt o **listă de dicționare Python** (`list[dict]`).
Returnată de `analizeaza_red_flags(contracte, config)` și completată cu HCL-uri din `analizeaza_hcl()`.

### 1.3 Câmpurile unui obiect nereguă (dict)

| Câmp | Tip Python | Descriere |
|---|---|---|
| `tip` | `str` | Cod tip: `OFERTANT_UNIC`, `ACHIZITIE_DIRECTA_PESTE_PRAG`, `APROAPE_DE_PRAG`, `FRAGMENTARE`, `PROCEDURI_NON_COMPETITIVE`, `FURNIZOR_DOMINANT`, `sedinte_extraordinare_excesive`, `hcl_*` |
| `severitate` | `str` | `"CRITIC"` / `"MAJOR"` / `"MEDIU"` |
| `titlu` | `str` | Titlu scurt pentru afișare |
| `descriere` | `str` | Text explicativ complet (inclus în HTML) |
| `contract_id` | `str` | ID contract SEAP (ex: `achizitie-directa-2025-489392`). Poate fi `"global"` sau `"HCL-META-001"` pentru flags sintetice |
| `contract_numar` | `str` | Numărul de înregistrare (ex: `"20571"` sau `"12345 + 67890"` la fragmentare) |
| `valoare` | `float` | Valoare în RON |
| `furnizor` | `str` | Numele firmei câștigătoare |
| `data` | `str` | Data publicării (`"YYYY-MM-DD"`) |
| `tip_procedura` | `str` | Tip procedură SEAP (ex: `"achizitie-directa"`, `"licitatie-deschisa"`) |

> **Notă enhance.js:** Scriptul detectează cardurile HTML prin prezența textului `CRITIC`/`MAJOR`/`MEDIU` în DOM — nu prin clase CSS. Câmpurile `severitate` și `titlu` sunt critice pentru detecție.

### 1.4 Locația template-ului HTML

Template-ul este **embedded ca f-string** în corpul funcției `genereaza_raport_html()`.
- Începe la linia ~810 cu `html = f"""`
- Se termină la linia ~1285 cu `"""`
- Conține `{variable}` Python intercalate cu HTML/CSS/JS inline
- `</head>` real la linia ~1013 din fișier (urmat de `<script src="enhance.js" defer></script>`)

### 1.5 Fișiere de output cu date brute

| Fișier | Tip | Generat de | Conținut |
|---|---|---|---|
| `raport_transparenta.html` | HTML | `main()` | Raport complet cu JS/CSS inline |
| `contracte.json` | JSON | `main()` | 506 contracte (id, titlu, valoare, data, tip, firma, cui, ofertanti) |
| `stare_anterioara.json` | JSON | `salveaza_stare()` | Flags + contracte + HCL-uri din rularea precedentă (pentru diff lunar) |
| `feed.xml` | Atom XML | `main()` via `genereaza_feed_atom()` | Top-20 nereguli ordonate severitate desc → valoare desc *(adăugat în feat/seo-rss)* |

> **Lipsă identificată:** Nu există un `raport.json` cu toate datele brute (flags + buget + contracte) care să poată fi consumat de terți sau de enhance.js fără a parsa HTML. Acesta este obiectul **Faza 2-B** din IMPROVEMENTS.md.

### 1.6 Funcția de comparare cu raportul anterior

**Funcție:** `detecteaza_flags_noi(flags_curente, stare_anterioara)`

- Locație: secțiunea 4 (`# == 4. STATE MANAGEMENT ==`), linia ~794
- Logică: compară `contract_id` din flags curente cu cele din `stare_anterioara["flags"]`
- Returnează lista de flags care **nu existau** în rularea precedentă
- Folosit în `main()` → `flags_noi` → pasă la `genereaza_raport_html()` (marcate cu badge "NOU")
- Funcțiile conexe: `incarca_stare_anterioara()`, `salveaza_stare()`

---

## 2. Algoritmi de detecție (5 algoritmi activi)

| # | Cod tip | Severitate | Descriere |
|---|---|---|---|
| 1 | `OFERTANT_UNIC` | MEDIU/MAJOR | Contract >20k RON cu un singur ofertant |
| 1b | `ACHIZITIE_DIRECTA_PESTE_PRAG` | CRITIC | Achiziție directă individuală >130k RON |
| 2 | `APROAPE_DE_PRAG` | MAJOR | Valoare >97% din 130k sau 500k RON |
| 3 | `FRAGMENTARE` | CRITIC | Același furnizor, 2 contracte similare (similaritate >40%) la interval <90 zile, sumă combinată >prag |
| 4 | `PROCEDURI_NON_COMPETITIVE` | MAJOR | >40% din contracte prin cumpărare directă/negociere |
| 5 | `FURNIZOR_DOMINANT` | MAJOR/CRITIC | Un furnizor >40% (MAJOR) sau >60% (CRITIC) din totalul valorii contractelor |
| HCL | `sedinte_extraordinare_excesive` | MAJOR/CRITIC | Rata ședințe extraordinare >30% (MAJOR) sau >50% (CRITIC) |
| HCL | `hcl_*` | MAJOR | Hotărâri suspecte detectate prin OCR (fără transparență, urgență nejustificată) |

**Praguri legale configurate** (`CONFIG`):
```python
"prag_servicii_furnizare": 130_000,   # RON
"prag_lucrari": 500_000,              # RON
"marja_fragmentare_pct": 0.97,        # 97% din prag = suspect
```

---

## 3. Structura contractelor (dict intern)

Un contract din `fetch_contracts_seap()` are câmpurile:

| Câmp | Tip | Sursă xlsx |
|---|---|---|
| `id` | `str` | Generat: `"achizitie-directa-{an}-{nr}"` |
| `titlu` | `str` | Coloana CPV din xlsx |
| `valoare_ron` | `float` | "Valoare contract" / "Valoare achizitie" |
| `castigator` | `str` | "Denumire ofertant" / "Denumire furnizor" |
| `castigator_cui` | `str` | "CUI ofertant" / "CUI furnizor" |
| `data_publicare` | `str` | "Data contract" / "Data achizitie" |
| `tip_procedura` | `str` | "Tip procedura" |
| `numar` | `str` | "Numar contract" / "Numar inregistrare" |
| `nr_ofertanti` | `int` | Dedus din tip procedură (1 = direct, 2+ = competitiv) |

**CUI-uri:** Normalizate în JS cu `.replace(/[^0-9]/g, '')` pentru a elimina prefixul `RO`.
Excepție: AUTO MARCU'S GRUP SA are CUI `86` (eroare data entry) — rămâne cu căutare după nume.

---

## 4. GitHub Actions Workflow

**Fișier:** `.github/workflows/update-report.yml`

| Proprietate | Valoare |
|---|---|
| Nume | "Monitor Transparență Pantelimon" |
| Schedule | `cron: '0 6 1-7 * 1'` — prima luni din fiecare lună, 06:00 UTC (08:00 Romania) |
| Trigger manual | `workflow_dispatch: true` |
| Runner | `ubuntu-latest` |
| Python | `3.11` |
| Permisiuni | `contents: write` (pentru commit înapoi în repo) |
| Secrets/env vars | **Niciun secret configurat** în workflow |

**Pașii workflow-ului:**
1. `actions/checkout@v4`
2. `actions/setup-python@v5` cu Python 3.11
3. Instalare Tesseract OCR + Poppler (`apt-get install tesseract-ocr tesseract-ocr-ron poppler-utils`)
4. `pip install requests beautifulsoup4 openpyxl pytesseract pdf2image`
5. `python monitor_pantelimon.py`
6. Git commit: `raport_transparenta.html stare_anterioara.json` *(+ `feed.xml` pe branch seo-rss)*

> ⚠️ **Discrepanță dependențe:** Workflow instalează `pdf2image` dar `requirements.txt` listează `pymupdf>=1.23.0`. Codul folosește `import fitz` (PyMuPDF) în `ocr_pdf_prima_pagina()`. Workflow-ul ar putea eșua pe OCR PDF. De remediat.

---

## 5. Dependențe Python

**Fișier:** `requirements.txt` (există)

```
requests==2.31.0
beautifulsoup4==4.12.3
openpyxl==3.1.5
pytesseract>=0.3.10
pymupdf>=1.23.0
Pillow>=10.0.0
```

**Nu există:** `pyproject.toml`, `setup.py`, `poetry.lock`, `Pipfile`

> ⚠️ **Discrepanță vs workflow** (detaliat mai sus): workflow instalează `pdf2image` în loc de `pymupdf`. OCR-ul PDF poate eșua în CI.

---

## 6. enhance.js — Funcționalități active

**Fișier:** `enhance.js` (v1.0, ~800 linii, inclus pe toate cele 3 pagini HTML cu `defer`)

| Feature | Descripție |
|---|---|
| Nav unificat | Sticky bar pe toate paginile (Acasă / Nereguli / Buget / Surse), dark mode toggle |
| Search | Câmp liber filtru live pe carduri (`/` → focus, `Esc` → clear) |
| Filtre severitate | Butoane CRITIC / MAJOR / MEDIU pe raport |
| Dropdown furnizor | Filtru per furnizor pe raport |
| Sortare | Câmp sort pe raport |
| Export CSV/JSON | Download direct din browser |
| Paginare | Load more 25 carduri odată |
| Widget top-10 | Top furnizori după valoare/număr + bară severitate |
| Permalinks | `#nereguli-N` per card — click pe titlu copiază link |
| Print CSS | Stil optimizat pentru salvare PDF |
| Back-to-top | Buton flotant |
| Storage prefs | Salvează preferințe în `localStorage` (key: `tp-prefs-v1`) |

> ⚠️ **Detecție carduri:** enhance.js identifică flag-urile prin prezența `CRITIC`/`MAJOR`/`MEDIU` în textul DOM, nu prin clase CSS. Orice modificare care elimină aceste cuvinte din HTML va rupe filtrele și export-ul.

---

## 7. Surse de date externe

| Sursă | URL | Tip acces | Frecvență |
|---|---|---|---|
| SEAP contracte | `https://data.gov.ro/api/3/action/package_search?q=pantelimon` | HTTP GET + xlsx | Trimestrial (data.gov.ro publică export SEAP trimestrial) |
| Buget ANAF | `https://transparenta.eu/...?cui=4420759` | HTTP GET JSON | Lunar |
| HCL-uri primărie | `https://www.pantelimon.ro/hotarari-consiliu-local/` | HTML scraping + OCR | Lunar |

> ℹ️ **SEAP API (`/api-pub/v1/`):** endpoint-urile REST returnează 404 din exterior (Angular SPA). Soluție actuală corectă: xlsx de la data.gov.ro.

---

## 8. Limitări și gap-uri identificate (input pentru Bloc 2)

| # | Gap | Faza IMPROVEMENTS | Prioritate |
|---|---|---|---|
| 1 | Nu există `raport.json` structurat consumabil de JS/terți | Faza 2-B | Mare |
| 2 | Cardurile HTML nu au atribute `data-*` → enhance.js heuristic fragil | Faza 2-A | Mare |
| 3 | `detecteaza_flags_noi()` compară doar `contract_id` — nu captează modificări de valoare | Faza 1-I | Medie |
| 4 | OCR workflow folosește `pdf2image` în loc de `pymupdf` (discrepanță requirements) | Remediere imediată | Mare |
| 5 | Nu există pagini per furnizor (deep links imposibile) | Faza 3-D | Medie |
| 6 | Nu există scor de transparență calculat | Faza 3-E | Scăzut |
| 7 | Feed Atom generat (feat/seo-rss) dar fără auto-descoperire (`<link rel="alternate">` în HTML) | Faza 1-H | Scăzut |
| 8 | `feed.xml` nu este inclus în `contracte.json` `git add` din workflow | Remediat în feat/seo-rss | — |

---

## 9. Structura repo în întregime

```
transparenta-pantelimon/
├── .github/workflows/update-report.yml   # CI lunar (prima luni / lună)
├── docs/
│   └── INVESTIGATION-NOTES.md            # ← acest fișier (Faza 0)
├── contracte.json                         # 506 contracte cu CUI
├── enhance.js                             # Progressive enhancement JS (~800 linii)
├── feed.xml                               # Feed Atom (generat, în feat/seo-rss)
├── index.html                             # Landing page static
├── monitor_pantelimon.py                  # Script principal Python (1450+ linii)
├── raport_transparenta.html               # Generat automat de monitor
├── requirements.txt                       # Dependențe Python
├── robots.txt                             # SEO (adăugat în feat/seo-rss)
├── sitemap.xml                            # SEO (adăugat în feat/seo-rss)
├── stare_anterioara.json                  # State persistence pentru diff lunar
├── transparenta_pantelimon.html           # Pagina de analize bugetare (~2650 linii)
├── CLAUDE.md                              # Context pentru Claude Code (untracked)
└── IMPROVEMENTS.md                        # Plan 12 feature-uri / 5 faze
```

---

*Investigare completă. Toate gap-urile documentate. Gata pentru implementare Faza 1 → Faza 5.*
