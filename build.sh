#\!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt

cd frontend
npm install
npm run build
cd ..

python migrate_new_columns.py
python seed_if_empty.py
