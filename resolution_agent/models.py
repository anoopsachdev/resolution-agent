"""Model back-ends for the agent loop.

All share one interface:  generate(system, messages, tools) -> list of content blocks
(Anthropic Messages API format: "text" and "tool_use" blocks).

* ClaudeModel   - the real LLM (needs ANTHROPIC_API_KEY and `pip install anthropic`).
* PolicyModel   - offline, deterministic stand-in so the project runs without an API key.
                  It decides ONLY from the conversation history (what an LLM sees) and
                  never reads the database.
* ScriptedModel - replays fixed responses; used by the tests to simulate a model that
                  calls unknown tools, sends malformed arguments, or loops forever.
"""

import itertools
import json
import os
import re

_ids = itertools.count(1)


def _tool_use(name, args, thought=""):
    blocks = [{"type": "text", "text": thought}] if thought else []
    blocks.append({"type": "tool_use", "id": f"toolu_{next(_ids):04d}", "name": name, "input": args})
    return blocks


def _text(msg):
    return [{"type": "text", "text": msg}]


class ClaudeModel:
    def __init__(self, model="claude-sonnet-5-5", max_tokens=1024):
        import anthropic

        self.client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self.model = model
        self.max_tokens = max_tokens

    def generate(self, system, messages, tools):
        response = self.client.messages.create(
            model=self.model, max_tokens=self.max_tokens, system=system, tools=tools, messages=messages
        )
        return [block.model_dump(exclude_none=True) for block in response.content]


class PolicyModel:
    ORDER_RE = re.compile(r"\bORD-\d+\b", re.IGNORECASE)

    def generate(self, system, messages, tools):
        results = self._tool_results(messages)
        if results and results[-1]["result"].get("error_code") in ("INVALID_ARGUMENTS", "MALFORMED_ARGUMENTS", "UNAUTHORIZED_TOOL"):
            return _text("I ran into a problem processing this request, so I'm passing it to a human agent.")

        match = self.ORDER_RE.search(messages[0]["content"])
        if not match:
            return _text("I'm sorry about the problem with your item. Could you share your order ID (e.g. ORD-1234)?")
        order_id = match.group(0).upper()

        lookup = self._latest(results, "lookup_order")
        if lookup is None:
            return _tool_use("lookup_order", {"order_id": order_id},
                             f"The customer reports an issue with {order_id}. Looking up the order first.")
        if lookup["status"] == "error":
            return _text(f"I'm sorry, but I couldn't find an order with the ID {order_id}. Could you please "
                         "verify the order ID from your confirmation email and send it again?")
        order = lookup["order"]
        first = order["customer_name"].split()[0]

        inventory = self._latest(results, "check_inventory")
        if inventory is None:
            return _tool_use("check_inventory", {"item_id": order["item_id"]},
                             f"Order found ({order['item_name']}). Checking whether a replacement is in stock.")

        exchangeable = order["exchange_eligible"] and inventory.get("units_available", 0) > 0
        refund = self._latest(results, "process_refund")

        if not exchangeable and refund is None:
            why = "the order is not eligible for exchange" if not order["exchange_eligible"] else "the replacement is out of stock"
            return _tool_use("process_refund", {"order_id": order_id, "reason": f"Damaged item; {why}"},
                             f"Cannot exchange because {why}. Initiating a refund.")

        if self._latest(results, "send_notification") is None:
            if exchangeable:
                body = (f"Hi {first}, your exchange for order {order_id} ({order['item_name']}) is confirmed. "
                        "A replacement unit will be shipped to you.")
            else:
                body = (f"Hi {first}, we've refunded {refund['currency']} {refund['amount_refunded']:,.2f} for order "
                        f"{order_id} to your {refund['refunded_to']}. Refund reference: {refund['refund_reference']}.")
            return _tool_use("send_notification", {"customer_email": order["customer_email"], "message": body},
                             "Sending the confirmation email.")

        if exchangeable:
            return _text(f"Hi {first}, I'm sorry your {order['item_name']} arrived damaged. A replacement is in stock, "
                         f"so I've confirmed an exchange for order {order_id}. A confirmation has been sent to "
                         f"{order['customer_email']}.")
        why = "your order isn't eligible for exchange" if not order["exchange_eligible"] else "the replacement is out of stock"
        return _text(f"Hi {first}, I'm sorry your {order['item_name']} arrived damaged. I couldn't arrange an exchange "
                     f"because {why}, so I've refunded {refund['currency']} {refund['amount_refunded']:,.2f} to your "
                     f"{refund['refunded_to']} (reference {refund['refund_reference']}). A confirmation has been sent "
                     f"to {order['customer_email']}.")

    @staticmethod
    def _tool_results(messages):
        names, out = {}, []
        for m in messages:
            if isinstance(m["content"], list):
                for b in m["content"]:
                    if b["type"] == "tool_use":
                        names[b["id"]] = b["name"]
                    elif b["type"] == "tool_result":
                        out.append({"name": names.get(b["tool_use_id"]), "result": json.loads(b["content"])})
        return out

    @staticmethod
    def _latest(results, name):
        return next((r["result"] for r in reversed(results) if r["name"] == name), None)


class ScriptedModel:
    """Replays a fixed list of responses; repeats the last one once exhausted."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def generate(self, system, messages, tools):
        response = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return [dict(b, id=f"toolu_s{self.calls}_{i}") if b["type"] == "tool_use" else b
                for i, b in enumerate(response)]
