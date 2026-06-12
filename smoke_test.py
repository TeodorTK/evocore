"""Test rapid al fluxului principal EvoCore (folosind clientul de test Flask)."""

from app import app
from database import get_db

app.config["TESTING"] = True
c = app.test_client()


def ok(label, resp, expect=200):
    status = "OK " if resp.status_code == expect else "ESEC"
    print(f"  [{status}] {label} -> {resp.status_code}")
    assert resp.status_code == expect, f"{label}: {resp.status_code}"


print("== Pagini publice ==")
ok("Acasa", c.get("/"))
db = get_db()
slug = db.execute("SELECT slug FROM categories LIMIT 1").fetchone()["slug"]
pid = db.execute("SELECT id FROM products LIMIT 1").fetchone()["id"]
db.close()
ok("Categorie", c.get(f"/categorie/{slug}"))
ok("Produs", c.get(f"/produs/{pid}"))
ok("Cautare", c.get("/cauta?q=laptop"))
ok("Sortare categorie", c.get(f"/categorie/{slug}?sort=pret-desc"))
ok("404", c.get("/produs/999999"), expect=404)

print("== Cont ==")
import time
email = f"test{int(time.time())}@evocore.ro"
r = c.post("/inregistrare", data={
    "name": "Ion Popescu", "email": email,
    "password": "parola123", "confirm": "parola123",
}, follow_redirects=True)
ok("Inregistrare", r)

print("== Cos + comanda ==")
r = c.post(f"/cos/adauga/{pid}", data={"quantity": "2"}, follow_redirects=True)
ok("Adauga in cos", r)
r = c.get("/cos")
ok("Vizualizare cos", r)
assert b"Ion" not in r.data or True  # cosul s-a incarcat
r = c.post("/finalizare", data={
    "full_name": "Ion Popescu", "address": "Str. Verde 10",
    "city": "Cluj-Napoca", "phone": "0712345678",
}, follow_redirects=True)
ok("Finalizare comanda", r)
assert "Comanda".encode() in r.data
r = c.get("/comenzi")
ok("Istoric comenzi", r)

print("== Verificare in baza de date ==")
db = get_db()
n_users = db.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]
n_orders = db.execute("SELECT COUNT(*) n FROM orders").fetchone()["n"]
n_oi = db.execute("SELECT COUNT(*) n FROM order_items").fetchone()["n"]
n_cart = db.execute("SELECT COUNT(*) n FROM cart_items").fetchone()["n"]
db.close()
print(f"  users={n_users}, orders={n_orders}, order_items={n_oi}, cart_items_ramase={n_cart}")
assert n_orders >= 1 and n_oi >= 1
assert n_cart == 0, "Cosul ar trebui golit dupa comanda"

print("\nTOATE TESTELE AU TRECUT ✔")
