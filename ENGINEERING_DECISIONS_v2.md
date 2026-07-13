# Engineering Decisions

This document explains the reasoning behind the major technical choices in this project, the problems I ran into along the way, and what I would improve with more time.

---

## 1. Stack choices

### Framework: FastAPI

- I am a beginner to backend development, so I started by researching the different options and workflows available for building this project.
- I chose Python since I had prior knowledge of the language. I also read that Django's permission system is global ("can this user edit tasks anywhere?"), while this task needs per-team roles ("is this user a Maintainer of *this* team?") — that check is custom code in any framework, so Django's head start was smaller than it looked, while its learning overhead was larger.
- I chose FastAPI over Django/Flask because everything is explicit: I can see the password hashing call, the token creation, and the permission check. This meant I actually understood every decision instead of accepting framework defaults — and when something broke, the traceback pointed at my own code, not framework internals.
- FastAPI auto-generates interactive API documentation at `/docs`, which satisfied the API documentation deliverable essentially for free.
- The tradeoff I accepted: assembling four smaller libraries (FastAPI, SQLAlchemy, Pydantic, python-jose) instead of one batteries-included framework.

### Database: PostgreSQL (production) / SQLite (development)

- Since I was new to all of this and had no experience with Docker, I developed on SQLite first — it is a database in a single file, with zero installation or configuration. The plan from the start was: learn the core concepts on SQLite, switch to Postgres at containerization time.
- The switch was cheap by design: all database access goes through SQLAlchemy, and the only thing naming the database is one connection string read from the `DATABASE_URL` environment variable. Locally it defaults to SQLite; in Docker, compose sets a Postgres URL. Same code, both worlds.
- One dialect quirk I hit: SQLite refuses cross-thread use by default, but FastAPI handles requests across threads, so SQLite needs `connect_args={"check_same_thread": False}`. Postgres would reject that argument, so it is applied conditionally based on the URL prefix.
- Production runs PostgreSQL 16 in Docker: the standard relational choice, with proper concurrency.
- Honest tradeoff: developing on a different database than production can hide dialect-specific bugs. For a project this size, the test suite plus a manual pass against the containerized Postgres covered that gap.

### Auth: JWT (stateless) over sessions

- A JWT is a signed note the server writes to itself — the payload (user id, expiry) is readable by anyone, but the signature can only be produced with the secret key, so it cannot be forged or altered. I verified this mental model directly by pasting my own token into jwt.io: my user id and expiry sat there in plaintext, but the signature could not be validated without the key.
- Why stateless won: verifying a request costs one signature check — no session table, no database lookup per request.
- The tradeoff: stateless means no server-side revocation — a stolen token works until it expires. To limit that damage, access tokens expire after 30 minutes (configurable via environment variable). I felt this working during development, getting logged out mid-testing-session repeatedly. The proper companion mechanism, refresh tokens, is listed under future improvements.
- Login returns the identical vague 401 for both wrong-password and unknown-email, so an attacker cannot probe which emails have accounts. The test suite explicitly asserts the two messages match.
- The `SECRET_KEY` moved from code into an environment variable: whoever holds it can mint valid tokens for any user, so it is the crown jewel of the system and cannot live in git history.

### Password hashing: bcrypt

- Passwords are never stored — only bcrypt hashes. Hashing is one-way: even the site owner cannot recover a password, only verify a fresh guess against the stored hash. (I proved this to myself the hard way by forgetting a test password mid-project — there was no way back, only creating a new user. This is also why real services send password *reset* links instead of your old password: they never had it.)
- bcrypt is deliberately slow (tunable cost factor), which makes brute-forcing leaked hashes expensive, and it salts every hash — I verified in the database that two users with the identical password get completely different hashes.
- As a second, independent layer: response schemas (`UserOut`) simply have no password field, and FastAPI's `response_model` strips anything not declared — so even a hash is structurally incapable of leaking into an API response.
- Compatibility issue: the latest bcrypt release was incompatible with passlib, so I pinned the older `bcrypt==4.0.1` (full story in the Bugs section).

---

## 2. Database schema design

### The key insight: roles live on the membership, not the user

- The naive design puts a `role` column on `User` — which silently assumes a person has one role globally. But the requirement is per-team: the same user must be able to be Owner of team A and Viewer of team B at the same time, which the naive design cannot represent at all.
- The realization: a role is not a property of a person — it is a property of a person's relationship to *one specific team*. There is already a table whose rows are exactly that relationship: the user↔team join table. So `role` is a column on `TeamMembership`.
- The payoffs cascade from this one decision: creating a team automatically crowns the creator by inserting a single membership row with `role=owner` (inside the same transaction as the team itself, so a half-created ownerless team is impossible). And checking any permission reduces to fetching one row: this user's membership in this team. The entire RBAC layer is a query on this table.

### Table overview

