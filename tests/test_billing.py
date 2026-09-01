"""Tests for invoices and payments, focused on the status ladder
(unpaid -> partial -> paid) and its balance arithmetic."""

import pytest


@pytest.fixture()
def holding(client, seeded):
    return client.post(
        f"/slips/{seeded['slip']}/holdings",
        json={"person_id": seeded["person"], "boat_id": seeded["boat"], "start_date": "2026-05-01"},
    ).get_json()["id"]


def test_create_invoice_unpaid(client, holding):
    r = client.post(f"/holdings/{holding}/invoices", json={"amount_due": 2400, "due_date": "2026-05-15"})
    assert r.status_code == 201
    body = r.get_json()
    assert body["status"] == "unpaid"
    assert body["balance"] == 2400


def test_create_invoice_missing_amount_400(client, holding):
    assert client.post(f"/holdings/{holding}/invoices", json={}).status_code == 400


def test_create_invoice_holding_404(client):
    assert client.post("/holdings/9999/invoices", json={"amount_due": 100}).status_code == 404


def test_payment_partial_then_paid(client, holding):
    iid = client.post(f"/holdings/{holding}/invoices", json={"amount_due": 2400}).get_json()["id"]

    p1 = client.post(f"/invoices/{iid}/payments", json={"amount": 1000, "method": "card"})
    assert p1.status_code == 201
    assert p1.get_json()["invoice"]["status"] == "partial"
    assert p1.get_json()["invoice"]["balance"] == 1400

    p2 = client.post(f"/invoices/{iid}/payments", json={"amount": 1400})
    assert p2.get_json()["invoice"]["status"] == "paid"
    assert p2.get_json()["invoice"]["balance"] == 0


def test_payment_zero_keeps_unpaid(client, holding):
    # Covers the 'else -> unpaid' arm of the status ladder.
    iid = client.post(f"/holdings/{holding}/invoices", json={"amount_due": 500}).get_json()["id"]
    r = client.post(f"/invoices/{iid}/payments", json={"amount": 0})
    assert r.get_json()["invoice"]["status"] == "unpaid"


def test_get_invoice_with_payments(client, holding):
    iid = client.post(f"/holdings/{holding}/invoices", json={"amount_due": 100}).get_json()["id"]
    client.post(f"/invoices/{iid}/payments", json={"amount": 100})
    body = client.get(f"/invoices/{iid}").get_json()
    assert body["status"] == "paid"
    assert len(body["payments"]) == 1


def test_get_invoice_404(client):
    assert client.get("/invoices/9999").status_code == 404


def test_payment_invoice_404(client):
    assert client.post("/invoices/9999/payments", json={"amount": 10}).status_code == 404


def test_payment_missing_amount_400(client, holding):
    iid = client.post(f"/holdings/{holding}/invoices", json={"amount_due": 100}).get_json()["id"]
    assert client.post(f"/invoices/{iid}/payments", json={}).status_code == 400
