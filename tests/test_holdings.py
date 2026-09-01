"""Tests for slip holdings — the core lease object and its guardrails.

These deliberately exercise both sides of the branchy logic: the boat-fit
check (length / beam / draft, each with its None-guard), the double-booking
rule, and the holding-status transitions.
"""

import pytest

# label, boat payload, expect the lease to succeed (201)
FIT_CASES = [
    ("fits",        {"name": "ok",   "length_ft": 36, "beam_ft": 12, "draft_ft": 6}, True),
    ("only_length", {"name": "min",  "length_ft": 30},                                True),  # beam/draft None -> guards skip
    ("too_long",    {"name": "long", "length_ft": 60, "beam_ft": 12, "draft_ft": 6}, False),
    ("too_wide",    {"name": "wide", "length_ft": 36, "beam_ft": 20, "draft_ft": 6}, False),
    ("too_deep",    {"name": "deep", "length_ft": 36, "beam_ft": 12, "draft_ft": 99}, False),
]


@pytest.mark.parametrize("label, boat, expect_ok", FIT_CASES, ids=[c[0] for c in FIT_CASES])
def test_fit_check_branches(client, seeded, label, boat, expect_ok):
    bid = client.post(f"/people/{seeded['person']}/boats", json=boat).get_json()["id"]
    r = client.post(
        f"/slips/{seeded['slip']}/holdings",
        json={"person_id": seeded["person"], "boat_id": bid, "start_date": "2026-05-01"},
    )
    assert (r.status_code == 201) == expect_ok
    if not expect_ok:
        assert "does not fit" in r.get_json()["error"]


def test_create_holding_occupies_slip(client, seeded):
    r = client.post(
        f"/slips/{seeded['slip']}/holdings",
        json={
            "person_id": seeded["person"],
            "boat_id": seeded["boat"],
            "start_date": "2026-05-01",
            "rate_amount": 2400,
            "rate_period": "seasonal",
        },
    )
    assert r.status_code == 201
    assert r.get_json()["status"] == "active"
    assert client.get(f"/slips/{seeded['slip']}").get_json()["status"] == "occupied"


def test_create_holding_without_boat(client, seeded):
    r = client.post(
        f"/slips/{seeded['slip']}/holdings",
        json={"person_id": seeded["person"], "start_date": "2026-05-01"},
    )
    assert r.status_code == 201
    assert r.get_json()["boat_id"] is None


def test_double_booking_returns_409(client, seeded):
    base = {"person_id": seeded["person"], "start_date": "2026-05-01"}
    assert client.post(f"/slips/{seeded['slip']}/holdings", json={**base, "boat_id": seeded["boat"]}).status_code == 201
    second = client.post(f"/slips/{seeded['slip']}/holdings", json=base)
    assert second.status_code == 409
    assert "active holding" in second.get_json()["error"]


def test_holding_boat_owner_mismatch_400(client, seeded):
    other = client.post("/people", json={"name": "Bob"}).get_json()["id"]
    r = client.post(
        f"/slips/{seeded['slip']}/holdings",
        json={"person_id": other, "boat_id": seeded["boat"], "start_date": "2026-05-01"},
    )
    assert r.status_code == 400
    assert "does not belong" in r.get_json()["error"]


def test_holding_boat_not_found_404(client, seeded):
    r = client.post(
        f"/slips/{seeded['slip']}/holdings",
        json={"person_id": seeded["person"], "boat_id": 9999, "start_date": "2026-05-01"},
    )
    assert r.status_code == 404


@pytest.mark.parametrize("missing", ["person_id", "start_date"])
def test_holding_missing_required_400(client, seeded, missing):
    payload = {"person_id": seeded["person"], "start_date": "2026-05-01"}
    del payload[missing]
    assert client.post(f"/slips/{seeded['slip']}/holdings", json=payload).status_code == 400


def test_holding_bad_rate_period_400(client, seeded):
    r = client.post(
        f"/slips/{seeded['slip']}/holdings",
        json={"person_id": seeded["person"], "start_date": "2026-05-01", "rate_period": "weekly"},
    )
    assert r.status_code == 400


def test_holding_bad_start_date_400(client, seeded):
    r = client.post(
        f"/slips/{seeded['slip']}/holdings",
        json={"person_id": seeded["person"], "start_date": "not-a-date"},
    )
    assert r.status_code == 400
    assert "ISO date" in r.get_json()["error"]


def test_holding_slip_not_found_404(client, seeded):
    r = client.post(
        "/slips/9999/holdings",
        json={"person_id": seeded["person"], "start_date": "2026-05-01"},
    )
    assert r.status_code == 404


def test_list_holdings_by_slip_and_person(client, seeded):
    client.post(
        f"/slips/{seeded['slip']}/holdings",
        json={"person_id": seeded["person"], "boat_id": seeded["boat"], "start_date": "2026-05-01"},
    )
    assert len(client.get(f"/slips/{seeded['slip']}/holdings").get_json()["holdings"]) == 1
    assert len(client.get(f"/people/{seeded['person']}/holdings").get_json()["holdings"]) == 1


def _make_holding(client, seeded):
    return client.post(
        f"/slips/{seeded['slip']}/holdings",
        json={"person_id": seeded["person"], "start_date": "2026-05-01"},
    ).get_json()["id"]


def test_end_holding_frees_slip(client, seeded):
    hid = _make_holding(client, seeded)
    r = client.patch(f"/holdings/{hid}", json={"status": "ended"})
    assert r.status_code == 200
    assert r.get_json()["status"] == "ended"
    assert client.get(f"/slips/{seeded['slip']}").get_json()["status"] == "available"


def test_patch_holding_to_pending(client, seeded):
    hid = _make_holding(client, seeded)
    r = client.patch(f"/holdings/{hid}", json={"status": "pending"})
    assert r.status_code == 200
    assert r.get_json()["status"] == "pending"


def test_patch_holding_end_date_only(client, seeded):
    hid = _make_holding(client, seeded)
    r = client.patch(f"/holdings/{hid}", json={"end_date": "2026-09-30"})
    assert r.status_code == 200
    assert r.get_json()["end_date"] == "2026-09-30"


def test_patch_holding_bad_status_400(client, seeded):
    hid = _make_holding(client, seeded)
    assert client.patch(f"/holdings/{hid}", json={"status": "frozen"}).status_code == 400


def test_patch_holding_404(client):
    assert client.patch("/holdings/9999", json={"status": "ended"}).status_code == 404
