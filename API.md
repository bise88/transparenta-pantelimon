# API public — Transparența Pantelimon

Datele generate automat de `monitor_pantelimon.py` sunt disponibile public ca endpoint JSON.
Actualizate lunar (de obicei pe 15 ale lunii).

**Licență:** Creative Commons CC-BY 4.0 — atribuire obligatorie: „Transparența Pantelimon / aprindemlumina.eu"

---

## Endpoint: `raport.json`

**URL:** `https://aprindemlumina.eu/raport.json`

Raportul complet cu toate neregulile detectate, totaluri și scor de transparență.

### Schema

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-05-15T14:32:10.123456",
  "entity": {
    "name": "Primăria Pantelimon",
    "cif": "4420759",
    "judet": "Ilfov"
  },
  "totals": {
    "flags": 299,
    "contracts_analyzed": 506,
    "total_value_ron": 313680510.12,
    "by_severity": {
      "CRITIC": 107,
      "MAJOR": 55,
      "MEDIU": 137
    }
  },
  "flags": [
    {
      "id": 1,
      "severity": "CRITIC",
      "title": "Achiziție directă peste pragul legal",
      "explanation": "Descriere detaliată cu baza legală.",
      "supplier": "MIDAS ROAD S.R.L.",
      "sum_ron": 880000.0,
      "date": "2024-04-03",
      "contract_id": "achizitie-directa-2024-489392",
      "procedure": "Achizitie directa",
      "type": "ACHIZITIE_DIRECTA_PESTE_PRAG",
      "anchor": "nereguli-1"
    }
  ],
  "scor_transparenta": {
    "scor": 47,
    "componente": {
      "achizitii_directe": 55,
      "ofertant_unic": 40,
      "sedinte_extraordinare": 70,
      "fragmentare": 60,
      "documente": 50
    }
  }
}
```

### Câmpuri flag

| Câmp | Tip | Descriere |
|---|---|---|
| `id` | integer | Index 1-based în ordinea sortată (CRITIC → MAJOR → MEDIU) |
| `severity` | string | `CRITIC`, `MAJOR` sau `MEDIU` |
| `title` | string | Titlu scurt al neregulii |
| `explanation` | string | Descriere detaliată cu baza legală (max ~500 caractere) |
| `supplier` | string | Denumire firmă furnizor (dacă e aplicabil) |
| `sum_ron` | number | Valoare contract în RON |
| `date` | string | Data contractului (format `YYYY-MM-DD`) |
| `contract_id` | string | ID contract SEAP (ex: `achizitie-directa-2024-489392`) |
| `procedure` | string | Tipul procedurii (`Achizitie directa`, `Licitatie deschisa` etc.) |
| `type` | string | Codul intern al tipului de nereguă (vezi mai jos) |
| `anchor` | string | ID-ul HTML al cardului în raport (`nereguli-N`) |

### Tipuri de nereguli (`type`)

| Cod | Severitate tipică | Descriere |
|---|---|---|
| `ACHIZITIE_DIRECTA_PRAG` | MEDIU | Achiziție directă >97% din prag (126.100 RON) |
| `ACHIZITIE_DIRECTA_PESTE_PRAG` | CRITIC | Achiziție directă individuală depășește 130.000 RON |
| `OFERTANT_UNIC` | MEDIU/MAJOR | Un singur ofertant — lipsă concurență reală |
| `FRAGMENTARE` | CRITIC | Fragmentare artificială pentru eludarea pragului |
| `FRAGMENTARE_TEMPORARA` | CRITIC | Contracte similare consecutive sub prag (L98/2016 art.11) |
| `CONCENTRARE_FURNIZOR` | MAJOR/CRITIC | Top 3 furnizori dețin >60% din valoarea totală |
| `CONTRACTE_CONSECUTIVE` | MAJOR | Același furnizor, ≥4 contracte în 30 de zile |
| `SEDINTE_EXTRAORDINARE_EXCESIVE` | MAJOR/CRITIC | Rata ședințelor extraordinare >25% din total |
| `PUBLICARE_INTARZIATA` | MEDIU/CRITIC | Publicare SEAP la >11 zile lucrătoare de la atribuire |
| `VALORI_IDENTICE_ACEEASI_ZI` | CRITIC | Valori identice atribuite la firme diferite în aceeași zi |
| `BURST_CONTRACTE` | MEDIU/MAJOR | Volum anormal de contracte într-o singură zi |
| `SEMNARE_ZILE_NELUCRATOARE` | MEDIU | Contract semnat în weekend sau sărbătoare legală |

---

## Endpoint: `contracte.json`

**URL:** `https://aprindemlumina.eu/contracte.json`

Lista tuturor contractelor analizate (sursa: SEAP).

### Schema

```json
[
  {
    "id": "achizitie-directa-2025-2637",
    "titlu": "Publicatii periodice",
    "valoare": 66000.0,
    "data": "2025-01-08",
    "tip": "Achizitie directa",
    "firma": "ASOCIATIA CENTRUL ROMAN...",
    "cui": "12345678",
    "ofertanti": 1
  }
]
```

---

## Endpoint: `feed.xml`

**URL:** `https://aprindemlumina.eu/feed.xml`

Feed Atom cu top 20 nereguli (compatibil RSS). Util pentru Feedly, Inoreader etc.

---

## Utilizare responsabilă

- Respectă limitele serverului (max 1 req/minut dacă faci poll automat)
- Citează sursa: „Date: Transparența Pantelimon / aprindemlumina.eu, CC-BY 4.0"
- Datele SEAP au decalaj de 1-3 luni față de realitate
- Neregulile detectate sunt indicatori factuali, nu concluzii juridice definitive

## Contact

Probleme cu schema sau lipsă date: [GitHub Issues](https://github.com/transparenta-locala/transparenta-pantelimon/issues)
