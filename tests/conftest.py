"""Shared pytest fixtures.

Every test gets a brand-new app bound to an isolated in-memory SQLite database,
so tests are fully independent and never touch persistence/storable.db.
"""

import pytest

from main import create_app


@pytest.fixture()
def client():
    app = create_app("sqlite:///:memory:")
    with app.test_client() as c:
        yield c


@pytest.fixture()
def seeded(client):
    """A marina + a 40ft slip + a person + a fitting 36ft boat. Returns their ids."""
    marina = client.post(
        "/marinas", json={"name": "Harbor Point", "location": "Lake Union"}
    ).get_json()["id"]
    slip = client.post(
        f"/marinas/{marina}/slips",
        json={"identifier": "A-14", "length_ft": 40, "beam_ft": 14, "depth_ft": 8, "power": "50A"},
    ).get_json()["id"]
    person = client.post(
        "/people", json={"name": "Ada Lovelace", "email": "ada@example.com"}
    ).get_json()["id"]
    boat = client.post(
        f"/people/{person}/boats",
        json={"name": "Analytical", "boat_type": "sail", "length_ft": 36, "beam_ft": 12, "draft_ft": 6},
    ).get_json()["id"]
    return {"marina": marina, "slip": slip, "person": person, "boat": boat}