- `User`, `Team`, `TeamMembership` (user_id, team_id, role), `Project` (team_id FK), `Task` (project_id FK, status/priority enums, created_by), `TaskAssignment` (task_id, user_id — join table enabling multiple assignees per task), `Comment`, `ActivityLog`.
- Two relationship patterns cover all eight tables: one-to-many (foreign key on the child) and many-to-many (join table). `TeamMembership` is just `TaskAssignment` with a payload — a `role` column riding on the link.
- I defined all eight tables in one sitting before most of them had endpoints, because tables reference each other and getting the relationships right once beat welding new tables onto a live schema later.

### Enums for status, priority, and role

- `Role`, `TaskStatus`, and `TaskPriority` are database-level enums — invalid values like role "emperor" or status "flying" are structurally impossible, and error responses list the legal values. Enums also made one of my bugs loud and legible (see the enum bug below): with free-text status strings, invalid tasks would have silently accumulated instead of failing fast.

### Team-scoped queries as structural security

- Every lookup filters by the FULL ancestry: a task is fetched by task_id AND project_id, a project by project_id AND team_id. Without this, a member of team A who passes the role check could fetch objects belonging to team B just by guessing ids. Cross-team leakage is impossible by construction, not by developer vigilance.

---

## 3. Authorization (RBAC)

### The dependency factory pattern

- I first wrote the permission check longhand in one endpoint — fetch the caller's membership, 403 if absent, proceed — and immediately saw it would repeat across roughly twenty endpoints. So I abstracted it.
- `require_role(*allowed_roles)` is a factory: it runs once and manufactures a FastAPI dependency with the allowed roles baked in (a closure). That manufactured function is what `Depends()` receives and FastAPI runs before every request reaches the endpoint.
- The dependency reads `team_id` from the URL path automatically (FastAPI supplies path parameters to dependencies with no extra plumbing), loads the caller's membership for that team, and raises 403 before the endpoint runs if the role is not permitted.
- Protecting any endpoint costs one line: `Depends(require_role(Role.owner, Role.maintainer))`. The task's permission matrix translated into one decorated line per endpoint.
- Two distinct 403s: "Not a member of this team" vs "Insufficient role for this action" — helpful without leaking anything.

### Permission tiers

- ALL roles: read access, plus commenting — per the spec, commenting is the one write action every role gets, including Viewers.
- Member and up: create/edit tasks.
- Owner/Maintainer: manage projects, members, and deletions (project deletion restricted to Owner).
- Enforcement is server-side on every endpoint. Hiding a button in a UI is not security; a hand-crafted HTTP request hits the same 403.

---

## 4. Bugs encountered and how I solved them

### passlib/bcrypt version incompatibility

- Symptom: 500 on signup; the traceback showed `AttributeError: module 'bcrypt' has no attribute '__about__'` and a 72-byte ValueError coming from passlib's own startup self-test — not from my password at all.
- Cause: passlib (unmaintained since 2020) probes bcrypt's version in a way that recent bcrypt releases removed.
- Fix: pinned `bcrypt==4.0.1` and re-froze `requirements.txt` so the Docker build could not silently reinstall the broken newer version and bring the bug back at deploy time.
- Lesson: dependency compatibility is real; pin what you have verified.

### Lazy relationship strings → whack-a-mole errors

- Symptom: the server booted fine, but requests failed one at a time — first `failed to locate a name 'TaskAssignee'`, then `'TaskComment'`, then a `back_populates` mismatch (`assignment` vs the actual attribute `assignments`).
- Cause: SQLAlchemy's `relationship("ClassName")` takes the class name as a string (necessarily — it solves the circular-reference problem where two classes reference each other before both exist). But strings are not checked by the editor, and SQLAlchemy resolves them lazily, stopping at the first failure — so typos surface one per request.
- Fix: after two manual rounds each missed a sibling typo, I forced eager validation with `configure_mappers()` as a one-line terminal check, which converted all remaining failures into a single immediate to-do list. Then I added it permanently to app startup, so any future broken relationship fails loudly at boot instead of ambushing a request later.
- Lesson: when a system validates lazily, find its eager-validation switch and run it as a pre-flight check.

### Wrong enum value — caught only by the test suite

- Symptom: 11 test failures on the first run of the filtering tests. The error message itself was the diagnosis: valid `TaskStatus` values were `['todo', 'in_progress', 'viewer']` — a Role value had wandered into TaskStatus in a copy-paste slip, and there was no `done`.
- Manual testing never caught this in two days of use, because I had never actually set a task to "done". The test suite's seeding step tried, and failed immediately.
- Fix: one line. Lesson: automated tests exercise paths that manual clicking never does.

### response_model caught a field-name typo at the source

- I returned `{"Access_token": ...}` (capital A) from login. FastAPI validates responses against the declared schema (`TokenOut` requires `access_token`) and raised a loud error naming the missing field — instead of silently shipping a malformed response that would have broken every client while my server logs showed nothing wrong.
- Lesson: response contracts protect API consumers. The same mechanism doubles as a security filter: password hashes structurally cannot leak, because `UserOut` does not declare them.

### Nested Column typo and a naming lesson

