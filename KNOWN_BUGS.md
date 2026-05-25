# Bug-uri cunoscute (descoperite in Faza 2)

Documentate pe 25 mai 2026. Nu sunt adresate in branch-ul `feat/reconciliation-widget`.
Vor fi rezolvate intr-o Faza 2.5 separata.

---

## BUG-1: 4,2M RON hardcodat in `transparenta_pantelimon.html` (3 locatii)

**Severitate:** MAJOR — date false pentru utilizatorii fara JavaScript  
**Fisier:** `transparenta_pantelimon.html`  
**Linii:** 1137, 1168, 2682

### Descriere

KPI-ul "Valoare totala contracte 2025" este hardcodat static ca `4.200.000 RON` in trei locatii:

```html
<!-- Linia 1137 — fallback static KPI (suprascris de JS daca se incarca) -->
<span class="val" id="kpi-val-total">4,2M RON</span>

<!-- Linia 1168 — text hardcodat in tabel comparativ -->
<strong>💰 Valoare totala contracte 2025 — 4.200.000 RON</strong>

<!-- Linia 2682 — rand in tabelul de reconciliere manual -->
<tr><td>Valoare totala contracte 2025</td><td>4.200.000 RON</td>...</tr>
```

Utilizatorii fara JS (crawlere, cititoare de ecran, conexiuni lente) vad 4,2M in loc de
valoarea reala (~257M RON dupa dedup, ~313M brut din toate contractele).

### Fix propus

Functia `actualizeaza_tabel_contracte()` (§1.1) sa actualizeze si aceste trei locatii
cu valoarea calculata din `contracte.json`. Alternativ: generare statica similara cu
tabelul tbody.

---

## BUG-2: `_renderKpi(data)` sumeaza toate contractele fara filtru de an

**Severitate:** MAJOR — KPI-ul JS afiseaza suma multi-anuala, nu suma anului curent  
**Fisier:** `transparenta_pantelimon.html`  
**Linie:** 2391

### Descriere

```javascript
// Linia 2391 — sumeaza TOATE contractele din contracte.json, indiferent de an
const total = data.reduce(function(s,c){ return s+c.valoare; }, 0);
```

`contracte.json` contine contracte din 2023, 2024, 2025, 2026. Suma rezultata este
~313M RON (toate anile) in loc de ~257M RON (doar 2025, dupa dedup).

Utilizatorul vede pe aceeasi pagina:
- KPI dinamic (dupa JS): 313M RON (toti anii)
- Widget reconciliere (Python, filtrat pe 2025 cu dedup): 257M RON
→ Contradictie vizibila.

### Fix propus

Adauga filtru de an in `_renderKpi`:
```javascript
const an = new Date().getFullYear();
const data2025 = data.filter(function(c){ return (c.data||'').startsWith(String(an)); });
const total = data2025.reduce(function(s,c){ return s+c.valoare; }, 0);
```

Sau: expune anul curent ca variabila din Python in HTML si foloseste-l in JS.

---

## BUG-3: Inconsistenta NoJS vs JS — utilizatorul vede cifre diferite

**Severitate:** MEDIU — experienta inconsistenta, potential de confuzie  
**Fisier:** `transparenta_pantelimon.html`

### Descriere

Starea fara JS: KPI = `4,2M RON` (hardcodat, BUG-1)  
Starea cu JS incarcat: KPI = `313M RON` (suma multi-anuala, BUG-2)  
Widget reconciliere (raport): `257M RON` (2025, dedupat)

Trei cifre diferite pe doua pagini pentru acelasi concept ("valoare contracte SEAP").

### Fix propus

Rezolva BUG-1 + BUG-2 mai intai. Dupa aceea, aliniaza formula JS cu formula Python
din `reconciliere_buget_seap()` (filtru an + dedup canonic).

---

## BUG-4: Rev.2 dubleaza valoarea contractelor in SEAP (problema upstream)

**Severitate:** INFO — sursa: SEAP, nu codul nostru  
**Impact:** Inflatie artificiala a sumei brute din `contracte.json`

### Descriere

SEAP republica valoarea INTREAGA a unui contract la fiecare modificare (act aditional = Rev.X).
Din 417 contracte 2025 in `contracte.json`:
- 381 au `Rev.2` in titlu (91%) → suma bruta: 269M RON
- 36 nu au Rev.X → suma: 185K RON

Dupa deduplicare canonica (`_suma_seap_dedupata`): 242 contracte unice, 257M RON.

### Status

Partial mitigat in Faza 2 prin `_suma_seap_dedupata()` in `reconciliere_buget_seap()`.
Ramane o discrepanta (257M > 146M ANAF) probabila din cauza contractelor multi-anuale.
Nu se poate rezolva complet fara acces la schema completa SEAP (data_start/data_sfarsit).
