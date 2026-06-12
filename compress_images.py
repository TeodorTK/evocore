"""
EvoCore - Comprimă imaginile produselor pentru încărcare mai rapidă.

Redimensionează la max 480px (suficient pentru afișarea din site) și convertește
PNG/JPEG în WebP. Actualizează coloana products.image în baza de date.

Rulează:
    ./venv/bin/python compress_images.py

Pentru baza Neon (producție):
    export DATABASE_URL="postgresql://..."
    ./venv/bin/python compress_images.py
"""

import os
import sys
from pathlib import Path

from database import BASE_DIR, get_db

IMG_DIR = Path(BASE_DIR) / "static" / "img" / "products"
MAX_SIDE = 480
WEBP_QUALITY = 82
SOURCE_EXTS = {".png", ".jpg", ".jpeg"}


def _open_image(path):
    from PIL import Image

    with Image.open(path) as img:
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            return img.convert("RGBA")
        return img.convert("RGB")


def compress_image(src: Path, dest: Path) -> tuple[int, int]:
    """Redimensionează și salvează ca WebP. Returnează (bytes_înainte, bytes_după)."""
    from PIL import Image

    before = src.stat().st_size
    img = _open_image(src)
    if max(img.size) > MAX_SIDE:
        img.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)

    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, format="WEBP", quality=WEBP_QUALITY, method=6)
    after = dest.stat().st_size
    img.close()
    return before, after


def compress_product_images(*, dry_run: bool = False) -> dict:
    """Procesează toate imaginile din static/img/products/."""
    if not IMG_DIR.is_dir():
        print(f"Folder inexistent: {IMG_DIR}")
        return {"files": 0, "saved": 0}

    sources = sorted(
        p for p in IMG_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in SOURCE_EXTS
    )
    if not sources:
        print("Nicio imagine PNG/JPEG de comprimat.")
        return {"files": 0, "saved": 0}

    updates: list[tuple[str, str]] = []
    total_before = 0
    total_after = 0
    converted = 0

    for src in sources:
        dest = src.with_suffix(".webp")
        if dry_run:
            print(f"  [dry-run] {src.name} -> {dest.name}")
            continue

        before, after = compress_image(src, dest)
        total_before += before
        total_after += after
        converted += 1

        if src.resolve() != dest.resolve():
            src.unlink()
        updates.append((src.name, dest.name))

    if dry_run:
        return {"files": len(sources), "saved": 0}

    if updates:
        conn = get_db()
        for old_name, new_name in updates:
            conn.execute(
                "UPDATE products SET image = ? WHERE image = ?",
                (new_name, old_name),
            )
        conn.commit()
        conn.close()

    saved = total_before - total_after
    print(f"\nGata! {converted} imagini convertite în WebP.")
    print(f"  Înainte: {total_before / 1024 / 1024:.1f} MB")
    print(f"  După:    {total_after / 1024 / 1024:.1f} MB")
    print(f"  Economie: {saved / 1024 / 1024:.1f} MB ({100 * saved / total_before:.0f}%)")
    if updates:
        print(f"  Baza de date: {len(updates)} înregistrări actualizate.")

    return {"files": converted, "saved": saved}


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    try:
        compress_product_images(dry_run=dry)
    except ImportError:
        print("Lipsește Pillow. Rulează: ./venv/bin/pip install Pillow")
        sys.exit(1)
