# Shiprocket Integration Guide — Daillyfresh

## Overview

This document covers integrating Shiprocket's shipping & tracking API into the Daillyfresh Django application. It includes architecture assessment, model changes, API service setup, webhook handling, and testing strategy.

---

## 1. Architecture Assessment

### What Already Fits

| Existing Model | Shiprocket Requirement | Status |
|---|---|---|
| `Address` (name, phone, street, city, state, pincode) | Billing/shipping address | ✅ Ready |
| `Order` (items, subtotal, delivery_fee, total) | Order amount & line items | ✅ Ready |
| `OrderItem` (product, qty, price) | `order_items[]` array | ✅ Ready |
| `Customer` (unique `customer_id`) | Reference order ID | ✅ Ready |

### Gaps to Fill

| What's Missing | Why It's Needed |
|---|---|
| `Product.weight` | Shiprocket requires package weight |
| `Product.sku` | Shiprocket requires SKU per item |
| `Order.shiprocket_order_id` | To link local order with Shiprocket |
| `Order.shipment_id` | To track shipment on Shiprocket |
| `Order.awb_code` | Airway Bill number for tracking |
| `Order.courier_name` | To show which courier is delivering |
| `Order.payment_mode` | Shiprocket needs COD vs Prepaid |
| More `Order.status` choices | Map to Shiprocket's shipping statuses |

---

## 2. Shiprocket Account Setup

