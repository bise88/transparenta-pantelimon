# API public — transparenta-pantelimon

Date disponibile public pe GitHub Pages, actualizate lunar automat.

---

## `raport.json`

**URL:** `https://bise88.github.io/transparenta-pantelimon/raport.json`  
**Frecvență:** actualizat în prima luni a fiecărei luni  
**Licență:** Creative Commons CC-BY 4.0 (cu atribuire la inițiativa cetățenească)

### Schema

```json
{
  "schema_version": "1.0",
  "generated_at": "2025-05-01T06:12:34.000000",
  "entity": {
    "name": "Primăria Pantelimon",
    "cif": "4420759",
    "judet": "Ilfov"
  },
  "totals": {
    "flags": 12,
    "contracts_analyzed": 506,
    "total_value_ron": 45230000.00,
    "by_severity": {
      "CRITIC": 3,
      "MAJOR": 6,
      "MEDIU": 3
    }
  },
  "flags": [
    {
      "id": 1,
      "severity": "CRITIC",
      "title": "Posibilă fragmentare artificială a contractelor",
      "explanation": "Furnizor X a primit 2 contracte similare la interval de 12 zile...",
      "supplier": "MIDAS ROAD S.R.L.",
      "supplier_cif": "12345678",
      "sum_ron": 245000.00,
      "date": "2024-04-03",
      "contract_id": "achizitie-directa-2024-489392",
      "contract_numar": "20571",
      "procedure": "achizitie-directa",
      "anchor": "nereguli-1"
    }
  ]
}
```

### Câmpuri `flags[]`

| Câmp | Tip | Descriere |
|---|---|---|
| `id` | `int` | Index de la 1 (ordinea în raport: CRITIC → MAJOR → MEDIU) |
| `severity` | `string` | `"CRITIC"`, `"MAJOR"` sau `"MEDIU"` |
| `title` | `string` | Titlul scurt al neregulii |
| `explanation` | `string` | Descriere completă |
| `supplier` | `string` | Denumirea firmei câștigătoare |
| `supplier_cif` | `string` | CUI-ul firmei (fără prefix `RO`) |
| `sum_ron` | `float` | Valoarea în RON |
| `date` | `string` | Data publicării (`YYYY-MM-DD`) |
| `contract_id` | `string` | ID-ul contractului în SEAP |
| `contract_numar` | `string` | Numărul de înregistrare |
| `procedure` | `string` | Tipul de procedură |
| `anchor` | `string` | ID HTML pentru permalink (`#nereguli-N`) |

---

## `contracte.json`

**URL:** `https://bise88.github.io/transparenta-pantelimon/contracte.json`  
**Conținut:** toate contractele analizate (506 în ultima rulare)

```json
[
  {
    "id": "achizitie-directa-2024-489392",
    "titlu": "Servicii de reparații",
    "valoare": 125000.00,
    "data": "2024-04-03",
    "tip": "achizitie-directa",
    "firma": "MIDAS ROAD S.R.L.",
    "cui": "12345678",
    "ofertanti": 1
  }
]
```

---

## `feed.xml` (Atom)

**URL:** `https://bise88.github.io/transparenta-pantelimon/feed.xml`  
**Format:** Atom 1.0  
**Conținut:** Top 20 nereguli ordonate CRITIC → MAJOR → MEDIU, apoi descrescător după valoare

Compatibil cu Feedly, Inoreader, NewsBlur și orice cititor RSS/Atom.

---

## Note

- Datele sunt extrase din surse publice oficiale (SEAP via data.gov.ro, ANAF via transparenta.eu)
- Nu conțin date personale — doar informații despre entități juridice și contracte publice
- Pentru întrebări sau sesizări: deschide un [issue pe GitHub](https://github.com/bise88/transparenta-pantelimon/issues)
