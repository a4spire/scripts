# Werkstatt-Lagerverwaltung

Self-hosted Lagerverwaltung mit Projekt-Zuordnung und KI-gestützter Erfassung (Anthropic API).
Architektur, Datenmodell und MVP-Scope: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Quickstart (Docker Compose)

```bash
cp .env.example .env
# .env ausfüllen: ANTHROPIC_API_KEY, SESSION_SECRET, Passwörter

docker compose up --build
```

- Frontend: http://localhost:3000 (PWA, "Zum Startbildschirm hinzufügen" möglich)
- Backend-API: http://localhost:4000
- Login mit `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` aus `.env` (wird beim ersten Start gesät)

Hinweis: `NEXT_PUBLIC_API_URL` wird beim Frontend-Build fest einkompiliert (Next.js-Verhalten für
`NEXT_PUBLIC_*`-Variablen). Bei Domain-Änderung (z. B. Cloudflare Tunnel) muss das Frontend-Image
neu gebaut werden (`docker compose build frontend`).

## Lokale Entwicklung ohne Docker

Backend:
```bash
cd backend
cp .env.example .env   # DATABASE_URL auf lokale Postgres-Instanz anpassen
npm install
npm run prisma:migrate:dev
npm run prisma:seed
npm run dev
```

Frontend:
```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

## Betrieb hinter Cloudflare Tunnel

Frontend und Backend als zwei Tunnel-Hostnamen (oder ein Hostname mit Pfad-Routing) exposen.
`CORS_ORIGIN` im Backend muss exakt der öffentlichen Frontend-URL entsprechen (Cookies laufen mit
`credentials: include`, daher kein Wildcard-Origin möglich).

## Projektstruktur

```
backend/    Fastify + TypeScript + Prisma + PostgreSQL
frontend/   Next.js (App Router) + TypeScript + Tailwind, PWA via @ducanh2912/next-pwa
docs/       Architektur- und Scope-Dokumentation
```
