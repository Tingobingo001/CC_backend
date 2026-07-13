# TaskForge API

A project and task management backend (think a simplified Trello/Asana) built as part of a backend recruitment task. Users can sign up, form teams, create projects inside those teams, add tasks with multiple assignees, comment on tasks, and everything is gated by role-based access control (Owner / Maintainer / Member / Viewer).

I was a complete beginner to backend development when I started this — the reasoning behind every major decision (and every bug I hit along the way) is documented in [ENGINEERING_DECISIONS.md](ENGINEERING_DECISIONS.md).

---

## Tech stack

- **FastAPI** — web framework (auto-generates interactive API docs at `/docs`)
- **PostgreSQL 16** — production database (SQLite for local development)
- **SQLAlchemy** — ORM
- **Pydantic** — request/response validation
- **JWT (python-jose)** + **bcrypt** — authentication and password hashing
- **Docker + docker-compose** — three-container stack: API, Postgres, NGINX
- **NGINX** — reverse proxy (the only public entry point)
- **pytest** — 49 automated end-to-end tests

---

## Running the project

### With Docker (recommended — this is the production setup)

Requires Docker Desktop.

```bash
git clone https://github.com/Tingobingo001/CC_backend.git
cd CC_backend
docker compose up --build
```

Then open **http://localhost/docs** — that request goes through NGINX on port 80, gets proxied to the API container, which talks to Postgres. The API container itself is bound to 127.0.0.1 only, so NGINX is the only way in from outside.

Data persists across restarts in a named Docker volume (`pgdata`). To wipe everything and start fresh:

```bash
docker compose down -v
docker compose up
```

### Without Docker (local development mode)

Requires Python 3.12+.

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows (source .venv/bin/activate on Linux/Mac)
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open **http://127.0.0.1:8000/docs**. This mode uses SQLite (a `dev.db` file appears automatically) — no database setup needed.

---

## Environment variables

Everything has a dev default, so local setup is zero-config. Production overrides them in `docker-compose.yml`.

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./dev.db` | Database connection string |
| `SECRET_KEY` | `dev-secret-change-me` | Signs every JWT — must be changed for any real deployment |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token lifetime |

---

## Running the tests

```bash
pytest tests/ -v
```

49 end-to-end tests covering auth (including that wrong-password and unknown-email return identical 401s), the full permission matrix across four identities, assignee edge cases, search/filter/pagination correctness, and validation errors. The tests run against a throwaway `test.db` — your dev data is untouched.

---

## API overview

Full interactive documentation is auto-generated at `/docs` (Swagger UI). A Postman collection is included at `docs/postman_collection.json`.

The endpoint structure follows the resource hierarchy — everything below a team is scoped by it:

```
POST   /auth/signup                     create account
POST   /auth/login                      get a JWT
GET    /auth/me                         current user

POST   /teams                           create team (creator becomes Owner)
GET    /teams                           my teams
GET    /teams/{id}/members              roster with roles
POST   /teams/{id}/members              invite by email (Owner/Maintainer)
GET    /teams/{id}/activity             audit log

POST   /teams/{id}/projects             create (Owner/Maintainer)
GET    /teams/{id}/projects             list (any member)
PATCH  /teams/{id}/projects/{pid}       partial update
DELETE /teams/{id}/projects/{pid}       Owner only

POST   /teams/{id}/projects/{pid}/tasks             create, with assignee_ids (Member+)
GET    /teams/{id}/projects/{pid}/tasks             supports ?search= &status= &priority= &limit= &offset=
PATCH  /teams/{id}/projects/{pid}/tasks/{tid}       partial update
DELETE /teams/{id}/projects/{pid}/tasks/{tid}       Owner/Maintainer
POST   /teams/{id}/projects/{pid}/tasks/{tid}/assignees/{uid}    assign a member
DELETE /teams/{id}/projects/{pid}/tasks/{tid}/assignees/{uid}    unassign

POST   /teams/{id}/projects/{pid}/tasks/{tid}/comments    any member incl. Viewers
GET    /teams/{id}/projects/{pid}/tasks/{tid}/comments    list
```

Roles: **Owner** (everything), **Maintainer** (manage projects/tasks/members), **Member** (create and edit tasks), **Viewer** (read + comment). Every check is enforced server-side on every endpoint.

Errors come back in one consistent shape:

```json
{ "error": { "code": 403, "message": "Insufficient role for this action" } }
```

---

## Repository structure

```
CC_backend/
├── app/
│   ├── main.py            # app entry point, routers, exception handlers
│   ├── config.py          # environment variable config
│   ├── database.py        # engine, session, get_db dependency
│   ├── models.py          # all 8 SQLAlchemy tables
│   ├── schemas.py         # Pydantic request/response shapes
│   ├── auth.py            # hashing, JWT, get_current_user, require_role
│   └── routers/
│       ├── users.py       # signup, login, me
│       ├── teams.py       # teams, members, activity feed
│       ├── projects.py
│       ├── tasks.py       # tasks + assignees + search/filter/pagination
│       └── comments.py
├── tests/
│   └── test_api.py        # 49 end-to-end tests
├── Dockerfile
├── docker-compose.yml     # api + postgres + nginx
├── nginx.conf
├── requirements.txt
├── ENGINEERING_DECISIONS.md
└── README.md
```

---

## Deployment

The full production stack — Docker, docker-compose, PostgreSQL with a persistent volume, and NGINX as reverse proxy with the API bound to localhost — is implemented and verified locally (see "Running the project" above; `http://localhost/docs` goes through the complete chain).

Cloud deployment was blocked by payment constraints (my GitHub Student Pack verification did not complete in time), so below is the exact runbook I would execute on a VPS. Every step after cloning uses the same compose file that is verified in this repo.

### VPS runbook

**1. Provision a server** — Ubuntu 24.04 LTS, smallest size (1GB RAM is enough), e.g. a DigitalOcean droplet. Note the IP.

**2. Install Docker on the server:**

```bash
ssh root@SERVER_IP
curl -fsSL https://get.docker.com | sh
```

**3. Clone and configure:**

```bash
git clone https://github.com/Tingobingo001/CC_backend.git
cd CC_backend
```

Set production secrets in `docker-compose.yml`: a real `SECRET_KEY` (`openssl rand -hex 32`) and a strong `POSTGRES_PASSWORD` (must also be updated inside `DATABASE_URL`).

```bash
docker compose up -d --build
```

At this point the API answers at `http://SERVER_IP` (NGINX on port 80).

**4. Domain** — register a free subdomain at duckdns.org and point it at the server IP.

**5. HTTPS** — replace the containerized NGINX with the host's NGINX (or add certbot to the stack); the simplest path:

```bash
apt install -y nginx certbot python3-certbot-nginx
# site config proxying to 127.0.0.1:8000, then:
certbot --nginx -d yourname.duckdns.org
```

Certbot obtains a Let's Encrypt certificate, rewrites the NGINX config for SSL, and sets up auto-renewal. The API is then live at `https://yourname.duckdns.org/docs`.

**6. Firewall:**

```bash
ufw allow OpenSSH && ufw allow 'Nginx Full' && ufw enable
```

---

## Known limitations / future improvements

Documented in detail in [ENGINEERING_DECISIONS.md](ENGINEERING_DECISIONS.md#8-what-i-would-improve-with-more-time) — headline items: Alembic migrations, refresh tokens, `ON DELETE CASCADE` foreign keys, and rate limiting on auth endpoints.
