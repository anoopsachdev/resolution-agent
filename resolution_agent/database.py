"""In-memory mock database: orders, warehouse inventory, refunds ledger, email outbox."""

from copy import deepcopy

_SEED_ORDERS = {
    "ORD-1001": {
        "order_id": "ORD-1001",
        "customer_name": "Aisha Khan",
        "customer_email": "aisha.khan@example.com",
        "item_id": "SKU-HEADPHONES-01",
        "item_name": "Wireless Noise-Cancelling Headphones",
        "amount_paid": 7999.00,
        "currency": "INR",
        "payment_method": "Visa card ending 4417",
        "order_status": "delivered",
        "exchange_eligible": True,
    },
    "ORD-1002": {
        "order_id": "ORD-1002",
        "customer_name": "Rahul Mehta",
        "customer_email": "rahul.mehta@example.com",
        "item_id": "SKU-KETTLE-02",
        "item_name": "Electric Glass Kettle 1.7L",
        "amount_paid": 2499.00,
        "currency": "INR",
        "payment_method": "UPI",
        "order_status": "delivered",
        "exchange_eligible": True,
    },
    "ORD-1003": {
        "order_id": "ORD-1003",
        "customer_name": "Priya Nair",
        "customer_email": "priya.nair@example.com",
        "item_id": "SKU-WATCH-03",
        "item_name": "Fitness Smartwatch",
        "amount_paid": 4999.00,
        "currency": "INR",
        "payment_method": "Mastercard ending 9021",
        "order_status": "delivered",
        "exchange_eligible": False,  # outside the exchange window
    },
}

_SEED_INVENTORY = {
    "SKU-HEADPHONES-01": {"warehouse": "Gurugram FC-2", "units_available": 14},
    "SKU-KETTLE-02": {"warehouse": "Gurugram FC-2", "units_available": 0},
    "SKU-WATCH-03": {"warehouse": "Bhiwandi FC-1", "units_available": 22},
}

ORDERS: dict = {}
INVENTORY: dict = {}
REFUNDS: list = []
OUTBOX: list = []


def reset() -> None:
    """Restore the seed data (used before each demo scenario and test)."""
    ORDERS.clear()
    ORDERS.update(deepcopy(_SEED_ORDERS))
    INVENTORY.clear()
    INVENTORY.update(deepcopy(_SEED_INVENTORY))
    REFUNDS.clear()
    OUTBOX.clear()


reset()
