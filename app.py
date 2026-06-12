"""
EvoCore - Magazin online (proiect Baze de Date).

Aplicatie web Flask cu: conturi de utilizator, catalog de produse pe
categorii, cautare, cos de cumparaturi si comenzi. Datele sunt stocate
intr-o baza de date SQLite (vezi database.py si seed.py).

Pornire:
    python seed.py      # o singura data, populeaza baza de date
    python app.py       # porneste serverul pe http://127.0.0.1:5000
"""

import os
import re

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, abort,
)
from werkzeug.security import generate_password_hash, check_password_hash

from database import get_db, init_db

app = Flask(__name__)
# In productie, cheia secreta vine din variabila de mediu SECRET_KEY.
app.secret_key = os.environ.get("SECRET_KEY", "evocore-cheie-secreta-dev")


# ---------------------------------------------------------------------------
# Functii ajutatoare
# ---------------------------------------------------------------------------

def current_user():
    """Returneaza randul utilizatorului autentificat sau None."""
    uid = session.get("user_id")
    if not uid:
        return None
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    db.close()
    return user


def lei(value):
    """Formateaza un numar ca pret in lei: 8299 -> '8.299,00 lei'."""
    s = f"{value:,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s} lei"


def cart_count():
    """Numarul total de produse din cosul utilizatorului curent."""
    user = current_user()
    if not user:
        return 0
    db = get_db()
    row = db.execute(
        "SELECT COALESCE(SUM(quantity), 0) AS n FROM cart_items WHERE user_id = ?",
        (user["id"],),
    ).fetchone()
    db.close()
    return row["n"]


@app.context_processor
def inject_globals():
    """Variabile disponibile in toate sabloanele."""
    db = get_db()
    categories = db.execute(
        "SELECT * FROM categories ORDER BY name").fetchall()
    db.close()
    return {
        "all_categories": categories,
        "user": current_user(),
        "cart_count": cart_count(),
        "lei": lei,
    }


# ---------------------------------------------------------------------------
# Pagini publice: acasa, categorii, produs, cautare
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    db = get_db()
    # Cateva produse recomandate (aleatoriu) pentru pagina principala.
    featured = db.execute(
        "SELECT * FROM products ORDER BY RANDOM() LIMIT 8").fetchall()
    # Cate un produs reprezentativ pentru fiecare categorie.
    categories = db.execute("SELECT * FROM categories ORDER BY name").fetchall()
    cat_previews = []
    for c in categories:
        sample = db.execute(
            "SELECT * FROM products WHERE category_id = ? ORDER BY RANDOM() LIMIT 1",
            (c["id"],),
        ).fetchone()
        cat_previews.append({"category": c, "sample": sample})
    db.close()
    return render_template("index.html", featured=featured, cat_previews=cat_previews)


@app.route("/categorie/<slug>")
def category(slug):
    db = get_db()
    cat = db.execute(
        "SELECT * FROM categories WHERE slug = ?", (slug,)).fetchone()
    if not cat:
        db.close()
        abort(404)

    sort = request.args.get("sort", "")
    order_by = {
        "pret-asc": "price ASC",
        "pret-desc": "price DESC",
        "nume": "name ASC",
    }.get(sort, "id ASC")

    products = db.execute(
        f"SELECT * FROM products WHERE category_id = ? ORDER BY {order_by}",
        (cat["id"],),
    ).fetchall()
    db.close()
    return render_template("category.html", category=cat, products=products, sort=sort)


@app.route("/produs/<int:pid>")
def product(pid):
    db = get_db()
    prod = db.execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()
    if not prod:
        db.close()
        abort(404)
    cat = db.execute(
        "SELECT * FROM categories WHERE id = ?", (prod["category_id"],)).fetchone()
    # Produse similare din aceeasi categorie.
    similar = db.execute(
        "SELECT * FROM products WHERE category_id = ? AND id != ? ORDER BY RANDOM() LIMIT 4",
        (prod["category_id"], pid),
    ).fetchall()
    db.close()
    # Transformam specificatiile (separate prin virgula) intr-o lista.
    spec_list = [s.strip() for s in (prod["specs"] or "").split(",") if s.strip()]
    return render_template(
        "product.html", product=prod, category=cat,
        similar=similar, spec_list=spec_list)


