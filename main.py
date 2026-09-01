# Storable: a slip-management API (boats + marina slips), backed by SQLite.
#
# Run locally:
#   .venv\Scripts\python.exe main.py
# Then visit http://127.0.0.1:5000/
#
# The database file (storable.db) is created automatically on first run.
# To point at PostgreSQL instead, set the DATABASE_URL environment variable.

from datetime import date

from flask import Flask, jsonify, request

from db import SessionLocal, init_db
from models import (
    BOAT_TYPES,
    HOLDING_STATUSES,
    POWER_OPTIONS,
    PRONOUNS,
    RATE_PERIODS,
    SALUTATIONS,
    SLIP_STATUSES,
    WAITLIST_STATUSES,
    Boat,
    Invoice,
    Marina,
    Payment,
    Person,
    Slip,
    SlipHolding,
    WaitlistEntry,
)

app = Flask(__name__)

# Create tables if they don't exist yet. Safe to run on every startup.
init_db()

# --- Small helpers -----------------------------------------------------------
class ApiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


@app.errorhandler(ApiError)
def _handle_api_error(err):
    return jsonify(error=err.message), err.status


def body():
    return request.get_json(silent=True) or {}


def require(data, *fields):
    missing = [f for f in fields if data.get(f) in (None, "")]
    if missing:
        raise ApiError(f"missing required field(s): {', '.join(missing)}")


def check_enum(value, allowed, field):
    if value is not None and value not in allowed:
        raise ApiError(f"{field} must be one of {list(allowed)}")


def parse_date(value, field):
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        raise ApiError(f"{field} must be an ISO date (YYYY-MM-DD)")


def get_or_404(session, model, obj_id, label):
    obj = session.get(model, obj_id)
    if obj is None:
        raise ApiError(f"{label} not found", status=404)
    return obj


# --- Meta --------------------------------------------------------------------
@app.route("/")
def index():
    return jsonify(status="ok", message="Storable slip-management API is running.")


@app.route("/health")
def health():
    return jsonify(status="healthy")


# --- Marinas -----------------------------------------------------------------
@app.route("/marinas", methods=["POST"])
def create_marina():
    data = body()
    require(data, "name")
    with SessionLocal() as session:
        owner_id = data.get("owner_id")
        if owner_id is not None:
            get_or_404(session, Person, owner_id, "owner")
        marina = Marina(
            name=data["name"], location=data.get("location"), owner_id=owner_id
        )
        session.add(marina)
        session.commit()
        return jsonify(marina.to_dict()), 201


@app.route("/marinas", methods=["GET"])
def list_marinas():
    with SessionLocal() as session:
        marinas = session.query(Marina).order_by(Marina.id).all()
        return jsonify(marinas=[m.to_dict() for m in marinas])


@app.route("/marinas/<int:marina_id>", methods=["GET"])
def get_marina(marina_id):
    with SessionLocal() as session:
        marina = get_or_404(session, Marina, marina_id, "marina")
        return jsonify(marina.to_dict())


# --- Slips -------------------------------------------------------------------
@app.route("/marinas/<int:marina_id>/slips", methods=["POST"])
def create_slip(marina_id):
    data = body()
    require(data, "identifier", "length_ft", "beam_ft")
    check_enum(data.get("power"), POWER_OPTIONS, "power")
    check_enum(data.get("status"), SLIP_STATUSES, "status")
    with SessionLocal() as session:
        get_or_404(session, Marina, marina_id, "marina")
        slip = Slip(
            marina_id=marina_id,
            identifier=data["identifier"],
            length_ft=data["length_ft"],
            beam_ft=data["beam_ft"],
            depth_ft=data.get("depth_ft"),
            power=data.get("power"),
            covered=bool(data.get("covered", False)),
            status=data.get("status", "available"),
        )
        session.add(slip)
        session.commit()
        return jsonify(slip.to_dict()), 201


@app.route("/marinas/<int:marina_id>/slips", methods=["GET"])
def list_slips(marina_id):
    status = request.args.get("status")
    min_length = request.args.get("min_length", type=float)
    with SessionLocal() as session:
        get_or_404(session, Marina, marina_id, "marina")
        q = session.query(Slip).filter_by(marina_id=marina_id)
        if status:
            q = q.filter(Slip.status == status)
        if min_length is not None:
            q = q.filter(Slip.length_ft >= min_length)
        slips = q.order_by(Slip.id).all()
        return jsonify(slips=[s.to_dict() for s in slips])


@app.route("/slips/<int:slip_id>", methods=["GET"])
def get_slip(slip_id):
    with SessionLocal() as session:
        slip = get_or_404(session, Slip, slip_id, "slip")
        return jsonify(slip.to_dict())


