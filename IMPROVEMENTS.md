# Plan de îmbunătățiri — transparenta-pantelimon

Document master pentru Claude Code. Conține 9 îmbunătățiri grupate în 4 faze, cu instrucțiuni
de implementare, dependențe, criterii de verificare și mesaje de commit sugerate.

---

## INSTRUCȚIUNI PENTRU CLAUDE CODE (citește înainte de orice)

1. **Nu implementa tot deodată.** Întreabă userul ce fază să ataci. Lucrează fază cu fază.
2. **Branch per fază.** Înainte de orice modificare, creează un branch nou:
   `git checkout -b feat/faza-1-seo-rss-banner`.
3. **Investigare înainte de cod.** La fiecare fază, prima dată citește fișierele relevante,
   raportează ce ai găsit, apoi implementează. Niciodată nu modifica codul fără să fi
   citit întâi.
4. **Commit-uri mici și descriptive.** Un commit per modificare logică, nu un mega-commit.
   Formatul: `feat(SECȚIUNE): descriere scurtă` sau `fix(...)`, `chore(...)`, `docs(...)`.
5. **Verifică după fiecare modificare.** Rulează `python -m py_compile monitor_pantelimon.py`
   să confirmi că nu ai stricat sintaxa. Dacă există teste sau linters, rulează-le.
6. **Cere confirmare userului** înainte de:
   - merge în main / push în main
   - rularea live a `monitor_pantelimon.py` (face scraping pe SEAP — costisitor)
   - ștergerea/redenumirea fișierelor existente
   - schimbări care strică `enhance.js` (script-ul JS de pe site)
7. **Întreabă, nu presupune.** Dacă vreun detaliu nu e clar (ex: ce câmpuri are obiectul
   nereguă în Python), întreabă userul sau caută în cod. Nu inventa.
8. **La final fă PR draft.** Nu face merge direct în main. Userul va revizui PR-ul.

---

## CONTEXT REPO (pentru orientare)

- **Repo**: `transparenta-locala/transparenta-pantelimon`, publicat pe GitHub Pages.
- **Script principal**: `monitor_pantelimon.py` — rulează lunar automat (probabil GitHub
  Actions; verifică `.github/workflows/`). Face scraping pe SEAP + transparenta.eu, aplică
  5 algoritmi de detecție nereguli, generează `raport_transparenta.html`.
- **Pagini**:
  - `index.html` — landing page (static, scris manual).
  - `transparenta_pantelimon.html` — analize bugetare cu grafice (static).
  - `raport_transparenta.html` — generat automat de Python.
- **enhance.js** (deja livrat) — strat de progressive enhancement încărcat pe toate paginile.
  Adaugă nav unificat, search/filtre/export pe raport, widget rezumat. Detectează cardurile
  prin heuristici text (`CRITIC`/`MAJOR`/`MEDIU`). NU strica detecția cardurilor.

---

## CUPRINS

