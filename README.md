# DakPro Academy v2 — Installatie

## Snelstart in GitHub Codespaces

### 1. Backend
```bash
cd backend
npm install
cp .env.example .env
# Vul Stripe sleutels in .env
sqlite3 database.demo.db < schema.sql
sqlite3 database.demo.db < seed.sql
node server.js
```
Ports → 3000 → **Public** → kopieer URL

### 2. Frontend
Pas `API_BASE` aan in `frontend/public/app.js`:
```js
const API_BASE = "https://[jouw-naam]-3000.app.github.dev";
```
```bash
cd frontend/public
python3 -m http.server 5173
```
Ports → 5173 → **Public** → open in browser

### 3. PWA installeren
- **Android**: Chrome → menu ⋮ → Toevoegen aan beginscherm
- **iPhone**: Safari → Deel → Zet op beginscherm
- **PC**: Chrome → adresbalk installeer-icoon

### 4. Demo account
Email: `demo@dakpro.nl` → heeft toegang tot roofing + leien cursus

## Cursusinhoud
1. **Bitumineuze dakbedekking** — SBS, APP, Groendak (Sopralene Optima Garden), Renovatie (DuO HT / Aero FC)
2. **Leien dakbedekking** — EN 12326, Ekoderdecking, legpatronen, details
3. **VGM** — preview only

## Foto's
Eigen projectfoto's in `frontend/public/images/` (uw eigendom, geen licentieprobleem)

## Stripe setup
Zie .env.example — vul PRICE_MAP aan in server.js met echte Price IDs
