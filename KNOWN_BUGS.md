# Bug-uri cunoscute (descoperite in Faza 2)

Documentate pe 25 mai 2026. BUG-1, BUG-2, BUG-3 rezolvate in Faza 2.5 (branch `feat/fix-kpi-consistency`).

---

## ~~BUG-1: 4,2M RON hardcodat in `transparenta_pantelimon.html` (3 locatii)~~ ✅ REZOLVAT in Faza 2.5

**Rezolvat prin:** functia `actualizeaza_kpi_seap()` in `monitor_pantelimon.py`  
**Mecanism:** regex replace pe cele 3 locatii; injecteaza `data-an` si `data-total-ron` ca sursa unica de adevar  
**Commit:** `fix(kpi): BUG-1 + BUG-2 — KPI consistent cu widget reconciliere`

### Descriere originala

KPI-ul "Valoare totala contracte 2025" era hardcodat static ca `4.200.000 RON` in trei locatii:

```html
<!-- BUG-1a: fallback static KPI (acum: data-total-ron + _format_kpi) -->
<span class="val" id="kpi-val-total">4,2M RON</span>

<!-- BUG-1b: text hardcodat in tabel comparativ (acum: an curent + suma dedupata) -->
<strong>💰 Valoare totala contracte 2025 — 4.200.000 RON</strong>

<!-- BUG-1c: rand in tabelul de reconciliere manual (acum: an curent + suma dedupata) -->
<tr><td>Valoare totala contracte 2025</td><td>4.200.000 RON</td>...</tr>
```

---

## ~~BUG-2: `_renderKpi(data)` sumeaza toate contractele fara filtru de an~~ ✅ REZOLVAT in Faza 2.5

**Rezolvat prin:** `_renderKpi()` citeste `data-total-ron` din elementul `#kpi-val-total`  
**Fallback:** filtru pe `data-an` daca atributul lipseste  
**Commit:** `fix(kpi): BUG-1 + BUG-2 — KPI consistent cu widget reconciliere`

### Descriere originala

```javascript
// Vechi: sumeaza TOATE contractele din contracte.json, indiferent de an
const total = data.reduce(function(s,c){ return s+c.valoare; }, 0);
```

`contracte.json` contine contracte din mai multi ani. Suma rezultata era
~313M RON (toti anii) in loc de valoarea anului curent (dupa dedup).

---

## ~~BUG-3: Inconsistenta NoJS vs JS — utilizatorul vede cifre diferite~~ ✅ REZOLVAT in Faza 2.5

**Rezolvat prin:** BUG-1 + BUG-2 rezolvate → sursa unica de adevar `data-total-ron`  
**Commit:** `fix(kpi): BUG-1 + BUG-2 — KPI consistent cu widget reconciliere`

### Descriere originala

Starea fara JS: KPI = `4,2M RON` (hardcodat, BUG-1)  
Starea cu JS incarcat: KPI = `313M RON` (suma multi-anuala, BUG-2)  
Widget reconciliere (raport): `257M RON` (2025, dedupat)

Trei cifre diferite pe doua pagini pentru acelasi concept.

---

## ~~BUG-5: `toggleFlag` / `openFirmaPanel` nedefinite — SyntaxError JS~~ ✅ REZOLVAT în PR #46

**Rezolvat prin:** șters `}}` orfan din template-ul Python (`monitor_pantelimon.py` linia ~4318) și `}` din `raport_transparenta.html`  
**Commit:** `fix(js): inlatura } orfan care bloca toggleFlag si openFirmaPanel`

### Descriere originală

Un `}` extra la finalul blocului `<script>` inline în `raport_transparenta.html` cauza un **SyntaxError JavaScript** la parsare. Întreg scriptul (13 688 chars) nu executa deloc — funcțiile nu erau definite în global scope:

- `toggleFlag()` — clic pe „▼ detalii" nu producea niciun efect vizibil
- `openFirmaPanel()` — badge RISC (ex: „⚠️ RISC 46") nu deschidea panoul firmei
- `_getContracte()`, `_getRisc()`, `closeFirmaPanel()`, `showFirmaContracts()` — toate nedefinite

`printRaport` funcționa *aparent* corect deoarece `enhance.js` îl exporta explicit via `window.printRaport = printRaport` — mascând simptomele.

**Cauza:** `}}` orfan în template Python, reziduu dintr-un refactoring care a eliminat un IIFE wrapper (`(function() { ... })()`) dar a lăsat `}}` de închidere în urmă.

---

## BUG-4: Rev.2 dubleaza valoarea contractelor in SEAP (problema upstream)

**Severitate:** INFO — sursa: SEAP, nu codul nostru  
**Impact:** Inflatie artificiala a sumei brute din `contracte.json`  
**Status:** Partial mitigat prin `_suma_seap_dedupata()` in Faza 2. Nu se poate rezolva complet
fara acces la schema completa SEAP (data_start/data_sfarsit).

### Descriere

SEAP republica valoarea INTREAGA a unui contract la fiecare modificare (act aditional = Rev.X).
Din 417 contracte 2025 in `contracte.json`:
- 381 au `Rev.2` in titlu (91%) → suma bruta: 269M RON
- 36 nu au Rev.X → suma: 185K RON

Dupa deduplicare canonica (`_suma_seap_dedupata`): 242 contracte unice, 257M RON.

Ramane o discrepanta (257M > 146M ANAF) probabila din cauza contractelor multi-anuale.

---

## ~~BUG-6: Shell filter chips (⚠️ Orice risc, 👥 0 angajați, 📉 CA=0) — rând ascuns, riskCount=0 pentru toți~~ ✅ REZOLVAT în PR #47

**Rezolvat prin:** enhance.js citește acum `#risc-firma-data` JSON pentru `riskCount` (câmpul `scor`) în loc de `.supplier-risk-panel` care nu există în HTML-ul curent.  
**Commit:** `fix(filter): BUG-6 — shell chips citesc risc din #risc-firma-data`

### Descriere originală

`enhance.js` linia ~707 căuta `.supplier-risk-panel[data-risk-count]` în fiecare card. Aceste elemente **nu sunt generate** de `monitor_pantelimon.py` în versiunea curentă. Rezultat:
- `shellPanelsFound = 0` → `#tp-shell-row { display: none }` (rândul de chip-uri shell era **complet ascuns**)
- `riskCount = 0` pentru toți cei 299 itemi → filtrul `any-risk` returna 0/299

### Starea după fix

- Sursă: `#risc-firma-data` JSON (93 firme, toate cu `scor > 0`)  
- `any-risk` chip: afișează 299/299 (toți furnizorii flagați au scor risc > 0 — corect)
- `zero-sal` / `zero-ca`: afișează 0/299 — date ANAF/ONRC (angajați, cifra afaceri) **nu sunt încă populate** în `risc-firma-data.onrc`/`.openapi`; chips sunt vizibile dar fără date relevante deocamdată
