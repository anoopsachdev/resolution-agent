"""Tests for the assignment's acceptance criteria and guardrails.  Run:  python -m pytest -v"""

import pytest

from resolution_agent import database as db
from resolution_agent.agent import MAX_ITERATIONS, run_agent
from resolution_agent.dispatcher import dispatch
from resolution_agent.models import PolicyModel, ScriptedModel


@pytest.fixture(autouse=True)
def fresh_db():
    db.reset()


def names(result):
    return [name for name, _, _ in result.tool_calls]


# Acceptance 1: autonomous investigation
def test_agent_reads_order_and_inventory_on_its_own():
    result = run_agent("My headphones from ORD-1001 arrived damaged.", PolicyModel())
    assert names(result)[:2] == ["lookup_order", "check_inventory"]
    assert result.tool_calls[1][1] == {"item_id": "SKU-HEADPHONES-01"}


# Acceptance 2: conditional branching
def test_stock_zero_triggers_refund():
    result = run_agent("The kettle from ORD-1002 arrived broken.", PolicyModel())
    assert names(result) == ["lookup_order", "check_inventory", "process_refund", "send_notification"]
    assert db.REFUNDS[0]["amount_refunded"] == 2499.00


def test_stock_available_triggers_exchange_not_refund():
    result = run_agent("My headphones from ORD-1001 arrived damaged.", PolicyModel())
    assert names(result) == ["lookup_order", "check_inventory", "send_notification"]
    assert db.REFUNDS == []
    assert "exchange" in result.final_answer


def test_ineligible_order_triggers_refund():
    result = run_agent("My smartwatch from ORD-1003 arrived damaged.", PolicyModel())
    assert "process_refund" in names(result)


# Acceptance 3: complete fulfilment
@pytest.mark.parametrize("order_id", ["ORD-1001", "ORD-1002", "ORD-1003"])
def test_resolution_ends_with_email_and_summary(order_id):
    result = run_agent(f"The item in {order_id} arrived damaged.", PolicyModel())
    assert not result.escalated
    assert len(db.OUTBOX) == 1 and db.OUTBOX[0]["to"] == db.ORDERS[order_id]["customer_email"]
    assert "sorry" in result.final_answer.lower()


# Acceptance 4: resilience to an invalid order ID
def test_invalid_order_id_is_explained():
    result = run_agent("Order ORD-9999 arrived damaged.", PolicyModel())
    assert result.tool_calls[0][2]["error_code"] == "ORDER_NOT_FOUND"
    assert "couldn't find" in result.final_answer and "verify" in result.final_answer


# Step 3: registry whitelist / authorization check
def test_unregistered_tool_is_rejected():
    model = ScriptedModel([
        [{"type": "tool_use", "name": "delete_all_orders", "input": {}}],
        [{"type": "text", "text": "That action isn't available."}],
    ])
    result = run_agent("ORD-1001 is damaged", model)
    assert result.tool_calls[0][2]["error_code"] == "UNAUTHORIZED_TOOL"
    assert result.final_answer == "That action isn't available."


# Step 5.3: argument validation fed back so the model can self-correct
@pytest.mark.parametrize("raw, code", [
    ("{order_id: ORD-1001", "MALFORMED_ARGUMENTS"),
    ({}, "INVALID_ARGUMENTS"),
    ({"order_id": 1001}, "INVALID_ARGUMENTS"),
])
def test_bad_arguments_return_feedback(raw, code):
    assert dispatch("lookup_order", raw)["error_code"] == code


def test_model_self_corrects_after_validation_error():
    model = ScriptedModel([
        [{"type": "tool_use", "name": "lookup_order", "input": {"orderId": "ORD-1001"}}],
        [{"type": "tool_use", "name": "lookup_order", "input": {"order_id": "ORD-1001"}}],
        [{"type": "text", "text": "Found it."}],
    ])
    result = run_agent("ORD-1001 is damaged", model)
    assert result.tool_calls[0][2]["error_code"] == "INVALID_ARGUMENTS"
    assert result.tool_calls[1][2]["status"] == "success"


# Step 5.1: execution ceiling
def test_runaway_loop_is_halted_and_escalated():
    model = ScriptedModel([[{"type": "tool_use", "name": "lookup_order", "input": {"order_id": "ORD-1001"}}]])
    result = run_agent("ORD-1001 is damaged", model)
    assert result.escalated and model.calls == MAX_ITERATIONS == 5
    assert "human" in result.final_answer
