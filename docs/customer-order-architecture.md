# Customer & Order Architecture

## Overview

Every registered user automatically receives a **Customer** profile with a unique Customer ID (e.g. `DF-A1B2C3`). This ID is used to track and identify customers across orders in the Django admin panel.

---

## Models

### Customer

| Field         | Type                    | Description                                      |
|---------------|-------------------------|--------------------------------------------------|
| `user`        | OneToOneField → `User`  | Links to Django's built-in User model             |
| `customer_id` | CharField (unique)      | Auto-generated ID in format `DF-XXXXXX`           |
| `created_at`  | DateTimeField           | Timestamp of when the customer profile was created |

**Key behaviour:**

- A `Customer` is **auto-created** via a `post_save` signal whenever a new `User` is created (signup, `createsuperuser`, admin, etc.).
- The `customer_id` is generated once on first save and never changes.
- Format: `DF-` prefix followed by 6 uppercase hex characters (e.g. `DF-D94757`).
- Uniqueness is enforced at both the application and database level.

### Order (updated)

A new `customer` ForeignKey was added to the existing `Order` model:

| Field      | Type                        | Description                               |
|------------|-----------------------------|-------------------------------------------|
| `customer` | ForeignKey → `Customer`     | Links the order to the customer profile   |

**Key behaviour:**

- On `Order.save()`, if a `user` is set but `customer` is not, the customer is auto-populated from `user.customer`.
- This means existing code that only sets `order.user` will continue to work — the customer link is filled in automatically.

---

## Admin Panel

### Customers Section (`/admin/core/customer/`)

**List view:**

| Column       | Description                                  |
|--------------|----------------------------------------------|
| Customer ID  | Unique identifier (e.g. `DF-D94757`)         |
| Full Name    | From `User.first_name` + `User.last_name`    |
| Email        | From `User.email`                            |
| Total Orders | Count of orders linked to this customer      |
| Created At   | When the customer profile was created        |

- **Search** by Customer ID, username, first name, last name, or email.
- **Add** button is disabled — customers are auto-created via the User signal.

**Detail view (click on a customer):**

- **Customer ID** — read-only unique identifier
- **Profile Info** — username, full name, email, date joined, last login
- **Order Summary** — total orders placed + total amount spent (₹)
- **Orders (inline table)** — list of all past orders with:
  - Clickable `Order #N` link → navigates to that order's detail page
  - Status
  - Total amount
  - Date

### Orders Section (`/admin/core/order/`)

**List view:**

| Column      | Description                                         |
|-------------|-----------------------------------------------------|
| ID          | Order number                                        |
| Customer ID | Clickable link → navigates to the customer's detail |
| User        | Django username                                     |
| Status      | Editable inline (dropdown)                          |
| Total       | Order total in ₹                                    |
| Created At  | Order date                                          |

- **Search** by order ID, username, email, or Customer ID.
- **Filter** by status or date.

**Detail view (click on an order):**

- **Customer section** — user, clickable customer link, shipping address
- **Pricing section** — subtotal, delivery fee, coupon, discount, total
- **Status & Dates** — status (editable), created at, updated at
- **Items (inline table)** — each line item with product, quantity, price, and item total

---

## Data Flow

```
User signs up
    │
    ▼
post_save signal fires
    │
    ▼
Customer profile auto-created (DF-XXXXXX)
    │
    ▼
User places an order
    │
    ▼
Order.save() auto-links order.customer from order.user
    │
    ▼
Admin can view customer → see all their orders
Admin can view order → jump to the customer
```

---

## Files Changed

| File                     | Changes                                                    |
|--------------------------|------------------------------------------------------------|
| `apps/core/models.py`   | Added `Customer` model, `post_save` signal, `Order.customer` FK, `Order.save()` override |
| `apps/core/admin.py`    | Added `CustomerAdmin`, `OrderAdmin`, `OrderItemInline`, `OrderInline`, `AddressAdmin` |
| `apps/core/migrations/0023_*.py` | Migration for Customer model + Order.customer field |

---

## Management Commands

### Backfill existing data

If there are users without a Customer profile (e.g. created before this feature), run:

```bash
python manage.py shell -c "
from django.apps import apps
from django.contrib.auth.models import User

Customer = apps.get_model('core', 'Customer')
Order = apps.get_model('core', 'Order')

for u in User.objects.all():
    Customer.objects.get_or_create(user=u)

for o in Order.objects.filter(customer__isnull=True, user__isnull=False).select_related('user'):
    try:
        o.customer = o.user.customer
        o.save(update_fields=['customer'])
    except Customer.DoesNotExist:
        pass
"
```

This is only needed once after deployment. All future users and orders are handled automatically.
