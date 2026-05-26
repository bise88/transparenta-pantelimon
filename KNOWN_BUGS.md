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
