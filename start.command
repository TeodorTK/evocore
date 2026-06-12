#!/bin/bash
# EvoCore - script de pornire (dublu-click pe macOS sau ruleaza in terminal).
cd "$(dirname "$0")"

# Creeaza mediul virtual daca nu exista.
if [ ! -d "venv" ]; then
    echo "Creez mediul virtual si instalez Flask..."
    python3 -m venv venv
    ./venv/bin/pip install --quiet -r requirements.txt
fi

# Populeaza baza de date daca nu exista.
if [ ! -f "evocore.db" ]; then
    echo "Populez baza de date din folderul arhiva..."
    ./venv/bin/python seed.py
fi

echo ""
echo "EvoCore porneste pe  http://127.0.0.1:5000"
echo "Apasa Ctrl+C ca sa opresti serverul."
echo ""
./venv/bin/python app.py