# --- People ------------------------------------------------------------------
@app.route("/people", methods=["POST"])
def create_person():
    data = body()
    require(data, "name")
    check_enum(data.get("salutation"), SALUTATIONS, "salutation")
    check_enum(data.get("pronouns"), PRONOUNS, "pronouns")
    with SessionLocal() as session:
        person = Person(
            name=data["name"],
            email=data.get("email"),
            phone=data.get("phone"),
            salutation=data.get("salutation"),
            pronouns=data.get("pronouns"),
        )
        session.add(person)
        session.commit()
        return jsonify(person.to_dict()), 201


@app.route("/people", methods=["GET"])
def list_people():
    with SessionLocal() as session:
        people = session.query(Person).order_by(Person.id).all()
        return jsonify(people=[p.to_dict() for p in people])


@app.route("/people/<int:person_id>", methods=["GET"])
def get_person(person_id):
    with SessionLocal() as session:
        person = get_or_404(session, Person, person_id, "person")
        return jsonify(person.to_dict())


@app.route("/people/<int:person_id>", methods=["PATCH"])
def update_person(person_id):
    """Update a person in one place; the change is reflected everywhere the
    person is referenced (owned marinas, boats, holdings, waitlist entries)."""
    data = body()
    if "name" in data and not data["name"]:
        raise ApiError("name cannot be empty")
    check_enum(data.get("salutation"), SALUTATIONS, "salutation")
    check_enum(data.get("pronouns"), PRONOUNS, "pronouns")
    with SessionLocal() as session:
        person = get_or_404(session, Person, person_id, "person")
        for field in ("name", "email", "phone", "salutation", "pronouns"):
            if field in data:
                setattr(person, field, data[field])
        session.commit()
        return jsonify(person.to_dict())


# --- Boats -------------------------------------------------------------------
@app.route("/people/<int:person_id>/boats", methods=["POST"])
def create_boat(person_id):
    data = body()
    require(data, "name", "length_ft")
    check_enum(data.get("boat_type"), BOAT_TYPES, "boat_type")
    with SessionLocal() as session:
        get_or_404(session, Person, person_id, "person")
        boat = Boat(
            owner_id=person_id,
            name=data["name"],
            boat_type=data.get("boat_type"),
            length_ft=data["length_ft"],
            beam_ft=data.get("beam_ft"),
            draft_ft=data.get("draft_ft"),
            registration_no=data.get("registration_no"),
            insurance=data.get("insurance"),
        )
        session.add(boat)
        session.commit()
        return jsonify(boat.to_dict()), 201


@app.route("/people/<int:person_id>/boats", methods=["GET"])
def list_boats(person_id):
    with SessionLocal() as session:
        get_or_404(session, Person, person_id, "person")
        boats = session.query(Boat).filter_by(owner_id=person_id).order_by(Boat.id).all()
        return jsonify(boats=[b.to_dict() for b in boats])


# --- Slip holdings (the core "ownership"/lease object) -----------------------
def _fits(boat, slip):
    """A boat fits a slip when it is no larger in each known dimension."""
    if boat.length_ft is not None and boat.length_ft > slip.length_ft:
        return False, "boat length exceeds slip length"
    if boat.beam_ft is not None and slip.beam_ft is not None and boat.beam_ft > slip.beam_ft:
        return False, "boat beam exceeds slip beam"
    if boat.draft_ft is not None and slip.depth_ft is not None and boat.draft_ft > slip.depth_ft:
        return False, "boat draft exceeds slip depth"
    return True, None


@app.route("/slips/<int:slip_id>/holdings", methods=["POST"])
def create_holding(slip_id):
    data = body()
    require(data, "person_id", "start_date")
    check_enum(data.get("rate_period"), RATE_PERIODS, "rate_period")
    start_date = parse_date(data["start_date"], "start_date")
    end_date = parse_date(data.get("end_date"), "end_date")

    with SessionLocal() as session:
        slip = get_or_404(session, Slip, slip_id, "slip")
        person = get_or_404(session, Person, data["person_id"], "person")

        boat = None
        if data.get("boat_id") is not None:
            boat = get_or_404(session, Boat, data["boat_id"], "boat")
            if boat.owner_id != person.id:
                raise ApiError("boat does not belong to that person")
            ok, why = _fits(boat, slip)
            if not ok:
                raise ApiError(f"boat does not fit slip: {why}")

        # No double-booking: reject if the slip already has an active holding.
        existing = (
            session.query(SlipHolding)
            .filter_by(slip_id=slip_id, status="active")
            .first()
        )
        if existing is not None:
            raise ApiError(
                f"slip already has an active holding (id={existing.id})", status=409
            )

        holding = SlipHolding(
            slip_id=slip_id,
            person_id=person.id,
            boat_id=boat.id if boat else None,
            start_date=start_date,
            end_date=end_date,
            season=data.get("season"),
            rate_amount=data.get("rate_amount"),
            rate_period=data.get("rate_period"),
            status="active",
        )
        session.add(holding)
        slip.status = "occupied"  # activating a holding occupies the slip
        session.commit()
        return jsonify(holding.to_dict()), 201


