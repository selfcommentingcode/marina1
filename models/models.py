"""ORM models for the slip-management domain.

Three layers of entity:
  * Physical:  Marina -> Slip
  * Actors:    Person, Boat
  * Over time: SlipHolding (a Person's long-term/seasonal lease on a Slip,
               referencing the Boat occupying it), plus Invoice/Payment
               (billing) and WaitlistEntry.

"Slip" is used in the boating sense: a parking spot for a boat. The marina
owns the physical slips; a customer *holds* one under a lease (SlipHolding).

Enum-like fields are plain strings validated against the constant tuples below,
rather than DB-native enums, to stay portable across SQLite and PostgreSQL.
"""

from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from persistence.db import Base

# --- Enum-like value sets (validated in the route layer) ---------------------
SLIP_STATUSES = ("available", "occupied", "reserved", "out_of_service")
POWER_OPTIONS = ("30A", "50A", "100A")
BOAT_TYPES = ("sail", "power")
RATE_PERIODS = ("monthly", "seasonal", "annual")
HOLDING_STATUSES = ("pending", "active", "ended")
INVOICE_STATUSES = ("unpaid", "partial", "paid", "void")
WAITLIST_STATUSES = ("waiting", "offered", "fulfilled", "cancelled")

# Person metadata. Kept as extensible tuples so new values are a one-line change.
SALUTATIONS = ("Mr", "Mrs", "Miss", "Dr", "Prof", "Capt")
PRONOUNS = (
    "he/him",
    "she/her",
)


def _utcnow():
    return datetime.now(timezone.utc)