1. Register at [app.shiprocket.in/register](https://app.shiprocket.in/register)
2. Go to **Settings → API → Add New API User**
3. Click **"Create API User"**
4. Enter a unique email (different from your main Shiprocket login)
5. Select the API modules you need access to
6. Click **"Create User"** — password is sent to your registered email
7. Note down the **API email** and **API password**

---

## 3. Environment Variables

Add to `.env`:

```env
SHIPROCKET_ENABLED=true
SHIPROCKET_EMAIL=your-api-user@email.com
SHIPROCKET_PASSWORD=your-api-password
```

Add to `config/settings/base.py`:

```python
SHIPROCKET_ENABLED = os.getenv("SHIPROCKET_ENABLED", "false").lower() == "true"
SHIPROCKET_EMAIL = os.getenv("SHIPROCKET_EMAIL", "")
SHIPROCKET_PASSWORD = os.getenv("SHIPROCKET_PASSWORD", "")
```

---

## 4. Model Changes

### 4.1 Product Model — Add `weight` and `sku`

```python
# In Product model
sku = models.CharField(max_length=100, blank=True, default='', help_text="Stock Keeping Unit code")
weight = models.DecimalField(max_digits=6, decimal_places=2, default=0.5, help_text="Weight in KG")
```

Also add the same fields to the `Combo` model if combos are shippable.

### 4.2 Order Model — Add Shiprocket Fields

```python
# New status choices
STATUS_CHOICES = (
    ('Pending', 'Pending'),
    ('Processing', 'Processing'),
    ('Shipped', 'Shipped'),
    ('In Transit', 'In Transit'),
    ('Out for Delivery', 'Out for Delivery'),
    ('Delivered', 'Delivered'),
    ('Cancelled', 'Cancelled'),
    ('RTO', 'Returned to Origin'),
    ('Completed', 'Completed'),
)

PAYMENT_CHOICES = (
    ('COD', 'Cash on Delivery'),
    ('Prepaid', 'Prepaid'),
)

# New fields
payment_mode = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default='COD')
shiprocket_order_id = models.CharField(max_length=50, blank=True, null=True)
shipment_id = models.CharField(max_length=50, blank=True, null=True)
awb_code = models.CharField(max_length=50, blank=True, null=True, help_text="Airway Bill number for tracking")
courier_name = models.CharField(max_length=100, blank=True, null=True)
```

### 4.3 Run Migrations

```bash
python manage.py makemigrations core
python manage.py migrate
```

---

## 5. Shiprocket API Service

Create `apps/core/shiprocket.py`:

```python
import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

SHIPROCKET_BASE_URL = "https://apiv2.shiprocket.in/v1/external"


class ShiprocketAPI:
    """Wrapper for Shiprocket REST API."""

    def __init__(self):
        self.token = None

    def authenticate(self):
        """
        POST /auth/login
        Returns a Bearer token valid for 10 days.
        """
        response = requests.post(
            f"{SHIPROCKET_BASE_URL}/auth/login",
            json={
                "email": settings.SHIPROCKET_EMAIL,
                "password": settings.SHIPROCKET_PASSWORD,
            },
        )
        response.raise_for_status()
        self.token = response.json()["token"]
        return self.token

    def _headers(self):
        """Return auth headers, auto-authenticating if needed."""
        if not self.token:
            self.authenticate()
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }

    def _request(self, method, endpoint, **kwargs):
        """Make an API request with auto-retry on 401."""
        url = f"{SHIPROCKET_BASE_URL}{endpoint}"
        response = getattr(requests, method)(url, headers=self._headers(), **kwargs)
        if response.status_code == 401:
            self.authenticate()
            response = getattr(requests, method)(url, headers=self._headers(), **kwargs)
        return response

    # ── Order APIs ───────────────────────────────────────────

    def create_order(self, order):
        """
        POST /orders/create/adhoc
        Push a Daillyfresh Order to Shiprocket.
        """
        address = order.shipping_address
        items = order.items.select_related("product").all()

        payload = {
            "order_id": str(order.id),
            "order_date": order.created_at.strftime("%Y-%m-%d %H:%M"),
            "pickup_location": "Primary",  # Must match name in Shiprocket dashboard
            "billing_customer_name": address.full_name.split()[0],
            "billing_last_name": " ".join(address.full_name.split()[1:]) or "",
            "billing_address": address.street_address,
            "billing_city": address.city,
            "billing_pincode": address.pincode,
            "billing_state": address.state,
            "billing_country": "India",
            "billing_email": order.user.email if order.user else "",
            "billing_phone": address.phone_number,
            "shipping_is_billing": True,
            "order_items": [
                {
                    "name": item.product.name if item.product else "Product",
                    "sku": item.product.sku if item.product else f"PROD-{item.id}",
                    "units": item.quantity,
                    "selling_price": str(item.price),
                    "discount": "0",
                    "tax": "0",
                    "hsn": "",
                }
                for item in items
            ],
            "payment_method": order.payment_mode,
            "sub_total": str(order.total_amount),
            "length": 10,   # cm
            "breadth": 10,   # cm
            "height": 10,    # cm
            "weight": float(
                sum(
                    (item.product.weight * item.quantity) if item.product else 0.5
                    for item in items
                )
            ),
        }

        response = self._request("post", "/orders/create/adhoc", json=payload)
        data = response.json()

        if response.status_code in (200, 201):
            order.shiprocket_order_id = str(data.get("order_id", ""))
            order.shipment_id = str(data.get("shipment_id", ""))
            order.status = "Processing"
            order.save()
            logger.info(f"Shiprocket order created: {data}")
        else:
            logger.error(f"Shiprocket order creation failed: {data}")

        return data

    def cancel_order(self, shiprocket_order_ids):
        """
        POST /orders/cancel
        Cancel one or more orders on Shiprocket.
        """
        response = self._request("post", "/orders/cancel", json={"ids": shiprocket_order_ids})
        return response.json()

    # ── Tracking APIs ────────────────────────────────────────

    def track_by_awb(self, awb_code):
        """GET /courier/track/awb/{awb_code}"""
        response = self._request("get", f"/courier/track/awb/{awb_code}")
        return response.json()

    def track_by_shipment(self, shipment_id):
        """GET /courier/track/shipment/{shipment_id}"""
        response = self._request("get", f"/courier/track/shipment/{shipment_id}")
        return response.json()

    def track_by_order(self, order_id):
        """GET /courier/track?order_id={order_id}"""
        response = self._request("get", f"/courier/track", params={"order_id": order_id})
        return response.json()


# Singleton instance
shiprocket = ShiprocketAPI()
```

---

## 6. Integrate into Order Placement

In `apps/core/views.py` → `place_order()`, add after creating the order:

```python
from django.conf import settings
from core.shiprocket import shiprocket

# After order and order items are created:
if settings.SHIPROCKET_ENABLED:
    try:
        sr_response = shiprocket.create_order(order)
    except Exception as e:
        logger.error(f"Shiprocket order push failed for Order #{order.id}: {e}")
        # Order is still saved locally — can be pushed manually later
```

---

## 7. Webhook for Live Tracking Updates

### 7.1 Create Webhook View

In `apps/core/views.py`:

```python
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def shiprocket_webhook(request):
    """
    Receive tracking updates from Shiprocket.
    Shiprocket sends a POST with JSON body on every tracking event.
    """
    if request.method != "POST":
        return JsonResponse({"status": "error"}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "bad request"}, status=400)

    sr_order_id = str(data.get("sr_order_id", ""))
    awb = data.get("awb", "")
    current_status = data.get("current_status", "")
    courier_name = data.get("courier_name", "")

    # Map Shiprocket statuses to Daillyfresh statuses
    STATUS_MAP = {
        "MANIFEST GENERATED": "Processing",
        "PICKED UP": "Shipped",
        "SHIPPED": "Shipped",
        "IN TRANSIT": "In Transit",
        "OUT FOR DELIVERY": "Out for Delivery",
        "DELIVERED": "Delivered",
        "RTO INITIATED": "RTO",
        "RTO DELIVERED": "RTO",
        "CANCELED": "Cancelled",
    }

    try:
        order = Order.objects.get(shiprocket_order_id=sr_order_id)
        order.awb_code = awb
        order.courier_name = courier_name
        new_status = STATUS_MAP.get(current_status)
        if new_status:
            order.status = new_status
        order.save()
        logger.info(f"Webhook updated Order #{order.id} → {current_status}")
    except Order.DoesNotExist:
        logger.warning(f"Webhook: No order found for sr_order_id={sr_order_id}")

    return JsonResponse({"status": "ok"})
```

### 7.2 Add URL Route

In `config/urls.py`:

```python
path('webhook/shipping/', shiprocket_webhook, name='shiprocket_webhook'),
```

### 7.3 Configure in Shiprocket Dashboard

1. Log in to Shiprocket
2. Go to **Settings → API → Webhooks**
3. Set Webhook URL: `https://yourdomain.com/webhook/shipping/`
4. Enable the toggle
5. Optionally add a security token (sent as `x-api-key` header)

> **Important:** Do NOT use words like `shiprocket`, `sr`, `kartrocket`, or `kr` in your webhook URL.

---

## 8. Shiprocket Status Reference

These are the statuses Shiprocket sends via webhook/API:

| Status | Status ID | Meaning |
|---|---|---|
| `MANIFEST GENERATED` | 5 | Label/manifest created |
| `PICKED UP` | 42 | Courier picked up package |
| `SHIPPED` | 6 | Received at origin center |
| `IN TRANSIT` | 18 | Moving between hubs |
| `OUT FOR DELIVERY` | 17 | Last mile, out for delivery |
| `DELIVERED` | 7 | Successfully delivered |
| `RTO INITIATED` | 9 | Return to origin started |
| `RTO DELIVERED` | 14 | Package returned to seller |
| `CANCELED` | 12 | Order cancelled |
| `LOST` | 10 | Package lost in transit |
| `DISPOSED OFF` | 11 | Package disposed |

### Webhook Payload Fields

```json
{
  "awb": "19041424751540",
  "courier_name": "Delhivery Surface",
  "current_status": "IN TRANSIT",
  "current_status_id": 20,
  "shipment_status": "IN TRANSIT",
  "shipment_status_id": 18,
  "current_timestamp": "23 05 2023 11:43:52",
  "order_id": "your_order_id",
  "sr_order_id": 348456385,
  "awb_assigned_date": "2023-05-19 11:59:16",
  "pickup_scheduled_date": "2023-05-19 11:59:17",
  "etd": "2023-05-23 15:40:19",
  "is_return": 0,
  "pod_status": "OTP Based Delivery",
  "scans": [
    {
      "date": "2023-05-19 15:32:17",
      "status": "X-PPOM",
      "activity": "In Transit - Shipment picked up",
      "location": "Delhi (Delhi)",
      "sr-status": "42",
      "sr-status-label": "PICKED UP"
    }
  ]
}
```

---

## 9. Testing Strategy

### 9.1 Local Testing (Shiprocket Disabled)

Set `SHIPROCKET_ENABLED=false` in `.env`. Orders will be created locally but NOT pushed to Shiprocket. You can test the entire order flow without affecting Shiprocket.

### 9.2 Shiprocket Test Orders

When `SHIPROCKET_ENABLED=true`:
- Orders are pushed to Shiprocket but **won't actually ship** until you:
  - Assign a courier in Shiprocket dashboard
  - Schedule a pickup
  - Complete KYC on your Shiprocket account
- You can see test orders in your Shiprocket dashboard under **Orders**
- Cancel test orders via dashboard or API to keep things clean

### 9.3 Webhook Testing

Use [webhook.site](https://webhook.site) or ngrok to test webhooks locally:

```bash
# Expose local server
ngrok http 8000

# Set the ngrok URL as webhook in Shiprocket:
# https://abc123.ngrok.io/webhook/shipping/
```

### 9.4 Management Command for Manual Push

Create `apps/core/management/commands/push_to_shiprocket.py` to manually push existing orders:

```python
from django.core.management.base import BaseCommand
from core.models import Order
from core.shiprocket import shiprocket


class Command(BaseCommand):
    help = "Push pending orders to Shiprocket"

    def add_arguments(self, parser):
        parser.add_argument("--order-id", type=int, help="Specific order ID to push")

    def handle(self, *args, **options):
        if options["order_id"]:
            orders = Order.objects.filter(id=options["order_id"])
        else:
            orders = Order.objects.filter(
                shiprocket_order_id__isnull=True,
                status="Pending",
            )

        for order in orders:
            try:
                result = shiprocket.create_order(order)
                self.stdout.write(self.style.SUCCESS(
                    f"Order #{order.id} → Shiprocket ID: {result.get('order_id')}"
                ))
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f"Order #{order.id} failed: {e}"
                ))
```

Usage:
```bash
python manage.py push_to_shiprocket              # Push all pending orders
python manage.py push_to_shiprocket --order-id 42 # Push specific order
```

---

## 10. Order Flow After Integration

```
Customer places order on website
        │
        ▼
Order created in DB (status: Pending)
        │
        ▼
Shiprocket API called → POST /orders/create/adhoc
        │
        ▼
Shiprocket returns order_id + shipment_id (status: Processing)
        │
        ▼
Admin assigns courier on Shiprocket dashboard
(or via API: POST /courier/assign/awb)
        │
        ▼
Shiprocket webhook fires on each event:
  ┌─ PICKED UP       → status: Shipped
  ├─ IN TRANSIT       → status: In Transit
  ├─ OUT FOR DELIVERY → status: Out for Delivery
  ├─ DELIVERED        → status: Delivered
  └─ RTO INITIATED    → status: RTO
        │
        ▼
Customer sees live status on "My Orders" page
```

---

## 11. Shiprocket API Quick Reference

| Action | Method | Endpoint |
|---|---|---|
| Authenticate | POST | `/auth/login` |
| Create Order | POST | `/orders/create/adhoc` |
| Cancel Order | POST | `/orders/cancel` |
| Track by AWB | GET | `/courier/track/awb/{awb}` |
| Track by Shipment | GET | `/courier/track/shipment/{id}` |
| Track by Order | GET | `/courier/track?order_id={id}` |
| Get Couriers | GET | `/courier/courierListWithCounts` |
| Assign AWB | POST | `/courier/assign/awb` |
| Schedule Pickup | POST | `/courier/generate/pickup` |
| Generate Label | POST | `/courier/generate/label` |

**Base URL:** `https://apiv2.shiprocket.in/v1/external`
**Auth:** Bearer token (valid 10 days)

---

## 12. Dependency

Add to `requirements.txt`:

```
requests>=2.32.0
```

(`requests` is already present in the project.)

---

## 13. Files to Create/Modify

| File | Action |
|---|---|
| `.env` | Add `SHIPROCKET_*` variables |
| `config/settings/base.py` | Add Shiprocket settings |
| `apps/core/models.py` | Add fields to Product & Order |
| `apps/core/shiprocket.py` | **New** — API service module |
| `apps/core/views.py` | Update `place_order`, add webhook view |
| `config/urls.py` | Add webhook URL |
| `apps/core/management/commands/push_to_shiprocket.py` | **New** — manual push command |