@app.route("/cauta")
def search():
    q = request.args.get("q", "").strip()
    products = []
    if q:
        db = get_db()
        # LOWER(...) pe ambele parti => cautare insensibila la majuscule,
        # la fel in SQLite si in PostgreSQL.
        like = f"%{q.lower()}%"
        products = db.execute(
            """SELECT * FROM products
               WHERE LOWER(name) LIKE ? OR LOWER(description) LIKE ?
                  OR LOWER(specs) LIKE ?
               ORDER BY name""",
            (like, like, like),
        ).fetchall()
        db.close()
    return render_template("search.html", q=q, products=products)


# ---------------------------------------------------------------------------
# Conturi: inregistrare, autentificare, deconectare
# ---------------------------------------------------------------------------

@app.route("/inregistrare", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        errors = []
        if not name:
            errors.append("Numele este obligatoriu.")
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            errors.append("Adresa de email nu este valida.")
        if len(password) < 6:
            errors.append("Parola trebuie sa aiba cel putin 6 caractere.")
        if password != confirm:
            errors.append("Parolele nu coincid.")

        db = get_db()
        if email and db.execute(
                "SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            errors.append("Exista deja un cont cu acest email.")

        if errors:
            db.close()
            for e in errors:
                flash(e, "error")
            return render_template("register.html", name=name, email=email)

        db.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password)),
        )
        db.commit()
        uid = db.execute(
            "SELECT id FROM users WHERE email = ?", (email,)).fetchone()["id"]
        db.close()
        session["user_id"] = uid
        flash(f"Bun venit, {name}! Contul a fost creat.", "success")
        return redirect(url_for("index"))

    return render_template("register.html")