@app.route("/slips/<int:slip_id>/holdings", methods=["GET"])
def list_slip_holdings(slip_id):
    with SessionLocal() as session:
        get_or_404(session, Slip, slip_id, "slip")
        holdings = (
            session.query(SlipHolding)
            .filter_by(slip_id=slip_id)
            .order_by(SlipHolding.id)
            .all()
        )
        return jsonify(holdings=[h.to_dict() for h in holdings])


@app.route("/people/<int:person_id>/holdings", methods=["GET"])
def list_person_holdings(person_id):
    with SessionLocal() as session:
        get_or_404(session, Person, person_id, "person")
        holdings = (
            session.query(SlipHolding)
            .filter_by(person_id=person_id)
            .order_by(SlipHolding.id)
            .all()
        )
        return jsonify(holdings=[h.to_dict() for h in holdings])


@app.route("/holdings/<int:holding_id>", methods=["PATCH"])
def update_holding(holding_id):
    data = body()
    check_enum(data.get("status"), HOLDING_STATUSES, "status")
    with SessionLocal() as session:
        holding = get_or_404(session, SlipHolding, holding_id, "holding")
        new_status = data.get("status")
        if new_status == "ended":
            holding.status = "ended"
            holding.end_date = parse_date(data.get("end_date"), "end_date") or date.today()
            holding.slip.status = "available"  # freeing the slip
        elif new_status is not None:
            holding.status = new_status
        if "end_date" in data and new_status != "ended":
            holding.end_date = parse_date(data.get("end_date"), "end_date")
        session.commit()
        return jsonify(holding.to_dict())


# --- Billing -----------------------------------------------------------------
@app.route("/holdings/<int:holding_id>/invoices", methods=["POST"])
def create_invoice(holding_id):
    data = body()
    require(data, "amount_due")
    with SessionLocal() as session:
        get_or_404(session, SlipHolding, holding_id, "holding")
        invoice = Invoice(
            holding_id=holding_id,
            amount_due=data["amount_due"],
            due_date=parse_date(data.get("due_date"), "due_date"),
        )
        session.add(invoice)
        session.commit()
        return jsonify(invoice.to_dict()), 201


@app.route("/invoices/<int:invoice_id>", methods=["GET"])
def get_invoice(invoice_id):
    with SessionLocal() as session:
        invoice = get_or_404(session, Invoice, invoice_id, "invoice")
        data = invoice.to_dict()
        data["payments"] = [p.to_dict() for p in invoice.payments]
        return jsonify(data)


@app.route("/invoices/<int:invoice_id>/payments", methods=["POST"])
def create_payment(invoice_id):
    data = body()
    require(data, "amount")
    with SessionLocal() as session:
        invoice = get_or_404(session, Invoice, invoice_id, "invoice")
        payment = Payment(
            invoice_id=invoice_id,
            amount=data["amount"],
            method=data.get("method"),
            paid_date=parse_date(data.get("paid_date"), "paid_date") or date.today(),
        )
        session.add(payment)
        session.flush()  # so amount_paid() sees this payment

        # Recompute invoice status from total paid vs due.
        paid = float(invoice.amount_paid())
        due = float(invoice.amount_due)
        if paid >= due:
            invoice.status = "paid"
        elif paid > 0:
            invoice.status = "partial"
        else:
            invoice.status = "unpaid"

        session.commit()
        return jsonify(payment=payment.to_dict(), invoice=invoice.to_dict()), 201


# --- Waitlist ----------------------------------------------------------------
@app.route("/marinas/<int:marina_id>/waitlist", methods=["POST"])
def create_waitlist_entry(marina_id):
    data = body()
    require(data, "person_id")
    check_enum(data.get("power"), POWER_OPTIONS, "power")
    check_enum(data.get("status"), WAITLIST_STATUSES, "status")
    with SessionLocal() as session:
        get_or_404(session, Marina, marina_id, "marina")
        get_or_404(session, Person, data["person_id"], "person")
        entry = WaitlistEntry(
            marina_id=marina_id,
            person_id=data["person_id"],
            min_length_ft=data.get("min_length_ft"),
            power=data.get("power"),
            notes=data.get("notes"),
            status=data.get("status", "waiting"),
        )
        session.add(entry)
        session.commit()
        return jsonify(entry.to_dict()), 201


@app.route("/marinas/<int:marina_id>/waitlist", methods=["GET"])
def list_waitlist(marina_id):
    with SessionLocal() as session:
        get_or_404(session, Marina, marina_id, "marina")
        entries = (
            session.query(WaitlistEntry)
            .filter_by(marina_id=marina_id)
            .order_by(WaitlistEntry.id)
            .all()
        )
        return jsonify(waitlist=[e.to_dict() for e in entries])


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