def _iso(value):
    """Serialize a date/datetime to ISO string, tolerating None."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return None


def _num(value):
    """Serialize a Numeric/Decimal to float for JSON, tolerating None."""
    return float(value) if value is not None else None


# --- Physical layer ----------------------------------------------------------
class Marina(Base):
    __tablename__ = "marinas"

    id: Mapped[int] = mapped_column(primary_key=True)
    # The person who owns this marina and leases its slips out (the lessor).
    # Nullable so a marina can exist before an owner is recorded.
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("people.id"))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    location: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    owner: Mapped["Person | None"] = relationship(back_populates="marinas")
    slips: Mapped[list["Slip"]] = relationship(
        back_populates="marina", cascade="all, delete-orphan"
    )
    waitlist_entries: Mapped[list["WaitlistEntry"]] = relationship(
        back_populates="marina", cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "owner_id": self.owner_id,
            "name": self.name,
            "location": self.location,
            "slip_count": len(self.slips),
            "created_at": _iso(self.created_at),
        }


class Slip(Base):
    __tablename__ = "slips"

    id: Mapped[int] = mapped_column(primary_key=True)
    marina_id: Mapped[int] = mapped_column(ForeignKey("marinas.id"), nullable=False)
    identifier: Mapped[str] = mapped_column(String(50), nullable=False)

    # Physical dimensions (feet).
    length_ft: Mapped[float] = mapped_column(Float, nullable=False)
    beam_ft: Mapped[float] = mapped_column(Float, nullable=False)
    depth_ft: Mapped[float | None] = mapped_column(Float)

    # Utilities / type.
    power: Mapped[str | None] = mapped_column(String(10))
    covered: Mapped[bool] = mapped_column(Boolean, default=False)

    status: Mapped[str] = mapped_column(String(20), default="available")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    marina: Mapped["Marina"] = relationship(back_populates="slips")
    holdings: Mapped[list["SlipHolding"]] = relationship(
        back_populates="slip", cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "marina_id": self.marina_id,
            "identifier": self.identifier,
            "length_ft": self.length_ft,
            "beam_ft": self.beam_ft,
            "depth_ft": self.depth_ft,
            "power": self.power,
            "covered": self.covered,
            "status": self.status,
            "created_at": _iso(self.created_at),
        }


# --- Actor layer -------------------------------------------------------------
class Person(Base):
    __tablename__ = "people"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(50))

    # Presentational metadata. Validated against SALUTATIONS / PRONOUNS in the
    # route layer. Centralizing these on Person means one update reflects
    # everywhere the person is referenced (owned marinas, boats, holdings, ...).
    salutation: Mapped[str | None] = mapped_column(String(20))
    pronouns: Mapped[str | None] = mapped_column(String(30))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    marinas: Mapped[list["Marina"]] = relationship(back_populates="owner")
    boats: Mapped[list["Boat"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )
    holdings: Mapped[list["SlipHolding"]] = relationship(back_populates="person")
    waitlist_entries: Mapped[list["WaitlistEntry"]] = relationship(
        back_populates="person"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "salutation": self.salutation,
            "pronouns": self.pronouns,
            "boat_count": len(self.boats),
            "marina_count": len(self.marinas),
            "created_at": _iso(self.created_at),
        }


class Boat(Base):
    __tablename__ = "boats"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("people.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    boat_type: Mapped[str | None] = mapped_column(String(20))

    # Dimensions (feet) drive slip fit.
    length_ft: Mapped[float] = mapped_column(Float, nullable=False)
    beam_ft: Mapped[float | None] = mapped_column(Float)
    draft_ft: Mapped[float | None] = mapped_column(Float)

    registration_no: Mapped[str | None] = mapped_column(String(100))
    insurance: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    owner: Mapped["Person"] = relationship(back_populates="boats")
    holdings: Mapped[list["SlipHolding"]] = relationship(back_populates="boat")

    def to_dict(self):
        return {
            "id": self.id,
            "owner_id": self.owner_id,
            "name": self.name,
            "boat_type": self.boat_type,
            "length_ft": self.length_ft,
            "beam_ft": self.beam_ft,
            "draft_ft": self.draft_ft,
            "registration_no": self.registration_no,
            "insurance": self.insurance,
            "created_at": _iso(self.created_at),
        }


# --- Relationship-over-time layer -------------------------------------------
class SlipHolding(Base):
    """A Person's long-term/seasonal lease on a Slip (the 'ownership' object).

    Business rule (enforced in the route layer): at most one holding with
    status 'active' per slip at any time.
    """

    __tablename__ = "slip_holdings"

    id: Mapped[int] = mapped_column(primary_key=True)
    slip_id: Mapped[int] = mapped_column(ForeignKey("slips.id"), nullable=False)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id"), nullable=False)
    boat_id: Mapped[int | None] = mapped_column(ForeignKey("boats.id"))

    # Term.
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date)
    season: Mapped[str | None] = mapped_column(String(50))

    # Money.
    rate_amount: Mapped[float | None] = mapped_column(Numeric(10, 2))
    rate_period: Mapped[str | None] = mapped_column(String(20))

    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    slip: Mapped["Slip"] = relationship(back_populates="holdings")
    person: Mapped["Person"] = relationship(back_populates="holdings")
    boat: Mapped["Boat | None"] = relationship(back_populates="holdings")
    invoices: Mapped[list["Invoice"]] = relationship(
        back_populates="holding", cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "slip_id": self.slip_id,
            "person_id": self.person_id,
            "boat_id": self.boat_id,
            "start_date": _iso(self.start_date),
            "end_date": _iso(self.end_date),
            "season": self.season,
            "rate_amount": _num(self.rate_amount),
            "rate_period": self.rate_period,
            "status": self.status,
            "created_at": _iso(self.created_at),
        }


# --- Billing -----------------------------------------------------------------
class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    holding_id: Mapped[int] = mapped_column(
        ForeignKey("slip_holdings.id"), nullable=False
    )
    amount_due: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    issued_date: Mapped[date] = mapped_column(Date, default=lambda: _utcnow().date())
    due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="unpaid")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    holding: Mapped["SlipHolding"] = relationship(back_populates="invoices")
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )

    def amount_paid(self):
        return sum((p.amount for p in self.payments), 0)

    def to_dict(self):
        paid = _num(self.amount_paid()) or 0.0
        due = _num(self.amount_due) or 0.0
        return {
            "id": self.id,
            "holding_id": self.holding_id,
            "amount_due": due,
            "amount_paid": paid,
            "balance": round(due - paid, 2),
            "issued_date": _iso(self.issued_date),
            "due_date": _iso(self.due_date),
            "status": self.status,
            "created_at": _iso(self.created_at),
        }


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    paid_date: Mapped[date] = mapped_column(Date, default=lambda: _utcnow().date())
    method: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    invoice: Mapped["Invoice"] = relationship(back_populates="payments")

    def to_dict(self):
        return {
            "id": self.id,
            "invoice_id": self.invoice_id,
            "amount": _num(self.amount),
            "paid_date": _iso(self.paid_date),
            "method": self.method,
            "created_at": _iso(self.created_at),
        }


# --- Waitlist ----------------------------------------------------------------
class WaitlistEntry(Base):
    __tablename__ = "waitlist_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    marina_id: Mapped[int] = mapped_column(ForeignKey("marinas.id"), nullable=False)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id"), nullable=False)

    min_length_ft: Mapped[float | None] = mapped_column(Float)
    power: Mapped[str | None] = mapped_column(String(10))
    notes: Mapped[str | None] = mapped_column(String(500))

    requested_date: Mapped[date] = mapped_column(Date, default=lambda: _utcnow().date())
    status: Mapped[str] = mapped_column(String(20), default="waiting")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    marina: Mapped["Marina"] = relationship(back_populates="waitlist_entries")
    person: Mapped["Person"] = relationship(back_populates="waitlist_entries")

    def to_dict(self):
        return {
            "id": self.id,
            "marina_id": self.marina_id,
            "person_id": self.person_id,
            "min_length_ft": self.min_length_ft,
            "power": self.power,
            "notes": self.notes,
            "requested_date": _iso(self.requested_date),
            "status": self.status,
            "created_at": _iso(self.created_at),
        }
