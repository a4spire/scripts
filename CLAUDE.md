# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A self-hosted workshop/garage inventory management app with project-based material tracking and
Anthropic-powered capture flows (photo recognition, free-text parsing). Single-user today, but the
data model already carries a `User` reference on every movement/capture for future multi-user support.
Full rationale, ER diagram, and MVP scope are in `docs/ARCHITECTURE.md` (German) — read it before
making architectural changes.

Two independent npm packages, no monorepo tooling (deliberate, see ARCHITECTURE.md):

- `backend/` — Fastify + TypeScript + Prisma + PostgreSQL
- `frontend/` — Next.js 16 (App Router) + TypeScript + Tailwind, installable PWA

## Commands

### Backend (`cd backend`)

```bash
npm install
npm run prisma:migrate:dev   # apply/create migrations against a local Postgres
npm run prisma:seed          # creates SEED_ADMIN_EMAIL/SEED_ADMIN_PASSWORD admin user
npm run dev                  # tsx watch, http://localhost:4000
npm run build && npm start   # compile to dist/ and run
npx tsc -p tsconfig.json --noEmit   # typecheck only
```

Requires a `.env` (copy `backend/.env.example`) with at minimum `DATABASE_URL`, `SESSION_SECRET`
(≥32 chars — `@fastify/session` throws otherwise), `ANTHROPIC_API_KEY`. `WHISPER_API_URL` is optional;
voice capture throws if unset.

There is no test suite yet. Verification so far has been: `tsc --noEmit`, applying the Prisma
migration against a real Postgres, and manual `curl`/Playwright smoke runs through the API and UI.

### Frontend (`cd frontend`)

```bash
npm install
npm run dev      # next dev --webpack, http://localhost:3000
npm run build    # next build --webpack
npm run lint
```

**Always keep `--webpack` on `dev`/`build`.** Next 16 defaults to Turbopack, which is incompatible
with `@ducanh2912/next-pwa`'s webpack-based service-worker generation — dropping the flag breaks the
build with a Turbopack/webpack-config conflict error.

`NEXT_PUBLIC_API_URL` is inlined into the client bundle **at build time** (standard Next.js behavior
for `NEXT_PUBLIC_*` vars) — changing it requires a rebuild, not just a container restart. In
`docker-compose.yml` this is passed as a build `arg`, not a runtime `environment` var; keep it that way.

### Docker Compose (repo root)

```bash
cp .env.example .env   # fill in ANTHROPIC_API_KEY, SESSION_SECRET, passwords
docker compose up --build
```

Services: `postgres`, `whisper` (`onerahmet/openai-whisper-asr-webservice`, local ASR for voice
capture), `backend`, `frontend`. Photos persist in a named volume mounted at the backend's
`PHOTO_STORAGE_DIR`.

## Architecture

### Data model (`backend/prisma/schema.prisma`)

`Item.quantity` is a **denormalized cache**, never written directly outside of
`services/movement-service.ts`. The source of truth is the `StockMovement` log; every booking goes
through `bookMovement()`, which in one transaction (a) computes a signed delta from the movement
`type` (IN/RETURN add, OUT subtracts, CORRECTION applies the signed value as-is), (b) rejects the
booking if the resulting quantity would go negative, and (c) writes both the movement row and the
updated `Item.quantity`. Never update `Item.quantity` from a route handler directly.

Moving material between projects (or back to general stock) is **not** a distinct movement type —
`transferBetweenProjects()` emits a paired RETURN (from the source project) + OUT (to the destination,
or `null` for general stock), which keeps "sum of movements == current stock" true without a special
case in the booking logic.

`Location` and `Category` are self-referential trees (`parentId`) — no fixed depth. `AiCapture` records
every AI interaction (photo/text/voice/barcode-fallback) with the raw input and the proposed action
*before* anything is committed; `resultItemId`/`resultMovementId` link back to what was actually created
once confirmed. This table is what enforces requirement #14 (no AI-driven change without human
confirmation) — the only code path that writes to `Item`/`StockMovement` from an AI proposal is
`POST /api/ai/captures/:id/confirm` in `backend/src/routes/ai.ts`.

Migrations are hand/CLI-generated with `prisma migrate diff --from-empty --to-schema-datamodel` rather
than against a live shadow DB in this environment (no Docker daemon available locally) — if you add
schema changes, generate the migration SQL the same way and verify it applies cleanly, since there's
no CI wired up yet to catch a broken migration.

### AI capture flow (`backend/src/services/ai-service.ts`, `backend/src/routes/ai.ts`)

Photo recognition and free-text parsing both use Anthropic's forced tool-use (`tool_choice: {type:
"tool", name: ...}`) to get structured JSON back, validated with the zod schemas in that same file
(`photoProposalSchema`, `textProposalSchema`). Free-text parsing is given the current DB state (item
names+ids, locations, active projects, categories) as grounding context so Claude can resolve
references like "Regal A3" or "Projekt Bühnenbau X" to real IDs instead of inventing them.

The confirm endpoint takes a client-resolved `operations[]` array (`create_item` | `book_movement`,
see `confirmSchema` in `routes/ai.ts`) rather than re-trusting the original AI proposal — the frontend
capture page (`frontend/src/app/capture/page.tsx`) renders the proposal as editable fields first, and
whatever the user actually submits is what gets applied. A capture's `AiCapture.resultItemId`/
`resultMovementId` only ever stores the *last* item/movement created if `operations` has more than
one entry — a known simplification, not a bug; the movements themselves remain fully authoritative.

Voice capture (`POST /api/ai/voice`) transcribes via a local Whisper ASR container
(`transcribeAudio()`, hits `WHISPER_API_URL/asr?output=text`) and then reuses `parseFreeText()` — same
confirmation path as text capture. Claude has no direct audio input in this codebase; transcription is
a separate self-hosted step by design (see `docs/ARCHITECTURE.md` stack rationale).

### Auth

Cookie session via `@fastify/session` (in-memory store — fine for one Fastify instance, would need a
shared store like Redis before scaling to multiple backend instances). `requireAuth` is a per-route
`preHandler` hook (registered per route file, not globally), not global middleware — new route files
must add `fastify.addHook("preHandler", fastify.requireAuth)` themselves, following the pattern in
`routes/locations.ts` etc.

**Always select user fields explicitly via `userPublicSelect` (`backend/src/lib/selects.ts`) when
including a `User` relation** — the full `User` model includes `passwordHash`, and an `include: {
user: true }` will leak it into the JSON response (this was caught and fixed once already during
initial development; the item/movement/project routes all use `userPublicSelect` now).

### Frontend

Client components only (no server-side data fetching from Prisma) — all pages call the backend over
`fetch` with `credentials: "include"` via `frontend/src/lib/api.ts`. `AuthProvider`
(`frontend/src/components/AuthProvider.tsx`) checks `/api/auth/me` on mount and redirects to `/login`
on 401, skipping that check when already on `/login`. Session cookies work across the different
frontend/backend ports in local dev because they're same-site (same hostname, different port); in
production behind Cloudflare Tunnel, `CORS_ORIGIN` on the backend must exactly match the frontend's
public origin (no wildcard, since requests are made with credentials).
