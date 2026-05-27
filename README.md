# Transparenta Pantelimon

Monitorizare cetateasca automata a achizitiilor publice ale Primariei Pantelimon.

**Site live:** [aprindemlumina.eu](https://aprindemlumina.eu)
**Raport nereguli:** [aprindemlumina.eu/raport_transparenta.html](https://aprindemlumina.eu/raport_transparenta.html)

---

## Ce face

- Trage lunar contractele din SEAP (e-licitatie.ro) si bugetul de la ANAF
- Aplica algoritmi de detectie pentru pattern-uri de risc (fragmentare artificiala, monopol furnizor, achizitii directe peste prag, shell companies, geocodare furnizori)
- Genereaza raport HTML + JSON + RSS + press-kit + harta interactiva furnizori
- Publica automat pe GitHub Pages prin GitHub Actions
- Surse externe: Curtea de Conturi, ANI declaratii avere, TED Europa, MOL primarie

## Structura repo

```
monitor_pantelimon.py        # Scriptul principal (~5800 linii)
monitor_uat.py               # CLI wrapper multi-UAT (orice CIF de primarie)
transparenta_pantelimon.html # Pagina principala (site static)
raport_transparenta.html     # Raport generat (output monitor)
harta.html                   # Harta interactiva furnizori (Leaflet.js)
presa.html                   # Pagina jurnalisti + press kit
petitie.html                 # Petitie cetateneasca (Formspree)
despre.html                  # Metodologie + institutii sesizare
gdpr.html                    # Politica de confidentialitate
sw.js                        # Service Worker PWA (Cache-First/Network-First)
manifest.webmanifest         # PWA manifest (instalabil pe telefon)
icon-192.png / icon-512.png  # Icoane PWA
contracte.json               # Export contracte SEAP (JSON)
contracte.csv                # Export contracte SEAP (CSV — Excel/Sheets)
raport.json                  # Export flags/nereguli (format JSON public)
feed.xml                     # RSS/Atom feed nereguli noi
press_kit.json               # Press kit date structurate (generat automat)
press_kit.md                 # Press kit Markdown (descarcabil de jurnalisti)
pnrr_projects.json           # Proiecte PNRR (generat automat)
firme_geocoded.json          # Sedii firme geocodate cu Nominatim OSM
curtea_de_conturi.json       # Rapoarte audit CC (generat automat)
ani_declaratii.json          # Declaratii avere ANI (generat automat)
ted_notices.json             # Anunturi TED Europa (generat automat)
mol_primarie.json            # Documente MOL primarie (generat automat)
furnizori/                   # Pagini per furnizor (generate automat)
risc_firma.py                # Modul detector shell companies
.github/workflows/           # GitHub Actions (rulare automata lunara)
API.md                       # Documentatie API JSON/CSV public
IMPROVEMENTS.md              # Roadmap si idei de imbunatatire
AUDIT.md                     # Audit tehnic cu propuneri cod
```

## Replicare pentru alta localitate

```bash
git clone https://github.com/transparenta-locala/transparenta-pantelimon
cd transparenta-pantelimon
pip install -r requirements.txt

# Foloseste CLI-ul multi-UAT:
py monitor_uat.py 4420759                                            # Pantelimon (default)
py monitor_uat.py 4364643 --judet Ilfov --uat-search Voluntari      # Voluntari
py monitor_uat.py 4364660 --judet Ilfov --uat-search Popesti-Leordeni
py monitor_uat.py 4420759 --dry-run                                  # Preview CONFIG fara scraping
```

## Algoritmi de detectie (red flags)

| Algoritm | Tip flag | Severitate | Ce detecteaza |
|----------|----------|-----------|---------------|
| 1a | `OFERTANT_UNIC` | MAJOR | Achizitie directa aproape de prag (>97% din 130.000 RON) |
| 1b | `ACHIZITIE_DIRECTA_PESTE_PRAG` | CRITIC | Contract individual PESTE pragul legal (>130.000 RON) |
| 2 | `PROCEDURI_NON_COMPETITIVE` | MAJOR | Exces proceduri non-competitive (>40%) |
| 3 | `FRAGMENTARE` | CRITIC | Fragmentare artificiala (acelasi furnizor, titluri similare, interval <60 zile) |
| 4 | `FURNIZOR_DOMINANT` | MEDIU | Furnizor cu >35% din totalul contractelor |
| 5 | `CONCENTRARE_FURNIZOR` | MAJOR/CRITIC | Top-3 furnizori >60% / >80% din valoarea totala |
| 6 | `FRAGMENTARE_TEMPORARA` | CRITIC | Ferestra 90 zile, suma sub-prag > prag |
| 7 | `CRESTERE_BRUSCA_VALOARE` | MAJOR/CRITIC | Revizie contract cu crestere >50% de valoare |
| 8 | `VALOARE_ROTUNDA_SUSPECTA` | MEDIU | Valori rotunde (multiplu de 10k) — posibil fara studiu de piata |
| 9 | `VALORI_IDENTICE_ACEEASI_ZI` | CRITIC | Valoare exact identica la firme diferite in aceeasi zi |
| 10 | `BURST_CONTRACTE` | MEDIU/MAJOR | Volum anormal de contracte intr-o singura zi |
| 11 | `SEMNARE_ZI_NELUCRATOARE` | MEDIU | Contract semnat in weekend sau sarbatoare legala |
| 12 | `FIRMA_INACTIVA` | CRITIC | Contract cu firma inactiva/radiata la ANAF/ORC |
| 13 | `FIRMA_NOU_CREATA` | MAJOR/CRITIC | Firma cu <24 luni vechime la data contractului |
| 14 | `RISC_SISTEMIC_FIRMA` | CRITIC | Firma aparuta in >=3 categorii diferite de nereguli |
| 15 | `PUBLICARE_INTARZIATA` | MEDIU/CRITIC | Intarziere publicare contract (>11 zile lucratoare) |
| 16 | `SEDINTE_EXTRAORDINARE_EXCESIVE` | MAJOR/CRITIC | Rata ridicata sedinte extraordinare (>25% / >=40%) |
| 17 | `GEOGRAFIE_ANORMALA` | MEDIU | Servicii locale (curatenie/paza/salubrizare) de la firma din afara Ilfov+limitrofe |
| 18 | `CIFRA_AFACERI_ZERO` | CRITIC | CA = 0 RON in anul anterior contractului (risc_firma.py) |
| 19 | `ZERO_ANGAJATI` | MAJOR | 0 angajati declarati la ANAF (risc_firma.py) |

Praguri: Legea 98/2016 — 130.000 RON (servicii/furnizare), 500.000 RON (lucrari).

## Surse externe integrate

| Sursa | Functie | Cache |
|---|---|---|
| SEAP / data.gov.ro | Contracte achiziții publice | 30 zile |
| ANAF / transparenta.eu | Buget executie | 30 zile |
| openapi.ro (ONRC) | Date firme (CUI, adresa, actionariat) | 30 zile |
| mfinante.gov.ro | Cifra afaceri, nr. angajati (shell detector) | 30 zile |
| Curtea de Conturi | Rapoarte audit UAT | 30 zile |
| ANI integritate.eu | Declaratii avere alesi locali | 30 zile |
| TED Europa | Anunturi contracte >500k EUR | 7 zile |
| MOL primarie | HCL-uri / rectificari buget | 7 zile |
| Nominatim OSM | Geocodare sedii firme | 180 zile |
| proiecte.pnrr.gov.ro | Proiecte PNRR beneficiar CIF | 7 zile |

## Teste automate

```bash
py -m pytest tests/ -v
```

**216 teste unitare in 14 fisiere** — toate ruleaza fara conexiune la retea (mock urllib/requests).

```
tests/test_detectors.py          # detectori batch 1 (fragmentare, concentrare, sedinte, publicare)
tests/test_detectors_batch2.py   # detectori batch 2 (valori identice, burst, semnare nelucratoare)
tests/test_geographic.py         # detector anomalie geografica
tests/test_risc_firma.py         # modul shell company (risc_firma.py)
tests/test_reconciliere.py       # widget reconciliere ANAF vs SEAP
tests/test_sitemap_mentiuni.py   # sitemap dinamic + mentiuni presa furnizori
tests/test_geocoding.py          # geocodare Nominatim + cache SQLite
tests/test_cc_ani.py             # Curtea de Conturi + ANI declaratii avere
tests/test_ted_mol.py            # TED Europa + MOL primarie
tests/test_press_kit.py          # press kit JSON + Markdown
tests/test_pwa.py                # Service Worker + manifest PWA + icoane
tests/test_pnrr.py               # PNRR tracker (cache SQLite + JSON/HTML fallback)
tests/test_monitor_uat.py        # CLI multi-UAT (argparse + build_config_overrides)
tests/test_csv_feed.py           # CSV export + feed Atom (XSS, sortare, max 20)
```

## Contribuie

- **Issues:** bug-uri, false-positive-uri sau idei noi
- **PR-uri:** cod nou (vezi `IMPROVEMENTS.md` si `AUDIT.md` pentru roadmap detaliat)
- **Fork la alta localitate:** deschide un issue, te ajutam cu configurarea

## Licenta

**Cod:** MIT
**Date generate (rapoarte, JSON, feed):** [CC-BY 4.0](https://creativecommons.org/licenses/by/4.0/)
Atribuire: *Transparenta Pantelimon — aprindemlumina.eu*

## Disclaimer

Toate datele sunt fapte publice (SEAP, ANAF, ONRC). Site-ul nu face afirmatii
despre intentii sau vinovatie — doar afiseaza statistici si legi posibil incalcate.
Concluziile sunt la latitudinea cititorului.

## Contact

Initiativa civica independenta a unui membru USR Pantelimon (Alexandru).
Intrebari si sesizari: [deschide un Issue](https://github.com/transparenta-locala/transparenta-pantelimon/issues)

---

*Generat automat cu [GitHub Actions](https://github.com/transparenta-locala/transparenta-pantelimon/actions) — date publice SEAP + ANAF*
