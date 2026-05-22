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

| Algoritm | Severitate | Ce detecteaza |
|----------|-----------|---------------|
| 1a | MAJOR | Achizitie directa aproape de prag (>97% din 130.000 RON) |
| 1b | CRITIC | Contract individual PESTE pragul legal (>130.000 RON) |
| 2 | MEDIU | Furnizor monopol (singur ofertant repetat) |
| 3 | MAJOR | Fragmentare artificiala (acelasi furnizor, suma combinata > prag) |
| 4 | MAJOR | Contract fara licitatie pentru valori mari |

Praguri: Legea 98/2016 — 130.000 RON (servicii/furnizare), 500.000 RON (lucrari).

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
