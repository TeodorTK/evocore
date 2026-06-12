"""
EvoCore - Stratul de acces la baza de date.

Functioneaza cu doua motoare de baze de date:
  * SQLite      - implicit, pentru dezvoltare locala (fisier evocore.db).
  * PostgreSQL  - cand este setata variabila de mediu DATABASE_URL
                  (ex: in productie pe Vercel + Neon).

Codul aplicatiei foloseste mereu acelasi API (conn.execute(sql, params)
cu semnul de intrebare "?" ca marcaj de parametru); pentru PostgreSQL
marcajele sunt convertite automat in "%s".
"""

import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "evocore.db")

# Daca exista DATABASE_URL folosim PostgreSQL, altfel SQLite.
DATABASE_URL = os.environ.get("DATABASE_URL")
IS_POSTGRES = bool(DATABASE_URL)


# --- Schema, scrisa pentru fiecare motor (diferentele sunt mici) -----------

def _schema():
    if IS_POSTGRES:
        pk = "SERIAL PRIMARY KEY"
        real = "DOUBLE PRECISION"
        ts = "TIMESTAMP NOT NULL DEFAULT NOW()"
    else:
        pk = "INTEGER PRIMARY KEY AUTOINCREMENT"
        real = "REAL"
        ts = "TEXT NOT NULL DEFAULT (datetime('now'))"

    return f"""
    CREATE TABLE IF NOT EXISTS categories (
        id    {pk},
        name  TEXT NOT NULL UNIQUE,
        slug  TEXT NOT NULL UNIQUE
    );

    CREATE TABLE IF NOT EXISTS products (
        id          {pk},
        category_id INTEGER NOT NULL REFERENCES categories(id),
        name        TEXT NOT NULL,
        price       {real} NOT NULL,
        description TEXT,
        specs       TEXT,
        image       TEXT,
        stock       INTEGER NOT NULL DEFAULT 25
    );

    CREATE TABLE IF NOT EXISTS users (
        id            {pk},
        name          TEXT NOT NULL,
        email         TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        created_at    {ts}
    );

    CREATE TABLE IF NOT EXISTS cart_items (
        id         {pk},
        user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
        quantity   INTEGER NOT NULL DEFAULT 1,
        UNIQUE (user_id, product_id)
    );

    CREATE TABLE IF NOT EXISTS orders (
        id         {pk},
        user_id    INTEGER NOT NULL REFERENCES users(id),
        total      {real} NOT NULL,
        status     TEXT NOT NULL DEFAULT 'In procesare',
        full_name  TEXT NOT NULL,
        address    TEXT NOT NULL,
        city       TEXT NOT NULL,
        phone      TEXT NOT NULL,
        created_at {ts}
    );

    CREATE TABLE IF NOT EXISTS order_items (
        id         {pk},
        order_id   INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
        product_id INTEGER REFERENCES products(id),
        name       TEXT NOT NULL,
        price      {real} NOT NULL,
        quantity   INTEGER NOT NULL
    );
    """


class _PgConn:
    """Adaptor subtire peste o conexiune psycopg, ca sa expuna acelasi API
    ca sqlite3 (execute cu "?", commit, close)."""

    def __init__(self, conn):
        self._c = conn

    def execute(self, sql, params=()):
        # Convertim marcajele de parametru din "?" in "%s" pentru psycopg.
        return self._c.execute(sql.replace("?", "%s"), params)

    def executescript(self, sql):
        self._c.execute(sql)

    def commit(self):
        self._c.commit()

    def close(self):
        self._c.close()


def get_db():
    """Deschide o conexiune noua catre baza de date (SQLite sau PostgreSQL)."""
    if IS_POSTGRES:
        import psycopg
        from psycopg.rows import dict_row
        conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
        return _PgConn(conn)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Creeaza tabelele daca nu exista deja."""
    conn = get_db()
    conn.executescript(_schema())
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    engine = "PostgreSQL" if IS_POSTGRES else f"SQLite ({DB_PATH})"
    print(f"Baza de date initializata: {engine}")
