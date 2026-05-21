/*!
 * transparenta-enhance.js  v1.0
 * Progressive enhancement pentru https://bise88.github.io/transparenta-pantelimon/
 *
 * Funcționalități:
 *   - Bară de navigare unificată pe toate paginile (Acasă / Nereguli / Buget / surse)
 *   - Pe pagina raportului: search liber, filtre severitate, dropdown furnizor,
 *     sortare, contor live, export CSV/JSON, paginare "load more" 25 deodată
 *   - Widget rezumat: top 10 furnizori după valoare/număr + bară severitate
 *   - Permalink per nereguă (#nereguli-42) — click pe titlu copiază link
 *   - Stil de print optimizat pentru salvare PDF
 *   - Back-to-top, scurtături "/" (focus search) și Esc (clear)
 *
 * Instalare: <script src="enhance.js" defer></script> înainte de </head> pe toate paginile.
 *
 * Robustețe: scriptul detectează cardurile prin pattern-uri text (nu depinde de
 * clase CSS specifice ale generatorului). Dacă structura HTML se schimbă, scriptul
 * se degradă elegant și loghează un warning în consolă.
 */
(function () {
  'use strict';

  // ──────────────────────────────────────────────────────────────
  // CONFIG
  // ──────────────────────────────────────────────────────────────
  const CFG = {
    pageSize: 25,
    storageKey: 'tp-prefs-v1',
    severityOrder: { CRITIC: 0, MAJOR: 1, MEDIU: 2 },
    severityColor: {
      CRITIC: '#dc2626',
      MAJOR:  '#f59e0b',
      MEDIU:  '#eab308',
    },
  };

  // ──────────────────────────────────────────────────────────────
  // CSS (injectat inline)
  // ──────────────────────────────────────────────────────────────
  const CSS = `
:root {
  --tp-bg:#ffffff; --tp-fg:#1a1a1a; --tp-muted:#6b7280;
  --tp-border:#e5e7eb; --tp-card-bg:#fafafa; --tp-link:#2563eb;
  --tp-accent:#dc2626; --tp-warn:#f59e0b; --tp-info:#eab308;
}
html[data-tp-theme="dark"] {
  --tp-bg:#0a0a0a; --tp-fg:#f3f4f6; --tp-muted:#9ca3af;
  --tp-border:#2a2a2a; --tp-card-bg:#141414; --tp-link:#60a5fa;
  color-scheme: dark;
}

/* Sticky nav */
.tp-nav {
  position: sticky; top: 0; z-index: 100;
  background: var(--tp-bg);
  border-bottom: 1px solid var(--tp-border);
}
.tp-nav-inner {
  max-width: 1200px; margin: 0 auto;
  padding: .55rem 1rem;
  display: flex; align-items: center; gap: .75rem; flex-wrap: wrap;
}
.tp-nav-brand {
  font-weight: 700; text-decoration: none; color: var(--tp-fg);
  white-space: nowrap; font-size: .95rem;
}
.tp-nav-links {
  display: flex; gap: .15rem; flex: 1; flex-wrap: wrap;
}
.tp-nav-links a {
  padding: .4rem .75rem; border-radius: 6px;
  text-decoration: none; color: var(--tp-fg); font-size: .88rem;
}
.tp-nav-links a:hover { background: var(--tp-card-bg); }
.tp-nav-links a.active { background: var(--tp-accent); color: #fff; }

/* Toolbar */
.tp-toolbar {
  position: sticky; top: 49px; z-index: 90;
  background: var(--tp-bg);
  border-bottom: 1px solid var(--tp-border);
  padding: .65rem 1rem;
}
.tp-toolbar-inner {
  max-width: 1200px; margin: 0 auto;
  display: grid; gap: .55rem;
}
.tp-toolbar-row {
  display: flex; gap: .45rem; flex-wrap: wrap; align-items: center;
}
.tp-search {
  flex: 1; min-width: 200px;
  padding: .5rem .75rem;
  border: 1px solid var(--tp-border); border-radius: 8px;
  background: var(--tp-bg); color: var(--tp-fg); font-size: .95rem;
}
.tp-search:focus { outline: 2px solid var(--tp-link); outline-offset: -1px; }
.tp-select {
  padding: .5rem .65rem;
  border: 1px solid var(--tp-border); border-radius: 8px;
  background: var(--tp-bg); color: var(--tp-fg);
  font-size: .88rem; cursor: pointer; max-width: 280px;
}
.tp-chip {
  display: inline-flex; align-items: center; gap: .3rem;
  padding: .35rem .75rem;
  border: 1px solid var(--tp-border); border-radius: 999px;
  background: var(--tp-bg); color: var(--tp-fg);
  cursor: pointer; font-size: .82rem; user-select: none;
}
.tp-chip:hover { background: var(--tp-card-bg); }
.tp-chip[data-sev="CRITIC"].active { background: #dc2626; border-color: #dc2626; color: #fff; }
.tp-chip[data-sev="MAJOR"].active  { background: #f59e0b; border-color: #f59e0b; color: #1a1a1a; }
.tp-chip[data-sev="MEDIU"].active  { background: #eab308; border-color: #eab308; color: #1a1a1a; }

.tp-btn {
  padding: .45rem .85rem;
  border: 1px solid var(--tp-border); border-radius: 6px;
  background: var(--tp-bg); color: var(--tp-fg);
  cursor: pointer; font-size: .85rem; text-decoration: none;
  display: inline-flex; align-items: center; gap: .3rem;
}
.tp-btn:hover { background: var(--tp-card-bg); }
.tp-btn-primary { background: var(--tp-accent); color: #fff; border-color: var(--tp-accent); }
.tp-btn-primary:hover { background: #b91c1c; }

.tp-stats {
  font-size: .82rem; color: var(--tp-muted);
  display: flex; gap: 1rem; flex-wrap: wrap;
}
.tp-stats strong { color: var(--tp-fg); }

/* Summary widget */
.tp-summary {
  max-width: 1200px; margin: 1rem auto; padding: 1rem;
  background: var(--tp-card-bg);
  border: 1px solid var(--tp-border); border-radius: 12px;
}
.tp-summary h3 { margin: 0 0 .75rem 0; font-size: 1rem; }
.tp-summary-grid {
  display: grid; gap: 1rem;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
}
.tp-summary-list { font-size: .85rem; }
.tp-summary-li {
  display: flex; justify-content: space-between;
  padding: .35rem 0;
  border-bottom: 1px solid var(--tp-border); gap: .5rem;
}
.tp-summary-li:last-child { border: 0; }
.tp-summary-li strong { color: var(--tp-fg); font-weight: 600; }
.tp-summary-li span.tp-muted { color: var(--tp-muted); font-size: .8rem; }
.tp-summary-bar {
  height: 22px; border-radius: 6px; overflow: hidden;
  display: flex; margin-top: .35rem;
  border: 1px solid var(--tp-border);
}
.tp-summary-bar > span {
  height: 100%;
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-size: .75rem; font-weight: 600;
}

/* Carduri */
.tp-card-hidden { display: none !important; }
.tp-card-anchor {
  margin-left: .5rem; color: var(--tp-muted);
  text-decoration: none; font-size: .8rem;
  opacity: 0; transition: opacity .15s;
}
*:hover > .tp-card-anchor { opacity: 1; }
.tp-card-anchor:hover { color: var(--tp-link); }
.tp-card-flash {
  animation: tpFlash 1.5s ease-out;
}
@keyframes tpFlash {
  0%   { background: rgba(220,38,38,.18); }
  100% { background: transparent; }
}

/* Load more / empty */
.tp-loadmore {
  max-width: 1200px; margin: 1.5rem auto;
  display: flex; justify-content: center;
}
.tp-empty {
  text-align: center; padding: 3rem 1rem;
  color: var(--tp-muted);
}

/* Back-to-top */
.tp-back-top {
  position: fixed; bottom: 1.25rem; right: 1.25rem;
  width: 44px; height: 44px; border-radius: 50%;
  border: 1px solid var(--tp-border);
  background: var(--tp-bg); color: var(--tp-fg);
  cursor: pointer; box-shadow: 0 4px 12px rgba(0,0,0,.12);
  opacity: 0; pointer-events: none;
  transition: opacity .2s;
  z-index: 50; font-size: 1.1rem;
}
.tp-back-top.visible { opacity: 1; pointer-events: auto; }

/* Mobile */
@media (max-width: 640px) {
  .tp-nav-inner { padding: .4rem .6rem; gap: .4rem; }
  .tp-nav-brand { font-size: .82rem; }
  .tp-nav-links a { padding: .35rem .55rem; font-size: .8rem; }
  .tp-toolbar { top: 52px; padding: .55rem .6rem; }
  .tp-search { font-size: 16px; } /* fără zoom iOS */
  .tp-select { max-width: 100%; flex: 1; }
}

/* Print */
@media print {
  .tp-nav, .tp-toolbar, .tp-back-top,
  .tp-loadmore, .tp-summary, .tp-banner-whats-new { display: none !important; }
  .tp-card-hidden { display: block !important; }
  .flag-detail { display: block !important; }
  .no-print { display: none !important; }
  details { page-break-inside: avoid; }
  details summary { font-weight: 700; }
  details:not([open]) > *:not(summary) { display: block !important; }
  body { font-size: 11pt; }
  a { color: inherit; text-decoration: none; }
  a[href]::after { content: " (" attr(href) ")"; font-size: 9pt; color: #555; }
  a[href^="#"]::after,
  a[href^="javascript"]::after { content: ""; }
  .tp-flag { page-break-inside: avoid; border: 1px solid #ddd !important; margin-bottom: 8pt !important; }
}

/* Banner "ce e nou" */
.tp-banner-whats-new {
  background: var(--tp-accent, #dc2626); color: #fff;
  padding: .6rem 1rem; text-align: center;
  position: relative; font-size: .9rem;
}
.tp-banner-whats-new a { color: #fff; text-decoration: underline; margin: 0 .4rem; }
.tp-banner-close {
  position: absolute; right: 1rem; top: 50%;
  transform: translateY(-50%);
  background: transparent; border: 0; color: #fff;
  font-size: 1.4rem; line-height: 1; cursor: pointer;
  padding: 0 .2rem;
}
.tp-banner-close:hover { opacity: .8; }
`;

  // ──────────────────────────────────────────────────────────────
  // UTILITARE
  // ──────────────────────────────────────────────────────────────
  const $  = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  function debounce(fn, ms) {
    let t;
    return function (...args) {
      clearTimeout(t);
      t = setTimeout(() => fn.apply(this, args), ms);
    };
  }

  function fmtRON(n) {
    if (!Number.isFinite(n) || n === 0) return '—';
    if (n >= 1e6) return (n / 1e6).toFixed(2) + ' mil. RON';
    if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K RON';
    return n.toLocaleString('ro-RO') + ' RON';
  }

  function parseSum(text) {
    // Acoperă: "880.000 RON", "1.234.567,89 lei", "17.92 mil. RON", "13,94 milioane"
    if (!text) return 0;
    const milMatch = text.match(/([\d.,]+)\s*mil(?:\.|ioane)?/i);
    if (milMatch) {
      const v = parseFloat(milMatch[1].replace(/\./g, '').replace(',', '.'));
      return Number.isFinite(v) ? v * 1e6 : 0;
    }
    const rawMatch = text.match(/([\d.,]+)\s*(?:RON|lei)/i);
    if (!rawMatch) return 0;
    let s = rawMatch[1];
    // Format RO: punct = mii, virgulă = zecimale
    if (s.includes(',')) {
      s = s.replace(/\./g, '').replace(',', '.');
    } else if (/^\d{1,3}(\.\d{3})+$/.test(s)) {
      s = s.replace(/\./g, '');
    }
    const v = parseFloat(s);
    return Number.isFinite(v) ? v : 0;
  }

  function escapeHTML(s) {
    return String(s || '').replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
  }

  function loadPrefs() {
    try { return JSON.parse(localStorage.getItem(CFG.storageKey)) || {}; }
    catch (e) { return {}; }
  }
  function savePrefs(p) {
    try { localStorage.setItem(CFG.storageKey, JSON.stringify(p)); }
    catch (e) {}
  }

  // ──────────────────────────────────────────────────────────────
  // NAV (toate paginile)
  // ──────────────────────────────────────────────────────────────
  function injectStyle() {
    if ($('#tp-enhance-styles')) return;
    const s = document.createElement('style');
    s.id = 'tp-enhance-styles';
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  function injectNav() {
    if ($('.tp-nav')) return;
    const nav = document.createElement('nav');
    nav.className = 'tp-nav';
    nav.setAttribute('aria-label', 'Navigare principală');

    const here = (location.pathname.split('/').pop() || 'index.html').toLowerCase();
    const base = location.pathname.replace(/\/[^/]*$/, '/');

    const links = [
      { href: 'index.html',                 label: '🏠 Acasă' },
      { href: 'raport_transparenta.html',   label: '🚩 Nereguli' },
      { href: 'transparenta_pantelimon.html', label: '📊 Buget' },
    ];

    const linksHTML = links.map(l => {
      const active = l.href.toLowerCase() === here || (here === '' && l.href === 'index.html');
      return `<a href="${base}${l.href}"${active ? ' class="active" aria-current="page"' : ''}>${l.label}</a>`;
    }).join('');

    nav.innerHTML = `
      <div class="tp-nav-inner">
        <a href="${base}index.html" class="tp-nav-brand">🏛️ Transparența Pantelimon</a>
        <div class="tp-nav-links">
          ${linksHTML}
          <a href="https://transparenta.eu/entities/4420759" target="_blank" rel="noopener">ANAF ↗</a>
          <a href="https://github.com/bise88/transparenta-pantelimon" target="_blank" rel="noopener">GitHub ↗</a>
        </div>
      </div>
    `;
    document.body.insertBefore(nav, document.body.firstChild);
  }

  // ──────────────────────────────────────────────────────────────
  // BACK TO TOP
  // ──────────────────────────────────────────────────────────────
  function injectBackToTop() {
    const b = document.createElement('button');
    b.className = 'tp-back-top';
    b.setAttribute('aria-label', 'Înapoi sus');
    b.title = 'Înapoi sus';
    b.textContent = '↑';
    b.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));
    document.body.appendChild(b);
    window.addEventListener('scroll', () => {
      b.classList.toggle('visible', window.scrollY > 600);
    }, { passive: true });
  }

  // ──────────────────────────────────────────────────────────────
  // DETECȚIE CARDURI (raport_transparenta.html)
  // ──────────────────────────────────────────────────────────────
  function detectCards() {
    // Strategie 1: <details> care conțin severitate
    let cards = $$('details').filter(d => /CRITIC|MAJOR|MEDIU/.test(d.textContent));
    if (cards.length >= 5) return cards;

    // Strategie 2: orice element cu clasă conținând "card"/"nereg"/"issue"/"flag"
    cards = $$('[class*="card"], [class*="nereg"], [class*="issue"], [class*="flag"]')
      .filter(el => /CRITIC|MAJOR|MEDIU/.test(el.textContent) && el.children.length > 1);
    if (cards.length >= 5) return cards;

    // Strategie 3: căutăm părinții comuni ai textelor "**[CRITIC]**" etc.
    const markers = $$('strong, b').filter(el => /^(CRITIC|MAJOR|MEDIU)$/.test(el.textContent.trim()));
    if (markers.length >= 5) {
      // urcăm până găsim un container care nu mai conține alți markeri
      const seen = new Set();
      markers.forEach(m => {
        let p = m.parentElement;
        while (p && p !== document.body) {
          const inside = p.querySelectorAll('strong, b');
          let count = 0;
          inside.forEach(s => { if (/^(CRITIC|MAJOR|MEDIU)$/.test(s.textContent.trim())) count++; });
          if (count === 1) { seen.add(p); break; }
          p = p.parentElement;
        }
      });
      cards = Array.from(seen);
      if (cards.length >= 5) return cards;
    }

    return [];
  }

  function parseCard(el, idx) {
    const txt = el.textContent;
    let sev = 'MEDIU';
    if (/\bCRITIC\b/.test(txt))      sev = 'CRITIC';
    else if (/\bMAJOR\b/.test(txt))  sev = 'MAJOR';
    else if (/\bMEDIU\b/.test(txt))  sev = 'MEDIU';

    // Titlu: prima propoziție bold după marcajul de severitate (sau primul <strong>)
    let title = '';
    const strongs = el.querySelectorAll('strong, b');
    for (const s of strongs) {
      const t = s.textContent.trim();
      if (/^(CRITIC|MAJOR|MEDIU)$/.test(t)) continue;
      title = t; break;
    }
    if (!title) {
      const m = txt.match(/(?:CRITIC|MAJOR|MEDIU)\s*[\s\S]{0,3}([A-ZĂÎÂȘȚ][^\n.]{10,180})/);
      title = m ? m[1].trim() : '(fără titlu)';
    }

    // Suma — luăm cea mai mare valoare RON găsită
    const sumMatches = txt.match(/[\d.,]+\s*(?:mil(?:\.|ioane)?\s*)?(?:RON|lei)/gi) || [];
    let sum = 0;
    sumMatches.forEach(m => { const v = parseSum(m); if (v > sum) sum = v; });

    // Furnizor — după 🏢 sau "Firmă:"
    let supplier = '';
    const supMatch = txt.match(/(?:🏢|Firm[ăa]\s*:)\s*([^📅⚙️🔍🌐📊\n|]+)/);
    if (supMatch) {
      supplier = supMatch[1].trim()
        .replace(/^[:\-]\s*/, '')
        .replace(/\s+\|.*$/, '')
        .replace(/\s+/g, ' ')
        .trim();
    }

    // Dată — pattern dd.mm.yyyy / yyyy-mm-dd / dd/mm/yyyy
    const dateMatch = txt.match(/(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}|\d{4}-\d{2}-\d{2})/);
    const date = dateMatch ? dateMatch[1] : '';

    // Cod contract — după 📋
    let contract = '';
    const cMatch = txt.match(/📋\s*([^💰🏢📅⚙️\n]+)/);
    if (cMatch) contract = cMatch[1].trim().replace(/\s+\|.*$/, '').replace(/\s+/g, ' ');

    return {
      idx,
      el,
      severity: sev,
      title,
      supplier,
      sum,
      date,
      contract,
      // tot textul minuscul, pentru search liber
      haystack: txt.toLowerCase().replace(/\s+/g, ' ').slice(0, 4000),
    };
  }

  // ──────────────────────────────────────────────────────────────
  // PAGINA RAPORT
  // ──────────────────────────────────────────────────────────────
  function enhanceReport() {
    const cardEls = detectCards();
    if (!cardEls.length) {
      console.warn('[tp-enhance] Nu am detectat carduri de nereguli. Toolbar-ul nu va fi inserat.');
      return;
    }

    // Indexare
    const items = cardEls.map((el, i) => parseCard(el, i));

    // Ancore + permalink
    items.forEach(item => {
      const id = 'nereguli-' + (item.idx + 1);
      item.el.id = id;
      // adăugăm un mic link "#" lângă titlul cardului
      const heading = item.el.querySelector('summary, strong, h3, h2');
      if (heading && !heading.querySelector('.tp-card-anchor')) {
        const a = document.createElement('a');
        a.className = 'tp-card-anchor';
        a.href = '#' + id;
        a.textContent = '#';
        a.title = 'Copiază link direct';
        a.addEventListener('click', (ev) => {
          ev.preventDefault();
          const url = location.origin + location.pathname + '#' + id;
          history.replaceState(null, '', '#' + id);
          if (navigator.clipboard) {
            navigator.clipboard.writeText(url).catch(() => {});
          }
          item.el.classList.add('tp-card-flash');
          setTimeout(() => item.el.classList.remove('tp-card-flash'), 1500);
        });
        heading.appendChild(a);
      }
    });

    // Listă unică de furnizori
    const supplierCounts = new Map();
    items.forEach(it => {
      if (!it.supplier) return;
      const cur = supplierCounts.get(it.supplier) || { count: 0, sum: 0 };
      cur.count++; cur.sum += it.sum;
      supplierCounts.set(it.supplier, cur);
    });
    const suppliers = Array.from(supplierCounts.entries())
      .sort((a, b) => b[1].count - a[1].count);

    // State filtre
    const prefs = loadPrefs();
    const state = {
      q: '',
      sev: { CRITIC: true, MAJOR: true, MEDIU: true },
      supplier: '',
      sort: prefs.sort || 'idx-asc',
      shown: CFG.pageSize,
      _domReordered: false,  // true când DOM-ul a fost sortat (nu idx-asc)
    };

    // ─── TOOLBAR ──────────────────────────────────────────────
    const toolbar = document.createElement('div');
    toolbar.className = 'tp-toolbar';
    toolbar.setAttribute('role', 'search');
    toolbar.innerHTML = `
      <div class="tp-toolbar-inner">
        <div class="tp-toolbar-row">
          <input type="search" class="tp-search" id="tp-q"
                 placeholder="🔍 Caută în nereguli (furnizor, sumă, cod contract, lege)…"
                 aria-label="Caută în nereguli">
          <button class="tp-chip active" data-sev="CRITIC" aria-pressed="true">🔴 CRITIC</button>
          <button class="tp-chip active" data-sev="MAJOR"  aria-pressed="true">🟠 MAJOR</button>
          <button class="tp-chip active" data-sev="MEDIU"  aria-pressed="true">🟡 MEDIU</button>
        </div>
        <div class="tp-toolbar-row">
          <select class="tp-select" id="tp-supplier" aria-label="Filtrează după furnizor">
            <option value="">Toți furnizorii (${suppliers.length})</option>
            ${suppliers.map(([name, info]) =>
              `<option value="${escapeHTML(name)}">${escapeHTML(name)} (${info.count})</option>`
            ).join('')}
          </select>
          <select class="tp-select" id="tp-sort" aria-label="Sortare">
            <option value="idx-asc">Sortare: ordinea originală</option>
            <option value="sev-asc">Severitate (CRITIC întâi)</option>
            <option value="sum-desc">Sumă (mare → mic)</option>
            <option value="sum-asc">Sumă (mic → mare)</option>
            <option value="supplier-asc">Furnizor (A → Z)</option>
            <option value="date-desc">Dată (recent → vechi)</option>
          </select>
          <button class="tp-btn" id="tp-export-csv" title="Descarcă rezultatele filtrate ca CSV">⬇ CSV</button>
          <button class="tp-btn" id="tp-export-json" title="Descarcă rezultatele filtrate ca JSON">⬇ JSON</button>
          <button class="tp-btn" id="tp-reset" title="Curăță toate filtrele">✕ Reset</button>
        </div>
        <div class="tp-toolbar-row">
          <div class="tp-stats" id="tp-stats" aria-live="polite"></div>
        </div>
      </div>
    `;

    // ─── SUMMARY WIDGET ───────────────────────────────────────
    const summary = buildSummaryWidget(items, suppliers);

    // Inserăm toolbar + summary înainte de primul card
    const firstCard = cardEls[0];
    const anchor = firstCard.parentElement;
    anchor.insertBefore(toolbar, firstCard);
    anchor.insertBefore(summary, firstCard);

    // Container "load more" + empty state, după ultimul card
    const lastCard = cardEls[cardEls.length - 1];
    const loadMore = document.createElement('div');
    loadMore.className = 'tp-loadmore';
    loadMore.innerHTML = `<button class="tp-btn tp-btn-primary" id="tp-load-more">Încarcă încă ${CFG.pageSize} →</button>`;
    lastCard.parentElement.insertBefore(loadMore, lastCard.nextSibling);

    // Sentinel invizibil — marchează poziția originală a cardurilor în DOM
    // Folosit de applyFilters pentru insertBefore în loc de appendChild (care muta itemii la finalul wrap-ului)
    const tpRestoreRef = document.createElement('span');
    tpRestoreRef.style.cssText = 'display:none';
    tpRestoreRef.setAttribute('data-tp-ref', '1');
    loadMore.parentElement.insertBefore(tpRestoreRef, loadMore);

    const empty = document.createElement('div');
    empty.className = 'tp-empty tp-card-hidden';
    empty.id = 'tp-empty';
    empty.innerHTML = `<p>🤷 Niciun rezultat pentru filtrele curente.</p>
      <button class="tp-btn" onclick="document.getElementById('tp-reset').click()">Curăță filtrele</button>`;
    loadMore.parentElement.insertBefore(empty, loadMore);

    // Setăm sortarea salvată
    $('#tp-sort').value = state.sort;

    // ─── EVENT BINDING ────────────────────────────────────────
    const apply = debounce(() => applyFilters(items, state), 80);

    $('#tp-q').addEventListener('input', (e) => {
      state.q = e.target.value.trim().toLowerCase();
      state.shown = CFG.pageSize;
      apply();
    });
    toolbar.querySelectorAll('.tp-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        const s = chip.dataset.sev;
        state.sev[s] = !state.sev[s];
        chip.classList.toggle('active', state.sev[s]);
        chip.setAttribute('aria-pressed', state.sev[s] ? 'true' : 'false');
        state.shown = CFG.pageSize;
        apply();
      });
    });
    $('#tp-supplier').addEventListener('change', (e) => {
      state.supplier = e.target.value;
      state.shown = CFG.pageSize;
      apply();
    });
    $('#tp-sort').addEventListener('change', (e) => {
      state.sort = e.target.value;
      savePrefs({ ...loadPrefs(), sort: state.sort });
      apply();
    });
    $('#tp-reset').addEventListener('click', () => {
      state.q = ''; state.supplier = '';
      state.sev = { CRITIC: true, MAJOR: true, MEDIU: true };
      state.shown = CFG.pageSize;
      $('#tp-q').value = '';
      $('#tp-supplier').value = '';
      toolbar.querySelectorAll('.tp-chip').forEach(c => {
        c.classList.add('active');
        c.setAttribute('aria-pressed', 'true');
      });
      apply();
    });
    $('#tp-export-csv').addEventListener('click', () => exportCSV(items, state));
    $('#tp-export-json').addEventListener('click', () => exportJSON(items, state));
    $('#tp-load-more').addEventListener('click', () => {
      state.shown += CFG.pageSize;
      apply();
    });

    // Scurtături tastatură: "/" focus search, Esc clear
    document.addEventListener('keydown', (e) => {
      if (e.target.matches('input, textarea, select')) {
        if (e.key === 'Escape' && e.target.id === 'tp-q') {
          e.target.value = '';
          state.q = '';
          apply();
        }
        return;
      }
      if (e.key === '/') {
        e.preventDefault();
        $('#tp-q').focus();
      }
    });

    // Aplicăm hash din URL (dacă există filtre / ancoră)
    applyHash(items, state);
    apply();

    // Dacă URL conține #nereguli-X, scrollăm acolo după render
    if (/^#nereguli-\d+$/.test(location.hash)) {
      requestAnimationFrame(() => {
        const t = document.getElementById(location.hash.slice(1));
        if (t) {
          state.shown = Math.max(state.shown,
            (items.find(i => i.el === t)?.idx || 0) + 5);
          apply();
          t.scrollIntoView({ behavior: 'smooth', block: 'start' });
          t.classList.add('tp-card-flash');
          setTimeout(() => t.classList.remove('tp-card-flash'), 1500);
        }
      });
    }
  }

  function applyHash(items, state) {
    // Permite #q=foo&sev=CRITIC&supplier=BAR în URL
    const h = location.hash.replace(/^#/, '');
    if (!h.includes('=')) return;
    const params = new URLSearchParams(h);
    if (params.has('q')) {
      state.q = params.get('q').toLowerCase();
      const inp = $('#tp-q'); if (inp) inp.value = params.get('q');
    }
    if (params.has('sev')) {
      const sevs = params.get('sev').split(',').map(s => s.toUpperCase());
      ['CRITIC','MAJOR','MEDIU'].forEach(s => {
        state.sev[s] = sevs.includes(s);
        const chip = document.querySelector(`.tp-chip[data-sev="${s}"]`);
        if (chip) {
          chip.classList.toggle('active', state.sev[s]);
          chip.setAttribute('aria-pressed', state.sev[s] ? 'true' : 'false');
        }
      });
    }
    if (params.has('supplier')) {
      state.supplier = params.get('supplier');
      const sel = $('#tp-supplier'); if (sel) sel.value = state.supplier;
    }
  }

  function applyFilters(items, state) {
    // 1. Filtru
    let visible = items.filter(it => {
      if (!state.sev[it.severity]) return false;
      if (state.supplier && it.supplier !== state.supplier) return false;
      if (state.q) {
        const q = state.q;
        if (!it.haystack.includes(q) &&
            !it.supplier.toLowerCase().includes(q) &&
            !it.title.toLowerCase().includes(q)) return false;
      }
      return true;
    });

    // 2. Sortare
    const cmp = {
      'idx-asc':       (a, b) => a.idx - b.idx,
      'sev-asc':       (a, b) => CFG.severityOrder[a.severity] - CFG.severityOrder[b.severity] || a.idx - b.idx,
      'sum-desc':      (a, b) => b.sum - a.sum,
      'sum-asc':       (a, b) => a.sum - b.sum,
      'supplier-asc':  (a, b) => (a.supplier || 'zzz').localeCompare(b.supplier || 'zzz', 'ro'),
      'date-desc':     (a, b) => (b.date || '').localeCompare(a.date || ''),
    }[state.sort] || ((a, b) => a.idx - b.idx);

    const sorted = visible.slice().sort(cmp);

    // 3. Reordonare DOM (doar dacă sortarea diferă de idx-asc)
    // BUG FIX: folosim insertBefore(item, tpRestoreRef) în loc de appendChild(item)
    // appendChild muta TOȚI itemii la finalul div.wrap (după statistici), spărgând paginarea.
    const tpRef = document.querySelector('[data-tp-ref]');
    const tpParent = tpRef ? tpRef.parentElement : items[0].el.parentElement;
    if (state.sort !== 'idx-asc') {
      state._domReordered = true;
      sorted.forEach(it => tpParent.insertBefore(it.el, tpRef));
    } else if (state._domReordered) {
      // Restaurăm ordinea originală NUMAI dacă am sortat anterior
      state._domReordered = false;
      items.slice().sort((a, b) => a.idx - b.idx).forEach(it => tpParent.insertBefore(it.el, tpRef));
    }
    // else: idx-asc fără reordonare anterioară — nu mișcăm nimic, elementele sunt deja în ordine

    // 4. Show/hide + paginare
    const visibleSet = new Set(sorted.slice(0, state.shown).map(it => it.el));
    items.forEach(it => {
      it.el.classList.toggle('tp-card-hidden', !visibleSet.has(it.el));
    });

    // 5. Stats
    const totalSum = visible.reduce((s, it) => s + it.sum, 0);
    const byS = visible.reduce((acc, it) => {
      acc[it.severity] = (acc[it.severity] || 0) + 1; return acc;
    }, {});
    const stats = $('#tp-stats');
    if (stats) {
      stats.innerHTML = `
        <span><strong>${visible.length}</strong> / ${items.length} nereguli afișate</span>
        <span>🔴 <strong>${byS.CRITIC || 0}</strong> · 🟠 <strong>${byS.MAJOR || 0}</strong> · 🟡 <strong>${byS.MEDIU || 0}</strong></span>
        <span>Total: <strong>${fmtRON(totalSum)}</strong></span>
        ${state.shown < visible.length ? `<span style="color: var(--tp-muted)">Vizibile primele ${Math.min(state.shown, visible.length)}</span>` : ''}
      `;
    }

    // 6. Load more / empty
    const lm = $('#tp-load-more');
    if (lm) {
      const rest = visible.length - state.shown;
      if (rest > 0) {
        lm.parentElement.classList.remove('tp-card-hidden');
        lm.textContent = `Încarcă încă ${Math.min(rest, CFG.pageSize)} (rămase: ${rest}) →`;
      } else {
        lm.parentElement.classList.add('tp-card-hidden');
      }
    }
    const emp = $('#tp-empty');
    if (emp) emp.classList.toggle('tp-card-hidden', visible.length > 0);
  }

  // ──────────────────────────────────────────────────────────────
  // EXPORT
  // ──────────────────────────────────────────────────────────────
  function getFiltered(items, state) {
    return items.filter(it => {
      if (!state.sev[it.severity]) return false;
      if (state.supplier && it.supplier !== state.supplier) return false;
      if (state.q) {
        const q = state.q;
        if (!it.haystack.includes(q) &&
            !it.supplier.toLowerCase().includes(q) &&
            !it.title.toLowerCase().includes(q)) return false;
      }
      return true;
    });
  }

  function exportCSV(items, state) {
    const data = getFiltered(items, state);
    const cols = ['nr', 'severitate', 'titlu', 'furnizor', 'suma_RON', 'data', 'cod_contract', 'link'];
    const rows = data.map(it => [
      it.idx + 1,
      it.severity,
      it.title,
      it.supplier,
      it.sum,
      it.date,
      it.contract,
      location.origin + location.pathname + '#nereguli-' + (it.idx + 1),
    ]);
    const csv = [cols.join(',')].concat(
      rows.map(r => r.map(v => {
        const s = String(v == null ? '' : v).replace(/"/g, '""');
        return /[",\n;]/.test(s) ? `"${s}"` : s;
      }).join(','))
    ).join('\n');
    download(csv, 'nereguli-pantelimon.csv', 'text/csv;charset=utf-8');
  }

  function exportJSON(items, state) {
    const data = getFiltered(items, state).map(it => ({
      nr: it.idx + 1,
      severitate: it.severity,
      titlu: it.title,
      furnizor: it.supplier,
      suma_RON: it.sum,
      data: it.date,
      cod_contract: it.contract,
      link: location.origin + location.pathname + '#nereguli-' + (it.idx + 1),
    }));
    const payload = {
      sursa: location.href,
      generat_la: new Date().toISOString(),
      total: data.length,
      filtru: { q: state.q, severitate: state.sev, furnizor: state.supplier, sortare: state.sort },
      nereguli: data,
    };
    download(JSON.stringify(payload, null, 2), 'nereguli-pantelimon.json', 'application/json');
  }

  function download(content, filename, mime) {
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click();
    setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 100);
  }

  // ──────────────────────────────────────────────────────────────
  // SUMMARY WIDGET
  // ──────────────────────────────────────────────────────────────
  function buildSummaryWidget(items, suppliers) {
    const wrap = document.createElement('section');
    wrap.className = 'tp-summary';
    wrap.setAttribute('aria-label', 'Rezumat statistici');

    // Severitate
    const sevCount = { CRITIC: 0, MAJOR: 0, MEDIU: 0 };
    items.forEach(it => sevCount[it.severity]++);
    const total = items.length || 1;

    // Top furnizori după număr
    const topByCount = suppliers.slice(0, 10);
    // Top furnizori după valoare
    const topByValue = suppliers.slice().sort((a, b) => b[1].sum - a[1].sum).slice(0, 10);

    wrap.innerHTML = `
      <h3>📈 Rezumat — ${items.length} nereguli analizate</h3>
      <div class="tp-summary-bar" aria-label="Distribuție pe severități">
        <span style="background:${CFG.severityColor.CRITIC}; width:${(sevCount.CRITIC/total*100).toFixed(1)}%">
          ${sevCount.CRITIC > 5 ? sevCount.CRITIC + ' CRITIC' : ''}
        </span>
        <span style="background:${CFG.severityColor.MAJOR}; color:#1a1a1a; width:${(sevCount.MAJOR/total*100).toFixed(1)}%">
          ${sevCount.MAJOR > 5 ? sevCount.MAJOR + ' MAJOR' : ''}
        </span>
        <span style="background:${CFG.severityColor.MEDIU}; color:#1a1a1a; width:${(sevCount.MEDIU/total*100).toFixed(1)}%">
          ${sevCount.MEDIU > 5 ? sevCount.MEDIU + ' MEDIU' : ''}
        </span>
      </div>
      <div class="tp-summary-grid" style="margin-top:1rem">
        <div>
          <strong style="font-size:.85rem">🏢 Top furnizori după nereguli</strong>
          <div class="tp-summary-list" style="margin-top:.5rem">
            ${topByCount.map(([name, info]) => `
              <div class="tp-summary-li">
                <button class="tp-link-btn" data-supplier="${escapeHTML(name)}"
                        style="background:none;border:0;color:var(--tp-link);cursor:pointer;text-align:left;padding:0;font:inherit">
                  ${escapeHTML(name)}
                </button>
                <span><strong>${info.count}</strong> <span class="tp-muted">${fmtRON(info.sum)}</span></span>
              </div>
            `).join('') || '<div class="tp-muted">—</div>'}
          </div>
        </div>
        <div>
          <strong style="font-size:.85rem">💰 Top furnizori după valoare</strong>
          <div class="tp-summary-list" style="margin-top:.5rem">
            ${topByValue.map(([name, info]) => `
              <div class="tp-summary-li">
                <button class="tp-link-btn" data-supplier="${escapeHTML(name)}"
                        style="background:none;border:0;color:var(--tp-link);cursor:pointer;text-align:left;padding:0;font:inherit">
                  ${escapeHTML(name)}
                </button>
                <span><strong>${fmtRON(info.sum)}</strong> <span class="tp-muted">${info.count} ctr.</span></span>
              </div>
            `).join('') || '<div class="tp-muted">—</div>'}
          </div>
        </div>
      </div>
    `;

    // Click pe furnizor → filtrăm
    wrap.addEventListener('click', (e) => {
      const btn = e.target.closest('[data-supplier]');
      if (!btn) return;
      const sel = $('#tp-supplier');
      if (sel) {
        sel.value = btn.dataset.supplier;
        sel.dispatchEvent(new Event('change'));
        sel.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });

    return wrap;
  }

  // ──────────────────────────────────────────────────────────────
  // BOOT
  // ──────────────────────────────────────────────────────────────
  async function showWhatsNewBanner() {
    try {
      // Calea relativă funcționează atât pe GitHub Pages cât și local
      const r = await fetch('delta.json', { cache: 'no-store' });
      if (!r.ok) return;
      const d = await r.json();
      if (!d.nereguli_noi || d.nereguli_noi === 0) return;

      // Nu afișa bannerul dacă a fost deja respins pentru acest raport
      const dismissedFor = localStorage.getItem('tp-banner-dismissed');
      if (dismissedFor === d.data_curenta) return;

      const topNoi = (d.top_noi || []).slice(0, 2)
        .map(n => `<strong>${n.severitate}</strong>: ${escapeHTML(n.titlu)}`).join('; ');
      const link = 'raport_transparenta.html#nereguli-1';

      const banner = document.createElement('div');
      banner.className = 'tp-banner-whats-new';
      banner.setAttribute('role', 'status');
      banner.innerHTML =
        `🚩 <strong>${d.nereguli_noi} nereguli noi</strong> detectate față de raportul anterior` +
        (topNoi ? ` — ${topNoi}` : '') +
        ` <a href="${link}">vezi raportul →</a>` +
        `<button class="tp-banner-close" aria-label="Închide bannerul">×</button>`;

      banner.querySelector('.tp-banner-close').addEventListener('click', () => {
        try { localStorage.setItem('tp-banner-dismissed', d.data_curenta); } catch (e) {}
        banner.remove();
      });

      document.body.insertBefore(banner, document.body.firstChild);
    } catch (e) { /* fail silently — delta.json poate să nu existe */ }
  }

  function boot() {
    injectStyle();
    injectNav();
    injectBackToTop();
    showWhatsNewBanner();

    const path = location.pathname.toLowerCase();
    if (/raport_transparenta/.test(path)) {
      enhanceReport();
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  // ──────────────────────────────────────────────────────────────
  // PRINT / PDF — funcție apelată din raport_transparenta.html
  // ──────────────────────────────────────────────────────────────
  function printRaport() {
    // 1. Colectăm elementele ascunse
    const hiddenCards   = Array.from(document.querySelectorAll('.tp-card-hidden'));
    const hiddenDetails = Array.from(document.querySelectorAll('.flag-detail'));

    // 2. Afișăm tot
    hiddenCards.forEach(el => el.classList.remove('tp-card-hidden'));
    hiddenDetails.forEach(el => { el._origDisplay = el.style.display; el.style.display = 'block'; });

    // 3. Printăm
    window.print();

    // 4. Restaurăm după închiderea dialogului de print
    function restore() {
      hiddenCards.forEach(el => el.classList.add('tp-card-hidden'));
      hiddenDetails.forEach(el => { el.style.display = el._origDisplay || 'none'; delete el._origDisplay; });
    }
    // afterprint se declanșează când utilizatorul închide dialogul
    window.addEventListener('afterprint', restore, { once: true });
    // Fallback pentru browsere care nu suportă afterprint
    setTimeout(() => {
      window.removeEventListener('afterprint', restore);
      restore();
    }, 30000);
  }
  // Expunem global — butonul din raport_transparenta.html apelează printRaport()
  window.printRaport = printRaport;

})();