@app.route("/autentificare", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        db.close()
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            flash(f"Bine ai revenit, {user['name']}!", "success")
            return redirect(request.args.get("next") or url_for("index"))
        flash("Email sau parola gresita.", "error")
        return render_template("login.html", email=email)
    return render_template("login.html")


@app.route("/deconectare")
def logout():
    session.pop("user_id", None)
    flash("Te-ai deconectat cu succes.", "success")
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Cos de cumparaturi (necesita autentificare)
# ---------------------------------------------------------------------------

def require_login():
    """Redirectioneaza catre login daca utilizatorul nu e autentificat."""
    if not current_user():
        flash("Trebuie sa fii autentificat pentru aceasta actiune.", "error")
        return redirect(url_for("login", next=request.path))
    return None


@app.route("/cos")
def cart():
    user = current_user()
    if not user:
        return redirect(url_for("login", next=url_for("cart")))
    db = get_db()
    items = db.execute(
        """SELECT ci.id AS cart_id, ci.quantity, p.*
           FROM cart_items ci JOIN products p ON p.id = ci.product_id
           WHERE ci.user_id = ? ORDER BY ci.id""",
        (user["id"],),
    ).fetchall()
    db.close()
    total = sum(it["price"] * it["quantity"] for it in items)
    return render_template("cart.html", items=items, total=total)


@app.route("/cos/adauga/<int:pid>", methods=["POST"])
def cart_add(pid):
    user = current_user()
    if not user:
        flash("Autentifica-te pentru a adauga produse in cos.", "error")
        return redirect(url_for("login", next=url_for("product", pid=pid)))

    qty = max(1, int(request.form.get("quantity", 1)))
    db = get_db()
    prod = db.execute("SELECT id FROM products WHERE id = ?", (pid,)).fetchone()
    if not prod:
        db.close()
        abort(404)
    # Daca produsul e deja in cos, crestem cantitatea (UPSERT).
    db.execute(
        """INSERT INTO cart_items (user_id, product_id, quantity)
           VALUES (?, ?, ?)
           ON CONFLICT(user_id, product_id)
           DO UPDATE SET quantity = cart_items.quantity + excluded.quantity""",
        (user["id"], pid, qty),
    )
    db.commit()
    db.close()
    flash("Produs adaugat in cos.", "success")
    return redirect(request.referrer or url_for("cart"))


@app.route("/cos/actualizeaza/<int:cart_id>", methods=["POST"])
def cart_update(cart_id):
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    qty = int(request.form.get("quantity", 1))
    db = get_db()
    if qty <= 0:
        db.execute(
            "DELETE FROM cart_items WHERE id = ? AND user_id = ?",
            (cart_id, user["id"]))
    else:
        db.execute(
            "UPDATE cart_items SET quantity = ? WHERE id = ? AND user_id = ?",
            (qty, cart_id, user["id"]))
    db.commit()
    db.close()
    return redirect(url_for("cart"))


@app.route("/cos/sterge/<int:cart_id>", methods=["POST"])
def cart_remove(cart_id):
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    db = get_db()
    db.execute(
        "DELETE FROM cart_items WHERE id = ? AND user_id = ?",
        (cart_id, user["id"]))
    db.commit()
    db.close()
    flash("Produs eliminat din cos.", "success")
    return redirect(url_for("cart"))


# ---------------------------------------------------------------------------
# Finalizare comanda si istoric comenzi
# ---------------------------------------------------------------------------

@app.route("/finalizare", methods=["GET", "POST"])
def checkout():
    user = current_user()
    if not user:
        return redirect(url_for("login", next=url_for("checkout")))

    db = get_db()
    items = db.execute(
        """SELECT ci.quantity, p.*
           FROM cart_items ci JOIN products p ON p.id = ci.product_id
           WHERE ci.user_id = ?""",
        (user["id"],),
    ).fetchall()

    if not items:
        db.close()
        flash("Cosul tau este gol.", "error")
        return redirect(url_for("cart"))

    total = sum(it["price"] * it["quantity"] for it in items)

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        address = request.form.get("address", "").strip()
        city = request.form.get("city", "").strip()
        phone = request.form.get("phone", "").strip()

        if not (full_name and address and city and phone):
            db.close()
            flash("Completeaza toate campurile de livrare.", "error")
            return render_template("checkout.html", items=items, total=total)

        # Cream comanda...
        order_id = db.execute(
            """INSERT INTO orders (user_id, total, full_name, address, city, phone)
               VALUES (?, ?, ?, ?, ?, ?) RETURNING id""",
            (user["id"], total, full_name, address, city, phone),
        ).fetchone()["id"]

        # ...si liniile comenzii.
        for it in items:
            db.execute(
                """INSERT INTO order_items
                   (order_id, product_id, name, price, quantity)
                   VALUES (?, ?, ?, ?, ?)""",
                (order_id, it["id"], it["name"], it["price"], it["quantity"]),
            )

        # Golim cosul.
        db.execute("DELETE FROM cart_items WHERE user_id = ?", (user["id"],))
        db.commit()
        db.close()
        flash("Comanda a fost plasata cu succes!", "success")
        return redirect(url_for("order_detail", order_id=order_id))

    db.close()
    return render_template("checkout.html", items=items, total=total, user=user)


@app.route("/comenzi")
def orders():
    user = current_user()
    if not user:
        return redirect(url_for("login", next=url_for("orders")))
    db = get_db()
    rows = db.execute(
        "SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC",
        (user["id"],),
    ).fetchall()
    db.close()
    return render_template("orders.html", orders=rows)


@app.route("/comanda/<int:order_id>")
def order_detail(order_id):
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    db = get_db()
    order = db.execute(
        "SELECT * FROM orders WHERE id = ? AND user_id = ?",
        (order_id, user["id"]),
    ).fetchone()
    if not order:
        db.close()
        abort(404)
    items = db.execute(
        "SELECT * FROM order_items WHERE order_id = ?", (order_id,)).fetchall()
    db.close()
    return render_template("order_detail.html", order=order, items=items)


# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    init_db()  # asigura ca tabelele exista
    app.run(debug=True, port=5000)
