# Decision-Making Resolution Agent

**Assignment:** Building a Decision-Making Resolution Agent (Agentic AI: Build an Agent That Uses Tools)

## Why I built this

I built this as an assignment for Xebia's Forward Deployed Engineer (FDE) Launchpad programme. The goal was to learn how AI agents go beyond chatting and take real actions: reading data, making a decision, and carrying it out safely with guardrails.

## What it does

An autonomous, tool-using agent that resolves a customer's damaged-item complaint. It reads the order record and checks warehouse inventory. If the item can be exchanged, it confirms the exchange. If the replacement is out of stock or the order is ineligible, it initiates a refund. It then sends a confirmation notification and summarises the resolution for the customer.

## Run

```bash
pip install -r requirements.txt
python run_demo.py           # the 4 acceptance scenarios, with the full reasoning trace
python -m pytest -v          # tests for the acceptance criteria and guardrails

export ANTHROPIC_API_KEY=... # optional: drive the same loop with Claude
python run_demo.py --claude
```

Without an API key, the demo uses `PolicyModel`, a deterministic offline stand-in for the LLM. It decides only from the conversation history, never from the database, so the tool loop, dispatcher and guardrails run exactly as they would with a real model.

## Structure (mapped to the assignment steps)

| Step | File | Implementation |
|---|---|---|
| 1. Functional tools | `resolution_agent/tools.py` | `lookup_order`, `check_inventory`, `process_refund`, `send_notification`. Each returns structured data with `status: success \| error`. |
| 2. Tool contracts | `resolution_agent/schemas.py` | A name, description, typed and described parameters, and `required` fields for each tool. The refund description says it is used only when a replacement is unavailable or the order is ineligible. |
| 3. Registration & safe dispatch | `resolution_agent/dispatcher.py` | `TOOL_REGISTRY` whitelist. `dispatch()` rejects unregistered tools with `UNAUTHORIZED_TOOL`. |
| 4. Agentic state loop (ReAct) | `resolution_agent/agent.py` | Ordered message history → model call with tool schemas → detect tool calls → execute through the dispatcher → append results, linked by `tool_use_id` → repeat until a final text answer. |
| 5. Guardrails | `agent.py`, `dispatcher.py`, `tools.py` | `MAX_ITERATIONS = 5`, then a safe halt and human escalation. Tools return error payloads (e.g. `ORDER_NOT_FOUND`) instead of crashing. Malformed or invalid arguments go back into the loop as errors so the model can self-correct. |

Supporting files: `database.py` (mock orders, inventory, refunds and outbox), `models.py` (`ClaudeModel`, `PolicyModel`, and `ScriptedModel` for the tests), `run_demo.py`, `demo_output.txt`, `tests/test_acceptance.py`.

## Mock data

| Order | Item | Eligible | Stock | Expected outcome |
|---|---|---|---|---|
| ORD-1001 | Headphones | Yes | 14 | Exchange confirmed |
| ORD-1002 | Kettle | Yes | 0 | Refund |
| ORD-1003 | Smartwatch | No | 22 | Refund (ineligible) |
| ORD-9999 | n/a | n/a | n/a | "Order not found, please verify" |

## Acceptance criteria

| Criterion | Evidence |
|---|---|
| 1. Autonomous investigation | The agent calls `lookup_order`, then `check_inventory` with the looked-up `item_id`, without being told which tools to use (`test_agent_reads_order_and_inventory_on_its_own`). |
| 2. Correct branching | Stock 0 → `process_refund` (`test_stock_zero_triggers_refund`). Stock > 0 → exchange, no refund (`test_stock_available_triggers_exchange_not_refund`). Ineligible → refund (`test_ineligible_order_triggers_refund`). |
| 3. Complete fulfilment | Every resolution ends with `send_notification` and a polite summary (`test_resolution_ends_with_email_and_summary`). |
| 4. Resilience | An invalid order ID gets an explanation and a request to verify, with no crash (`test_invalid_order_id_is_explained`). |

## Sample trace (stock = 0 → refund)

```
CUSTOMER: The kettle I got in order ORD-1002 has a broken glass jug. Please sort this out.
  [1] tool : lookup_order({"order_id": "ORD-1002"})          -> exchange_eligible: true
  [2] tool : check_inventory({"item_id": "SKU-KETTLE-02"})   -> units_available: 0
  [3] model: Cannot exchange because the replacement is out of stock. Initiating a refund.
  [3] tool : process_refund({"order_id": "ORD-1002", ...})   -> RFD-…, INR 2,499.00
  [4] tool : send_notification({"customer_email": "rahul.mehta@example.com", ...})
  [5] AGENT: Hi Rahul, I'm sorry your Electric Glass Kettle 1.7L arrived damaged. I couldn't arrange an
             exchange because the replacement is out of stock, so I've refunded INR 2,499.00 ...
```

The full output for all four scenarios is in `demo_output.txt`.
