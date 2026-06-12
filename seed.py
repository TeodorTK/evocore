"""
EvoCore - Script de populare a bazei de date din folderul `arhiva`.

Parcurge fiecare subfolder din `arhiva` (o categorie), citeste fisierele de
date (.rtf si .txt) cu campurile name/price/description/specs, potriveste
fiecare produs cu imaginea lui (.png), copiaza imaginea in
`static/img/products/` si insereaza totul in baza de date SQLite.

Ruleaza:  python seed.py
"""

import os
import re
import shutil
from pathlib import Path
import subprocess
import unicodedata

from compress_images import compress_image
from database import BASE_DIR, IS_POSTGRES, get_db, init_db

ARHIVA_DIR = os.path.join(BASE_DIR, "arhiva")
IMG_DEST_DIR = os.path.join(BASE_DIR, "static", "img", "products")

# Cuvinte ignorate cand potrivim numele de produs cu numele imaginii.
STOPWORDS = {"joc", "de", "cu", "si", "la", "the", "of", "gen", "pe", "disc"}


def slugify(text):
    """Transforma un text (cu diacritice romanesti) intr-un slug pentru URL."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def rtf_to_text(path):
    """Converteste un fisier .rtf in text simplu.

    Pe macOS folosim utilitarul `textutil`. Daca lipseste, eliminam manual
    codurile de control RTF.
    """
    try:
        out = subprocess.run(
            ["textutil", "-convert", "txt", "-stdout", path],
            capture_output=True, text=True, check=True,
        )
        return out.stdout
    except Exception:
        with open(path, "r", encoding="latin-1", errors="ignore") as f:
            raw = f.read()
        raw = re.sub(r"\\'[0-9a-fA-F]{2}", "", raw)      # caractere escapate
        raw = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", raw)      # cuvinte de control
        raw = raw.replace("{", "").replace("}", "")
        return raw


def parse_fields(text):
    """Extrage campurile name/price/description/specs dintr-un text."""
    fields = {"name": "", "price": "", "description": "", "specs": ""}
    current = None
    for line in text.splitlines():
        m = re.match(r"^\s*(name|price|description|specs)\s*:\s*(.*)$", line, re.I)
        if m:
            current = m.group(1).lower()
            fields[current] = m.group(2).strip()
        elif current and line.strip():
            # continuarea unui camp pe mai multe linii
            fields[current] += " " + line.strip()
    return fields


def tokens(name):
    """Imparte un nume in cuvinte semnificative pentru potrivire."""
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    parts = re.split(r"[^a-z0-9]+", name.lower())
    return {p for p in parts if p and p not in STOPWORDS}


def match_images(data_files, png_files):
    """Potriveste fiecare fisier de date cu o imagine .png din acelasi folder.

    Intai potriviri exacte dupa nume, apoi potriviri aproximative dupa
    numarul de cuvinte comune (greedy).
    """
    result = {}
    remaining = set(png_files)

    # 1) Potrivire exacta dupa numele fisierului (fara extensie).
    for data in data_files:
        base = os.path.splitext(data)[0]
        candidate = base + ".png"
        if candidate in remaining:
            result[data] = candidate
            remaining.discard(candidate)

    # 2) Potrivire aproximativa pentru ce a ramas.
    for data in data_files:
        if data in result:
            continue
        data_tok = tokens(os.path.splitext(data)[0])
        best, best_score = None, 0
        for png in remaining:
            score = len(data_tok & tokens(os.path.splitext(png)[0]))
            if score > best_score:
                best, best_score = png, score
        if best:
            result[data] = best
            remaining.discard(best)

    return result


def seed():
    # Pornim de la zero ca rularea sa fie repetabila.
    if os.path.isdir(IMG_DEST_DIR):
        shutil.rmtree(IMG_DEST_DIR)
    os.makedirs(IMG_DEST_DIR, exist_ok=True)

    if IS_POSTGRES:
        # In PostgreSQL stergem tabelele existente ca sa repopulam curat.
        conn = get_db()
        conn.executescript(
            "DROP TABLE IF EXISTS order_items, orders, cart_items, "
            "products, users, categories CASCADE;")
        conn.commit()
        conn.close()
    else:
        # In SQLite e suficient sa stergem fisierul bazei de date.
        if os.path.exists(os.path.join(BASE_DIR, "evocore.db")):
            os.remove(os.path.join(BASE_DIR, "evocore.db"))

    init_db()
    conn = get_db()

    total_products = 0
    categories = sorted(
        d for d in os.listdir(ARHIVA_DIR)
        if os.path.isdir(os.path.join(ARHIVA_DIR, d))
    )

    for cat_name in categories:
        cat_dir = os.path.join(ARHIVA_DIR, cat_name)
        cat_id = conn.execute(
            "INSERT INTO categories (name, slug) VALUES (?, ?) RETURNING id",
            (cat_name, slugify(cat_name)),
        ).fetchone()["id"]

        files = os.listdir(cat_dir)
        data_files = sorted(f for f in files if f.lower().endswith((".rtf", ".txt")))
        png_files = [f for f in files if f.lower().endswith(".png")]
        image_map = match_images(data_files, png_files)

        count = 0
        for data in data_files:
            path = os.path.join(cat_dir, data)
            text = rtf_to_text(path) if data.lower().endswith(".rtf") else open(
                path, encoding="utf-8", errors="ignore").read()
            fields = parse_fields(text)

            if not fields["name"]:
                fields["name"] = os.path.splitext(data)[0]
            # Pretul: pastram doar cifrele.
            price_digits = re.sub(r"[^0-9.]", "", fields["price"]) or "0"
            try:
                price = float(price_digits)
            except ValueError:
                price = 0.0

            # Inseram produsul ca sa obtinem id-ul, apoi copiem imaginea.
            pid = conn.execute(
                """INSERT INTO products
                   (category_id, name, price, description, specs, image)
                   VALUES (?, ?, ?, ?, ?, ?) RETURNING id""",
                (cat_id, fields["name"], price,
                 fields["description"], fields["specs"], None),
            ).fetchone()["id"]

            png = image_map.get(data)
            if png:
                image_name = f"{pid}.webp"
                src_img = os.path.join(cat_dir, png)
                dest_img = os.path.join(IMG_DEST_DIR, image_name)
                compress_image(Path(src_img), Path(dest_img))
                conn.execute(
                    "UPDATE products SET image = ? WHERE id = ?", (image_name, pid))

            count += 1
            total_products += 1

        print(f"  [{count:2d} produse]  {cat_name}")

    conn.commit()
    conn.close()
    print(f"\nGata! {len(categories)} categorii, {total_products} produse populate.")


if __name__ == "__main__":
    seed()
