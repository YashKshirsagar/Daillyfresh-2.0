import requests
import logging
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

SHIPROCKET_BASE_URL = "https://apiv2.shiprocket.in/v1/external"

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

    def _pickup_location(self):
        return getattr(settings, "SHIPROCKET_PICKUP_LOCATION", "Home")

    def _set_sync_state(self, order, *, status, error='', synced=False):
        order.shiprocket_sync_status = status
        order.shiprocket_sync_error = error[:2000]
        order.shiprocket_synced_at = timezone.now() if synced else None
        order.save(update_fields=[
            'shiprocket_sync_status',
            'shiprocket_sync_error',
            'shiprocket_synced_at',
        ])

    def apply_tracking_update(self, order, *, current_status='', awb='', courier_name=''):
        updates = []

        if awb != order.awb_code:
            order.awb_code = awb
            updates.append('awb_code')

        if courier_name != order.courier_name:
            order.courier_name = courier_name
            updates.append('courier_name')

        mapped_status = STATUS_MAP.get((current_status or '').strip().upper())
        if mapped_status and mapped_status != order.status:
            order.status = mapped_status
            updates.append('status')

        if updates:
            order.save(update_fields=updates)

        return mapped_status

    def sync_order(self, order):
        self._set_sync_state(order, status='pending', error='')
        try:
            data = self.create_order(order)
            return {'success': True, 'data': data}
        except Exception as exc:
            error_message = str(exc)
            self._set_sync_state(order, status='failed', error=error_message)
            logger.error(f"Shiprocket sync failed for Order #{order.id}: {error_message}")
            return {'success': False, 'message': error_message}

    def extract_tracking_event(self, data):
        tracking_data = data.get('tracking_data') or {}
        shipment_track = tracking_data.get('shipment_track') or []
        latest_track = shipment_track[0] if shipment_track else {}
        activities = tracking_data.get('shipment_track_activities') or []
        latest_activity = activities[0] if activities else {}

        current_status = (
            data.get('current_status')
            or tracking_data.get('current_status')
            or tracking_data.get('shipment_status')
            or latest_track.get('current_status')
            or latest_track.get('shipment_status')
            or latest_activity.get('current_status')
            or latest_activity.get('activity')
            or ''
        )
        awb = (
            data.get('awb')
            or tracking_data.get('awb_code')
            or latest_track.get('awb_code')
            or ''
        )
        courier_name = (
            data.get('courier_name')
            or tracking_data.get('courier_name')
            or latest_track.get('courier_name')
            or ''
        )

        return {
            'current_status': current_status,
            'awb': awb,
            'courier_name': courier_name,
        }

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
            "pickup_location": self._pickup_location(),
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
            order.shiprocket_sync_status = 'success'
            order.shiprocket_sync_error = ''
            order.shiprocket_synced_at = timezone.now()
            order.save(update_fields=[
                "shiprocket_order_id", "shipment_id", "status",
                "shiprocket_sync_status", "shiprocket_sync_error", "shiprocket_synced_at",
            ])
            logger.info(f"Shiprocket order created for Order #{order.id}: {data}")
        else:
            message = data.get('message') or data.get('errors') or response.text
            order.shiprocket_sync_status = 'failed'
            order.shiprocket_sync_error = str(message)[:2000]
            order.shiprocket_synced_at = None
            order.save(update_fields=[
                'shiprocket_sync_status', 'shiprocket_sync_error', 'shiprocket_synced_at',
            ])
            logger.error(f"Shiprocket order failed for Order #{order.id}: {data}")
            raise RuntimeError(f"Shiprocket create order failed: {message}")

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
