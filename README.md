# 🌿 EvoCore — Magazin online (Proiect Baze de Date)

Magazin online de tip eMAG, in limba romana, cu tema verde. Construit cu
**Python + Flask** si o baza de date relationala **SQLite**.

Contine: conturi de utilizator, catalog cu **100 de produse** in **10 categorii**,
cautare, cos de cumparaturi, finalizare comanda si istoric comenzi.
Preturile sunt in **lei (RON)**.

## Pornire rapida

### Varianta 1 — dublu-click (macOS)
Dublu-click pe **`start.command`**. Se ocupa singur de tot (instaleaza
dependintele, populeaza baza de date, porneste serverul).

### Varianta 2 — din terminal
```bash
cd "Proiect BD"
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/python seed.py      # populeaza baza de date (o singura data)
./venv/bin/python app.py       # porneste serverul
```

Apoi deschide în browser: **http://127.0.0.1:5000**

## Structura proiectului

| Fisier / folder        | Rol                                                       |
|------------------------|-----------------------------------------------------------|
| `app.py`               | Aplicatia Flask: rutele si logica magazinului             |
| `database.py`          | Schema bazei de date (SQLite) + conexiunea                |
| `seed.py`              | Citeste folderul `arhiva` si populeaza baza de date        |
| `smoke_test.py`        | Test automat al fluxului principal                        |
| `templates/`           | Sabloanele HTML (Jinja2)                                  |
| `static/css/style.css` | Tema verde                                                |
| `static/img/products/` | Imaginile produselor (copiate din `arhiva`)               |
| `arhiva/`              | Datele sursa: cate un `.png` + `.txt`/`.rtf` per produs   |
| `evocore.db`           | Baza de date SQLite (generata de `seed.py`)               |

## Schema bazei de date

Schema este normalizata, cu chei externe:

- **categories** — categoriile de produse
- **products** — produsele (legate de o categorie)
- **users** — conturile (parole salvate criptat / hash)
- **cart_items** — cosul fiecarui utilizator (UNIQUE pe user+produs)
- **orders** — comenzile plasate
- **order_items** — liniile fiecarei comenzi

## Functionalitati

- 🔐 Inregistrare / autentificare / deconectare (parole hash-uite)
- 🗂️ Navigare pe 10 categorii, cu sortare dupa pret / nume
- 🔍 Cautare in nume, descriere si specificatii
- 📄 Pagina de produs cu specificatii, descriere si produse similare
- 🛒 Cos de cumparaturi (adaugare, modificare cantitate, stergere)
- 📦 Finalizare comanda cu date de livrare + istoric comenzi
- 🚚 Livrare gratuita peste 200 lei

## Test automat
```bash
./venv/bin/python smoke_test.py
```

## Re-populare baza de date
Pentru a reseta tot (produse, conturi, comenzi):
```bash
./venv/bin/python seed.py
```
