import pytest


def test_create_slip_available(client, seeded):
    r = client.post(
        f"/marinas/{seeded['marina']}/slips",
        json={"identifier": "B-1", "length_ft": 30, "beam_ft": 10},
    )
    assert r.status_code == 201
    assert r.get_json()["status"] == "available"


@pytest.mark.parametrize(
    "payload",
    [
        {"length_ft": 30, "beam_ft": 10},      # missing identifier
        {"identifier": "X", "beam_ft": 10},    # missing length_ft
        {"identifier": "X", "length_ft": 30},  # missing beam_ft
    ],
)
def test_create_slip_missing_fields_400(client, seeded, payload):
    assert client.post(f"/marinas/{seeded['marina']}/slips", json=payload).status_code == 400


def test_create_slip_bad_power_400(client, seeded):
    r = client.post(
        f"/marinas/{seeded['marina']}/slips",
        json={"identifier": "X", "length_ft": 30, "beam_ft": 10, "power": "220V"},
    )
    assert r.status_code == 400


def test_create_slip_bad_status_400(client, seeded):
    r = client.post(
        f"/marinas/{seeded['marina']}/slips",
        json={"identifier": "X", "length_ft": 30, "beam_ft": 10, "status": "sunk"},
    )
    assert r.status_code == 400


def test_create_slip_marina_404(client):
    r = client.post("/marinas/9999/slips", json={"identifier": "X", "length_ft": 30, "beam_ft": 10})
    assert r.status_code == 404


def test_get_slip_404(client):
    assert client.get("/slips/9999").status_code == 404


def test_list_slips_status_filter(client, seeded):
    # Occupy the seeded slip, add a free one, then filter both ways.
    client.post(
        f"/slips/{seeded['slip']}/holdings",
        json={"person_id": seeded["person"], "boat_id": seeded["boat"], "start_date": "2026-05-01"},
    )
    client.post(f"/marinas/{seeded['marina']}/slips", json={"identifier": "B-1", "length_ft": 30, "beam_ft": 10})
    occ = client.get(f"/marinas/{seeded['marina']}/slips?status=occupied").get_json()["slips"]
    avail = client.get(f"/marinas/{seeded['marina']}/slips?status=available").get_json()["slips"]
    assert len(occ) == 1
    assert len(avail) == 1


def test_list_slips_min_length_filter(client, seeded):
    client.post(f"/marinas/{seeded['marina']}/slips", json={"identifier": "B-1", "length_ft": 30, "beam_ft": 10})
    big = client.get(f"/marinas/{seeded['marina']}/slips?min_length=35").get_json()["slips"]
    assert len(big) == 1  # only the 40ft seeded slip clears the filter


def test_list_slips_marina_404(client):
    assert client.get("/marinas/9999/slips").status_code == 404
