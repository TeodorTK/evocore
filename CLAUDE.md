# CLAUDE.md — EvoCore

Guidance for Claude Code (and developers) working in this repository.

## 1. What this is

**EvoCore** is an eMAG-style online shop, **in Romanian**, with a **green theme**.
It is a university **Database course project** ("Proiect BD"), so the relational
database is the centerpiece — see the in-depth **§5 Database** below.

- **Stack:** Python + **Flask** (server-rendered Jinja2 templates) + a relational DB.
- **Database:** **dual-backend** — **SQLite** locally, **PostgreSQL** in production
  (selected automatically by the `DATABASE_URL` env var).
- **Catalog:** 100 products across 10 categories, prices in **lei (RON)**.
- **Features:** accounts (register/login, hashed passwords), category browsing +
  sorting, search, product pages, shopping cart, checkout → orders, order history.
- **Deployment target:** Vercel (serverless) + Neon (managed Postgres). See `DEPLOY.md`.

> ⚠️ The project directory is `"Proiect BD "` — note the **trailing space** in the name.

## 2. Running locally

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/python seed.py        # build + populate the database (idempotent)
./venv/bin/python app.py         # http://127.0.0.1:5000
```

Or double-click `start.command` (macOS). Run the test suite with
`./venv/bin/python smoke_test.py`. **Always use `./venv/bin/python`**, not a global
Python — Flask/psycopg/Pillow live in the venv.

### Backend selection
- **No `DATABASE_URL`** → SQLite, file `evocore.db` in the project root.
- **`DATABASE_URL` set** → PostgreSQL. To run anything (app, seed, compress) against
  Postgres, prefix the command: `export DATABASE_URL="postgresql://..."`.

## 3. Project structure

| Path                     | Role                                                            |
|--------------------------|----------------------------------------------------------------|
| `app.py`                 | Flask app: all routes, auth, cart/checkout logic, helpers       |
| `database.py`            | **DB layer**: dual-backend connection + schema (see §5)         |
| `seed.py`                | Parse `arhiva/` → populate DB + generate product images          |
| `compress_images.py`     | Resize/convert product images to WebP, sync `products.image`     |
| `smoke_test.py`          | End-to-end test of the main flow (works on both backends)       |
| `templates/`             | Jinja2 templates; `base.html` is the layout, `_macros.html` cards |
| `static/css/style.css`   | Green theme                                                     |
| `static/img/products/`   | Generated product images `<product_id>.webp` (committed)         |
| `arhiva/`                | **Source data**: per product a `.png` + a `.txt`/`.rtf`          |
| `api/index.py`           | Vercel serverless entry point (imports the Flask `app`)         |
| `vercel.json`            | Vercel routing (rewrites everything to `/api/index`)           |
| `evocore.db`             | Local SQLite DB (git-ignored; created by `seed.py`)             |

## 4. Conventions

- **Language:** all user-facing text is **Romanian**. Code comments are Romanian too.
- **Money:** stored as a floating-point number; formatted via `lei()` in `app.py`
  as `8.299,00 lei` (Romanian grouping: `.` thousands, `,` decimals).
- **SQL placeholder style:** always write `?` placeholders. The DB layer rewrites
  them to `%s` for Postgres automatically (see §5.2). Do **not** hand-write `%s`.
- **Row access:** query results are dict-like; access columns by name: `row["name"]`.
- **IDs in URLs:** products use numeric id (`/produs/<int:pid>`), categories use a
  `slug` (`/categorie/<slug>`).

---

## 5. Database (in depth)

This is the heart of the project. Everything about the schema lives in `database.py`.

### 5.1 Dual-backend design

`database.py` decides the engine at import time:

```python
DATABASE_URL = os.environ.get("DATABASE_URL")
IS_POSTGRES  = bool(DATABASE_URL)
```

- **SQLite** (`IS_POSTGRES = False`): `sqlite3` stdlib, file `evocore.db`,
  `row_factory = sqlite3.Row` (name-based column access), `PRAGMA foreign_keys = ON`.
- **PostgreSQL** (`IS_POSTGRES = True`): `psycopg` v3, `row_factory = dict_row`,
  connection string from `DATABASE_URL`.

A single `_schema()` function emits the DDL with engine-specific fragments so both
databases get the *same logical schema* from one source of truth:

| Concept            | SQLite                              | PostgreSQL                  |
|--------------------|-------------------------------------|-----------------------------|
| Auto-increment PK  | `INTEGER PRIMARY KEY AUTOINCREMENT` | `SERIAL PRIMARY KEY`        |
| Money / float      | `REAL`                              | `DOUBLE PRECISION`          |
| Timestamp default  | `TEXT DEFAULT (datetime('now'))`    | `TIMESTAMP DEFAULT NOW()`   |

> Money is intentionally a **float**, not a decimal, so the same arithmetic
> (e.g. `total + 19.99` shipping) works identically on both engines without
> `Decimal`/`float` type clashes.

### 5.2 Connection layer & placeholder translation

`get_db()` returns an object exposing a uniform API: `.execute(sql, params)`,
`.commit()`, `.close()`, `.executescript(sql)`.

- For SQLite it returns the raw `sqlite3.Connection` (already matches the API).
- For Postgres it returns a thin `_PgConn` wrapper whose `.execute()` does
  `sql.replace("?", "%s")` before delegating to psycopg. This is why **all app SQL
  uses `?`** regardless of engine. (Safe because no SQL string here contains a
  literal `?` or `%`.)

`.execute(...)` returns a cursor, so `.fetchone()` / `.fetchall()` chain directly,
e.g. `db.execute("SELECT ...", (x,)).fetchone()["name"]`.

### 5.3 Entity-relationship overview

```
 categories 1───∞ products
      │                │
      │                │ (snapshot copy at order time)
      ▼                ▼
   users 1───∞ cart_items ∞───1 products
      │
      │ 1
      ▼ ∞
   orders 1───∞ order_items ∞───0..1 products
