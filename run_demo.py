"""Run the four acceptance scenarios and print the full reasoning trace.

    python run_demo.py            # offline PolicyModel (no API key needed)
    python run_demo.py --claude   # real Claude model (needs ANTHROPIC_API_KEY, pip install anthropic)
"""

import sys

from resolution_agent import database as db
from resolution_agent.agent import run_agent
from resolution_agent.models import ClaudeModel, PolicyModel

SCENARIOS = [
    ("Exchange: damaged item, replacement in stock",
     "Hi, my headphones from order ORD-1001 arrived with a cracked headband. Can you help?"),
    ("Refund: damaged item, replacement out of stock",
     "The kettle I got in order ORD-1002 has a broken glass jug. Please sort this out."),
    ("Refund: order outside the exchange window",
     "My smartwatch from ORD-1003 stopped charging and the strap is torn."),
    ("Resilience: invalid order ID",
     "My order ORD-9999 arrived damaged, what can you do?"),
]


def main():
    model = ClaudeModel() if "--claude" in sys.argv else PolicyModel()
    print(f"Model back-end: {type(model).__name__}\n")
    for title, message in SCENARIOS:
        db.reset()
        print("=" * 78)
        print(f"SCENARIO: {title}")
        print(f"CUSTOMER: {message}\n")
        result = run_agent(message, model, verbose=True)
        print(f"\nAGENT REPLY ({result.iterations} iterations, escalated={result.escalated}):")
        print(f"  {result.final_answer}")
        if db.OUTBOX:
            print(f"\nEMAIL SENT to {db.OUTBOX[-1]['to']}: {db.OUTBOX[-1]['body']}")
        print()


if __name__ == "__main__":
    main()
