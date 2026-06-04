"""Signing and command guardrails for experiment control."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any


SIGNATURE_FIELD = "signature"
FORBIDDEN_EXECUTABLES = {
    "dd",
    "mkfs",
    "poweroff",
    "reboot",
    "rm",
    "shutdown",
}


def canonical_json(record: dict[str, Any]) -> bytes:
    unsigned = {key: value for key, value in record.items() if key != SIGNATURE_FIELD}
    return json.dumps(unsigned, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def sign_record(record: dict[str, Any], secret: str) -> str:
    if not secret:
        raise ValueError("signing secret must not be empty")
    digest = hmac.new(secret.encode("utf-8"), canonical_json(record), hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def attach_signature(record: dict[str, Any], secret: str) -> dict[str, Any]:
    signed = dict(record)
    signed[SIGNATURE_FIELD] = sign_record(signed, secret)
    return signed


def verify_signature(record: dict[str, Any], secret: str) -> bool:
    supplied = record.get(SIGNATURE_FIELD)
    if not isinstance(supplied, str):
        return False
    expected = sign_record(record, secret)
    return hmac.compare_digest(supplied, expected)


def validate_command_vector(command: object) -> list[str]:
    if not isinstance(command, list) or not command:
        raise ValueError("command must be a non-empty JSON array")
    if not all(isinstance(part, str) and part for part in command):
        raise ValueError("command entries must be non-empty strings")
    executable = command[0].strip().lower()
    if executable in FORBIDDEN_EXECUTABLES:
        raise ValueError(f"command executable {command[0]!r} is blocked by safety guardrails")
    return command

