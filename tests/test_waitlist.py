def test_create_waitlist_201(client, seeded):
    r = client.post(
        f"/marinas/{seeded['marina']}/waitlist",
        json={"person_id": seeded["person"], "min_length_ft": 30, "power": "30A", "notes": "x"},
    )
    assert r.status_code == 201
    assert r.get_json()["status"] == "waiting"


def test_waitlist_missing_person_400(client, seeded):
    assert client.post(f"/marinas/{seeded['marina']}/waitlist", json={}).status_code == 400


def test_waitlist_marina_404(client, seeded):
    assert client.post("/marinas/9999/waitlist", json={"person_id": seeded["person"]}).status_code == 404


def test_waitlist_person_404(client, seeded):
    assert client.post(f"/marinas/{seeded['marina']}/waitlist", json={"person_id": 9999}).status_code == 404


def test_waitlist_bad_power_400(client, seeded):
    r = client.post(
        f"/marinas/{seeded['marina']}/waitlist",
        json={"person_id": seeded["person"], "power": "220V"},
    )
    assert r.status_code == 400


def test_list_waitlist(client, seeded):
    client.post(f"/marinas/{seeded['marina']}/waitlist", json={"person_id": seeded["person"]})
    assert len(client.get(f"/marinas/{seeded['marina']}/waitlist").get_json()["waitlist"]) == 1
