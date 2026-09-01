def test_create_marina_201(client):
    r = client.post("/marinas", json={"name": "Harbor Point", "location": "Lake Union"})
    assert r.status_code == 201
    assert r.get_json()["name"] == "Harbor Point"


def test_create_marina_missing_name_400(client):
    assert client.post("/marinas", json={}).status_code == 400


def test_get_marina_ok(client):
    mid = client.post("/marinas", json={"name": "Harbor Point"}).get_json()["id"]
    r = client.get(f"/marinas/{mid}")
    assert r.status_code == 200
    assert r.get_json()["id"] == mid


def test_get_marina_404(client):
    assert client.get("/marinas/9999").status_code == 404


def test_list_marinas_empty_then_one(client):
    assert client.get("/marinas").get_json()["marinas"] == []
    client.post("/marinas", json={"name": "M"})
    assert len(client.get("/marinas").get_json()["marinas"]) == 1
