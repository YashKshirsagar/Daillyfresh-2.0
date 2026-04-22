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
        if not self.token:
            self.authenticate()
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }

    def _request(self, method, endpoint, **kwargs):
        """Make an API request with auto-retry on 401 (expired token)."""
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
        Returns the API response dict.
        """
        address = order.shipping_address
        items = order.items.select_related("product").all()

        payload = {
            "order_id": order.order_ref,
            "order_date": order.created_at.strftime("%Y-%m-%d %H:%M"),
            "pickup_location": "Home",
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
                    "sku": (item.product.sku if item.product and item.product.sku
                            else f"PROD-{item.product_id or item.id}"),
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
            "length": 10,
            "breadth": 10,
            "height": 10,
            "weight": float(
                sum(
                    (item.product.weight * item.quantity)
                    if item.product else 0.5
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
            order.save(update_fields=[
                "shiprocket_order_id", "shipment_id", "status",
            ])
            logger.info(f"Shiprocket order created for Order #{order.id}: {data}")
        else:
            logger.error(f"Shiprocket order failed for Order #{order.id}: {data}")

        return data

    def cancel_order(self, shiprocket_order_ids):
        """POST /orders/cancel"""
        response = self._request(
            "post", "/orders/cancel",
            json={"ids": shiprocket_order_ids},
        )
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
        response = self._request("get", "/courier/track", params={"order_id": order_id})
        return response.json()


# Singleton instance
shiprocket = ShiprocketAPI()