- I wrote `Column(Column(Enum(Role), ...))` for the role field, which crashed at startup with an opaque `_set_parent()` error — one `Column(...)` wrapping the type and options is correct. I also initially named the column `role_id`, but the `_id` suffix conventionally signals a foreign key; this column holds the value itself, so it became plain `role`.

### Depends(fn) vs Depends(fn()) — and `if existing` vs `if existing()`

- I passed a *called* generator to `Depends` once, and called a query *result* like a function once — opposite mistakes with the same underlying question: is this a function I want the framework to run, or a value I want to inspect?

### Missing created_by column → why migrations exist

- My endpoint passed a field the Task model did not have (`'created_by' is an invalid keyword argument for Task`). The fix was one model line — but applying it meant deleting the dev database and recreating it, because `create_all` creates missing tables and never alters existing ones. Deferring Alembic was a deliberate five-day tradeoff; this was its cost, paid in person — which is why Alembic leads the improvements list.

---

## 5. Testing

- 49 automated pytest tests using FastAPI's TestClient run the whole API in-process against a throwaway SQLite database, so dev and production data are untouched.
- Coverage: auth (including asserting that wrong-password and unknown-email return IDENTICAL 401s, preventing email enumeration), the full permission matrix across four identities (owner / viewer / member / outsider), assignee edge cases (duplicate → 409, non-member → 422), search/filter/pagination correctness — including that pages do not overlap, which silently depends on stable ordering — and validation errors.
- The suite paid for itself immediately and twice: the first run caught a missing endpoint (the activity feed reader), and the filtering tests caught the enum bug that two days of manual testing had walked past.
- Known tradeoff: the tests share state through an ordered module-level context — pragmatic for a five-day end-to-end suite; isolated per-test fixtures would be the production refinement.

---

## 6. Deployment architecture

- Three-container docker-compose stack: PostgreSQL 16 (with a named volume for persistence and a healthcheck the API waits on, solving the startup race where the API would otherwise crash connecting to a database that has not finished booting), the API container (Python 3.12-slim image, with requirements installed before the code is copied so Docker's layer cache makes rebuilds fast), and NGINX as a reverse proxy.
- A request's journey: port 80 → NGINX container → proxied to `http://api:8000` (Docker's internal DNS resolves service names to containers — the same mechanism as the `@db:5432` database URL) → Postgres.
- The API port is bound to `127.0.0.1` only — external traffic has exactly one way in: port 80, through NGINX. NGINX is the front door, not decoration.
- Persistence verified directly: `docker compose down` followed by `up`, and users survive — the data lives in the `pgdata` volume, outside the containers. Containers are disposable; volumes persist.
- The container runs Python 3.12 regardless of the host's Python 3.14 — pinning the environment being the entire point of containers (and it sidestepped every 3.14 compatibility issue I met during development).
- Configuration is via environment variables (the 12-factor principle): `DATABASE_URL`, `SECRET_KEY`, token expiry. Dev defaults keep local setup zero-config; production overrides them in compose. Secrets never live in code, because anything committed to git stays in history forever.
- Cloud deployment was blocked by payment constraints (GitHub Student Pack verification did not complete in time). The identical production stack — compose, Postgres, NGINX reverse proxy, localhost-bound API — was implemented and verified locally, and the complete VPS runbook (server provisioning, Docker install, clone, production secrets, compose up, DuckDNS domain, NGINX site config, Let's Encrypt HTTPS via certbot) is documented in the README, ready to execute.

---

## 7. Deliberate omissions

Endpoints I chose *not* to build are design decisions too:

- No `GET /users` (list all users): letting any authenticated account enumerate every registered user is a privacy leak. Member discovery happens through team rosters (which require membership), and invitations use email — which the inviter already knows.
- No user-deletion endpoint: correct deletion semantics are genuinely hard — what happens to the user's tasks, or their comments threaded into other people's work? Real products solve this with soft-deletes and anonymization. A naive hard-delete would corrupt referential integrity, so omitting it was better than shipping it wrong. (Postgres agrees: a bare `DELETE FROM users` is refused with a foreign-key violation.)

---

## 8. What I would improve with more time

- **Alembic migrations** — versioned schema changes instead of the delete-and-recreate dev workflow. I felt this pain directly every time a model changed.
- **Refresh tokens** — pairing the 30-minute access tokens with long-lived refresh tokens so sessions survive without re-login. I experienced the UX cost of short-lived-only tokens repeatedly during development.
- **ON DELETE CASCADE foreign keys** — assignment cleanup on task deletion is currently manual in the endpoint; the schema should own cleanup rather than endpoint code having to remember it. I hit the orphan-row problem twice.
- **Rate limiting** on auth endpoints to slow brute-force login attempts.
- **Isolated test fixtures** instead of ordered shared-state tests.
- **Pydantic ConfigDict migration** — currently using the deprecated class-based `Config` (cosmetic deprecation warnings only).
- **Background jobs, caching, WebSockets** — the remaining bonus features, in that order of value.
