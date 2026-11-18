"""Step 4 - The agentic state loop (ReAct cycle) + Step 5 guardrails."""

import json
import logging
from dataclasses import dataclass, field

from .dispatcher import dispatch
from .schemas import TOOL_SCHEMAS

log = logging.getLogger("resolution_agent")

MAX_ITERATIONS = 5  # Step 5.1 execution ceiling

SYSTEM_PROMPT = """You are an automated order-resolution specialist for an online store.
When a customer reports a problem with an item, resolve it end to end using your tools:
1. Look up the order with lookup_order.
2. Check replacement stock with check_inventory using the order's item_id.
3. Decide:
   - If the order is exchange_eligible AND units_available > 0: the item is exchangeable.
     Confirm the exchange (do NOT refund).
   - Otherwise (out of stock OR not eligible): call process_refund.
4. Call send_notification once with the customer's email, confirming the exchange or the
   refund (include the refund reference).
5. Finish with a short, polite summary for the customer: what happened, the reference,
   and what to expect next.
Rules: decide only from tool results, never invent order data. If a tool returns an error,
explain it plainly; for an unknown order ID, ask the customer to verify it. If you cannot
resolve the case, say it is being passed to a human agent."""

ESCALATION_MESSAGE = (
    "I wasn't able to fully resolve this automatically, so I've passed your case to a human "
    "support specialist. They'll contact you shortly. Reference: {ticket}."
)


@dataclass
class AgentResult:
    final_answer: str
    iterations: int
    escalated: bool = False
    tool_calls: list = field(default_factory=list)  # [(name, input, result), ...]
    messages: list = field(default_factory=list)


def run_agent(user_message: str, model, max_iterations: int = MAX_ITERATIONS, verbose: bool = False) -> AgentResult:
    # 1. State initialisation: ordered history of user input, model turns and tool results.
    messages = [{"role": "user", "content": user_message}]
    tool_log = []

    for iteration in range(1, max_iterations + 1):
        # 2. Invoke the model with full history + tool schemas.
        blocks = model.generate(SYSTEM_PROMPT, messages, TOOL_SCHEMAS)
        messages.append({"role": "assistant", "content": blocks})

        # 3. Tool-call detection.
        tool_uses = [b for b in blocks if b["type"] == "tool_use"]
        text = " ".join(b["text"] for b in blocks if b["type"] == "text").strip()
        if verbose and text:
            print(f"  [{iteration}] model: {text}")

        if not tool_uses:
            return AgentResult(text, iteration, False, tool_log, messages)

        # 4. Execute each requested tool via the safe dispatcher and feed results back,
        #    linked to the originating tool_use id.
        results = []
        for call in tool_uses:
            outcome = dispatch(call["name"], call.get("input"))
            tool_log.append((call["name"], call.get("input"), outcome))
            if verbose:
                print(f"  [{iteration}] tool  : {call['name']}({json.dumps(call.get('input'))})")
                print(f"           -> {json.dumps(outcome)}")
            results.append({
                "type": "tool_result",
                "tool_use_id": call["id"],
                "content": json.dumps(outcome),
                "is_error": outcome.get("status") == "error",
            })
        messages.append({"role": "user", "content": results})
        # 5. Loop continues: the model observes the results and picks the next action.

    # Execution ceiling reached: halt safely and flag for a human.
    ticket = f"ESC-{abs(hash(user_message)) % 100000:05d}"
    log.warning("Max iterations (%d) reached; escalating as %s", max_iterations, ticket)
    return AgentResult(ESCALATION_MESSAGE.format(ticket=ticket), max_iterations, True, tool_log, messages)