```

Six tables: `categories`, `products`, `users`, `cart_items`, `orders`,
`order_items`.

### 5.4 Tables — full specification

#### `categories` — the 10 product categories
| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id`   | INTEGER/SERIAL | **PK** | |
| `name` | TEXT | NOT NULL, **UNIQUE** | e.g. `Laptopuri, PC-uri & Servere` |
| `slug` | TEXT | NOT NULL, **UNIQUE** | URL-safe, ASCII, diacritics stripped, e.g. `laptopuri-pc-uri-servere` |

Slug is generated by `slugify()` in `seed.py` (NFKD-normalize → strip non-ASCII →
lowercase → non-alphanumerics to `-`).

#### `products` — the catalog (100 rows)
| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id`          | INTEGER/SERIAL | **PK** | also the image filename: `<id>.webp` |
| `category_id` | INTEGER | NOT NULL, **FK → categories(id)** | |
| `name`        | TEXT | NOT NULL | |
| `price`       | REAL/DOUBLE PRECISION | NOT NULL | in lei |
| `description` | TEXT | | one-line marketing copy |
| `specs`       | TEXT | | comma-separated; split into a list in the product page |
| `image`       | TEXT | | filename within `static/img/products/`, e.g. `1.webp` |
| `stock`       | INTEGER | NOT NULL, DEFAULT 25 | not enforced at checkout (display only) |

#### `users` — accounts
| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id`            | INTEGER/SERIAL | **PK** | |
| `name`          | TEXT | NOT NULL | full name |
| `email`         | TEXT | NOT NULL, **UNIQUE** | login identifier, stored lowercased |
| `password_hash` | TEXT | NOT NULL | from `werkzeug.security.generate_password_hash` (PBKDF2). **Plaintext passwords are never stored.** |
| `created_at`    | TEXT/TIMESTAMP | NOT NULL, DEFAULT now | |

#### `cart_items` — per-user shopping cart
| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id`         | INTEGER/SERIAL | **PK** | |
| `user_id`    | INTEGER | NOT NULL, **FK → users(id) ON DELETE CASCADE** | |
| `product_id` | INTEGER | NOT NULL, **FK → products(id) ON DELETE CASCADE** | |
| `quantity`   | INTEGER | NOT NULL, DEFAULT 1 | |
|              |         | **UNIQUE (user_id, product_id)** | one row per product per user |

The `UNIQUE(user_id, product_id)` constraint powers the **upsert** in
`cart_add` (§5.6). The cart is DB-backed and requires login.

#### `orders` — placed orders (order header)
| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id`         | INTEGER/SERIAL | **PK** | |
| `user_id`    | INTEGER | NOT NULL, **FK → users(id)** | |
| `total`      | REAL/DOUBLE PRECISION | NOT NULL | snapshot of order total |
| `status`     | TEXT | NOT NULL, DEFAULT `'In procesare'` | |
| `full_name`, `address`, `city`, `phone` | TEXT | NOT NULL | shipping details captured at checkout |
| `created_at` | TEXT/TIMESTAMP | NOT NULL, DEFAULT now | |

