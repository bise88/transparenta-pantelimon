# Audit bug-uri restante — 03 Iunie 2026

Verificat manual pe baza checklist-ului din roadmap. BUG-1..BUG-3, BUG-5..BUG-7 sunt deja rezolvate (KNOWN_BUGS.md). Noi bug-uri descoperite:

---

## 🔴 BUG-8 — Label KPI hardcodat cu an vechi (MAJOR)

**Fișier:** `transparenta_pantelimon.html` linia 1159  
**Actual:**
```html
<span class="lbl">Valoare contracte atribuite 2025</span>
```
**Problemă:** Afișează "2025" deși KPI arată `data-an="2026"`. Utilizatorii văd titlul "Valoare contracte atribuite 2025 — 12,3M RON".  
**Propunere fix:** `actualizeaza_kpi_seap()` din `monitor_pantelimon.py` adaugă un al 4-lea regex pentru acest label.

---

## 🔴 BUG-9 — Detail-grid KPI cu cifre stale din 2025 (MAJOR)

**Fișier:** `transparenta_pantelimon.html` liniile 1191-1194  
**Actual (stale):**
- Contracte lucrări: **2.420.000 RON**
- Servicii & furnizări: **1.780.000 RON**
- Nr. contracte: **66 contracte**
- Valoare medie: **63.636 RON**
- Total implicit: **4.200.000 RON** (suma celor 2 categorii)

**Header KPI (corect):** `12.286.283 RON` (2026)

**Impact:** Utilizatorul deschide panoul detalii și vede 4.2M ≠ 12.3M — contradictie flagrantă.  
**Propunere fix:** `actualizeaza_kpi_seap()` calculează breakdownul per categorie CAEN/tip din `contracte.json` și actualizează cele 4 celule + header-ul detalii.

---

## 🟡 BUG-10 — "506 contracte · 2025" hardcodat în 4 locații (MEDIU)

**Fișier:** `transparenta_pantelimon.html`  
**Linii afectate:**
- Linia 977: `"506 contracte"` în text inline
- Linia 1328: `"506 contracte publice 2025"` în subtitle analiză
- Linia 1345: `"506 contracte · 2025"` în subtitle chip-uri
- Linia 1519: `"Din 506 contracte, practic toate..."` în paragraf analiză
- Linia 1571: `<span class="val">506</span>` în stat bar

**Propunere fix:** Aceleași locații actualizate de `actualizeaza_tabel_contracte()` sau un nou regex în `actualizeaza_kpi_seap()`.

---

## 🔴 BUG-11 — index.html: "216 nereguli / 2 CRITICE" hardcodat (MAJOR)

**Fișier:** `index.html` linia 229  
**Actual:**
```html
🔴 <strong>216 nereguli detectate</strong> în ultima analiză automată, din care <strong>2 CRITICE</strong>
```
**Date reale (raport.json):** 299 nereguli, 107 CRITIC, 55 MAJOR, 137 MEDIU  
**Impact:** Prima pagina văzuta de oricine e complet deactualizata — arată <1/3 din neregulile reale.  
**Propunere fix:** `monitor_pantelimon.py` injectează dinamic din `raport.json` la generare, sau JS inline citeste `raport.json` la load.

---

## 🟡 BUG-12 — despre.html: "17 algoritmi" în loc de 19 (MEDIU)

**Fișier:** `despre.html` linia 160  
**Actual:** `"17 algoritmi independenți"`  
**Corect:** 19 algoritmi (cf. README.md și CLAUDE.md)  
**Propunere fix:** Actualizare manuală (nu e generat de monitor).

---

## 🟡 BUG-13 — 201.html: canonical URL stale + cifre 2025 (MEDIU)

**Fișier:** `201.html` (pagina "Buget vs. Realizat")  
**Probleme:**
1. Linia 14: `canonical` href → `bise88.github.io/...` (vechi, trebuie `aprindemlumina.eu`)
2. Linia 18: `og:url` → `bise88.github.io/...`
3. Linia 2522: link offline fallback → `bise88.github.io/...`
4. Linia 2716: referință text → `bise88.github.io/...`
5. Cifre de-a lungul paginii: 4.2M RON, 506 contracte, 2025 (stale față de 12.3M / 2026)

**Propunere fix:** Update canonical + og:url + 2 referinte text. Cifrele din detail-panel sunt calculate de JS (nu necesită schimbare manuală dacă `contracte.json` e corect).

---

## ✅ Verificări OK (fără bug-uri active)

| Check | Status |
|---|---|
| Service Worker: `skipWaiting()` + `clients.claim()` | ✅ Prezente (linia 45 + 57 sw.js) |
| SW: `raport_transparenta.html` în network-first | ✅ (linia 17 sw.js) |
| SW: `contracte.json` în network-first | ✅ (linia 31 sw.js) |
| SW cache version | `tp-static-v4` (bump la v5 dacă fix semantic) |
| Tests: 359/359 PASS | ✅ |
| Raport size: 2.0MB | ✅ (sub prag 3MB) |
| BUG-1,2,3,5,6,7 din KNOWN_BUGS.md | ✅ Rezolvate |
| BUG-4 (Rev.X SEAP) | INFO — upstream, nu fixabil |

---

## Sumar prioritizat

| ID | Severitate | Fișier | Propunere fix |
|---|---|---|---|
| BUG-11 | 🔴 MAJOR | `index.html` | JS dinamic din raport.json |
| BUG-8 | 🔴 MAJOR | `transparenta_pantelimon.html` | regex în actualizeaza_kpi_seap() |
| BUG-9 | 🔴 MAJOR | `transparenta_pantelimon.html` | detail-grid calculat din contracte.json |
| BUG-10 | 🟡 MEDIU | `transparenta_pantelimon.html` | regex "N contracte · YYYY" |
| BUG-12 | 🟡 MEDIU | `despre.html` | manual: 17→19 algoritmi |
| BUG-13 | 🟡 MEDIU | `201.html` | canonical + 3 referinte bise88 |
