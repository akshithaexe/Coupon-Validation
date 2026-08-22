# Coupon Business Logic

A one-time-per-user, 100% discount coupon system that correctly handles concurrent requests.

Built as a backend technical interview assignment.

## Problem Statement

Implement a coupon system where:
- A coupon can be used only once per user
- The coupon provides a 100% discount
- Concurrent requests must be handled correctly
- If a transaction fails, the coupon must not be consumed

## Architecture

```
Client → FastAPI Routes → Service Layer → SQLAlchemy → PostgreSQL
```

- **Routes** (`app/api/routes/coupons.py`): Thin HTTP layer, delegates to services
- **Service** (`app/services/coupon_service.py`): All business logic, transaction management
- **Models** (`app/db/models.py`): SQLAlchemy 2.x ORM models with constraints
- **Schemas** (`app/schemas/coupon.py`): Pydantic request/response validation

## Database Schema

### Users
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |

### Coupons
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| code | VARCHAR(50) | UNIQUE, NOT NULL |
| discount_percentage | INTEGER | NOT NULL, CHECK (1-100) |
| is_active | BOOLEAN | NOT NULL, default true |

### Transactions
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| user_id | UUID | FK → users, NOT NULL |
| coupon_id | UUID | FK → coupons, NOT NULL |
| original_amount | NUMERIC(12,2) | NOT NULL, CHECK > 0 |
| discount_amount | NUMERIC(12,2) | NOT NULL, CHECK >= 0 |
| final_amount | NUMERIC(12,2) | NOT NULL, CHECK >= 0 |
| status | VARCHAR(20) | NOT NULL, default 'success' |
| created_at | TIMESTAMPTZ | NOT NULL, default now() |

### Coupon Usages
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| coupon_id | UUID | FK → coupons, NOT NULL |
| user_id | UUID | FK → users, NOT NULL |
| transaction_id | UUID | FK → transactions, NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL, default now() |

**UNIQUE constraint on (coupon_id, user_id)** — the concurrency safety mechanism.

## API Endpoints

### POST /validate-coupon

Validates a coupon without modifying any state. Read-only.

**Request:**
```json
{
    "user_id": "11111111-1111-1111-1111-111111111111",
    "coupon_code": "WELCOME100",
    "amount": "150.00"
}
```

**Response (200):**
```json
{
    "valid": true,
    "coupon_code": "WELCOME100",
    "discount_percentage": 100,
    "original_amount": "150.00",
    "discount_amount": "150.00",
    "final_amount": "0.00",
    "message": "Coupon is valid"
}
```

### POST /apply-coupon

Validates and applies a coupon atomically. Creates a transaction and records usage.

**Request:**
```json
{
    "user_id": "11111111-1111-1111-1111-111111111111",
    "coupon_code": "WELCOME100",
    "amount": "150.00"
}
```

**Response (200):**
```json
{
    "transaction_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "user_id": "11111111-1111-1111-1111-111111111111",
    "coupon_code": "WELCOME100",
    "original_amount": "150.00",
    "discount_amount": "150.00",
    "final_amount": "0.00",
    "status": "success",
    "applied_at": "2024-01-01T00:00:00Z",
    "message": "Coupon applied successfully"
}
```

### Error Responses

| Status | Error Code | Scenario |
|--------|------------|----------|
| 404 | user_not_found | User does not exist |
| 404 | coupon_not_found | Coupon code not found |
| 400 | coupon_inactive | Coupon is deactivated |
| 409 | coupon_already_used | Coupon already used by this user |
| 422 | — | Invalid request body |

**Error format:**
```json
{
    "error": "coupon_already_used",
    "message": "This coupon has already been used by this user"
}
```

## Coupon Validation Flow

1. Verify user exists → 404 if not
2. Look up coupon by code → 404 if not found
3. Check `is_active` → 400 if inactive
4. Check `coupon_usages` for existing usage → 409 if exists
5. Calculate discount (100%: `discount_amount = amount`, `final_amount = 0`)
6. Return validation result — **no state modified**

## Coupon Application Flow

Inside a single database transaction:

1. Verify user exists
2. Validate coupon exists and is active
3. Check for existing usage (app-level, catches common case)
4. Calculate discount
5. Create transaction record
6. Create coupon_usage record
7. If UNIQUE constraint fires → automatic rollback → 409
8. Commit only if everything succeeds

