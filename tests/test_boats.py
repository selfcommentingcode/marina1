import pytest


def test_create_boat_201(client, seeded):
    r = client.post(f"/people/{seeded['person']}/boats", json={"name": "Second", "length_ft": 20})
    assert r.status_code == 201
    assert r.get_json()["owner_id"] == seeded["person"]


@pytest.mark.parametrize(
    "payload",
    [
        {"length_ft": 20},   # missing name
        {"name": "NoLen"},   # missing length_ft
    ],
)
def test_create_boat_missing_fields_400(client, seeded, payload):
    assert client.post(f"/people/{seeded['person']}/boats", json=payload).status_code == 400


def test_create_boat_bad_type_400(client, seeded):
    r = client.post(
        f"/people/{seeded['person']}/boats",
        json={"name": "X", "length_ft": 20, "boat_type": "hovercraft"},
    )
    assert r.status_code == 400


def test_create_boat_person_404(client):
    assert client.post("/people/9999/boats", json={"name": "X", "length_ft": 20}).status_code == 404


def test_list_boats(client, seeded):
    assert len(client.get(f"/people/{seeded['person']}/boats").get_json()["boats"]) == 1


def test_list_boats_person_404(client):
    assert client.get("/people/9999/boats").status_code == 404
