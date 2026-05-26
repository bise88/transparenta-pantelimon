# Transparenta Pantelimon

Monitorizare cetateasca automata a achizitiilor publice ale Primariei Pantelimon.

**Site live:** [aprindemlumina.eu](https://aprindemlumina.eu)  
**Raport nereguli:** [aprindemlumina.eu/raport_transparenta.html](https://aprindemlumina.eu/raport_transparenta.html)

---

## Ce face

- Trage lunar contractele din SEAP (e-licitatie.ro) si bugetul de la ANAF
- Aplica algoritmi de detectie pentru pattern-uri de risc (fragmentare artificiala, monopol furnizor, achizitii directe peste prag)
- Genereaza raport HTML + JSON + RSS
- Publica automat pe GitHub Pages prin GitHub Actions

## Structura repo

```
monitor_pantelimon.py        # Scriptul principal
transparenta_pantelimon.html # Pagina principala (site static)
raport_transparenta.html     # Raport generat (output monitor)
contracte.json               # Export contracte (506 intrari)
raport.json                  # Export flags/nereguli (format JSON public)
feed.xml                     # RSS/Atom feed nereguli noi
furnizori/                   # Pagini per furnizor (generate automat)
.github/workflows/           # GitHub Actions (rulare automata lunara)
IMPROVEMENTS.md              # Roadmap si idei de imbunatatire
```

## Replicare pentru alta localitate

```bash
git clone https://github.com/transparenta-locala/transparenta-pantelimon
cd transparenta-pantelimon
# editeaza CONFIG in monitor_pantelimon.py cu CUI + nume UAT
pip install -r requirements.txt
python monitor_pantelimon.py
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
| 6 | `FRAGMENTARE_TEMPORARA` | CRITIC | Ferestra 90 zile, suma sub-prag > prag (§2.1) |
| 7 | `CRESTERE_BRUSCA_VALOARE` | MAJOR/CRITIC | Revizie contract cu crestere >50% de valoare |
| 8 | `VALOARE_ROTUNDA_SUSPECTA` | MEDIU | Valori rotunde (multiplu de 10k) — posibil fara studiu de piata |
| 9 | `VALORI_IDENTICE_ACEEASI_ZI` | CRITIC | Valoare exact identica la firme diferite in aceeasi zi |
| 10 | `BURST_CONTRACTE` | MEDIU/MAJOR | Volum anormal de contracte intr-o singura zi |
| 11 | `SEMNARE_ZI_NELUCRATOARE` | MEDIU | Contract semnat in weekend sau sarbatoare legala |
| 12 | `FIRMA_INACTIVA` | CRITIC | Contract cu firma inactiva/radiata la ANAF/ORC |
| 13 | `FIRMA_NOU_CREATA` | MAJOR/CRITIC | Firma cu <24 luni vechime la data contractului |
| 14 | `RISC_SISTEMIC_FIRMA` | CRITIC | Firma aparuta in ≥3 categorii diferite de nereguli |
| HCL | `SEDINTE_EXTRAORDINARE_EXCESIVE` | MAJOR/CRITIC | Rata ridicata sedinte extraordinare (>25% / ≥40%) |
| PUB | `PUBLICARE_INTARZIATA` | MEDIU/CRITIC | Intarziere publicare contract (>11 zile lucratoare) |

Praguri: Legea 98/2016 — 130.000 RON (servicii/furnizare), 500.000 RON (lucrari).

## Teste automate

```bash
py -m pytest tests/ -v
```

37 teste unitare (batch 1: 20 teste, batch 2: 17 teste) — toate ruleaza fara conexiune la retea.

## Contribuie

- **Issues:** bug-uri, false-positive-uri sau idei noi
- **PR-uri:** cod nou (vezi `IMPROVEMENTS.md` pentru roadmap detaliat)
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

Inițiativa civica independenta a unui membru USR Pantelimon (Alexandru).  
Intrebari si sesizari: [deschide un Issue](https://github.com/transparenta-locala/transparenta-pantelimon/issues)

---

*Generat automat cu [GitHub Actions](https://github.com/transparenta-locala/transparenta-pantelimon/actions) — date publice SEAP + ANAF*
