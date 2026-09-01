# Storable — Data Model

Entity-relationship diagram for the slip-management schema. Every box is a table;
`PK` marks its primary key, `FK` marks a foreign key. The crow's-foot lines show
how the rows map to one another.

```mermaid
erDiagram
    MARINA        ||--o{ SLIP           : "has"
    MARINA        ||--o{ WAITLIST_ENTRY : "queues"
    PERSON        |o--o{ MARINA         : "owns"
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

## Reading the lines (crow's-foot notation)

The symbol nearest each box states how many of *that* entity participate:

| Symbol | Means |
|--------|-------|
| `||`   | exactly one |
| `o|`   | zero or one |
| `}o`   | zero or more (the "crow's foot") |
| `}|`   | one or more |

So `MARINA ||--o{ SLIP` reads: **one** marina relates to **zero-or-more** slips —
and, read back the other way, each slip belongs to **exactly one** marina.

## Foreign-key reference

| Child table      | FK column     | → Parent table | Cardinality | Nullable? |
|------------------|---------------|----------------|-------------|-----------|
| `marinas`        | `owner_id`    | `people`       | many → 1    | **yes**   |
| `slips`          | `marina_id`   | `marinas`      | many → 1    | no        |
| `boats`          | `owner_id`    | `people`       | many → 1    | no        |
| `slip_holdings`  | `slip_id`     | `slips`        | many → 1    | no        |
| `slip_holdings`  | `person_id`   | `people`       | many → 1    | no        |
| `slip_holdings`  | `boat_id`     | `boats`        | many → 1    | **yes**   |
| `invoices`       | `holding_id`  | `slip_holdings`| many → 1    | no        |
| `payments`       | `invoice_id`  | `invoices`     | many → 1    | no        |
| `waitlist_entries`| `marina_id`  | `marinas`      | many → 1    | no        |
| `waitlist_entries`| `person_id`  | `people`       | many → 1    | no        |

**Note:** every relationship in this schema is **one-to-many** — there are no
one-to-one relationships. Two foreign keys are *nullable*, so the child maps to
**zero-or-one** parent rather than exactly one:

- `boat_id` on `slip_holdings` — a slip can be leased before a specific boat is
  assigned.
- `owner_id` on `marinas` — a marina can exist before its owning person (the
  lessor who rents slips out) is recorded.
