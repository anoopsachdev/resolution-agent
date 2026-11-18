"""Step 3 - Tool registration and safe dispatch (+ Step 5.3 argument validation).

TOOL_REGISTRY is a whitelist. dispatch() is the execution gatekeeper: it rejects
unregistered tools, parses and validates arguments, and always returns a
structured result, so a bad request from the model never crashes the loop.
"""

import json

from . import tools
from .schemas import TOOL_SCHEMAS

TOOL_REGISTRY = {
    "lookup_order": tools.lookup_order,
    "check_inventory": tools.check_inventory,
    "process_refund": tools.process_refund,
    "send_notification": tools.send_notification,
}

_SCHEMAS = {s["name"]: s["input_schema"] for s in TOOL_SCHEMAS}


def _error(code: str, message: str) -> dict:
    return {"status": "error", "error_code": code, "message": message}


def dispatch(tool_name: str, raw_arguments) -> dict:
    # Authorization check: only whitelisted tools may run.
    if tool_name not in TOOL_REGISTRY:
        return _error(
            "UNAUTHORIZED_TOOL",
            f"Tool '{tool_name}' is not permitted. Allowed tools: {', '.join(TOOL_REGISTRY)}.",
        )

    # Safe parsing: accept a dict or a JSON string; catch malformed data.
    args = raw_arguments
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError as exc:
            return _error("MALFORMED_ARGUMENTS", f"Arguments are not valid JSON: {exc.msg}.")
    if not isinstance(args, dict):
        return _error("MALFORMED_ARGUMENTS", "Arguments must be a JSON object.")

    # Validation against the contract: required fields present, known fields, string values.
    schema = _SCHEMAS[tool_name]
    problems = [f"missing required field '{f}'" for f in schema["required"] if f not in args]
    problems += [f"unexpected field '{f}'" for f in args if f not in schema["properties"]]
    problems += [
        f"'{f}' must be a non-empty string"
        for f, v in args.items()
        if f in schema["properties"] and (not isinstance(v, str) or not v.strip())
    ]
    if problems:
        return _error("INVALID_ARGUMENTS", f"Invalid arguments for {tool_name}: {'; '.join(problems)}. Fix and retry.")

    try:
        return TOOL_REGISTRY[tool_name](**args)
    except Exception as exc:  # a tool failure must not crash the agent
        return _error("TOOL_EXECUTION_FAILED", f"{type(exc).__name__}: {exc}")
