"""Token handling, event signatures, and log redaction."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.logging_config import redact
from app.security import (
    create_access_token,
    create_service_token,
    decode_token,
    hash_password,
    sign_payload,
    verify_password,
    verify_signature,
)


def test_password_round_trip() -> None:
    hashed = hash_password("correct-horse-battery")
    assert hashed != "correct-horse-battery"
    assert verify_password("correct-horse-battery", hashed)
    assert not verify_password("wrong-password", hashed)


def test_user_token_round_trip() -> None:
    claims = decode_token(create_access_token("user@example.com"))
    assert claims["sub"] == "user@example.com"
    assert claims["typ"] == "user"


def test_service_token_is_typed_and_scoped() -> None:
    claims = decode_token(create_service_token("copy_agent", ["llm", "memory_read"]))
    assert claims["typ"] == "service"
    assert claims["tools"] == ["llm", "memory_read"]


def test_tampered_token_rejected() -> None:
    token = create_access_token("user@example.com")
    with pytest.raises(HTTPException) as exc:
        decode_token(token[:-4] + "aaaa")
    assert exc.value.status_code == 401


def test_signature_round_trip() -> None:
    payload = '{"event":"task_completed","task_id":1024}'
    assert verify_signature(payload, sign_payload(payload))


def test_signature_rejects_tampering_and_absence() -> None:
    payload = '{"event":"task_completed","task_id":1024}'
    signature = sign_payload(payload)
    assert not verify_signature('{"event":"task_completed","task_id":9999}', signature)
    assert not verify_signature(payload, None)
    assert not verify_signature(payload, "hmac-sha256:deadbeef")


@pytest.mark.parametrize(
    "line",
    [
        "calling systeme.io with X-MCP-Key: abc123def456",
        "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig",
        "api_key=sk-proj-abcdef0123456789abcdef",
        "password: hunter2-and-then-some",
    ],
)
def test_redaction_masks_secrets(line: str) -> None:
    cleaned = redact(line)
    assert "REDACTED" in cleaned
    for leaked in ("abc123def456", "eyJhbGciOiJIUzI1NiJ9", "sk-proj-abcdef0123456789abcdef"):
        assert leaked not in cleaned


def test_redaction_leaves_ordinary_lines_alone() -> None:
    line = "task.claimed task_id=1024 agent=copy_agent"
    assert redact(line) == line
