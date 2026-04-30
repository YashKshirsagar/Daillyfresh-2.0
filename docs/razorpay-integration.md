# Razorpay Integration Guide — Daillyfresh

## Overview

This document covers the Razorpay online payment integration added to Daillyfresh. It includes the full architecture, payment flow, model changes, view logic, frontend changes, and environment setup.

---

## 1. Architecture

### Payment Flow

```
Customer clicks "Place Order"
        │
        ▼
Payment Method Modal pops up
  ┌─────────────────────────┐
  │  💵 Cash on Delivery    │
  │  💳 Pay Online          │
  └─────────────────────────┘
        │                      │
        ▼                      ▼
   COD Path              Online Payment Path
        │                      │
        ▼                      ▼
place_order view      create_razorpay_order view
(existing flow)       - Validates cart server-side
payment_mode=COD      - Creates Razorpay order (no DB order yet)
DB order created      - Returns razorpay_order_id + amount to frontend
→ Shiprocket (COD)            │
                               ▼
                      Razorpay modal opens on frontend
                      (UPI / Cards / Net Banking / Wallets)
                               │
                    ┌──────────┴──────────┐
                    ▼                     ▼
             Payment success         Payment dismissed
                    │                 (no DB order)
                    ▼
           verify_payment view
           - Verifies HMAC signature
           - Recalculates totals server-side
           - Creates DB Order (payment_mode=Prepaid, status=Processing)
           - Pushes to Shiprocket with Prepaid mode
                    │
                    ▼
           Redirect → My Orders
```

### Key Principle
**No DB Order is created until Razorpay payment is verified.** This prevents ghost orders from abandoned payment flows, declined cards, or closed modals.

---

## 2. Environment Variables

### `.env`
```env
# Razorpay
RAZORPAY_KEY_ID=rzp_test_XXXXXXXXXXXXXXXX
RAZORPAY_KEY_SECRET=XXXXXXXXXXXXXXXXXXXXXXXX
```

### `config/settings/base.py`
```python
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
```

> **Security:** Never commit `.env` to version control. For production (Render), add these as environment variables in the Render dashboard under **Environment → Environment Variables**.

---

## 3. Going Live (Test → Production)

