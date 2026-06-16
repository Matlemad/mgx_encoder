"""Cyanite webhook receiver — Vercel Python serverless function.

Public endpoint (after deploy): POST/GET https://<domain>/api/cyanite/webhook

Responsibilities (minimal, first implementation):
- GET  -> healthcheck JSON.
- POST -> receive a Cyanite webhook event, optionally verify the HMAC-SHA512
          `Signature` header against CYANITE_WEBHOOK_SECRET, log/store the event,
          and respond 200 quickly (Cyanite cancels the request after ~3s).

This does NOT fetch Cyanite analysis results — it only prepares the endpoint
for API-key activation.

Cyanite signature scheme (per Cyanite API docs): HMAC-SHA512 of the raw request
body using the webhook secret, hex-encoded, sent in the `Signature` header.
Test events triggered from the Cyanite web app do NOT include a signature.

Local testing:
    python api/cyanite/webhook.py           # serves on http://localhost:8000
    curl http://localhost:8000/api/cyanite/webhook
    curl -X POST http://localhost:8000/api/cyanite/webhook \
        -H "Content-Type: application/json" \
        -d '{"version":"2","resource":{"type":"LibraryTrack","id":"test"},"event":{"type":"AudioAnalysisV7","status":"finished"}}'
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler

_HEALTH = {
    "ok": True,
    "service": "cyanite-webhook",
    "message": "Webhook endpoint is alive. Use POST for Cyanite events.",
}


# ── pure, testable helpers ───────────────────────────────────────────────────
def verify_signature(secret: str, signature: str, raw_body: bytes) -> bool:
    """Constant-time HMAC-SHA512 verification of the raw body.

    Tolerates an optional algorithm prefix like ``sha512=<hex>``.
    """
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha512).hexdigest()
    sig = signature.strip()
    if "=" in sig and sig.split("=", 1)[0].lower().startswith("sha"):
        sig = sig.split("=", 1)[1].strip()
    return hmac.compare_digest(expected, sig)


def extract_event(payload: dict) -> dict:
    """Pull the fields we care about from a Cyanite webhook payload."""
    resource = payload.get("resource") or {}
    event = payload.get("event") or {}
    return {
        "version": payload.get("version"),
        "resource_type": resource.get("type"),
        "resource_id": resource.get("id"),
        "event_type": event.get("type") or payload.get("type"),
        "event_status": event.get("status"),
        "received_at": datetime.now(timezone.utc).isoformat(),
    }


def store_event(event: dict) -> None:
    """Best-effort append to a local JSONL log. No-op on Vercel (read-only FS)."""
    if os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"):
        return  # production serverless FS is ephemeral/read-only; skip
    try:
        from pathlib import Path

        repo_root = Path(__file__).resolve().parents[2]
        out_dir = repo_root / "outputs"
        out_dir.mkdir(parents=True, exist_ok=True)
        with open(out_dir / "cyanite_webhook_events.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception as exc:  # noqa: BLE001 - logging must never break the response
        print(f"[cyanite-webhook] could not persist event locally: {exc}")


def _log(event: dict, verification: str) -> None:
    print(
        "[cyanite-webhook] event received | "
        f"version={event.get('version')} "
        f"resource.type={event.get('resource_type')} "
        f"resource.id={event.get('resource_id')} "
        f"event.type={event.get('event_type')} "
        f"event.status={event.get('event_status')} "
        f"verification={verification} "
        f"received_at={event.get('received_at')}"
    )


# ── Vercel serverless handler ────────────────────────────────────────────────
class handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler API)
        self._send(200, _HEALTH)

    def do_POST(self) -> None:  # noqa: N802
        try:
            length = int(self.headers.get("Content-Length") or 0)
            raw_body = self.rfile.read(length) if length > 0 else b""

            secret = os.environ.get("CYANITE_WEBHOOK_SECRET", "")
            signature = self.headers.get("Signature") or self.headers.get("signature")

            verification = "skipped"
            if secret:
                if signature:
                    if verify_signature(secret, signature, raw_body):
                        verification = "verified"
                    else:
                        print("[cyanite-webhook] invalid Signature: rejecting (401).")
                        self._send(401, {"ok": False, "error": "invalid_signature"})
                        return
                else:
                    # Cyanite web-app test events do not include a signature.
                    verification = "no_signature_header"
                    print("[cyanite-webhook] secret set but no Signature header (likely a test event); accepting.")
            else:
                print("CYANITE_WEBHOOK_SECRET missing: accepting webhook without signature verification.")

            try:
                payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
                if not isinstance(payload, dict):
                    raise ValueError("payload is not a JSON object")
            except (ValueError, UnicodeDecodeError) as exc:
                print(f"[cyanite-webhook] invalid JSON: {exc}")
                self._send(400, {"ok": False, "error": "invalid_json"})
                return

            event = extract_event(payload)
            _log(event, verification)
            store_event({**event, "verification": verification})

            self._send(200, {"ok": True, "received": True})
        except Exception as exc:  # noqa: BLE001 - never leak a stacktrace as a 200
            print(f"[cyanite-webhook] unexpected error: {exc}")
            self._send(500, {"ok": False, "error": "internal_error"})

    def _method_not_allowed(self) -> None:
        self._send(405, {"ok": False, "error": "method_not_allowed"})

    do_PUT = _method_not_allowed       # noqa: N815
    do_DELETE = _method_not_allowed    # noqa: N815
    do_PATCH = _method_not_allowed     # noqa: N815

    def log_message(self, *args) -> None:  # quieter default access logs
        return


if __name__ == "__main__":
    # Minimal local server for curl testing (not used by Vercel).
    from http.server import ThreadingHTTPServer

    port = int(os.environ.get("PORT", "8000"))
    print(f"Cyanite webhook listening on http://localhost:{port}/api/cyanite/webhook")
    ThreadingHTTPServer(("0.0.0.0", port), handler).serve_forever()
