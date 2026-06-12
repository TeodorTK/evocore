# 🚀 Punerea EvoCore online pe Vercel (cu bază de date PostgreSQL)

EvoCore rulează pe Vercel ca aplicație Python (Flask), iar datele (conturi,
coș, comenzi, produse) sunt salvate într-o bază de date **PostgreSQL** găzduită
gratuit pe **Neon**. Așa, totul se păstrează (spre deosebire de SQLite, care nu
funcționează pe Vercel pentru că serverul este „read-only").

Durează ~15 minute. Ai nevoie de 3 conturi gratuite: **GitHub**, **Neon**, **Vercel**.

---

## Pasul 1 — Creează baza de date PostgreSQL (Neon)

1. Intră pe **https://neon.tech** și creează un cont gratuit (poți folosi GitHub).
2. Apasă **Create project** → alege o regiune din Europa (ex. *Frankfurt*).
3. După creare, în secțiunea **Connection string**, alege varianta
   **Pooled connection** și copiază tot textul. Arată cam așa:

   ```
   postgresql://user:parola@ep-xxxx-pooler.eu-central-1.aws.neon.tech/neondb?sslmode=require
   ```

   👉 Ai nevoie de acest text mai jos — îl vom numi **DATABASE_URL**.

---

## Pasul 2 — Populează baza de date Neon (de pe calculatorul tău)

În terminal, în folderul proiectului:

```bash
cd "Proiect BD"
export DATABASE_URL="postgresql://...   (lipește aici textul de la Neon)"
./venv/bin/python seed.py
```

Ar trebui să vezi „10 categorii, 100 produse populate". Gata — produsele sunt
acum în Neon. (Comanda de mai sus folosește baza Neon doar pentru această
rulare; local, fără `export`, aplicația folosește în continuare SQLite.)

---

## Pasul 3 — Urcă proiectul pe GitHub

Am inițializat deja un repository Git local cu un prim commit. Mai trebuie doar
să-l legi de GitHub:

1. Pe **https://github.com/new** creează un repository nou, gol (ex. `evocore`).
   **Nu** bifa „Add README".
2. În terminal (înlocuiește `UTILIZATOR` cu numele tău de GitHub):

   ```bash
   cd "Proiect BD"
   git branch -M main
   git remote add origin https://github.com/UTILIZATOR/evocore.git
   git push -u origin main
   ```

---

## Pasul 4 — Conectează la Vercel și pune online

1. Intră pe **https://vercel.com** și creează cont (autentifică-te cu GitHub).
2. Apasă **Add New… → Project** și importă repository-ul `evocore`.
3. Înainte de **Deploy**, deschide secțiunea **Environment Variables** și adaugă:

   | Name           | Value                                          |
   |----------------|------------------------------------------------|
   | `DATABASE_URL` | textul de la Neon (același din Pasul 2)         |
   | `SECRET_KEY`   | un text aleatoriu lung (ex. `evocore-9f3k2...`) |

4. Apasă **Deploy** și așteaptă ~1 minut.

Gata! Vei primi un link public de forma **`https://evocore-xxxx.vercel.app`** pe
care îl poți trimite oricui. 🎉

---

## Actualizări ulterioare

Orice modificare în cod o pui online astfel:

```bash
git add -A
git commit -m "descrierea modificării"
git push
```

Vercel redeschide automat o nouă versiune la fiecare `push`.

---

## Întrebări frecvente

**De ce nu merge SQLite direct pe Vercel?**
Vercel rulează aplicația în funcții „serverless" cu disc read-only și temporar.
SQLite ar pierde toate datele la fiecare cerere. PostgreSQL (Neon) este o bază
de date externă, permanentă — de aceea o folosim în producție.

**Local mai merge ca înainte?**
Da. Fără variabila `DATABASE_URL`, aplicația folosește SQLite local
(`./venv/bin/python app.py`). Cu `DATABASE_URL` setat, folosește PostgreSQL.

**Imaginile produselor?**
Sunt incluse în repository (`static/img/products/`) și livrate de Vercel.
Numele fișierelor coincid cu ID-urile din baza de date.
