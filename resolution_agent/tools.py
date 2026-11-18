"""Step 1 - Functional tools.

Four isolated, deterministic functions. Each returns structured data with a
"status" field ("success" or "error") instead of unstructured prose.
"""

import uuid

from . import database as db


def _error(code: str, message: str) -> dict:
    return {"status": "error", "error_code": code, "message": message}


def lookup_order(order_id: str) -> dict:
    """Order Lookup Action: customer name, item details, order status, eligibility."""
    order = db.ORDERS.get(order_id.strip().upper())
    if order is None:
        return _error(
            "ORDER_NOT_FOUND",
            f"No order with ID '{order_id}' exists. Ask the customer to verify the order ID.",
        )
    return {"status": "success", "order": dict(order)}


def check_inventory(item_id: str) -> dict:
    """Inventory Inspection Action: real-time warehouse stock count and availability."""
    record = db.INVENTORY.get(item_id.strip().upper())
    if record is None:
        return _error("ITEM_NOT_FOUND", f"No inventory record for item '{item_id}'.")
    return {
        "status": "success",
        "item_id": item_id,
        "warehouse": record["warehouse"],
        "units_available": record["units_available"],
        "in_stock": record["units_available"] > 0,
    }


def process_refund(order_id: str, reason: str) -> dict:
    """Refund Processing Action: issues a refund reference and records the refunded amount."""
    order = db.ORDERS.get(order_id.strip().upper())
    if order is None:
        return _error("ORDER_NOT_FOUND", f"No order with ID '{order_id}' exists.")
    record = {
        "refund_reference": f"RFD-{uuid.uuid4().hex[:8].upper()}",
        "order_id": order["order_id"],
        "amount_refunded": order["amount_paid"],
        "currency": order["currency"],
        "refunded_to": order["payment_method"],
        "reason": reason,
    }
    db.REFUNDS.append(record)
    order["order_status"] = "refunded"
    return {"status": "success", **record}


def send_notification(customer_email: str, message: str) -> dict:
    """Customer Notification Action: dispatches a confirmation (to a mock outbox)."""
    if "@" not in customer_email:
        return _error("INVALID_EMAIL", f"'{customer_email}' is not a valid email address.")
    notification_id = f"NTF-{uuid.uuid4().hex[:8].upper()}"
    db.OUTBOX.append({"notification_id": notification_id, "to": customer_email, "body": message})
    return {"status": "success", "notification_id": notification_id, "delivered_to": customer_email}
