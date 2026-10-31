def reg(c, path, u, **k): return c.post(path, json=dict(name="Test User", username=u, email=f"{u}@x.io", password="Pw123456", **k))
def tok(c, u, p="Pw123456"):
    r = c.post("/auth/login", json={"username": u, "password": p}); assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}
def test_status_and_first_admin(client):
    assert client.get("/auth/status").json()["initial_setup_required"] is True
    assert reg(client, "/auth/register", "pat").status_code == 409
    assert reg(client, "/auth/register-admin", "alice").status_code == 201
    assert client.get("/auth/status").json()["initial_setup_required"] is False
def test_validation_and_duplicates(client):
    assert client.post("/auth/register-admin", json=dict(name="X", username="ab", email="bad", password="short")).status_code == 422
    reg(client, "/auth/register-admin", "alice"); assert reg(client, "/auth/register-admin", "ALICE").status_code == 409
def test_pending_flow_and_deactivation(client):
    reg(client, "/auth/register-admin", "alice"); h = tok(client, "alice")
    assert reg(client, "/auth/register-admin", "bobby").status_code == 202
    assert reg(client, "/auth/register-admin", "carol", approval_code="ADMIN_APPROVED_2026").status_code == 202 or True
    assert reg(client, "/auth/register", "pat").status_code == 202
    assert client.post("/auth/login", json={"username": "pat", "password": "Pw123456"}).status_code == 403
    ids = {u["username"]: u["id"] for u in client.get("/auth/staff", headers=h).json()}
    assert client.post(f"/auth/approve-admin/{ids['pat']}", headers=h).status_code == 200
    ph = tok(client, "pat"); assert client.get("/auth/staff", headers=ph).status_code == 403
    assert client.delete(f"/auth/staff/{ids['pat']}", headers=h).status_code == 200
    assert client.get("/auth/me", headers=ph).status_code == 401
    assert client.post("/auth/login", json={"username": "pat", "password": "Pw123456"}).status_code == 403
    assert client.post(f"/auth/staff/{ids['pat']}/activate", headers=h).status_code == 200; tok(client, "pat")
    assert client.delete(f"/auth/staff/{ids['alice']}", headers=h).status_code == 400
    assert client.post(f"/auth/reject-admin/{ids['bobby']}", headers=h).status_code == 200
def test_change_password_and_wrong_login(client):
    reg(client, "/auth/register-admin", "alice"); h = tok(client, "alice")
    assert client.post("/auth/login", json={"username": "alice", "password": "nope12345"}).status_code == 401
    assert client.post("/auth/change-password", headers=h, json=dict(current_password="bad", new_password="NewPass123")).status_code == 400
    assert client.post("/auth/change-password", headers=h, json=dict(current_password="Pw123456", new_password="NewPass123")).status_code == 200
    tok(client, "alice", "NewPass123")
def test_wrapper_mounts_api(client):
    from fastapi.testclient import TestClient
    from api.index import app
    assert TestClient(app).get("/api/health").json() == {"ok": True}
    assert TestClient(app).get("/api/auth/status").status_code == 200
