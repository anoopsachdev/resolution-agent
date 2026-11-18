"""Step 2 - Declarative tool contracts (schemas).

The model never sees the code in tools.py, only these contracts: a semantic
name, a description of when to use the tool, typed and described input
parameters, and the required fields. Format: Anthropic Messages API tools.
"""

TOOL_SCHEMAS = [
    {
        "name": "lookup_order",
        "description": (
            "Look up a customer order in the order database. Returns the customer's name and "
            "email, the purchased item (item_id and name), amount paid, payment method, order "
            "status, and whether the order is eligible for exchange (exchange_eligible). "
            "Call this first when a customer reports a problem with an order."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "The order identifier provided by the customer, e.g. 'ORD-1001'.",
                }
            },
            "required": ["order_id"],
        },
    },
    {
        "name": "check_inventory",
        "description": (
            "Check real-time warehouse stock for an item to decide whether a replacement unit "
            "is available for exchange. Returns units_available and in_stock. Use the item_id "
            "returned by lookup_order."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "item_id": {
                    "type": "string",
                    "description": "The item identifier from the order record, e.g. 'SKU-KETTLE-02'.",
                }
            },
            "required": ["item_id"],
        },
    },
    {
        "name": "process_refund",
        "description": (
            "Issue a financial refund to the customer's original payment method. Use this ONLY "
            "when the item cannot be exchanged: the replacement is unavailable (units_available "
            "is 0) or the order is not eligible for exchange. Do NOT use it when a replacement "
            "is in stock and the order is eligible. Returns a refund transaction reference and "
            "the refunded amount."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "The order identifier to refund."},
                "reason": {
                    "type": "string",
                    "description": "Why the refund is issued, e.g. 'Damaged item; replacement out of stock'.",
                },
            },
            "required": ["order_id", "reason"],
        },
    },
    {
        "name": "send_notification",
        "description": (
            "Send the customer an official confirmation email describing the resolution "
            "(exchange confirmed, or refund issued with its reference). Call once, after the "
            "resolution is decided, using the customer_email from lookup_order."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_email": {"type": "string", "description": "The customer's email address."},
                "message": {"type": "string", "description": "Full plain-text body of the confirmation."},
            },
            "required": ["customer_email", "message"],
        },
    },
]