1. Log in to [dashboard.razorpay.com](https://dashboard.razorpay.com)
2. Go to **Settings → API Keys**
3. Switch from **Test Mode** to **Live Mode** (toggle top-left)
4. Generate Live keys
5. Replace `.env` values:
   ```env
   RAZORPAY_KEY_ID=rzp_live_XXXXXXXXXXXXXXXX
   RAZORPAY_KEY_SECRET=XXXXXXXXXXXXXXXXXXXXXXXX
   ```
6. Complete KYC on Razorpay (required to accept live payments)

> Test key prefix: `rzp_test_`  
> Live key prefix: `rzp_live_`

---

## 4. Model Changes

### New Fields on `Order`

```python
# apps/core/models.py

razorpay_order_id = models.CharField(
    max_length=100, blank=True, null=True, db_index=True,
    help_text="Razorpay order ID (rzp_...)"
)
razorpay_payment_id = models.CharField(
    max_length=100, blank=True, null=True,
    help_text="Razorpay payment ID after successful payment"
)
```

### Existing Fields Used
| Field | COD Value | Online Value |
|---|---|---|
| `payment_mode` | `COD` | `Prepaid` |
| `status` | `Pending` | `Processing` |

### Migration
```
apps/core/migrations/0034_add_razorpay_fields.py
```

---

## 5. Views

### `create_razorpay_order` — `POST /api/razorpay/create-order/`

**Purpose:** Validates the cart server-side and creates a Razorpay order. Called before the Razorpay modal opens. Does NOT create a DB Order.

**Request body:**
```json
{
  "cart": [{ "id": 1, "quantity": 2 }],
  "address_id": 5,
  "coupon_code": "SAVE10"
}
```

**Response (success):**
```json
{
  "success": true,
  "razorpay_order_id": "order_XXXXXXXXXXXXXXXXXX",
  "amount": 63000,
  "key_id": "rzp_test_XXXXXXXXXXXXXXXX"
}
```
> `amount` is in paise (₹630 = `63000`)

**Response (failure):**
```json
{
  "success": false,
  "message": "Could not initiate payment. Please try again."
}
```

---

### `verify_payment` — `POST /api/razorpay/verify-payment/`

**Purpose:** Verifies the Razorpay HMAC signature. If valid, creates the DB Order and pushes to Shiprocket as Prepaid.

**Request body:**
```json
{
  "razorpay_order_id": "order_XXXXXXXXXXXXXXXXXX",
  "razorpay_payment_id": "pay_XXXXXXXXXXXXXXXXXX",
  "razorpay_signature": "HMAC_SHA256_SIGNATURE",
  "cart": [{ "id": 1, "quantity": 2 }],
  "address_id": 5,
  "coupon_code": "SAVE10"
}
```

**Response (success):**
```json
{
  "success": true,
  "message": "Payment successful! Order placed.",
  "order_ref": "DF-A3F2B1C9"
}
```

**Response (verification failure):**
```json
{
  "success": false,
  "message": "Payment verification failed. Contact support."
}
```

> The cart and totals are recalculated from the DB on this view too — frontend values are never trusted.

---

## 6. URL Routes

```python
# config/urls.py
path('api/razorpay/create-order/', create_razorpay_order, name='create_razorpay_order'),
path('api/razorpay/verify-payment/', verify_payment, name='verify_payment'),
```

---

## 7. Frontend (cart.html)

### Razorpay SDK
Loaded at the bottom of `cart.html` (deferred, only on the cart page):
```html
<script src="https://checkout.razorpay.com/v1/checkout.js" defer></script>
```

### Alpine.js State Added
```js
showPaymentModal: false,  // controls payment method modal visibility
```

### New Methods
| Method | Triggered by | Does |
|---|---|---|
| `placeOrder()` | Place Order button | Opens payment method modal |
| `confirmCOD()` | COD button in modal | Calls existing `place_order` view |
| `confirmOnlinePayment()` | Pay Online button in modal | Calls `create_razorpay_order`, opens Razorpay modal, then calls `verify_payment` |

### Payment Method Modal
A styled modal with two buttons appears after clicking "Place Order":
- **💵 Cash on Delivery** — order created immediately in DB with `payment_mode=COD`
- **💳 Pay Online** — Razorpay checkout opens; order created only after verified payment

---

## 8. Shiprocket Connection

| Payment Mode | Shiprocket `payment_method` | Order Status after placement |
|---|---|---|
| COD | `COD` | `Pending` |
| Prepaid (Razorpay) | `Prepaid` | `Processing` |

Shiprocket push happens in both cases **after** the order is confirmed — for COD inside `place_order`, for online inside `verify_payment`.

---

## 9. Dependency

Added to `requirements.txt`:
```
razorpay==1.4.2
```

Install locally:
```bash
pip install razorpay==1.4.2
```

---

## 10. Files Changed

| File | Change |
|---|---|
| `.env` | Added `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` |
| `config/settings/base.py` | Reads Razorpay keys from env |
| `requirements.txt` | Added `razorpay==1.4.2` |
| `apps/core/models.py` | Added `razorpay_order_id`, `razorpay_payment_id` |
| `apps/core/views.py` | Added `create_razorpay_order`, `verify_payment` views |
| `config/urls.py` | Registered 2 new API routes |
| `templates/cart.html` | Payment modal HTML, updated Alpine.js state and methods, Razorpay SDK script |
| `apps/core/migrations/0034_add_razorpay_fields.py` | Migration for new fields |

---

## 11. Testing

### Test Mode
Use Razorpay test credentials (`rzp_test_*`). Razorpay provides test card numbers:

| Type | Card Number | CVV | Expiry |
|---|---|---|---|
| Success | `4111 1111 1111 1111` | Any 3 digits | Any future date |
| Failure | `4000 0000 0000 0002` | Any 3 digits | Any future date |

**Test UPI:** Use `success@razorpay` for a successful UPI payment in test mode.

### Verify in Admin
After a successful test payment:
1. Go to `admin/core/order/`
2. The order should appear with:
   - `payment_mode = Prepaid`
   - `status = Processing`
   - `razorpay_order_id` populated
   - `razorpay_payment_id` populated

### Verify on Razorpay Dashboard
1. Log in to [dashboard.razorpay.com](https://dashboard.razorpay.com)
2. Go to **Transactions → Payments**
3. Test payments appear here in Test Mode

---

## 12. Security Notes

- **HMAC verification** is done server-side using `razorpay.Client.utility.verify_payment_signature()`. A forged payment ID without the correct signature is rejected.
- **Totals are always recalculated** from the DB in both `create_razorpay_order` and `verify_payment` — frontend amounts are ignored.
- **`RAZORPAY_KEY_SECRET` is never sent to the frontend.** Only `RAZORPAY_KEY_ID` (public key) is passed to the browser.
- Both views require `@login_required` — unauthenticated requests are rejected.