#### `order_items` — order line items
| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id`         | INTEGER/SERIAL | **PK** | |
| `order_id`   | INTEGER | NOT NULL, **FK → orders(id) ON DELETE CASCADE** | |
| `product_id` | INTEGER | **FK → products(id)**, nullable | nullable so history survives product deletion |
| `name`       | TEXT | NOT NULL | **snapshot** of product name at purchase time |
| `price`      | REAL/DOUBLE PRECISION | NOT NULL | **snapshot** of unit price |
| `quantity`   | INTEGER | NOT NULL | |

> **Design note — historical snapshots:** `order_items` copies `name` and `price`
> instead of relying only on `product_id`. This keeps past orders correct even if a
> product is later renamed, repriced, or deleted.

### 5.5 Constraints, indexes & referential integrity

- **Primary keys:** every table has a surrogate auto-increment `id`.
- **Unique constraints** (each backed by an automatic unique index):
  `categories.name`, `categories.slug`, `users.email`, `cart_items(user_id, product_id)`.
- **Foreign keys:** as listed above. `ON DELETE CASCADE` on `cart_items` (both FKs)
  and on `order_items.order_id`. SQLite enforces FKs only because we set
  `PRAGMA foreign_keys = ON` on every connection; Postgres enforces them always.
- No additional secondary indexes are defined — at 100 products the dataset is tiny,
  so category/search scans are fine. (If scaling up, index `products.category_id`.)

### 5.6 Notable query patterns

- **Upsert (add to cart, accumulate quantity):**
  ```sql
  INSERT INTO cart_items (user_id, product_id, quantity) VALUES (?, ?, ?)
  ON CONFLICT(user_id, product_id)
  DO UPDATE SET quantity = cart_items.quantity + excluded.quantity
  ```
  ⚠️ The right-hand `quantity` **must** be qualified as `cart_items.quantity` —
  unqualified it is ambiguous in Postgres (SQLite tolerates it). This was a real bug.
- **`RETURNING id`** is used after inserts (categories, products, orders) to get the
  new id on both engines (SQLite ≥ 3.35 supports it). Do not use `last_insert_rowid()`.
- **Case-insensitive search:** `WHERE LOWER(name) LIKE ?` with a lowercased param —
  consistent across SQLite (already case-insensitive) and Postgres (`LIKE` is
  case-sensitive). Searches `name`, `description`, and `specs`.
- **Random selection:** `ORDER BY RANDOM() LIMIT n` for featured/similar products
  (works on both engines).
- **Sorting** on category pages uses a whitelisted `ORDER BY` fragment
  (`pret-asc|pret-desc|nume`) — never interpolate raw user input into SQL.

### 5.7 Data lifecycle (how the DB gets populated)

`seed.py` is idempotent and rebuilds everything from `arhiva/`:

1. **Reset:** SQLite → delete `evocore.db`; Postgres → `DROP TABLE ... CASCADE`.
   Also clears `static/img/products/`.
2. **Create schema** via `init_db()`.
3. For each category folder: insert the category, then for each product data file
   (`.txt`/`.rtf`) parse `name / price / description / specs`
   (RTF converted via macOS `textutil`, with a regex fallback).
4. **Match each product to its image** (`match_images`): exact filename match first,
   then a greedy token-overlap fuzzy match (handles game files whose `.png` names
   differ from the data files, e.g. colons stripped).
5. Insert the product (`RETURNING id`), then **compress the matched image to WebP**
   (`compress_images.compress_image`, max 480px, quality 82) saved as `<id>.webp`,
   and store the filename in `products.image`.

`compress_images.py` can also be run standalone to (re)compress images and
`--sync-db` updates `products.image` from `.png`→`.webp` (useful post-deploy).
Image filenames are deterministic (`<id>.webp`) and insertion order is stable
(categories sorted, files sorted), so SQLite and Postgres assign identical ids —
the committed images stay valid for either backend.

### 5.8 Production database (Neon/Postgres)

In production the schema is created and seeded by running `seed.py` **locally with
`DATABASE_URL` pointing at Neon** — there is no migration framework. The app on
Vercel only reads/writes; it does not create tables on cold start (`init_db()` runs
only under `__main__`). Use Neon's **pooled** connection string for serverless.

---

## 6. Application routes (`app.py`)

| Route | Methods | Purpose |
|-------|---------|---------|
| `/` | GET | Home: featured + category previews |
| `/categorie/<slug>` | GET | Category listing (with `?sort=`) |
| `/produs/<int:pid>` | GET | Product detail + similar products |
| `/cauta?q=` | GET | Search across name/description/specs |
| `/inregistrare` | GET/POST | Register (validates, hashes password) |
| `/autentificare` | GET/POST | Login |
| `/deconectare` | GET | Logout |
| `/cos` | GET | View cart (login required) |
| `/cos/adauga/<int:pid>` | POST | Add to cart (upsert) |
| `/cos/actualizeaza/<int:cart_id>` | POST | Update quantity (0 = delete) |
| `/cos/sterge/<int:cart_id>` | POST | Remove line |
| `/finalizare` | GET/POST | Checkout → creates order + items, clears cart |
| `/comenzi` | GET | Order history |
| `/comanda/<int:order_id>` | GET | Order detail (ownership-checked) |

Auth uses Flask's signed-cookie **session** holding `user_id`; `current_user()`
loads the row. A `@context_processor` injects `all_categories`, `user`,
`cart_count`, and the `lei` formatter into every template.

## 7. Gotchas / things to be careful about

- The project folder name has a **trailing space** — quote paths.
- Use `?` placeholders only (the layer converts to `%s` for Postgres).
- Qualify columns in upsert `DO UPDATE SET` (Postgres ambiguity).
- Test changes on **both** backends — `smoke_test.py` runs against whichever
  `DATABASE_URL` is (or isn't) set. A local Dockerized Postgres works:
  `docker run -e POSTGRES_PASSWORD=evocore -e POSTGRES_DB=evocore -p 55432:5432 postgres:16-alpine`.
- Don't commit `evocore.db` (git-ignored). Product images **are** committed.