## Concurrency Strategy

### The Problem

Two concurrent requests could both observe "coupon not used yet" and both try to apply it:

```
Request A: SELECT usage → ∅     INSERT txn     INSERT usage ✓  COMMIT
Request B: SELECT usage → ∅     INSERT txn     INSERT usage ✗  ROLLBACK
```

### The Solution

**Database-level UNIQUE constraint on `(coupon_id, user_id)`** in the `coupon_usages` table.

- PostgreSQL enforces this regardless of application logic or isolation level
- Only one INSERT can succeed; the other gets an IntegrityError
- The `session.begin()` context manager automatically rolls back on IntegrityError
- Both the transaction and usage records are rolled back together

### Why the UNIQUE Constraint is Necessary

Without it, the application-level check (`SELECT ... WHERE coupon_id AND user_id`) creates a **TOCTOU race condition** — two requests can both see "no usage exists" before either commits. The UNIQUE constraint makes PostgreSQL the final arbiter, guaranteeing at most one usage record per (coupon, user) pair.

### What We Don't Use

- **SERIALIZABLE isolation**: Adds retry complexity; UNIQUE constraint is sufficient
- **SELECT FOR UPDATE**: Can't lock rows that don't exist yet
- **Redis/distributed locks**: Unnecessary for a single-database system

## Transaction/Rollback Behavior

```python
async with session.begin():
    # validate, create transaction, create usage
    await session.flush()  # triggers constraint check
# On success: COMMIT
# On IntegrityError: automatic ROLLBACK (transaction + usage both gone)
```

If the coupon_usage INSERT violates the UNIQUE constraint, the **entire transaction** is rolled back — including the transaction record. The coupon is never consumed without a successful transaction.

## How to Run

### Prerequisites
- Docker and Docker Compose

### Start the Project

```bash
# Start PostgreSQL and the application
docker compose up -d

# Run migrations (creates tables + seed data)
docker compose exec app alembic upgrade head

# The API is now available at http://localhost:8000
```

### Seed Data

The migrations create:
- **User 1**: `11111111-1111-1111-1111-111111111111`
- **User 2**: `22222222-2222-2222-2222-222222222222`
- **Active coupon**: code `WELCOME100`, 100% discount
- **Inactive coupon**: code `EXPIRED50`, 50% discount

### Example API Requests

```bash
# Validate a coupon
curl -X POST http://localhost:8000/validate-coupon \
  -H "Content-Type: application/json" \
  -d '{"user_id":"11111111-1111-1111-1111-111111111111","coupon_code":"WELCOME100","amount":"150.00"}'

# Apply a coupon
curl -X POST http://localhost:8000/apply-coupon \
  -H "Content-Type: application/json" \
  -d '{"user_id":"11111111-1111-1111-1111-111111111111","coupon_code":"WELCOME100","amount":"150.00"}'

# Try applying again (should return 409)
curl -X POST http://localhost:8000/apply-coupon \
  -H "Content-Type: application/json" \
  -d '{"user_id":"11111111-1111-1111-1111-111111111111","coupon_code":"WELCOME100","amount":"150.00"}'
```

## How to Run Tests

```bash
# Start PostgreSQL (tests need a real database)
docker compose up -d db

# Run all tests
docker compose run --rm app pytest tests/ -v

# Run specific test files
docker compose run --rm app pytest tests/test_concurrency.py -v
```

### How the Concurrency Test Demonstrates Correctness

The concurrency test (`test_concurrent_same_user_same_coupon`) uses `asyncio.Barrier` to synchronize 10 concurrent requests:

1. All 10 coroutines reach the barrier and wait
2. Once all 10 are ready, they are released simultaneously
3. All 10 POST to `/apply-coupon` with the same user and coupon
4. The test asserts:
   - Exactly **1** request returns 200
   - Exactly **9** requests return 409
   - Exactly **1** `coupon_usage` record in the database
   - Exactly **1** `transaction` record in the database

A second test (`test_concurrent_different_users_same_coupon`) verifies that different users can independently use the same coupon concurrently — proving the constraint is **one-time-per-user**, not one-time-globally.

## Technology Stack

- Python 3.12+
- FastAPI
- PostgreSQL 16
- SQLAlchemy 2.x (async)
- Pydantic v2
- Alembic
- Pytest (with pytest-asyncio)
- Docker / Docker Compose
