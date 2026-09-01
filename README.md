# Marina1 — Slip Management API

A small, well-tested REST API for running a boat marina: its slips, the people and
boats that use them, the seasonal **leases** that tie a boat to a slip, plus billing
and a waitlist.

![tests](https://github.com/selfcommentingcode/marina1/actions/workflows/tests.yml/badge.svg)
![python](https://img.shields.io/badge/python-3.12-blue)
![coverage](https://img.shields.io/badge/branch%20coverage-99%25-brightgreen)

---

## Executive summary

Marinas rent out **slips** (parking spots for boats) on seasonal leases, bill for them,
and keep a waitlist when full. Marina1 models that domain as a clean relational API:
eight related entities, guardrails that enforce the real-world rules (a boat must
physically fit its slip; a slip can't be double-booked), and a persistence layer that
runs on SQLite today and PostgreSQL tomorrow with a one-line change. It ships with a
runnable end-to-end demo and a 99%-branch-coverage test suite.

## Demonstration

**One-command, 23-step walkthrough.** Import [`postman/Marina1.postman_collection.json`](postman/Marina1.postman_collection.json)
into Postman and hit **Run** — it self-chains from an empty system all the way through
leasing a slip, billing it, and freeing it, asserting each step green (including the
guardrail rejections).

**Or from the shell:**

```bash
# 1. Is it up?
curl -s localhost:5000/health
# {"status":"healthy"}

# 2. Create a marina, then a slip in it
curl -s -X POST localhost:5000/marinas -H "Content-Type: application/json" \
  -d '{"name":"Harbor Point","location":"Lake Union"}'
# {"id":1,"name":"Harbor Point", ...}

curl -s -X POST localhost:5000/marinas/1/slips -H "Content-Type: application/json" \
  -d '{"identifier":"A-14","length_ft":40,"beam_ft":14,"depth_ft":8,"power":"50A"}'
# {"id":1,"status":"available", ...}

# 3. A person + their boat, then lease the slip to them
curl -s -X POST localhost:5000/people -H "Content-Type: application/json" \
  -d '{"name":"Ada Lovelace","email":"ada@example.com"}'
curl -s -X POST localhost:5000/people/1/boats -H "Content-Type: application/json" \
  -d '{"name":"Analytical","boat_type":"sail","length_ft":36,"beam_ft":12,"draft_ft":6}'

curl -s -X POST localhost:5000/slips/1/holdings -H "Content-Type: application/json" \
  -d '{"person_id":1,"boat_id":1,"start_date":"2026-05-01","rate_amount":2400,"rate_period":"seasonal"}'
# {"id":1,"status":"active", ...}   ← the slip is now "occupied"

# Guardrail in action: a 60ft boat won't fit a 40ft slip
# -> 400  {"error":"boat does not fit slip: boat length exceeds slip length"}
```

## Run it locally

```bash
# 1. Create a virtual environment and install runtime deps
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux
pip install -r requirements.txt

# 2. Start the API
python main.py                # serves http://127.0.0.1:5000
```

The SQLite database (`persistence/storable.db`) is created automatically on first run.
To use PostgreSQL instead, set `DATABASE_URL` before starting — no code changes:

```bash
export DATABASE_URL="postgresql+psycopg://user:pass@localhost/marina1"
```

## Testing & coverage

```bash
pip install -r requirements-dev.txt
pytest                                         # 67 tests
pytest --cov --cov-branch --cov-report=html    # branch coverage -> htmlcov/index.html
pytest tests/test_billing.py::test_payment_partial_then_paid   # a single test
```

**67 tests, 99% branch coverage** — the suite deliberately targets the error and edge
branches (fit checks, double-booking, the invoice status ladder, every 400/404). CI runs
it on each push via GitHub Actions and reports to Codecov.

## Implementation details

Flask (an **application factory** + a Blueprint) over the **SQLAlchemy 2.0** ORM. The
engine is built per-app from an injectable database URL, so tests spin up isolated
in-memory databases while production uses a SQLite file — and PostgreSQL is just a
different URL. Enum-like fields are validated in the route layer against constant tuples
to stay portable, and the domain rules (boat-fits-slip, one active lease per slip,
`unpaid → partial → paid`) live in the handlers and are pinned by the tests.

## Project structure

```
marina1/
├── main.py                    # App factory + all routes (Flask Blueprint)
├── models/models.py           # SQLAlchemy ORM — the 8 entities below
├── persistence/db.py          # Engine/session factories, schema bootstrap
├── tests/                     # pytest suite (67 tests)
├── postman/                   # Importable end-to-end demo collection
├── docs/SCHEMA.md             # Schema + FK reference
├── requirements.txt           # Runtime deps
├── requirements-dev.txt       # + pytest, pytest-cov
└── pyproject.toml             # pytest & coverage config
```

## API at a glance

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `POST` / `GET` | `/marinas` | Create / list marinas |
| `GET` | `/marinas/{id}` | Get a marina |
| `POST` / `GET` | `/marinas/{id}/slips` | Create / list slips (`?status=`, `?min_length=`) |
| `GET` | `/slips/{id}` | Get a slip |
| `POST` / `GET` | `/people` | Create / list people |
| `POST` / `GET` | `/people/{id}/boats` | Create / list a person's boats |
| `POST` / `GET` | `/slips/{id}/holdings` | Lease a slip / list its leases |
| `GET` | `/people/{id}/holdings` | A person's leases |
| `PATCH` | `/holdings/{id}` | End or update a lease |
| `POST` | `/holdings/{id}/invoices` | Invoice a lease |
| `GET` | `/invoices/{id}` | Get an invoice + its payments |
| `POST` | `/invoices/{id}/payments` | Record a payment |
| `POST` / `GET` | `/marinas/{id}/waitlist` | Join / list the waitlist |

## Data model

The relationships below render as a diagram on GitHub. `PK` = primary key, `FK` = foreign
key. Crow's-foot ends read as *exactly one* (`||`), *zero-or-one* (`|o`), or
*zero-or-more* (`o{`) — so `MARINA ||--o{ SLIP` means one marina has many slips, and each
slip belongs to exactly one marina.

```mermaid
erDiagram
    PERSON        |o--o{ MARINA         : "owns"
    MARINA        ||--o{ SLIP           : "has"
    MARINA        ||--o{ WAITLIST_ENTRY : "queues"
    PERSON        ||--o{ BOAT           : "owns"
    PERSON        ||--o{ SLIP_HOLDING   : "holds"
    PERSON        ||--o{ WAITLIST_ENTRY : "joins"
    SLIP          ||--o{ SLIP_HOLDING   : "leased via"
    BOAT          |o--o{ SLIP_HOLDING   : "occupies"
    SLIP_HOLDING  ||--o{ INVOICE        : "billed by"
    INVOICE       ||--o{ PAYMENT        : "settled by"

    MARINA {
        int id PK
        int owner_id FK "nullable"
        string name
        string location
        datetime created_at
    }
    SLIP {
        int id PK
        int marina_id FK
        string identifier
        float length_ft
        float beam_ft
        float depth_ft
        string power
        bool covered
        string status
        datetime created_at
    }
    PERSON {
        int id PK
        string name
        string email
        string phone
        string salutation
        string pronouns
        datetime created_at
    }
    BOAT {
        int id PK
        int owner_id FK
        string name
        string boat_type
        float length_ft
        float beam_ft
        float draft_ft
        string registration_no
        string insurance
        datetime created_at
    }
    SLIP_HOLDING {
        int id PK
        int slip_id FK
        int person_id FK
        int boat_id FK "nullable"
        date start_date
        date end_date
        string season
        decimal rate_amount
        string rate_period
        string status
        datetime created_at
    }
    INVOICE {
        int id PK
        int holding_id FK
        decimal amount_due
        date issued_date
        date due_date
        string status
        datetime created_at
    }
    PAYMENT {
        int id PK
        int invoice_id FK
        decimal amount
        date paid_date
        string method
        datetime created_at
    }
    WAITLIST_ENTRY {
        int id PK
        int marina_id FK
        int person_id FK
        float min_length_ft
        string power
        string notes
        date requested_date
        string status
        datetime created_at
    }
```
