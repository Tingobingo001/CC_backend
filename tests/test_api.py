"""
End-to-end API test suite.
Runs against a throwaway SQLite DB (test.db) — dev.db is untouched.
Tests run in file order and share state via `ctx`.
"""
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# --- test database, wired in BEFORE the app is imported ---
TEST_DB = "test.db"
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)

from app.database import Base, get_db
engine = create_engine(f"sqlite:///./{TEST_DB}", connect_args={"check_same_thread": False})
TestSession = sessionmaker(bind=engine, autoflush=False)

from app.main import app
Base.metadata.create_all(bind=engine)

def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

ctx = {}  # shared ids/tokens across tests

def auth(token):
    return {"Authorization": f"Bearer {token}"}

def login(email, password):
    r = client.post("/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


# ---------- auth ----------

def test_signup_owner():
    r = client.post("/auth/signup", json={"email": "owner@test.com", "name": "Owner", "password": "password123"})
    assert r.status_code == 201, r.text
    ctx["owner_id"] = r.json()["id"]
    assert "password" not in r.json() and "password_hash" not in r.json()

def test_signup_duplicate_email():
    r = client.post("/auth/signup", json={"email": "owner@test.com", "name": "Dup", "password": "password123"})
    assert r.status_code == 409

def test_signup_short_password():
    r = client.post("/auth/signup", json={"email": "x@test.com", "name": "X", "password": "abc"})
    assert r.status_code == 422

def test_signup_bad_email():
    r = client.post("/auth/signup", json={"email": "notanemail", "name": "X", "password": "password123"})
    assert r.status_code == 422

def test_signup_more_users():
    for email, name, key in [("bob@test.com", "Bob", "bob_id"),
                             ("carol@test.com", "Carol", "carol_id"),
                             ("dave@test.com", "Dave", "dave_id")]:
        r = client.post("/auth/signup", json={"email": email, "name": name, "password": "password123"})
        assert r.status_code == 201
        ctx[key] = r.json()["id"]

def test_login_ok():
    ctx["owner_token"] = login("owner@test.com", "password123")
    ctx["bob_token"] = login("bob@test.com", "password123")
    ctx["carol_token"] = login("carol@test.com", "password123")
    ctx["dave_token"] = login("dave@test.com", "password123")

def test_login_wrong_password():
    r = client.post("/auth/login", data={"username": "owner@test.com", "password": "wrong"})
    assert r.status_code == 401

def test_login_unknown_email_same_message():
    r1 = client.post("/auth/login", data={"username": "owner@test.com", "password": "wrong"})
    r2 = client.post("/auth/login", data={"username": "ghost@test.com", "password": "wrong"})
    assert r1.status_code == r2.status_code == 401
    assert r1.json()["detail"] == r2.json()["detail"]   # no email-probing

def test_me_requires_auth():
    assert client.get("/auth/me").status_code == 401

def test_me_ok():
    r = client.get("/auth/me", headers=auth(ctx["owner_token"]))
    assert r.status_code == 200 and r.json()["email"] == "owner@test.com"


# ---------- teams & memberships ----------

def test_create_team_auto_owner():
    r = client.post("/teams", json={"name": "Alpha"}, headers=auth(ctx["owner_token"]))
    assert r.status_code == 201, r.text
    ctx["team_id"] = r.json()["id"]
    r = client.get(f"/teams/{ctx['team_id']}/members", headers=auth(ctx["owner_token"]))
    roster = r.json()
    assert len(roster) == 1 and roster[0]["role"] == "owner"

def test_teams_require_auth():
    assert client.get("/teams").status_code == 401

def test_add_member_viewer_and_member():
    t = ctx["team_id"]
    r = client.post(f"/teams/{t}/members", json={"email": "bob@test.com", "role": "viewer"},
                    headers=auth(ctx["owner_token"]))
    assert r.status_code == 201, r.text
    r = client.post(f"/teams/{t}/members", json={"email": "carol@test.com", "role": "member"},
                    headers=auth(ctx["owner_token"]))
    assert r.status_code == 201, r.text

def test_add_member_duplicate():
    r = client.post(f"/teams/{ctx['team_id']}/members", json={"email": "bob@test.com", "role": "viewer"},
                    headers=auth(ctx["owner_token"]))
    assert r.status_code == 409

def test_add_member_unknown_email():
    r = client.post(f"/teams/{ctx['team_id']}/members", json={"email": "ghost@test.com", "role": "member"},
                    headers=auth(ctx["owner_token"]))
    assert r.status_code == 404

def test_add_member_invalid_role():
    r = client.post(f"/teams/{ctx['team_id']}/members", json={"email": "dave@test.com", "role": "emperor"},
                    headers=auth(ctx["owner_token"]))
    assert r.status_code == 422

def test_viewer_cannot_add_member():
    r = client.post(f"/teams/{ctx['team_id']}/members", json={"email": "dave@test.com", "role": "member"},
                    headers=auth(ctx["bob_token"]))
    assert r.status_code == 403

def test_outsider_cannot_view_roster():
    r = client.get(f"/teams/{ctx['team_id']}/members", headers=auth(ctx["dave_token"]))
    assert r.status_code == 403

def test_outsider_team_list_empty():
    r = client.get("/teams", headers=auth(ctx["dave_token"]))
    assert r.status_code == 200 and r.json() == []


# ---------- projects ----------

def test_create_project():
    r = client.post(f"/teams/{ctx['team_id']}/projects",
                    json={"name": "Website", "description": "Rebuild"},
                    headers=auth(ctx["owner_token"]))
    assert r.status_code == 201, r.text
    ctx["project_id"] = r.json()["id"]

def test_viewer_cannot_create_project():
    r = client.post(f"/teams/{ctx['team_id']}/projects", json={"name": "Nope"},
                    headers=auth(ctx["bob_token"]))
    assert r.status_code == 403

def test_viewer_can_list_projects():
    r = client.get(f"/teams/{ctx['team_id']}/projects", headers=auth(ctx["bob_token"]))
    assert r.status_code == 200 and len(r.json()) >= 1

def test_project_404():
    r = client.get(f"/teams/{ctx['team_id']}/projects/9999", headers=auth(ctx["owner_token"]))
    assert r.status_code == 404

def test_partial_update_keeps_name():
    p = ctx["project_id"]
    r = client.patch(f"/teams/{ctx['team_id']}/projects/{p}",
                     json={"description": "changed"}, headers=auth(ctx["owner_token"]))
    assert r.status_code == 200 and r.json()["name"] == "Website"


# ---------- tasks ----------

def test_create_task_with_assignees():
    r = client.post(f"/teams/{ctx['team_id']}/projects/{ctx['project_id']}/tasks",
                    json={"title": "Design homepage", "priority": "high",
                          "assignee_ids": [ctx["owner_id"], ctx["bob_id"]]},
                    headers=auth(ctx["owner_token"]))
    assert r.status_code == 201, r.text
    body = r.json()
    ctx["task_id"] = body["id"]
    assert set(body["assignee_ids"]) == {ctx["owner_id"], ctx["bob_id"]}

def test_create_task_invalid_status():
    r = client.post(f"/teams/{ctx['team_id']}/projects/{ctx['project_id']}/tasks",
                    json={"title": "Bad", "status": "flying"}, headers=auth(ctx["owner_token"]))
    assert r.status_code == 422

def test_create_task_nonmember_assignee():
    r = client.post(f"/teams/{ctx['team_id']}/projects/{ctx['project_id']}/tasks",
                    json={"title": "Bad", "assignee_ids": [ctx["dave_id"]]},
                    headers=auth(ctx["owner_token"]))
    assert r.status_code == 422

def test_member_can_create_task():
    r = client.post(f"/teams/{ctx['team_id']}/projects/{ctx['project_id']}/tasks",
                    json={"title": "Carol's task"}, headers=auth(ctx["carol_token"]))
    assert r.status_code == 201
    ctx["carol_task_id"] = r.json()["id"]

def test_viewer_cannot_create_task():
    r = client.post(f"/teams/{ctx['team_id']}/projects/{ctx['project_id']}/tasks",
                    json={"title": "Bob's task"}, headers=auth(ctx["bob_token"]))
    assert r.status_code == 403

def test_member_cannot_delete_task():
    r = client.delete(f"/teams/{ctx['team_id']}/projects/{ctx['project_id']}/tasks/{ctx['carol_task_id']}",
                      headers=auth(ctx["carol_token"]))
    assert r.status_code == 403

def test_assign_and_conflicts():
    base = f"/teams/{ctx['team_id']}/projects/{ctx['project_id']}/tasks/{ctx['carol_task_id']}/assignees"
    r = client.post(f"{base}/{ctx['bob_id']}", headers=auth(ctx["owner_token"]))
    assert r.status_code == 201
    r = client.post(f"{base}/{ctx['bob_id']}", headers=auth(ctx["owner_token"]))
    assert r.status_code == 409
    r = client.post(f"{base}/{ctx['dave_id']}", headers=auth(ctx["owner_token"]))
    assert r.status_code == 422

def test_unassign():
    base = f"/teams/{ctx['team_id']}/projects/{ctx['project_id']}/tasks/{ctx['carol_task_id']}/assignees"
    r = client.delete(f"{base}/{ctx['bob_id']}", headers=auth(ctx["owner_token"]))
    assert r.status_code == 204
    r = client.delete(f"{base}/{ctx['bob_id']}", headers=auth(ctx["owner_token"]))
    assert r.status_code == 404

def test_owner_can_delete_task():
    r = client.delete(f"/teams/{ctx['team_id']}/projects/{ctx['project_id']}/tasks/{ctx['carol_task_id']}",
                      headers=auth(ctx["owner_token"]))
    assert r.status_code == 204


# ---------- comments ----------

def test_viewer_can_comment():
    r = client.post(f"/teams/{ctx['team_id']}/projects/{ctx['project_id']}/tasks/{ctx['task_id']}/comments",
                    json={"content": "Looks good!"}, headers=auth(ctx["bob_token"]))
    assert r.status_code == 201, r.text
    assert r.json()["author_id"] == ctx["bob_id"]

def test_outsider_cannot_comment():
    r = client.post(f"/teams/{ctx['team_id']}/projects/{ctx['project_id']}/tasks/{ctx['task_id']}/comments",
                    json={"content": "Let me in"}, headers=auth(ctx["dave_token"]))
    assert r.status_code == 403

def test_list_comments():
    r = client.get(f"/teams/{ctx['team_id']}/projects/{ctx['project_id']}/tasks/{ctx['task_id']}/comments",
                   headers=auth(ctx["owner_token"]))
    assert r.status_code == 200 and len(r.json()) >= 1


# ---------- activity ----------

def test_activity_feed():
    r = client.get(f"/teams/{ctx['team_id']}/activity", headers=auth(ctx["owner_token"]))
    assert r.status_code == 200
    actions = " | ".join(a["action"] for a in r.json())
    assert "created team" in actions and "created task" in actions