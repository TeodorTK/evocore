"""Punctul de intrare pentru Vercel.

Vercel ruleaza fisierele din folderul `api/` ca functii serverless si
detecteaza automat obiectul WSGI numit `app`. Importam aplicatia Flask
din `app.py` (aflat in radacina proiectului).
"""

import os
import sys

# Adaugam radacina proiectului in calea de import, ca sa gasim `app.py`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402  (Vercel foloseste acest obiect `app`)