- [Faza 0 — Investigare](#faza-0)
- [Faza 1 — Quick wins (SEO, RSS, banner)](#faza-1)
  - [G. SEO + Open Graph](#g-seo--open-graph)
  - [H. RSS / Atom feed](#h-rss--atom-feed)
  - [I. Banner „ce e nou"](#i-banner-ce-e-nou)
- [Faza 2 — Refactor structural](#faza-2)
  - [A. Markup semantic pe carduri](#a-markup-semantic-pe-carduri)
  - [B. JSON embedded + endpoint API](#b-json-embedded--endpoint-api)
- [Faza 3 — Pagini noi & features](#faza-3)
  - [D. Pagină dedicată per furnizor](#d-pagină-per-furnizor)
  - [E. Scor de transparență](#e-scor-de-transparență)
- [Faza 4 — Strategic](#faza-4)
  - [F. Comparator multi-localitate](#f-comparator)
  - [C. Lazy loading carduri pe mobil](#c-lazy-loading)
- [Faza 5 — Profilare risc firme & finanțări](#faza-5)
  - [J. Detector firmă-fantomă (shell company alerts)](#j-shell-detector)
  - [K. Analiză rețea firme (network analysis)](#k-network-analysis)
  - [L. Tracking proiecte EU & PNRR](#l-fonduri-europene)

---

<a id="faza-0"></a>
## Faza 0 — Investigare (obligatorie, ~30 min)

Înainte de orice modificare de cod, fă raportul ăsta și arată-l userului:

1. Deschide `monitor_pantelimon.py` și răspunde:
   - Cum se numește funcția care generează HTML-ul (probabil `genereaza_raport_html`)?
   - Cum sunt stocate neregulile intern? (listă de dicționare? listă de obiecte? clase?)
   - Ce câmpuri are o nereguă în Python? Listează-le exact: nume + tip.
   - Unde se află template-ul HTML — e f-string, Jinja, sau string concatenation?
   - Există deja un fișier de output cu datele brute (JSON, CSV)?
   - Există funcție de comparare cu raportul anterior (pentru diff lunar)?
2. Deschide `.github/workflows/` (dacă există):
   - Ce workflow rulează lunar? Cum se numește?
   - Pe ce schedule (cron)?
   - Există secret-uri / env vars folosite?
3. Verifică dependențe:
   - Există `requirements.txt`? Listează pachetele.
   - Există `pyproject.toml`?

**Output așteptat**: un mesaj de ~200 cuvinte pentru user cu toate răspunsurile de mai sus.
Pe baza lor decidem împreună de unde să începem.

---

<a id="faza-1"></a>
## Faza 1 — Quick wins (~2 ore total)

Modificări mici, vizibile imediat, cu risc minim. Nu schimbă structura datelor.

---

### G. SEO + Open Graph

**De ce**: site-ul nu apare bine pe Google și share-urile pe Facebook arată fără imagine.

**Fișiere modificate**:
- `index.html` — direct
- `transparenta_pantelimon.html` — direct
- `monitor_pantelimon.py` — funcția care generează `<head>` (din raport)

**Implementare**:

1. Adaugă în `<head>` pe toate cele 3 pagini, după `<meta name="viewport">`:

   ```html
   <!-- SEO -->
   <meta name="description" content="Monitorizare cetățenească a Primăriei Pantelimon: nereguli detectate automat în achiziții publice. Date din SEAP și ANAF.">
   <meta name="keywords" content="transparență, Pantelimon, primărie, achiziții publice, SEAP, ANAF, monitorizare cetățenească, Ilfov">
   <meta name="author" content="Inițiativă cetățenească independentă">
   <link rel="canonical" href="https://transparenta-pantelimon.eu/{filename}">

   <!-- Open Graph (Facebook, LinkedIn) -->
   <meta property="og:type" content="website">
   <meta property="og:url" content="https://transparenta-pantelimon.eu/{filename}">
   <meta property="og:title" content="{TITLU_SPECIFIC_PAGINII}">
   <meta property="og:description" content="{DESCRIERE_SPECIFICĂ}">
   <meta property="og:image" content="https://transparenta-pantelimon.eu/og-image.png">
   <meta property="og:locale" content="ro_RO">
   <meta property="og:site_name" content="Transparența Pantelimon">

   <!-- Twitter -->
   <meta name="twitter:card" content="summary_large_image">
   <meta name="twitter:title" content="{TITLU}">
   <meta name="twitter:description" content="{DESCRIERE}">
   <meta name="twitter:image" content="https://transparenta-pantelimon.eu/og-image.png">
   ```

   Înlocuiește `{filename}`, `{TITLU_SPECIFIC_PAGINII}`, `{DESCRIERE_SPECIFICĂ}` cu valori
   reale per pagină:

   | Pagină | Titlu | Descriere |
   |---|---|---|
   | index.html | Transparența Banului Public — Primăria Pantelimon | Monitorizăm cheltuielile administrației locale. {N} nereguli detectate, {M} contracte analizate, {V} mil. RON. |
   | raport | Raport Transparență — {N} Nereguli Detectate | {N_CRITIC} critice, {N_MAJOR} majore. Achiziții directe peste prag, fragmentare contracte, ofertanți unici. |
   | transparenta_pantelimon | Buget vs. Realizat — Primăria Pantelimon | Grafice interactive: execuție bugetară pe capitole, evoluție 2020–2025, structura cheltuielilor. |

   Pe raport, numerele sunt deja calculate în Python — folosește variabilele existente
   (ex: `len(nereguli)`, `sum(1 for n in nereguli if n.severitate == 'CRITIC')`).

2. **Imaginea og-image.png** (1200x630px) — nu o avem. Două opțiuni:
   - **Opțiune simplă (recomandată pentru această fază)**: omite `og:image` deocamdată,
     adaugă-l în Faza 3 când avem timp să-l generăm.
   - **Opțiune ambițioasă**: generează-l automat în Python cu Pillow, având KPI-urile
     curente. Schiță cod în secțiunea „extras" la sfârșit.

3. Adaugă `sitemap.xml` în rădăcina repo-ului:

   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
     <url>
       <loc>https://transparenta-pantelimon.eu/</loc>
       <changefreq>monthly</changefreq>
       <priority>1.0</priority>
     </url>
     <url>
       <loc>https://transparenta-pantelimon.eu/raport_transparenta.html</loc>
       <changefreq>monthly</changefreq>
       <priority>0.9</priority>
     </url>
     <url>
       <loc>https://transparenta-pantelimon.eu/transparenta_pantelimon.html</loc>
       <changefreq>monthly</changefreq>
       <priority>0.8</priority>
     </url>
   </urlset>
   ```

4. Adaugă `robots.txt`:

   ```
   User-agent: *
   Allow: /
   Sitemap: https://transparenta-pantelimon.eu/sitemap.xml
   ```

**Verificare**:
- Pe Google Search Console după 2-3 zile.
- Live test: deschide `https://www.opengraph.xyz/url/https%3A%2F%2Ftransparenta-pantelimon.eu%2F`
  și verifică preview-ul.

**Commit**: `feat(seo): adaugă meta tags Open Graph + sitemap + robots.txt`

---

### H. RSS / Atom feed

**De ce**: jurnaliștii și activiștii care folosesc Feedly/Inoreader pot urmări automat
noile nereguli detectate.

**Fișier nou**: `feed.xml` (generat de `monitor_pantelimon.py`).

**Implementare**:

1. În `monitor_pantelimon.py`, după generarea raportului HTML, adaugă funcția:

   ```python
   def genereaza_feed_atom(nereguli, data_generare):
       """Generează feed Atom cu cele mai noi N=20 nereguli."""
       from datetime import datetime, timezone
       import html

       BASE = "https://transparenta-pantelimon.eu"
       updated = data_generare.astimezone(timezone.utc).isoformat()

       # Sortăm: CRITIC întâi, apoi MAJOR, apoi MEDIU
       sev_order = {"CRITIC": 0, "MAJOR": 1, "MEDIU": 2}
       sorted_nereguli = sorted(
           nereguli,
           key=lambda n: (sev_order.get(n["severitate"], 99), -n.get("suma", 0))
       )[:20]

       entries = []
       for i, n in enumerate(sorted_nereguli, 1):
           titlu = html.escape(n.get("titlu", "Nereguă"))
           sev = n.get("severitate", "MEDIU")
           furnizor = html.escape(n.get("furnizor", ""))
           suma = n.get("suma", 0)
           descriere = html.escape(n.get("descriere", ""))[:500]
           url = f"{BASE}/raport_transparenta.html#nereguli-{i}"

           entries.append(f"""  <entry>
       <title>[{sev}] {titlu}</title>
       <link href="{url}"/>
       <id>{url}</id>
       <updated>{updated}</updated>
       <summary type="html">&lt;p&gt;&lt;strong&gt;Furnizor:&lt;/strong&gt; {furnizor}&lt;br/&gt;&lt;strong&gt;Sumă:&lt;/strong&gt; {suma:,} RON&lt;/p&gt;&lt;p&gt;{descriere}&lt;/p&gt;</summary>
     </entry>""")

       feed = f"""<?xml version="1.0" encoding="UTF-8"?>
   <feed xmlns="http://www.w3.org/2005/Atom">
     <title>Transparența Pantelimon — Nereguli detectate</title>
     <subtitle>Monitorizare cetățenească automată</subtitle>
     <link href="{BASE}/feed.xml" rel="self"/>
     <link href="{BASE}/raport_transparenta.html"/>
     <updated>{updated}</updated>
     <id>{BASE}/feed.xml</id>
     <author><name>Inițiativă cetățenească</name></author>
   {chr(10).join(entries)}
   </feed>
   """
       return feed

   # … apoi în funcția principală:
   with open("feed.xml", "w", encoding="utf-8") as f:
       f.write(genereaza_feed_atom(nereguli, datetime.now()))
   ```

   Adaptează numele câmpurilor (`n["titlu"]`, `n["severitate"]` etc.) la cele reale
   găsite în Faza 0.

2. În `<head>` pe toate cele 3 pagini, adaugă:

   ```html
   <link rel="alternate" type="application/atom+xml" title="Nereguli Pantelimon" href="/transparenta-pantelimon/feed.xml">
   ```

3. În `index.html` și pe footerul raportului, adaugă un link vizibil:

   ```html
   <a href="feed.xml">📡 RSS / Atom feed</a>
   ```

**Verificare**:
- Validează `feed.xml` la https://validator.w3.org/feed/
- Adaugă feed-ul în Feedly.

**Commit**: `feat(feed): adaugă feed Atom cu top 20 nereguli`

---

### I. Banner „ce e nou"

**De ce**: utilizatorii recurenți vor să vadă imediat ce s-a schimbat luna asta.

**Pre-condiție**: `monitor_pantelimon.py` trebuie să compare deja cu raportul anterior
(verifică în Faza 0). Dacă nu, sari peste această secțiune până implementăm diff-ul.

**Implementare**:

1. În `monitor_pantelimon.py`, după calculul diff-ului, salvează un mic JSON:

   ```python
   delta = {
       "data_curenta": data_generare.isoformat(),
       "data_anterioara": data_raport_precedent.isoformat() if data_raport_precedent else None,
       "nereguli_noi": len(nereguli_noi),
       "nereguli_rezolvate": len(nereguli_disparute),
       "scor_anterior": scor_anterior,  # dacă faci și Faza E
       "scor_curent": scor_curent,
       "top_noi": [
           {"titlu": n["titlu"], "severitate": n["severitate"], "index": i}
           for i, n in enumerate(nereguli_noi[:3], 1)
       ],
   }
   with open("delta.json", "w", encoding="utf-8") as f:
       json.dump(delta, f, ensure_ascii=False, indent=2)
   ```

2. În `enhance.js`, adaugă o funcție care încearcă să fetcheze `delta.json` la load
   și afișează banner dacă există nereguli noi:

   ```javascript
   // adaugă în boot()
   showWhatsNewBanner();

   async function showWhatsNewBanner() {
     try {
       const r = await fetch('delta.json', { cache: 'no-store' });
       if (!r.ok) return;
       const d = await r.json();
       if (!d.nereguli_noi || d.nereguli_noi === 0) return;

       const dismissedFor = localStorage.getItem('tp-banner-dismissed');
       if (dismissedFor === d.data_curenta) return;

       const banner = document.createElement('div');
       banner.className = 'tp-banner-whats-new';
       banner.innerHTML = `
         <strong>🚩 ${d.nereguli_noi} nereguli noi</strong>
         detectate față de raportul anterior
         <a href="raport_transparenta.html#nereguli-1">vezi raportul →</a>
         <button class="tp-banner-close" aria-label="Închide">×</button>
       `;
       banner.querySelector('.tp-banner-close').addEventListener('click', () => {
         localStorage.setItem('tp-banner-dismissed', d.data_curenta);
         banner.remove();
       });
       document.body.insertBefore(banner, document.body.firstChild);
     } catch (e) { /* fail silently */ }
   }
   ```

   Și CSS-ul aferent în secțiunea CSS din `enhance.js`:

   ```css
   .tp-banner-whats-new {
     background: var(--tp-accent); color: #fff;
     padding: .6rem 1rem; text-align: center;
     position: relative;
   }
   .tp-banner-whats-new a { color: #fff; text-decoration: underline; }
   .tp-banner-close {
     position: absolute; right: 1rem; top: 50%;
     transform: translateY(-50%);
     background: transparent; border: 0; color: #fff;
     font-size: 1.4rem; cursor: pointer;
   }
   ```

**Verificare**:
- După rularea Python, deschide site-ul cu cache curat → banner apare.
- Click pe X → banner dispare și nu reapare la refresh (până la următoarea rulare).

**Commit-uri**:
- `feat(delta): exportă delta.json cu diff față de raportul anterior`
- `feat(enhance): banner "ce e nou" pe index și raport`

---

<a id="faza-2"></a>
## Faza 2 — Refactor structural (~4 ore)

Schimbări mai mari în generatorul Python care unele beneficii de durată:
parsare fără regex, indexare ușoară, date reutilizabile.

**⚠️ ATENȚIE**: Aceste schimbări pot strica detecția cardurilor în `enhance.js`. Lucrează
în ordine: întâi A (markup semantic), apoi imediat adaptează `enhance.js` să folosească
noile clase/data attributes, apoi B (JSON embedded).

---

### A. Markup semantic pe carduri

**Înainte** (estimat — verifică în Faza 0):
```html
<details>
  <summary>🔴 <strong>CRITIC</strong> Achiziție directă peste pragul legal</summary>
  📋 ID 💰 880.000 RON 🏢 MIDAS ROAD S.R.L. 📅 03.04.2024
</details>
```

**După**:
```html
<details class="tp-flag"
         data-severity="CRITIC"
         data-supplier="MIDAS ROAD S.R.L."
         data-supplier-cif="RO12345678"
         data-sum-ron="880000"
         data-date="2024-04-03"
         data-contract-id="CT-2024-001"
         data-procedure="achizitie-directa"
         data-law-ref="L98/2016 art.7"
         id="nereguli-1">
  <summary>
    <span class="sev-badge sev-critic" aria-label="Severitate critică">CRITIC</span>
    <span class="flag-title">Achiziție directă peste pragul legal</span>
  </summary>
  <dl class="flag-meta">
    <dt>Cod contract</dt>  <dd>CT-2024-001</dd>
    <dt>Furnizor</dt>       <dd>MIDAS ROAD S.R.L.</dd>
    <dt>CUI furnizor</dt>   <dd>RO12345678</dd>
    <dt>Sumă</dt>           <dd>880.000 RON</dd>
    <dt>Dată</dt>           <dd>03.04.2024</dd>
    <dt>Procedură</dt>      <dd>Achiziție directă</dd>
    <dt>Lege încălcată</dt> <dd>L98/2016 art.7</dd>
  </dl>
  <p class="flag-explanation">…</p>
  <div class="flag-actions">
    <a href="https://e-licitatie.ro/pub/..." target="_blank" rel="noopener">🔍 Deschide în SEAP</a>
    …
  </div>
</details>
```

**Implementare**:

1. În `monitor_pantelimon.py`, modifică funcția care emite HTML-ul per nereguă.
   Localizează blocul (probabil f-string în `genereaza_raport_html`) și transformă-l
   conform schemei de mai sus.
2. Adaugă CSS pentru noile clase. Pune-l în `<style>` în template-ul HTML sau într-un
   `assets/style.css` separat (recomandat):

   ```css
   .tp-flag { margin: .5rem 0; border: 1px solid #e5e7eb; border-radius: 8px; padding: .75rem 1rem; background: #fff; }
   .tp-flag[data-severity="CRITIC"] { border-left: 4px solid #dc2626; }
   .tp-flag[data-severity="MAJOR"]  { border-left: 4px solid #f59e0b; }
   .tp-flag[data-severity="MEDIU"]  { border-left: 4px solid #eab308; }

   .sev-badge { display: inline-block; padding: .15rem .6rem; border-radius: 999px; font-size: .75rem; font-weight: 700; }
   .sev-critic { background: #fef2f2; color: #dc2626; }
   .sev-major  { background: #fffbeb; color: #b45309; }
   .sev-mediu  { background: #fefce8; color: #854d0e; }

   .flag-title { margin-left: .5rem; font-weight: 600; }
   .flag-meta { display: grid; grid-template-columns: max-content 1fr; gap: .25rem .75rem; margin: .75rem 0; font-size: .9rem; }
   .flag-meta dt { color: #6b7280; }
   .flag-meta dd { margin: 0; color: #1a1a1a; }
   .flag-actions { display: flex; gap: .5rem; flex-wrap: wrap; margin-top: .5rem; }
   .flag-actions a { padding: .35rem .75rem; background: #f3f4f6; border-radius: 6px; text-decoration: none; color: #1a1a1a; font-size: .85rem; }
   ```

3. **Adaptează `enhance.js`** — în funcția `detectCards()` adaugă strategie prioritară:

   ```javascript
   function detectCards() {
     // Strategie 0 (NOUĂ): clase semantice explicite
     let cards = $$('.tp-flag');
     if (cards.length >= 5) return cards;

     // … restul strategiilor existente rămân fallback
   }
   ```

   În `parseCard()` adaugă cale rapidă care folosește data attributes:

   ```javascript
   function parseCard(el, idx) {
     // Cale rapidă: dacă elementul are data attributes, folosește-le
     if (el.dataset.severity) {
       return {
         idx, el,
         severity: el.dataset.severity,
         title: el.querySelector('.flag-title')?.textContent.trim() || '',
         supplier: el.dataset.supplier || '',
         supplierCif: el.dataset.supplierCif || '',
         sum: parseFloat(el.dataset.sumRon || '0') || 0,
         date: el.dataset.date || '',
         contract: el.dataset.contractId || '',
         procedure: el.dataset.procedure || '',
         lawRef: el.dataset.lawRef || '',
         haystack: el.textContent.toLowerCase().slice(0, 4000),
       };
     }
     // … cale veche (regex) rămâne fallback
   }
   ```

**Verificare**:
- Rulează `monitor_pantelimon.py` local cu un sample mic de date (sau folosește un mock).
- Verifică HTML-ul generat — toate atributele `data-*` populate corect.
- Deschide local cu enhance.js — confirmă că filtrele funcționează.

**Commit-uri**:
- `refactor(report): markup semantic cu data attributes pe carduri`
- `feat(enhance): folosește data attributes pentru parsing card-uri (cale rapidă)`

---

### B. JSON embedded + endpoint API

**De ce**:
- `enhance.js` nu mai face parse din DOM — citește JSON-ul direct (rapid, fără bug-uri).
- `raport.json` ca fișier separat devine endpoint public — jurnaliști, cercetători,
  cetățeni îl pot folosi în propriile tool-uri.
- Permite Faza 3 (pagini per furnizor, scor).

**Implementare**:

1. În `monitor_pantelimon.py`, scrie un dump JSON al neregulilor și totalurilor:

   ```python
   raport_json = {
       "schema_version": "1.0",
       "generated_at": data_generare.isoformat(),
       "entity": {
           "name": "Primăria Pantelimon",
           "cif": "4420759",
           "judet": "Ilfov",
       },
       "totals": {
           "flags": len(nereguli),
           "contracts_analyzed": numar_contracte,
           "total_value_ron": valoare_totala,
           "by_severity": {
               "CRITIC": sum(1 for n in nereguli if n["severitate"] == "CRITIC"),
               "MAJOR":  sum(1 for n in nereguli if n["severitate"] == "MAJOR"),
               "MEDIU":  sum(1 for n in nereguli if n["severitate"] == "MEDIU"),
           },
       },
       "flags": [
           {
               "id": i,
               "severity": n["severitate"],
               "title": n["titlu"],
               "explanation": n.get("descriere", ""),
               "supplier": n.get("furnizor", ""),
               "supplier_cif": n.get("cif_furnizor", ""),
               "sum_ron": n.get("suma", 0),
               "date": n.get("data", ""),
               "contract_id": n.get("cod_contract", ""),
               "procedure": n.get("procedura", ""),
               "law_refs": n.get("legi", []),
               "seap_url": n.get("url_seap", ""),
               "anchor": f"nereguli-{i}",
           }
           for i, n in enumerate(nereguli, 1)
       ],
   }

   # 1. Salvează ca fișier separat
   with open("raport.json", "w", encoding="utf-8") as f:
       json.dump(raport_json, f, ensure_ascii=False, indent=2)

   # 2. Embed în HTML (script tag)
   raport_json_embedded = json.dumps(raport_json, ensure_ascii=False)
   ```

   Și în template-ul HTML din `genereaza_raport_html`, înainte de `</body>`:

   ```html
   <script type="application/json" id="tp-data">{raport_json_embedded}</script>
   ```

2. **Adaptează `enhance.js`** — adaugă o funcție care preferă JSON-ul peste DOM parsing:

   ```javascript
   function loadDataFromJson() {
     const tag = document.getElementById('tp-data');
     if (!tag) return null;
     try {
       const data = JSON.parse(tag.textContent);
       return data.flags.map((f, i) => ({
         idx: i,
         el: document.getElementById(f.anchor) || null,
         severity: f.severity,
         title: f.title,
         supplier: f.supplier,
         sum: f.sum_ron,
         date: f.date,
         contract: f.contract_id,
         haystack: (f.title + ' ' + f.supplier + ' ' + f.explanation + ' ' + (f.law_refs || []).join(' ')).toLowerCase(),
       }));
     } catch (e) {
       console.warn('[tp-enhance] tp-data invalid JSON, fallback la DOM parsing.');
       return null;
     }
   }

   // în enhanceReport():
   const items = loadDataFromJson() || cardEls.map((el, i) => parseCard(el, i));
   ```

3. Documentează schema JSON într-un fișier `API.md`:

   ```markdown
   # API public — transparenta-pantelimon

   ## raport.json
   URL: https://transparenta-pantelimon.eu/raport.json
   Schema: vezi mai jos.
   Frecvență: actualizat lunar.
   Licență: Creative Commons CC-BY 4.0 (atribuire la inițiativa cetățenească).

   ```json
   {
     "schema_version": "1.0",
     …
   }
   ```
   ```

**Verificare**:
- `python -c "import json; json.load(open('raport.json'))"` → exit 0.
- Validează schema mental.
- Deschide site-ul, verifică în DevTools că `enhance.js` găsește `tp-data`.

**Commit-uri**:
- `feat(data): exportă raport.json (schema v1.0) ca endpoint public`
- `feat(report): embed raport.json în pagina raportului (script tag tp-data)`
- `feat(enhance): citește datele din tp-data în loc de regex pe DOM`
- `docs(api): documentează schema raport.json în API.md`

---

<a id="faza-3"></a>
## Faza 3 — Pagini noi & features (~1-2 zile per feature)

**Pre-condiție**: Faza 2 trebuie să fie completă (avem raport.json).

---

### D. Pagină per furnizor

**De ce**: SEO bun (căutarea „MIDAS ROAD Pantelimon" pe Google duce direct la dosar);
partajabil pe Facebook / către jurnaliști.

**Implementare**:

1. În `monitor_pantelimon.py`, după generarea raportului, identifică furnizorii cu ≥3
   contracte:

   ```python
   from collections import defaultdict
   import re

   def slugify(s):
       s = re.sub(r'[^a-zA-Z0-9À-ſ\s-]', '', s).strip().lower()
       s = re.sub(r'\s+', '-', s)
       return s[:60]

   furnizori = defaultdict(list)
   for n in nereguli:
       if n.get("furnizor"):
           furnizori[n["furnizor"]].append(n)

   import os
   os.makedirs("furnizori", exist_ok=True)

   index_furnizori = []
   for nume, contracte in furnizori.items():
       if len(contracte) < 3:
           continue
       slug = slugify(nume)
       valoare_totala = sum(c.get("suma", 0) for c in contracte)
       html = genereaza_pagina_furnizor(nume, slug, contracte, valoare_totala)
       with open(f"furnizori/{slug}.html", "w", encoding="utf-8") as f:
           f.write(html)
       index_furnizori.append({
           "nume": nume, "slug": slug,
           "count": len(contracte), "valoare": valoare_totala,
       })

   # generează și un index al furnizorilor
   genereaza_index_furnizori(index_furnizori)
   ```

2. Funcția `genereaza_pagina_furnizor` produce HTML cu:
   - Header: nume firmă, CUI, total contracte, valoare totală.
   - Cronologie contracte (cele mai noi sus).
   - Listă completă de nereguli detectate (carduri identice cu cele din raport).
   - Link spre profilul oficial ONRC (`https://termene.ro/firma/{cif}`).
   - Meta OG cu numele firmei (vezi G).
   - `<script src="../enhance.js" defer></script>` (path relativ corect).

3. Adaugă `furnizori/index.html` cu listă A-Z + filtre după număr/valoare contracte.

4. Pe `raport_transparenta.html`, fiecare card cu furnizor cunoscut link-uiește spre
   pagina sa: `<a href="furnizori/midas-road.html">MIDAS ROAD S.R.L.</a>`.

5. Adaugă în `sitemap.xml` o intrare per furnizor.

**Verificare**:
- Deschide o pagină furnizor — toate cardurile relevante apar.
- Link-urile spre ONRC/SEAP merg.
- Google Search Console reindexează în 1-2 zile.

**Commit-uri**:
- `feat(suppliers): generează pagină dedicată per furnizor cu ≥3 contracte`
- `feat(suppliers): index A-Z al furnizorilor`
- `feat(seo): include paginile furnizorilor în sitemap`

---

### E. Scor de transparență

**De ce**: dă presei un titlu de prins din zbor — „Scorul de transparență al Pantelimon
a scăzut de la 62 la 47 în mai 2026".

**Atenție**: scorul e o **decizie subiectivă** despre cum ponderezi cele 5 algoritmi.
Înainte de implementare, **întreabă userul** ce ponderi vrea. Sugestie de pornire:

| Indicator | Pondere | Calcul |
|---|---|---|
| Achiziții directe peste prag (CRITIC) | 30% | `100 - min(100, n_critic * 3)` |
| Ofertant unic dominant | 20% | bazat pe % contracte cu top-3 furnizori |
| Ședințe extraordinare | 15% | `100 - procent_extraordinare` |
| Fragmentare contracte | 15% | bazat pe nr. cazuri |
| Documente publicate | 10% | dacă pagina financiară e populată |
| Răspuns la cereri 544/2001 | 10% | manual, default 50 |
| **Total** | **100%** | medie ponderată |

**Implementare**:

1. Adaugă funcție în Python:

   ```python
   def calculeaza_scor_transparenta(nereguli, n_contracte, ...):
       scoruri = {}
       n_crit = sum(1 for n in nereguli if n["severitate"] == "CRITIC")
       scoruri["achizitii_directe"] = max(0, 100 - n_crit * 3)
       # ... restul
       scor_final = sum(s * pondere[k] for k, s in scoruri.items())
       return {"scor": round(scor_final), "componente": scoruri}
   ```

2. Salvează istoricul în `istoric_scor.json`:

   ```json
   {
     "puncte": [
       { "data": "2026-03-15", "scor": 52 },
       { "data": "2026-04-15", "scor": 49 },
       { "data": "2026-05-15", "scor": 47 }
     ]
   }
   ```

3. Pe `index.html` adaugă un widget mare cu scorul + mini-grafic cu istoricul
   (folosește Chart.js sau SVG inline).

4. Pune scorul și în `raport.json` și în `delta.json`.

**Verificare**:
- Calculează manual pentru un sample → confirmă cifrele.
- Userul aprobă ponderile înainte de a face commit.

**Commit-uri**:
- `feat(score): introduce scor de transparență (componente A-F)`
- `feat(score): istoric scor în istoric_scor.json + widget pe index`

---

<a id="faza-4"></a>
## Faza 4 — Strategic (necesită planificare separată)

---

### F. Comparator multi-localitate

**De ce**: Replicabilitate. Codul tău Python funcționează pentru orice CIF de primărie —
poți extinde la Voluntari, Popești-Leordeni, alte comune din Ilfov, etc.

**Nu ataca această fază fără discuție cu userul.** Necesită:
- Decizii de design (un singur site cu multi-locație vs. site per localitate).
- Listă explicită de localități + CIF-uri.
- Decizii despre branding (Transparența România? Transparența Ilfov?).
- Posibilă infrastructură separată (custom domain, multi-tenant).

**Output așteptat din această fază** (dacă userul o aprobă): un document de design,
nu cod. Cod abia după ce designul e validat.

---

### C. Lazy loading carduri pe mobil

**De ce**: 216 carduri într-un singur DOM = scroll lag pe mobile vechi.

**Pre-condiție**: măsoară întâi. Deschide pagina pe un telefon real / DevTools mobile
mode (4G throttle, CPU 4x slowdown) și vezi dacă există lag perceptibil. Dacă nu, nu
implementa — e premature optimization.

**Dacă este nevoie**:
- Generează în Python doar primele 25 carduri în HTML.
- Restul intră în `raport.json` (deja există după Faza 2).
- `enhance.js` rendererează la cerere când userul dă „Load more" sau aplică un filtru
  care le-ar afișa.

**Commit-uri**:
- `perf(mobile): generează doar primele 25 carduri în HTML, restul lazy`
- `feat(enhance): rendering lazy din raport.json pentru cardurile dincolo de prag`

---

<a id="faza-5"></a>
## Faza 5 — Profilare risc firme & finanțări (proiect mare, ~2-4 săptămâni)

**Context**: până acum scriptul analizează doar comportamentul primăriei (cum atribuie
contracte). Faza 5 mută focusul către **cui** atribuie — adaugă context despre firmele
care primesc bani publici. Aici devine instrument de investigație jurnalistică propriu-zisă.

**ATENȚIE — 4 considerente critice pentru tot ce urmează**:

1. **Risc juridic.** Etichetarea unei firme ca „suspectă" / „fantomă" / „parte din rețea"
   poate fi calomnie dacă nu e suportată de date factuale neutre. Regulă de aur:
   afișează **fapte**, nu **interpretări**. „0 angajați declarați la ANAF" e fapt.
   „Firmă-fantomă" e interpretare — lasă cititorul să o tragă.

2. **GDPR.** Numele administratorilor sunt date personale. Publicarea în interes public
   (transparență bani publici) e legală sub Art. 6(1)(e) GDPR + Legea 363/2018, dar
   adaugă pe site o politică de confidențialitate care invocă explicit această bază
   legală și un mecanism de contact pentru rectificare.

3. **Surse plătite vs gratuite.** ONRC oficial = API plătit (zeci de RON/lookup).
   termene.ro = scraping gratuit, dar limite și schimbări frecvente de HTML.
   listafirme.ro = idem. data.gov.ro = gratuit dar inconsistent. Userul trebuie să
   decidă bugetul înainte de implementare.

4. **Calitatea datelor.** Date stale (admin se schimbă lunar), false-positive la
   name-matching („Ion Popescu" e un nume comun), date lipsă (cifra de afaceri publicată
   cu 1 an decalaj). Toate features-urile de aici sunt **probabilistice**, nu definitive.

**ÎNTREBĂRI DESCHISE PENTRU USER** (Claude Code: cere răspunsuri înainte de orice implementare):

- Q1. **Buget pentru date plătite?** ONRC API costă ~5–15 RON/lookup. La 50 firme/lună =
  ~500 RON/lună. Acceptabil sau mergem doar pe scraping gratuit?
- Q2. **Tonul scoring-ului**: neutru-factual („0 angajați, înființată în 2024") sau
  evaluativ („Risc ridicat de firmă-fantomă")? Recomand strict neutru. Confirmi?
- Q3. **Pentru rețele de firme**: pagină dedicată cu graf interactiv, sau doar widget
  pe pagina fiecărui furnizor?
- Q4. **Mențiunile media (scandaluri)**: curatorial manual (tu adaugi link-uri într-un
  fișier) sau automatizat (Google News API)? Automatul are risc mare de false-positive.
- Q5. **Fonduri europene**: tracking doar pe Pantelimon, sau extins la toate primăriile
  monitorizate (dacă faci Faza 4-F)?

---

<a id="j-shell-detector"></a>
### J. Detector firmă-fantomă (shell company alerts)

**De ce**: o firmă creată cu 4 luni înainte de a câștiga un contract de 1 mil. RON, cu
0 angajați, e un indicator factual care merită semnalat.

**Surse de date (în ordinea calității)**:

| Sursă | Cost | Conține | Limită |
|---|---|---|---|
| **ONRC** (api.onrc.ro) | plătit | Date oficiale, înființare, capital, administratori, status | Cost per lookup |
| **termene.ro** | gratuit (scraping) | Aceleași date, cu 1-7 zile decalaj | Risc blocare IP, HTML poate schimba |
| **listafirme.ro** | gratuit | Similar | Idem |
| **ANAF — declarații financiare** | gratuit | Cifră afaceri, profit/pierdere, **nr. salariați** | Decalaj 6-12 luni |
| **mfinante.ro** | gratuit | Datorii bugetare | Decalaj |
| **risco.ro** | freemium | Indicatori risc agregat | Limitat free |

**Strategia recomandată**:
- **Primary**: termene.ro (gratuit, date publice). Cache local agresiv (sqlite).
- **Backup**: listafirme.ro dacă termene.ro pică.
- **Pentru angajați**: ANAF — endpoint public pentru numărul mediu de salariați din
  declarațiile fiscale (există pe `mfinante.ro` la „Indicatori din situațiile financiare").

**Indicatori de risc (toți factual-neutri)**:

| Cod | Descriere | Severitate |
|---|---|---|
| FIRMA_NOUA | Înființată cu <6 luni înainte de atribuirea contractului | CRITIC |
| FIRMA_NOUA_1AN | Înființată cu <12 luni înainte | MAJOR |
| ZERO_ANGAJATI | 0 salariați în ultima declarație disponibilă | MAJOR |
| FEW_EMPLOYEES | 1–2 salariați declarați | MEDIU |
| ZERO_REVENUE | Cifră de afaceri 0 în anul anterior contractului | MAJOR |
| CAPITAL_MINIM | Capital social = 200 RON (minim legal SRL) | MEDIU |
| SEDIU_AGLOMERAT | Sediu social la o adresă cu >10 firme (cabinet avocat/contabil) | MEDIU |
| ADMIN_RECENT | Administrator schimbat <6 luni înainte de atribuire | MEDIU |
| DEBT_FLAG | Datorii bugetare > 10% din valoare contract | MAJOR |
| INACTIV_LA_ATRIBUIRE | Status „suspendat"/"inactivă" în perioada contractului | CRITIC |

**Schema datelor noi** (extensie a `raport.json`):

```json
{
  "supplier_profile": {
    "cif": "RO12345678",
    "name": "MIDAS ROAD S.R.L.",
    "founded": "2023-11-15",
    "founded_days_before_contract": 137,
    "employees": 0,
    "employees_year": 2024,
    "share_capital_ron": 200,
    "revenue_prev_year_ron": 0,
    "address": "București, Sector 3, Strada X nr. 1",
    "address_companies_count": 47,
    "administrators": [{"name": "Ion Popescu", "since": "2023-11-15", "role": "asociat unic"}],
    "status": "active",
    "anaf_debts_ron": 0,
    "risk_flags": ["FIRMA_NOUA", "ZERO_ANGAJATI", "CAPITAL_MINIM", "SEDIU_AGLOMERAT"],
    "data_freshness": "2026-05-10",
    "sources": ["termene.ro", "mfinante.ro"]
  }
}
```

**Implementare**:

1. **Modul nou** `risc_firma.py`:
   ```python
   # API public:
   def fetch_supplier_profile(cif: str) -> dict:
       """Returnează profilul firmei. Folosește cache, retry, rate limiting."""

   def evaluate_risk_flags(profile: dict, contract_date: str, contract_value: float) -> list[dict]:
       """Returnează lista de flag-uri factuale (cod, severitate, descriere)."""
   ```

2. **Cache** local în sqlite (`firme_cache.db`) cu TTL 30 zile, ca să nu refetcham
   aceeași firmă la fiecare rulare.

3. **Rate limiting** strict: max 1 request/secundă pe termene.ro, header User-Agent
   identificator („transparenta-pantelimon bot — contact: …"), respectă robots.txt.

4. **Extinde cardul de nereguă** cu o secțiune „Profil firmă":
   ```html
   <div class="supplier-risk-panel" data-risk-count="4">
     <h4>📇 Profil firmă (date publice ONRC + ANAF)</h4>
     <dl>
       <dt>Înființată</dt> <dd>15.11.2023 <span class="risk-tag">⚠ cu doar 4 luni înainte de contract</span></dd>
       <dt>Angajați declarați</dt> <dd>0 <span class="risk-tag">⚠ în ultima declarație ANAF</span></dd>
       <dt>Capital social</dt> <dd>200 RON (minim legal)</dd>
       <dt>Adresa sediu</dt> <dd>… <span class="risk-tag">⚠ adresă cu 47 alte firme</span></dd>
       <dt>Cifră afaceri an precedent</dt> <dd>0 RON</dd>
     </dl>
     <p class="data-attribution">Surse: <a href="https://termene.ro/firma/…">termene.ro</a>, <a href="https://mfinante.ro/…">ANAF/MF</a>. Actualizat 10.05.2026.</p>
   </div>
   ```

5. **CSS** pentru risc panel (adaugă în template):
   ```css
   .supplier-risk-panel { margin: .75rem 0; padding: .75rem 1rem; background: #fff7ed; border: 1px solid #fed7aa; border-radius: 8px; }
   .supplier-risk-panel[data-risk-count="0"] { background: #f0fdf4; border-color: #bbf7d0; }
   .supplier-risk-panel dl { display: grid; grid-template-columns: max-content 1fr; gap: .25rem .75rem; margin: 0; }
   .supplier-risk-panel dt { color: #6b7280; font-size: .85rem; }
   .supplier-risk-panel dd { margin: 0; font-size: .9rem; }
   .risk-tag { display: inline-block; padding: .1rem .4rem; background: #fef2f2; color: #991b1b; border-radius: 4px; font-size: .75rem; margin-left: .4rem; }
   .data-attribution { font-size: .75rem; color: #6b7280; margin-top: .5rem; }
   ```

6. **Filtru nou în enhance.js** — un chip „🏢 Doar firme noi (<1 an)" și „🏢 Doar firme
   cu 0 angajați". Adaugă în toolbar (vezi structura existentă).

7. **Disclaimer** vizibil pe pagină:
   > „Profilurile firmelor afișează date publice de la ONRC și ANAF. Faptele
   > prezentate (data înființării, număr angajați, etc.) sunt obiective. Concluziile
   > rămân la latitudinea cititorului."

**Limitări de comunicat utilizatorului**:
- Datele ANAF au decalaj 6-12 luni — o firmă cu „0 angajați" poate avea acum 50.
- Nu toate firmele au declarații financiare publicate.
- Numele administratorilor pot fi diferiți acum față de momentul atribuirii.

**Commit-uri**:
- `feat(risk): modul risc_firma.py — profil firmă din termene.ro + ANAF`
- `feat(risk): cache sqlite pentru profilurile firmelor (TTL 30 zile)`
- `feat(risk): 10 indicatori factuali de risc pe profil firmă`
- `feat(report): adaugă panel "Profil firmă" pe cardurile de nereguli`
- `feat(enhance): filtre noi pentru firme nou-create / 0 angajați`
- `docs: politică de confidențialitate + atribuire surse de date`

---

<a id="k-network-analysis"></a>
### K. Analiză rețea firme (network analysis)

**De ce**: o firmă singură cu 0 angajați e indicator. 5 firme cu același administrator,
toate cu 0 angajați, toate câștigând contracte la aceeași primărie = pattern.

**Provocările principale**:

1. **Name matching e nefiabil**. „Ion Popescu" administrator la firma A nu e neapărat
   aceeași persoană ca „Ion Popescu" la firma B. ONRC nu expune CNP-uri public.
   - **Strategie**: marchează „posibilă conexiune" (nu „confirmată") când numele e
     identic. Confirmarea o face jurnalistul manual.
   - **Heuristică auxiliară**: dacă două firme cu același nume admin au și sediu social
     la aceeași adresă → confidence mult mai mare.

2. **Volum date**. 50 firme × ~2 administratori = 100 lookup-uri persoane × restul
   firmelor unde apar = creștere exponențială. Trebuie:
   - Limită la firme care apar deja în raport.
   - Cache agresiv.

3. **Date stale**. Administratorii se pot schimba. Datele extrase trebuie marcate cu
   data extracției.

**Methodologie**:

1. **Extragere**: pentru fiecare firmă din raport, scoate lista administratori + asociați
   + cota deținută (de pe termene.ro).

2. **Construire graf** (NetworkX):
   - Noduri tip „firmă" (CUI ca identificator unic).
   - Noduri tip „persoană" (cheie compusă: nume normalizat + opțional CNP-uri).
   - Muchii „administrator" / „asociat" / „împuternicit" cu greutate = cotă deținută.

3. **Detecție comunități**: algoritm Louvain (`python-louvain`) sau Girvan-Newman pentru
   a identifica clustere.

4. **Scoring conexiuni**:
   - **Direct A↔B**: au cel puțin un administrator comun (name match exact).
   - **Indirect A→X→B**: persoană X e administrator la A și asociat la B.
   - **Adresa comună**: 2+ firme cu același sediu social.
   - **Aceeași dată înființare**: 2+ firme înființate în aceeași săptămână cu același admin.

5. **Vizualizare**:
   - **Pagină nouă** `retea.html` cu graf interactiv (recomand **Cytoscape.js** — mai bun
     decât vis.js pentru grafe medii, mai bun decât d3-force pentru UX out-of-the-box).
   - Filtre: doar firme cu nereguli, doar conexiuni de tip X, prag minim greutate.
   - Click pe nod → side panel cu detalii + link spre pagina firmei (Faza D).

6. **Mențiuni media** (separat de graf, dar pe aceeași pagină):
   - Fișier manual `mentiuni_media.json` curatorial (tu adaugi):
     ```json
     {
       "MIDAS ROAD S.R.L.": [
         {
           "title": "Investigație rise.ro despre firmele Pantelimon",
           "url": "https://rise.ro/...",
           "date": "2026-04-12",
           "outlet": "rise.ro"
         }
       ]
     }
     ```
   - Pe pagina firmei (D) și pe graf (K), afișează cu icon 📰.
   - **NU automatiza prin Google News** — risk false-positive (omonime, articole irelevante).
     Mai bine adăugat manual, cu link sursă verificabil.

**Schema datelor noi**:

```json
{
  "network": {
    "nodes": [
      {"id": "RO12345678", "type": "company", "name": "MIDAS ROAD S.R.L.", "flags_count": 7},
      {"id": "person:ion-popescu-1", "type": "person", "name": "Ion Popescu", "companies_count": 4}
    ],
    "edges": [
      {"source": "person:ion-popescu-1", "target": "RO12345678", "role": "administrator", "since": "2023-11-15"}
    ],
    "communities": [
      {"id": 1, "members": ["RO12345678", "RO87654321"], "label": "Cluster A"}
    ],
    "data_freshness": "2026-05-10"
  }
}
```

**Implementare**:

1. **Modul nou** `retea_firme.py` cu funcțiile:
   - `build_network(suppliers: list[dict]) -> nx.Graph`
   - `detect_communities(graph) -> list[set]`
   - `export_cytoscape_json(graph) -> dict`

2. **Pagină nouă** `retea.html`:
   - Include Cytoscape.js de la CDN.
   - Layout fcose sau cola pentru aspect natural.
   - Side panel cu detalii nod.

3. **Disclaimer obligatoriu** pe pagină:
   > „Conexiunile afișate sunt bazate pe potriviri de nume în datele publice ONRC.
   > Numele identice nu garantează că este aceeași persoană. Această vizualizare
   > este un punct de pornire pentru investigație, nu o concluzie."

**Commit-uri**:
- `feat(network): modul retea_firme.py — extragere administratori + asociați`
- `feat(network): detecție comunități prin Louvain`
- `feat(network): pagină retea.html cu vizualizare Cytoscape.js`
- `feat(network): suport mențiuni media curatorial (mentiuni_media.json)`

---

<a id="l-fonduri-europene"></a>
### L. Tracking proiecte EU & PNRR

**De ce**: o mare parte din investițiile primăriei sunt cofinanțate UE. Compararea
plan-vs-realizat și a contractelor finanțate din fonduri europene cu cele detectate ca
nereguli e un unghi jurnalistic puternic.

**Surse de date**:

| Sursă | Conține | Format | Provocări |
|---|---|---|---|
| **data.gov.ro** | Dataset-uri PNRR, POR, POIM, POAT, POCU | CSV/Excel/JSON | Inconsistent, decalaj |
| **mfe.gov.ro** | Lista beneficiari oficială | HTML/PDF | Greu de scraped |
| **proiecte.pnrr.gov.ro** | Proiecte PNRR active | Tabele HTML | Necesită scraping |
| **MySMIS** | Sistemul unic de monitorizare | API plătit | Costuri mari |
| **primariapantelimon.ro** | Proiecte cu finanțare europeană | Pagini statice (dacă publică) | Format propriu |

**Strategia recomandată**:
- **Primary**: data.gov.ro pentru lista oficială.
- **Filter**: după CUI beneficiar `4420759` (Pantelimon).
- **Pentru contractele asociate**: cross-reference cu SEAP (deja avem) pe baza numelui
  proiectului.

**Indicatori per proiect**:

| Indicator | Calculat din |
|---|---|
| Nume proiect | data.gov.ro |
| Program (POR, PNRR, etc.) | data.gov.ro |
| Valoare totală contractată | data.gov.ro |
| Valoare cheltuită cumulat | data.gov.ro / MySMIS |
| % execuție bugetară | calcul: cheltuit / total |
| Stadiu fizic | dacă disponibil |
| Termen contractual | data.gov.ro |
| Întârziere (zile) | calcul: azi - termen, dacă > 0 |
| Contracte SEAP asociate | cross-ref cu raportul |
| Nereguli asociate | dintre cele 216 |
| Status risc | derived: dacă > 80% timp scurs și < 50% execuție → CRITIC |

**Schema datelor noi**:

```json
{
  "eu_projects": [
    {
      "id": "POR-2021-001",
      "name": "Reabilitare drumuri zona X",
      "program": "POR",
      "value_total_ron": 15000000,
      "value_spent_ron": 7500000,
      "execution_pct": 50,
      "start_date": "2022-01-15",
      "end_date_planned": "2025-12-31",
      "days_overdue": 0,
      "status": "in_progress",
      "linked_seap_contracts": ["CT-2023-045", "CT-2024-012"],
      "linked_flags": [12, 87],
      "risk": "MEDIU",
      "source_url": "https://data.gov.ro/dataset/...",
      "last_updated": "2026-04-30"
    }
  ]
}
```

**Implementare**:

1. **Modul nou** `fonduri_eu.py`:
   ```python
   def fetch_eu_projects(beneficiary_cif: str) -> list[dict]:
       """Caută în data.gov.ro toate proiectele cu acest beneficiar."""

   def cross_reference_with_seap(eu_projects, contracts) -> list[dict]:
       """Match-uiește proiecte EU cu contractele SEAP după nume / valori similare."""

   def evaluate_project_risk(project) -> str:
       """Returnează CRITIC / MAJOR / MEDIU / OK pe baza execuției."""
   ```

2. **Pagină nouă** `fonduri_europene.html`:
   - Tabel sortabil cu toate proiectele.
   - Coloane: Nume, Program, Valoare, Execuție %, Termen, Risc.
   - Grafic agregat: total contractat vs total cheltuit pe program.
   - Per rând, link expandabil cu contractele SEAP asociate și flag-urile detectate.

3. **Pe `index.html`**, adaugă KPI nou:
   ```
   N proiecte UE active · X mil. RON contractate · Y% execuție medie
   ```

4. **Integrare cu raport**: în cardurile de nereguli, dacă contractul e parte dintr-un
   proiect EU, adaugă tag `🇪🇺 PNRR` sau `🇪🇺 POR`.

**Provocări de comunicat**:
- data.gov.ro are coverage parțial pe Pantelimon. Posibil să nu găsim toate proiectele.
- MySMIS are date mai bune dar e plătit/limitat.
- Cross-referencing SEAP↔EU e fuzzy matching pe nume, predispus la erori.

**Commit-uri**:
- `feat(eu): modul fonduri_eu.py — fetch proiecte din data.gov.ro`
- `feat(eu): cross-reference proiecte EU cu contracte SEAP`
- `feat(eu): pagină fonduri_europene.html cu tabel + grafice`
- `feat(eu): tag-uri PNRR/POR pe cardurile de nereguli relevante`

---

## EXTRAS — generare og-image.png automată

Dacă vrei să generezi imaginea de share automat, adaugă în Python:

```python
from PIL import Image, ImageDraw, ImageFont

def genereaza_og_image(n_flags, n_critic, valoare_mil, scor=None):
    img = Image.new('RGB', (1200, 630), '#0a0a0a')
    d = ImageDraw.Draw(img)
    font_big = ImageFont.truetype("Arial.ttf", 90)
    font_med = ImageFont.truetype("Arial.ttf", 40)
    font_small = ImageFont.truetype("Arial.ttf", 28)

    d.text((60, 60), "Transparența Pantelimon", fill='#fff', font=font_med)
    d.text((60, 180), f"{n_flags} nereguli", fill='#dc2626', font=font_big)
    d.text((60, 300), f"{n_critic} CRITICE · {valoare_mil:.0f} mil. RON",
           fill='#f59e0b', font=font_med)
    if scor is not None:
        d.text((60, 480), f"Scor transparență: {scor}/100", fill='#fff', font=font_med)
    d.text((60, 570), "transparenta-pantelimon.eu",
           fill='#6b7280', font=font_small)

    img.save('og-image.png', 'PNG', optimize=True)
```

---

## REGULI FINALE

- **Nu face merge în main fără PR.** Userul revizuiește.
- **Nu rula `monitor_pantelimon.py` în CI fără aprobare explicită** — costă timp/resurse
  pe scraping SEAP.
- **Întotdeauna păstrează backward compatibility cu `enhance.js`** — strategiile vechi
  de detecție sunt fallback, nu le șterge.
- **Test pe mobil real, nu doar pe desktop.**
- **Commit `feat`-uri în engleză sau română — consistent în tot repo-ul.**
