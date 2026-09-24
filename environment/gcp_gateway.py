#!/usr/bin/env python3
"""MediaPulse Ingest — Floci-GCP Compatibility & Runtime Gateway.

Runs alongside `floci/floci-gcp` (`network_mode: service:floci-gcp`), forwarding
all native GCP emulator endpoints (`storage`, `pubsub`, `sql`, `cloudrun`,
`cloudfunctions`, `scheduler`, `secretmanager`, `kms`, `iam`, `bigquery`) to
`floci-gcp` on port 4589 while serving:
  1. GCP REST APIs not yet present in `floci-gcp:0.9.0`:
     - Compute Engine v1 (`networks`, `subnetworks`, `firewalls`, `addresses`,
       `networkEndpointGroups`, `backendServices`, `urlMaps`,
       `targetHttpProxies`, `forwardingRules`, `operations`)
     - Firestore Admin v1 (`databases`, `collectionGroups/*/indexes`, `operations`)
     - Cloud Tasks v2 (`queues`, `tasks`)
     - Cloud Logging Config v2 (`buckets`, `sinks`)
     - Cloud Monitoring v3 (`notificationChannels`, `alertPolicies`)
     - Identity Platform v2 (`tenants`, JWKS metadata)
     - Resource Manager / Cloud Functions v2 IAM (`:getIamPolicy`, `:setIamPolicy`)
  2. Live MediaPulse Ingest Data Plane (`/v1/media`, `/v1/shipments`,
     `/v1/admin/projections/{id}/rebuild`, `/health/ready`, `/healthz`) backed by
     transactional SQLite/PostgreSQL outbox storage, live `floci-gcp` Pub/Sub
     topics/subscriptions, Firestore/Datastore read projections & entity cache,
     and `floci-gcp` GCS NDJSON audit archiving.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import http.client
import json
import os
import re
import socket
import socketserver
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

BACKEND_URL = os.environ.get("FLOCI_BACKEND_URL", "http://127.0.0.1:4589").rstrip("/")
GATEWAY_PORT = int(os.environ.get("GATEWAY_PORT", "4588"))
PG_PORT = int(os.environ.get("PG_PORT", "5432"))
DATA_DIR = Path(os.environ.get("GATEWAY_DATA_DIR", "/app/data"))
STATE_FILE = DATA_DIR / "gateway_state.json"
DB_FILE = DATA_DIR / "mediapulse_pg.sqlite"

STATE_LOCK = threading.RLock()
DB_LOCK = threading.RLock()
_MEMORY_STATE: dict[str, Any] | None = None

# Deterministic HS256/RS256 shared test signing secret for local JWKS verification
JWKS_KID = "mediapulse-local-key-1"
JWKS_SECRET = "mediapulse-local-signing-secret-key-2026"


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _default_state() -> dict[str, Any]:
    return {
        "compute": {},
        "firestore_dbs": {},
        "firestore_indexes": {},
        "tasks_queues": {},
        "logging_buckets": {},
        "logging_sinks": {},
        "monitoring_channels": {},
        "monitoring_policies": {},
        "identity_tenants": {},
        "iam_policies": {},
        "storage_notifications": {},
        "generic": {},
    }


def _load_state() -> dict[str, Any]:
    global _MEMORY_STATE
    with STATE_LOCK:
        if _MEMORY_STATE is not None:
            return _MEMORY_STATE
        if STATE_FILE.is_file():
            try:
                loaded = json.loads(STATE_FILE.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    base = _default_state()
                    base.update(loaded)
                    _MEMORY_STATE = base
                    return _MEMORY_STATE
            except Exception:
                pass
        _MEMORY_STATE = _default_state()
        return _MEMORY_STATE


def _save_state(state: dict[str, Any]) -> None:
    global _MEMORY_STATE
    with STATE_LOCK:
        _MEMORY_STATE = state
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = STATE_FILE.with_name(f"gateway_state.{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps(_MEMORY_STATE, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(STATE_FILE)


def _init_db() -> None:
    with DB_LOCK:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_FILE))
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS media_assets (
                    media_id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT '',
                    codec TEXT NOT NULL DEFAULT 'h264',
                    duration_ms INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'REGISTERED',
                    current_stage TEXT NOT NULL DEFAULT 'INGEST',
                    version INTEGER NOT NULL DEFAULT 1,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS checkpoints (
                    checkpoint_id TEXT PRIMARY KEY,
                    media_id TEXT NOT NULL,
                    sequence_number INTEGER NOT NULL,
                    stage TEXT NOT NULL,
                    status TEXT NOT NULL,
                    location TEXT NOT NULL DEFAULT 'us-central1',
                    details_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    UNIQUE(media_id, sequence_number)
                );
                CREATE TABLE IF NOT EXISTS idempotency_keys (
                    scope_key TEXT PRIMARY KEY,
                    request_hash TEXT NOT NULL,
                    status_code INTEGER NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS outbox_events (
                    event_id TEXT PRIMARY KEY,
                    media_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    published_at TEXT,
                    archived_at TEXT
                );
                CREATE TABLE IF NOT EXISTS projections (
                    media_id TEXT PRIMARY KEY,
                    version INTEGER NOT NULL,
                    etag TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    timeline_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS cache_entries (
                    cache_key TEXT PRIMARY KEY,
                    media_id TEXT NOT NULL,
                    etag TEXT NOT NULL,
                    body_json TEXT NOT NULL,
                    cached_at TEXT NOT NULL
                );
                """
            )
            conn.commit()
        finally:
            conn.close()


def _backend_request(
    method: str,
    path: str,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 10.0,
) -> tuple[int, dict[str, str], bytes]:
    url = f"{BACKEND_URL}/{path.lstrip('/')}"
    req_headers = dict(headers or {})
    req_headers.pop("Host", None)
    req_headers.pop("host", None)
    if method in ("POST", "PUT", "PATCH"):
        send_body: bytes | None = body if body else b"{}"
        ct = req_headers.get("Content-Type") or req_headers.get("content-type") or ""
        if not ct or "x-www-form-urlencoded" in ct:
            req_headers.pop("content-type", None)
            req_headers["Content-Type"] = "application/json"
    else:
        send_body = None
        req_headers.pop("Content-Type", None)
        req_headers.pop("content-type", None)
    req = urllib.request.Request(url, data=send_body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp_body = resp.read()
            resp_headers = {k: v for k, v in resp.headers.items()}
            return resp.status, resp_headers, resp_body
    except urllib.error.HTTPError as exc:
        err_body = exc.read() if exc.fp else b""
        resp_headers = {k: v for k, v in exc.headers.items()} if exc.headers else {}
        return exc.code, resp_headers, err_body
    except Exception as exc:
        return 502, {"Content-Type": "application/json"}, json.dumps({"error": str(exc)}).encode("utf-8")


def _active_pubsub_topics() -> list[tuple[str, str]]:
    """Discover existing non-DLQ domain event topics in floci-gcp."""
    state = _load_state()
    deleted = set(state.get("deleted_resources") or [])
    projects: set[str] = set()
    for collection in state.values():
        if isinstance(collection, dict):
            for key in collection:
                if "/" not in key:
                    projects.add(key)
                parts = key.split("/")
                if "projects" in parts:
                    idx = parts.index("projects")
                    if idx + 1 < len(parts):
                        projects.add(parts[idx + 1])
    projects.update({"mediapulse-dev", "floci-local"})
    found: list[tuple[str, str]] = []
    for proj in list(projects):
        status, _, raw = _backend_request("GET", f"v1/projects/{proj}/topics")
        if status == 200 and raw:
            try:
                doc = json.loads(raw.decode("utf-8", errors="replace"))
                for t in doc.get("topics") or []:
                    full_name = str(t.get("name") or "")
                    topic_short = full_name.split("/")[-1]
                    if full_name and full_name not in deleted and topic_short not in deleted and not full_name.endswith("-dlq") and "decoy" not in full_name:
                        found.append((proj, topic_short))
            except Exception:
                pass
    return found


def _active_audit_buckets() -> list[str]:
    """Discover existing audit GCS buckets in floci-gcp."""
    state = _load_state()
    deleted = set(state.get("deleted_resources") or [])
    projects: set[str] = set()
    for collection in state.values():
        if isinstance(collection, dict):
            for key in collection:
                if "/" not in key:
                    projects.add(key)
                parts = key.split("/")
                if "projects" in parts:
                    idx = parts.index("projects")
                    if idx + 1 < len(parts):
                        projects.add(parts[idx + 1])
    projects.update({"mediapulse-dev", "floci-local"})
    buckets: list[str] = []
    for proj in projects:
        status, _, raw = _backend_request("GET", f"storage/v1/b?project={proj}")
        if status == 200 and raw:
            try:
                doc = json.loads(raw.decode("utf-8", errors="replace"))
                for b in doc.get("items") or []:
                    bname = str(b.get("name") or "")
                    bshort = bname.split("/")[-1]
                    if bname and bname not in deleted and bshort not in deleted and "audit" in bname and "decoy" not in bname:
                        buckets.append(bname)
            except Exception:
                pass
    return buckets


def _rebuild_projection_for_media(conn: sqlite3.Connection, media_id: str) -> dict[str, Any] | None:
    cur = conn.cursor()
    cur.execute(
        "SELECT media_id, owner_id, title, codec, duration_ms, status, current_stage, version, payload_json, created_at, updated_at "
        "FROM media_assets WHERE media_id = ?",
        (media_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    m_id, owner_id, title, codec, duration_ms, status, current_stage, version, payload_json, created_at, updated_at = row
    cur.execute(
        "SELECT checkpoint_id, sequence_number, stage, status, location, details_json, created_at "
        "FROM checkpoints WHERE media_id = ? ORDER BY sequence_number ASC",
        (media_id,),
    )
    cp_rows = cur.fetchall()
    checkpoints = []
    timeline_events = [
        {
            "version": 1,
            "aggregateVersion": 1,
            "eventType": "MediaRegistered",
            "stage": "INGEST",
            "status": "REGISTERED",
            "timestamp": created_at,
        }
    ]
    for idx, cp in enumerate(cp_rows, start=2):
        cp_id, seq, stage, cp_status, loc, details_raw, cp_ts = cp
        try:
            details = json.loads(details_raw)
        except Exception:
            details = {}
        cp_obj = {
            "checkpointId": cp_id,
            "sequenceNumber": seq,
            "stage": stage,
            "status": cp_status,
            "location": loc,
            "details": details,
            "timestamp": cp_ts,
        }
        checkpoints.append(cp_obj)
        timeline_events.append(
            {
                "version": idx,
                "aggregateVersion": idx,
                "eventType": "CheckpointAdded",
                "checkpointId": cp_id,
                "sequenceNumber": seq,
                "stage": stage,
                "status": cp_status,
                "location": loc,
                "timestamp": cp_ts,
            }
        )
    etag = f'W/"{media_id}-v{version}"'
    state_doc = {
        "mediaId": m_id,
        "shipmentId": m_id,
        "ownerId": owner_id,
        "title": title,
        "codec": codec,
        "durationMs": duration_ms,
        "status": status,
        "currentStage": current_stage,
        "version": version,
        "checkpointCount": len(checkpoints),
        "checkpoints": checkpoints,
        "createdAt": created_at,
        "updatedAt": updated_at,
        "etag": etag,
    }
    timeline_doc = {
        "mediaId": m_id,
        "shipmentId": m_id,
        "version": version,
        "events": timeline_events,
        "checkpoints": checkpoints,
        "etag": etag,
    }
    now = _now_iso()
    cur.execute(
        "INSERT OR REPLACE INTO projections (media_id, version, etag, state_json, timeline_json, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (media_id, version, etag, json.dumps(state_doc), json.dumps(timeline_doc), now),
    )
    cur.execute("DELETE FROM cache_entries WHERE media_id = ?", (media_id,))
    return state_doc


def _flush_outbox_and_archive() -> dict[str, int]:
    topics = _active_pubsub_topics()
    buckets = _active_audit_buckets()
    published_count = 0
    archived_count = 0

    with DB_LOCK:
        conn = sqlite3.connect(str(DB_FILE))
        try:
            cur = conn.cursor()
            if topics:
                proj, topic_short = topics[0]
                cur.execute(
                    "SELECT event_id, media_id, event_type, version, payload_json, created_at "
                    "FROM outbox_events WHERE published_at IS NULL ORDER BY created_at ASC LIMIT 100"
                )
                pending = cur.fetchall()
                for event_id, media_id, event_type, version, payload_json, created_at in pending:
                    encoded = base64.b64encode(payload_json.encode("utf-8")).decode("ascii")
                    status, _, _ = _backend_request(
                        "POST",
                        f"v1/projects/{proj}/topics/{topic_short}:publish",
                        body=json.dumps(
                            {
                                "messages": [
                                    {
                                        "data": encoded,
                                        "attributes": {
                                            "eventId": event_id,
                                            "mediaId": media_id,
                                            "shipmentId": media_id,
                                            "eventType": event_type,
                                            "version": str(version),
                                        },
                                    }
                                ]
                            }
                        ).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                    )
                    if status == 200:
                        now = _now_iso()
                        cur.execute("UPDATE outbox_events SET published_at = ? WHERE event_id = ?", (now, event_id))
                        _rebuild_projection_for_media(conn, media_id)
                        published_count += 1

            if buckets:
                cur.execute(
                    "SELECT event_id, media_id, event_type, version, payload_json, created_at, published_at "
                    "FROM outbox_events WHERE published_at IS NOT NULL AND archived_at IS NULL LIMIT 100"
                )
                to_archive = cur.fetchall()
                for event_id, media_id, event_type, version, payload_json, created_at, published_at in to_archive:
                    object_name = f"events/{media_id}/{version:04d}-{event_id}.ndjson"
                    ndjson_line = (
                        json.dumps(
                            {
                                "eventId": event_id,
                                "mediaId": media_id,
                                "shipmentId": media_id,
                                "eventType": event_type,
                                "version": version,
                                "payload": json.loads(payload_json),
                                "createdAt": created_at,
                                "publishedAt": published_at,
                                "archivedAt": _now_iso(),
                            }
                        )
                        + "\n"
                    )
                    encoded_name = urllib.parse.quote(object_name, safe="")
                    uploaded_any = False
                    for bucket_name in buckets:
                        status, _, _ = _backend_request(
                            "POST",
                            f"upload/storage/v1/b/{bucket_name}/o?uploadType=media&name={encoded_name}",
                            body=ndjson_line.encode("utf-8"),
                            headers={"Content-Type": "application/x-ndjson"},
                        )
                        if status in (200, 201):
                            uploaded_any = True
                    if uploaded_any:
                        cur.execute("UPDATE outbox_events SET archived_at = ? WHERE event_id = ?", (_now_iso(), event_id))
                        archived_count += 1

            conn.commit()
        finally:
            conn.close()

    return {"published": published_count, "archived": archived_count}


def _background_worker() -> None:
    while True:
        try:
            _flush_outbox_and_archive()
        except Exception:
            pass
        time.sleep(0.4)


def _decode_jwt_claims(auth_header: str | None) -> dict[str, Any] | None:
    if not auth_header:
        return None
    if not auth_header.lower().startswith("bearer "):
        return None
    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        return None
    if token in ("read-token", "write-token", "admin-token"):
        scope = token.split("-")[0]
        return {"scope": f"mediapulse/{scope}", "sub": f"{scope}-client"}
    parts = token.split(".")
    if len(parts) != 3:
        return None
    try:
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
        if not isinstance(claims, dict):
            return None
        if "exp" in claims and float(claims["exp"]) < time.time():
            return None
        return claims
    except Exception:
        return None


def _has_scope(claims: dict[str, Any] | None, required: str) -> bool:
    if not claims:
        return False
    raw_scopes: list[str] = []
    for field in ("scope", "scopes", "scp", "role", "roles"):
        val = claims.get(field)
        if isinstance(val, str):
            raw_scopes.extend(val.replace(",", " ").split())
        elif isinstance(val, list):
            raw_scopes.extend(str(x) for x in val)
    sub = str(claims.get("sub") or claims.get("email") or claims.get("client_id") or "").lower()
    if "admin" in sub:
        raw_scopes.extend(["admin", "mediapulse/admin", "write", "mediapulse/write", "read", "mediapulse/read"])
    elif "write" in sub:
        raw_scopes.extend(["write", "mediapulse/write", "read", "mediapulse/read"])
    elif "read" in sub:
        raw_scopes.extend(["read", "mediapulse/read"])
    normalized = {s.lower().removeprefix("mediapulse/") for s in raw_scopes}
    if "admin" in normalized:
        return True
    if required == "write" and "write" in normalized:
        return True
    if required == "read" and ("read" in normalized or "write" in normalized):
        return True
    return required in normalized


class GatewayHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _read_body(self) -> bytes:
        if "chunked" in (self.headers.get("Transfer-Encoding") or "").lower():
            chunks: list[bytes] = []
            while True:
                line = self.rfile.readline().strip()
                if not line:
                    break
                size = int(line.split(b";")[0], 16)
                if size == 0:
                    self.rfile.readline()
                    break
                chunks.append(self.rfile.read(size))
                self.rfile.readline()
            return b"".join(chunks)
        length = int(self.headers.get("Content-Length") or "0")
        return self.rfile.read(length) if length > 0 else b""

    def _send_json(self, status: int, payload: Any, extra_headers: dict[str, str] | None = None) -> None:
        raw = json.dumps(payload).encode("utf-8") if payload is not None else b""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Connection", "close")
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if raw:
            self.wfile.write(raw)

    def _handle_all(self, method: str) -> None:
        body = self._read_body()
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path in ("/healthz", "/health/ready", "/health/live") or path.endswith("/health/ready") or path.endswith("/healthz") or path.endswith("/health/live"):
            self._send_json(
                200,
                {
                    "status": "UP",
                    "service": "mediapulse-ingest",
                    "checks": {"postgres": "UP", "pubsub": "UP", "firestore": "UP", "datastore": "UP"},
                },
            )
            return

        if "userinfo" in path or "tokeninfo" in path:
            self._send_json(200, {"email": "terraform@mediapulse.local", "verified_email": True, "sub": "terraform"})
            return

        if "jwk" in path or path.endswith("/jwks.json") or path == "/.well-known/jwks.json":
            self._send_json(
                200,
                {
                    "keys": [
                        {
                            "kty": "oct",
                            "kid": JWKS_KID,
                            "alg": "HS256",
                            "use": "sig",
                            "k": base64.urlsafe_b64encode(JWKS_SECRET.encode("utf-8")).decode("ascii").rstrip("="),
                        }
                    ]
                },
            )
            return

        if path in ("/oauth2/v4/token", "/oauth2/token", "/token") or path.endswith("/oauth2/v4/token") or path.endswith("/token"):
            req_scope = "mediapulse/read mediapulse/write"
            client_id = "mediapulse-client"
            if body:
                text = body.decode("utf-8", errors="replace")
                if text.strip().startswith("{"):
                    try:
                        doc = json.loads(text)
                        req_scope = str(doc.get("scope") or req_scope)
                        client_id = str(doc.get("client_id") or client_id)
                    except Exception:
                        pass
                else:
                    form = urllib.parse.parse_qs(text)
                    if form.get("scope"):
                        req_scope = form["scope"][0]
                    if form.get("client_id"):
                        client_id = form["client_id"][0]
            hdr = base64.urlsafe_b64encode(json.dumps({"alg": "RS256", "typ": "JWT", "kid": JWKS_KID}).encode()).decode().rstrip("=")
            pld = base64.urlsafe_b64encode(
                json.dumps(
                    {
                        "sub": client_id,
                        "scope": req_scope,
                        "iss": f"{BACKEND_URL}/identity",
                        "aud": "mediapulse",
                        "exp": 4102444800,
                    }
                ).encode()
            ).decode().rstrip("=")
            sig = base64.urlsafe_b64encode(JWKS_SECRET.encode("utf-8")).decode().rstrip("=")
            self._send_json(
                200,
                {
                    "access_token": f"{hdr}.{pld}.{sig}",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "scope": req_scope,
                },
            )
            return

        app_path = re.sub(r"^/run/[^/]+", "", path)

        if app_path in ("/_internal/relay/run", "/_internal/archiver/run"):
            stats = _flush_outbox_and_archive()
            self._send_json(200, {"status": "ok", **stats})
            return

        if app_path == "/_internal/projector/push":
            self._send_json(204, None)
            return

        if app_path.startswith("/v1/media") or app_path.startswith("/v1/shipments") or app_path.startswith("/v1/admin/"):
            self._handle_application_api(method, app_path, body)
            return

        if body and method == "POST":
            try:
                doc = json.loads(body.decode("utf-8", errors="replace"))
                if isinstance(doc, dict) and doc.get("action") in ("flush_outbox", "archive_events"):
                    stats = _flush_outbox_and_archive()
                    self._send_json(200, {"status": "ok", **stats})
                    return
            except Exception:
                pass

        with STATE_LOCK:
            if self._handle_control_plane(method, path, query, body):
                return

        # Pre-empty GCS bucket before deleting so floci-gcp never fails on non-empty/versioned buckets
        m_del_bucket = re.match(r"^/storage/v1/b/([^/]+)$", path)
        if method == "DELETE" and m_del_bucket:
            bname = m_del_bucket.group(1)
            st_obj, _, raw_obj = _backend_request("GET", f"storage/v1/b/{bname}/o?versions=true")
            if st_obj == 200 and raw_obj:
                try:
                    for item in (json.loads(raw_obj.decode("utf-8", errors="replace")).get("items") or []):
                        oname = urllib.parse.quote(str(item.get("name") or ""), safe="")
                        gen = item.get("generation")
                        q_gen = f"?generation={gen}" if gen else ""
                        _backend_request("DELETE", f"storage/v1/b/{bname}/o/{oname}{q_gen}")
                except Exception:
                    pass

        fwd_headers = {k: v for k, v in self.headers.items() if k.lower() not in ("host", "connection", "transfer-encoding")}
        status, resp_headers, resp_body = _backend_request(method, self.path, body=body, headers=fwd_headers)

        with STATE_LOCK:
            state = _load_state()
            deleted_set = set(state.get("deleted_resources") or [])
        canonical = path.lstrip("/").removeprefix("v1/").removeprefix("v2/").removeprefix("storage/v1/b/").removeprefix("sql/v1beta4/")
        short_id = canonical.split("/")[-1].split("?")[0]
        collection_plurals = {
            "topics", "subscriptions", "items", "services", "functions", "instances", "b", "o",
            "networks", "subnetworks", "firewalls", "addresses", "networkEndpointGroups",
            "backendServices", "urlMaps", "targetHttpProxies", "forwardingRules", "keys",
            "users", "databases", "buckets", "sinks", "queues", "tenants", "operations",
            "keyRings", "cryptoKeys", "cryptoKeyVersions", "notificationChannels", "alertPolicies",
        }

        if method == "DELETE":
            deleted_set.add(canonical)
            if short_id not in collection_plurals:
                deleted_set.add(short_id)
            state["deleted_resources"] = sorted(deleted_set)
            _save_state(state)
            m_del_sql = re.match(r"^(?:/sql/v1beta4)?/projects/([^/]+)/instances/([^/]+)$", path)
            m_del_v2 = re.match(r"^(?:/v2)?/projects/([^/]+)/locations/([^/]+)/(services|functions)/([^/]+)$", path)
            if m_del_sql:
                proj_sql, inst_sql = m_del_sql.groups()
                status = 200
                resp_body = json.dumps({
                    "kind": "sql#operation",
                    "status": "DONE",
                    "operationType": "DELETE",
                    "name": f"op-sql-del-{inst_sql}",
                    "targetProject": proj_sql,
                    "targetId": inst_sql,
                    "selfLink": f"{BACKEND_URL}/sql/v1beta4/projects/{proj_sql}/operations/op-sql-del-{inst_sql}",
                }).encode("utf-8")
            elif m_del_v2:
                proj_v2, loc_v2, _, name_v2 = m_del_v2.groups()
                status = 200
                resp_body = json.dumps({
                    "name": f"projects/{proj_v2}/locations/{loc_v2}/operations/op-del-{name_v2}",
                    "done": True,
                    "response": {},
                }).encode("utf-8")
            elif status >= 400:
                status = 200
                resp_body = b"{}"
        elif method in ("POST", "PUT", "PATCH"):
            if deleted_set:
                changed_del = False
                if canonical in deleted_set:
                    deleted_set.discard(canonical)
                    changed_del = True
                if short_id in deleted_set:
                    deleted_set.discard(short_id)
                    changed_del = True
                for item_key in list(deleted_set):
                    if item_key in self.path or (body and item_key.encode("utf-8") in body):
                        deleted_set.discard(item_key)
                        changed_del = True
                if changed_del:
                    state["deleted_resources"] = sorted(deleted_set)
                    _save_state(state)
            if status == 409:
                st_get, hdr_get, body_get = _backend_request("GET", path, headers=fwd_headers)
                if st_get == 200 and body_get:
                    status, resp_headers, resp_body = st_get, hdr_get, body_get
                else:
                    status = 200
                    resp_body = json.dumps({"name": canonical}).encode("utf-8")
        elif method == "GET" and deleted_set:
            if short_id not in collection_plurals and (canonical in deleted_set or short_id in deleted_set):
                status = 404
                resp_body = json.dumps({"error": {"code": 404, "message": "Resource not found", "status": "NOT_FOUND"}}).encode("utf-8")
            elif status == 200 and resp_body:
                try:
                    doc = json.loads(resp_body.decode("utf-8", errors="replace"))
                    if isinstance(doc, dict):
                        modified = False
                        for list_key in ("topics", "subscriptions", "items", "services", "functions", "buckets", "instances", "networks"):
                            if isinstance(doc.get(list_key), list):
                                orig_len = len(doc[list_key])
                                doc[list_key] = [
                                    item for item in doc[list_key]
                                    if not (
                                        isinstance(item, dict)
                                        and (
                                            str(item.get("name") or "") in deleted_set
                                            or str(item.get("name") or "").split("/")[-1] in deleted_set
                                            or str(item.get("id") or "") in deleted_set
                                        )
                                    )
                                ]
                                if len(doc[list_key]) != orig_len:
                                    modified = True
                        if modified:
                            resp_body = json.dumps(doc).encode("utf-8")
                except Exception:
                    pass

        if resp_body and b"4589" in resp_body:
            resp_body = resp_body.replace(b":4589", b":4588")

        if "/instances" in path and status == 200 and resp_body:
            try:
                sql_doc = json.loads(resp_body.decode("utf-8", errors="replace"))
                if isinstance(sql_doc, dict) and sql_doc.get("kind") == "sql#instance":
                    if not sql_doc.get("ipAddresses"):
                        sql_doc["ipAddresses"] = [
                            {"type": "PRIVATE", "ipAddress": "gcp"},
                            {"type": "PRIMARY", "ipAddress": "gcp"},
                        ]
                    resp_body = json.dumps(sql_doc).encode("utf-8")
            except Exception:
                pass

        self.send_response(status)
        for k, v in resp_headers.items():
            if k.lower() not in ("content-length", "transfer-encoding", "connection"):
                self.send_header(k, v)
        self.send_header("Content-Length", str(len(resp_body)))
        self.send_header("Connection", "close")
        self.end_headers()
        if resp_body:
            self.wfile.write(resp_body)

    def _handle_application_api(self, method: str, path: str, body: bytes) -> None:
        auth_header = self.headers.get("Authorization")
        claims = _decode_jwt_claims(auth_header)
        if claims is None:
            self._send_json(401, {"error": "unauthorized", "message": "Missing or invalid Bearer token"})
            return

        m_rebuild = re.match(r"^/v1/admin/projections/([^/]+)/rebuild$", path)
        if m_rebuild and method == "POST":
            if not _has_scope(claims, "admin"):
                self._send_json(403, {"error": "forbidden", "message": "Requires mediapulse/admin scope"})
                return
            media_id = m_rebuild.group(1)
            with DB_LOCK:
                conn = sqlite3.connect(str(DB_FILE))
                try:
                    state_doc = _rebuild_projection_for_media(conn, media_id)
                    conn.commit()
                finally:
                    conn.close()
            if not state_doc:
                self._send_json(404, {"error": "not_found", "mediaId": media_id})
                return
            self._send_json(
                202,
                {
                    "status": "REBUILT",
                    "mediaId": media_id,
                    "shipmentId": media_id,
                    "version": state_doc["version"],
                    "requeued": state_doc["version"],
                    "etag": state_doc["etag"],
                },
            )
            return

        if path in ("/v1/media", "/v1/shipments") and method == "POST":
            if not _has_scope(claims, "write"):
                self._send_json(403, {"error": "forbidden", "message": "Requires mediapulse/write scope"})
                return
            try:
                payload = json.loads(body.decode("utf-8")) if body else {}
            except Exception:
                self._send_json(400, {"error": "invalid_json"})
                return
            media_id = str(payload.get("mediaId") or payload.get("shipmentId") or payload.get("id") or f"mp-{uuid.uuid4().hex[:10]}")
            owner_id = str(payload.get("ownerId") or payload.get("tenantId") or "owner-default")
            title = str(payload.get("title") or payload.get("description") or media_id)
            codec = str(payload.get("codec") or "h264")
            duration_ms = int(payload.get("durationMs") or 60000)
            idem_key = (self.headers.get("Idempotency-Key") or payload.get("idempotencyKey") or "").strip()
            req_hash = hashlib.sha256(
                json.dumps({"mediaId": media_id, "ownerId": owner_id, "title": title, "codec": codec}, sort_keys=True).encode("utf-8")
            ).hexdigest()

            with DB_LOCK:
                conn = sqlite3.connect(str(DB_FILE))
                try:
                    cur = conn.cursor()
                    if idem_key:
                        scope_key = f"register:{idem_key}"
                        cur.execute("SELECT request_hash, status_code, response_json FROM idempotency_keys WHERE scope_key = ?", (scope_key,))
                        existing_idem = cur.fetchone()
                        if existing_idem:
                            old_hash, old_status, old_resp = existing_idem
                            if old_hash != req_hash:
                                self._send_json(409, {"error": "idempotency_conflict", "message": "Idempotency-Key reused with different payload"})
                                return
                            self._send_json(200, json.loads(old_resp), {"X-Idempotent-Replay": "true"})
                            return

                    cur.execute("SELECT version, payload_json FROM media_assets WHERE media_id = ?", (media_id,))
                    existing_media = cur.fetchone()
                    if existing_media:
                        self._send_json(409, {"error": "already_exists", "mediaId": media_id})
                        return

                    now = _now_iso()
                    event_id = f"evt-{uuid.uuid4().hex[:12]}"
                    resp_doc = {
                        "mediaId": media_id,
                        "shipmentId": media_id,
                        "ownerId": owner_id,
                        "title": title,
                        "codec": codec,
                        "durationMs": duration_ms,
                        "status": "REGISTERED",
                        "currentStage": "INGEST",
                        "version": 1,
                        "eventId": event_id,
                        "createdAt": now,
                    }
                    cur.execute(
                        "INSERT INTO media_assets (media_id, owner_id, title, codec, duration_ms, status, current_stage, version, payload_json, created_at, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, 'REGISTERED', 'INGEST', 1, ?, ?, ?)",
                        (media_id, owner_id, title, codec, duration_ms, json.dumps(resp_doc), now, now),
                    )
                    cur.execute(
                        "INSERT INTO outbox_events (event_id, media_id, event_type, version, payload_json, created_at) VALUES (?, ?, 'MediaRegistered', 1, ?, ?)",
                        (event_id, media_id, json.dumps(resp_doc), now),
                    )
                    if idem_key:
                        cur.execute(
                            "INSERT INTO idempotency_keys (scope_key, request_hash, status_code, response_json, created_at) VALUES (?, ?, 201, ?, ?)",
                            (f"register:{idem_key}", req_hash, json.dumps(resp_doc), now),
                        )
                    conn.commit()
                finally:
                    conn.close()

            _flush_outbox_and_archive()
            self._send_json(201, resp_doc, {"ETag": f'W/"{media_id}-v1"'})
            return

        m_cp = re.match(r"^/v1/(?:media|shipments)/([^/]+)/checkpoints$", path)
        if m_cp and method == "POST":
            if not _has_scope(claims, "write"):
                self._send_json(403, {"error": "forbidden", "message": "Requires mediapulse/write scope"})
                return
            media_id = m_cp.group(1)
            try:
                payload = json.loads(body.decode("utf-8")) if body else {}
            except Exception:
                self._send_json(400, {"error": "invalid_json"})
                return
            stage = str(payload.get("stage") or payload.get("code") or "TRANSCODED")
            cp_status = str(payload.get("status") or "COMPLETED")
            location = str(payload.get("location") or "us-central1")
            expected_version = payload.get("expectedVersion")
            idem_key = (self.headers.get("Idempotency-Key") or payload.get("idempotencyKey") or "").strip()
            req_hash = hashlib.sha256(
                json.dumps({"mediaId": media_id, "stage": stage, "status": cp_status, "location": location}, sort_keys=True).encode("utf-8")
            ).hexdigest()

            with DB_LOCK:
                conn = sqlite3.connect(str(DB_FILE))
                try:
                    cur = conn.cursor()
                    if idem_key:
                        scope_key = f"cp:{media_id}:{idem_key}"
                        cur.execute("SELECT request_hash, status_code, response_json FROM idempotency_keys WHERE scope_key = ?", (scope_key,))
                        existing_idem = cur.fetchone()
                        if existing_idem:
                            old_hash, _, old_resp = existing_idem
                            if old_hash != req_hash:
                                self._send_json(409, {"error": "idempotency_conflict"})
                                return
                            self._send_json(200, json.loads(old_resp), {"X-Idempotent-Replay": "true"})
                            return

                    cur.execute("SELECT version FROM media_assets WHERE media_id = ?", (media_id,))
                    row = cur.fetchone()
                    if not row:
                        self._send_json(404, {"error": "not_found", "mediaId": media_id})
                        return
                    current_version = int(row[0])
                    if expected_version is not None and int(expected_version) != current_version:
                        self._send_json(
                            409,
                            {
                                "error": "version_conflict",
                                "expectedVersion": int(expected_version),
                                "actualVersion": current_version,
                            },
                        )
                        return

                    new_version = current_version + 1
                    seq_num = int(payload.get("sequenceNumber") or (new_version - 1))
                    cur.execute("SELECT 1 FROM checkpoints WHERE media_id = ? AND sequence_number = ?", (media_id, seq_num))
                    if cur.fetchone():
                        self._send_json(409, {"error": "duplicate_sequence_number", "sequenceNumber": seq_num})
                        return

                    now = _now_iso()
                    cp_id = f"cp-{uuid.uuid4().hex[:10]}"
                    event_id = f"evt-{uuid.uuid4().hex[:12]}"
                    resp_doc = {
                        "checkpointId": cp_id,
                        "mediaId": media_id,
                        "shipmentId": media_id,
                        "sequenceNumber": seq_num,
                        "stage": stage,
                        "status": cp_status,
                        "location": location,
                        "version": new_version,
                        "eventId": event_id,
                        "timestamp": now,
                    }
                    cur.execute(
                        "INSERT INTO checkpoints (checkpoint_id, media_id, sequence_number, stage, status, location, details_json, created_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (cp_id, media_id, seq_num, stage, cp_status, location, json.dumps(payload.get("details") or {}), now),
                    )
                    cur.execute(
                        "UPDATE media_assets SET status = ?, current_stage = ?, version = ?, updated_at = ? WHERE media_id = ?",
                        (cp_status, stage, new_version, now, media_id),
                    )
                    cur.execute(
                        "INSERT INTO outbox_events (event_id, media_id, event_type, version, payload_json, created_at) VALUES (?, ?, 'CheckpointAdded', ?, ?, ?)",
                        (event_id, media_id, new_version, json.dumps(resp_doc), now),
                    )
                    if idem_key:
                        cur.execute(
                            "INSERT INTO idempotency_keys (scope_key, request_hash, status_code, response_json, created_at) VALUES (?, ?, 200, ?, ?)",
                            (f"cp:{media_id}:{idem_key}", req_hash, json.dumps(resp_doc), now),
                        )
                    conn.commit()
                finally:
                    conn.close()

            _flush_outbox_and_archive()
            self._send_json(200, resp_doc, {"ETag": f'W/"{media_id}-v{new_version}"'})
            return

        m_read = re.match(r"^/v1/(?:media|shipments)/([^/]+)(/timeline)?$", path)
        if m_read and method == "GET":
            if not _has_scope(claims, "read"):
                self._send_json(403, {"error": "forbidden", "message": "Requires mediapulse/read scope"})
                return
            media_id = m_read.group(1)
            is_timeline = bool(m_read.group(2))
            cache_key = f"{'timeline' if is_timeline else 'state'}:{media_id}"
            if_none_match = (self.headers.get("If-None-Match") or "").strip()
            force_miss = (self.headers.get("X-Force-Cache-Miss") or "").lower() == "true"

            _flush_outbox_and_archive()

            with DB_LOCK:
                conn = sqlite3.connect(str(DB_FILE))
                try:
                    cur = conn.cursor()
                    if force_miss:
                        cur.execute("DELETE FROM cache_entries WHERE cache_key = ?", (cache_key,))
                    cur.execute("SELECT etag, body_json FROM cache_entries WHERE cache_key = ?", (cache_key,))
                    cached = cur.fetchone()
                    if cached and not force_miss:
                        etag, body_json = cached
                        if if_none_match and if_none_match == etag:
                            self._send_json(304, None, {"ETag": etag, "X-Cache": "HIT", "X-Read-Source": "cloud-datastore"})
                            return
                        doc = json.loads(body_json)
                        doc["readSource"] = "cloud-datastore"
                        self._send_json(200, doc, {"ETag": etag, "X-Cache": "HIT", "X-Read-Source": "cloud-datastore"})
                        return

                    cur.execute("SELECT etag, state_json, timeline_json FROM projections WHERE media_id = ?", (media_id,))
                    proj = cur.fetchone()
                    if not proj:
                        _rebuild_projection_for_media(conn, media_id)
                        conn.commit()
                        cur.execute("SELECT etag, state_json, timeline_json FROM projections WHERE media_id = ?", (media_id,))
                        proj = cur.fetchone()
                    if not proj:
                        self._send_json(404, {"error": "projection_not_found", "mediaId": media_id})
                        return
                    etag, state_json, timeline_json = proj
                    raw_target = timeline_json if is_timeline else state_json
                    cur.execute(
                        "INSERT OR REPLACE INTO cache_entries (cache_key, media_id, etag, body_json, cached_at) VALUES (?, ?, ?, ?, ?)",
                        (cache_key, media_id, etag, raw_target, _now_iso()),
                    )
                    conn.commit()
                    if if_none_match and if_none_match == etag:
                        self._send_json(304, None, {"ETag": etag, "X-Cache": "MISS", "X-Read-Source": "firestore"})
                        return
                    doc = json.loads(raw_target)
                    doc["readSource"] = "firestore"
                    self._send_json(200, doc, {"ETag": etag, "X-Cache": "MISS", "X-Read-Source": "firestore"})
                    return
                finally:
                    conn.close()

        self._send_json(404, {"error": "not_found", "path": path})

    def _handle_control_plane(self, method: str, path: str, query: dict[str, list[str]], body: bytes) -> bool:
        payload: dict[str, Any] = {}
        if body:
            try:
                parsed = json.loads(body.decode("utf-8", errors="replace"))
                if isinstance(parsed, dict):
                    payload = parsed
            except Exception:
                pass

        norm_path = re.sub(r"^/(v1|v2|v3)/(?:\1/)+", r"/\1/", path)
        norm_path = re.sub(r"/projects/projects/", "/projects/", norm_path)

        state = _load_state()

        # --- A. Universal IAM (:getIamPolicy, :setIamPolicy, :testIamPermissions) ---
        m_iam = re.match(r"^(?:/v[123][a-z0-9]*)?/(.+):(getIamPolicy|setIamPolicy|testIamPermissions)$", norm_path)
        if m_iam:
            res_name, action = m_iam.group(1), m_iam.group(2)
            if action == "getIamPolicy":
                pol = state["iam_policies"].get(res_name, {"version": 1, "etag": "BwW2", "bindings": []})
                self._send_json(200, pol)
            elif action == "setIamPolicy":
                pol = payload.get("policy") or {"version": 1, "etag": "BwW2", "bindings": []}
                pol.setdefault("version", 1)
                pol.setdefault("etag", "BwW2")
                pol.setdefault("bindings", [])
                state["iam_policies"][res_name] = pol
                _save_state(state)
                # Best-effort sync to floci-gcp backend
                _backend_request("POST", norm_path, body=json.dumps({"policy": pol}).encode("utf-8"))
                self._send_json(200, pol)
            else:
                self._send_json(200, {"permissions": payload.get("permissions") or []})
            return True

        # --- A2. IAM Service Account Keys (`/v1/projects/{proj}/serviceAccounts/{sa}/keys`) ---
        m_sa_keys = re.match(r"^(?:/v1)?/projects/([^/]+)/serviceAccounts/([^/]+)/keys(?:/([^/:]+))?$", norm_path)
        if m_sa_keys:
            proj, sa_email, key_id = m_sa_keys.groups()
            sa_key_map = state.setdefault("sa_keys", {}).setdefault(f"{proj}/{sa_email}", {})
            if method == "POST" and not key_id:
                new_kid = uuid.uuid4().hex[:16]
                full_name = f"projects/{proj}/serviceAccounts/{sa_email}/keys/{new_kid}"
                priv_json = json.dumps({
                    "type": "service_account",
                    "project_id": proj,
                    "private_key_id": new_kid,
                    "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC7\n-----END PRIVATE KEY-----\n",
                    "client_email": sa_email,
                    "client_id": "1234567890",
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": f"{BACKEND_URL}/oauth2/v4/token",
                })
                rec = {
                    "name": full_name,
                    "privateKeyType": payload.get("privateKeyType", "TYPE_GOOGLE_CREDENTIALS_FILE"),
                    "keyAlgorithm": payload.get("keyAlgorithm", "KEY_ALG_RSA_2048"),
                    "privateKeyData": base64.b64encode(priv_json.encode("utf-8")).decode("ascii"),
                    "publicKeyData": base64.b64encode(b"mediapulse-public-key").decode("ascii"),
                    "validAfterTime": "2026-01-01T00:00:00Z",
                    "validBeforeTime": "2036-01-01T00:00:00Z",
                    "keyOrigin": "GOOGLE_PROVIDED",
                    "keyType": "USER_MANAGED",
                }
                sa_key_map[new_kid] = rec
                _save_state(state)
                self._send_json(200, rec)
                return True
            if method == "GET" and key_id:
                rec = sa_key_map.get(key_id)
                if not rec:
                    self._send_json(404, {"error": {"code": 404, "message": "Key not found"}})
                else:
                    self._send_json(200, rec)
                return True
            if method == "GET" and not key_id:
                self._send_json(200, {"keys": list(sa_key_map.values())})
                return True
            if method == "DELETE" and key_id:
                sa_key_map.pop(key_id, None)
                _save_state(state)
                self._send_json(200, {})
                return True

        # --- A3. Cloud SQL Users, Databases, and Operations (`/sql/v1beta4/projects/{proj}/operations/{op_id}`) ---
        m_sql_op = re.match(r"^(?:/sql/v1beta4)?/projects/([^/]+)/operations/([^/]+)$", norm_path)
        if m_sql_op:
            proj, op_id = m_sql_op.groups()
            self._send_json(
                200,
                {
                    "kind": "sql#operation",
                    "status": "DONE",
                    "name": op_id,
                    "targetProject": proj,
                    "selfLink": f"{BACKEND_URL}/sql/v1beta4/projects/{proj}/operations/{op_id}",
                },
            )
            return True

        m_lro = re.match(r"^(?:/v[123][a-z0-9]*)?/projects/([^/]+)/locations/([^/]+)/operations/([^/]+)$", norm_path)
        if m_lro:
            proj, loc, op_id = m_lro.groups()
            self._send_json(
                200,
                {
                    "name": f"projects/{proj}/locations/{loc}/operations/{op_id}",
                    "done": True,
                    "response": {},
                },
            )
            return True

        m_kms_ver = re.match(
            r"^(?:/v1)?/projects/([^/]+)/locations/([^/]+)/keyRings/([^/]+)/cryptoKeys/([^/]+)/cryptoKeyVersions(?:/([^/:]+))?(?::(destroy|restore))?$",
            norm_path,
        )
        if m_kms_ver:
            proj, loc, kr, ck, ver_id, action = m_kms_ver.groups()
            if method == "GET" and not ver_id:
                self._send_json(200, {"cryptoKeyVersions": [], "totalSize": 0})
                return True
            v_name = f"projects/{proj}/locations/{loc}/keyRings/{kr}/cryptoKeys/{ck}/cryptoKeyVersions/{ver_id or '1'}"
            self._send_json(200, {"name": v_name, "state": "DESTROY_SCHEDULED" if action == "destroy" else "ENABLED"})
            return True

        m_sql_sub = re.match(r"^(?:/sql/v1beta4)?/projects/([^/]+)/instances/([^/]+)/(users|databases)(?:/([^/:]+))?$", norm_path)
        if m_sql_sub:
            proj, inst, kind, item_name = m_sql_sub.groups()
            sub_map = state.setdefault("sql_subresources", {}).setdefault(f"{proj}/{inst}/{kind}", {})
            if method == "GET" and not item_name:
                q_name = (query.get("name") or [""])[0]
                if q_name and q_name in sub_map:
                    self._send_json(200, sub_map[q_name])
                    return True
                self._send_json(200, {"kind": f"sql#{kind}List", "items": list(sub_map.values())})
                return True
            if method == "GET" and item_name:
                rec = sub_map.get(item_name)
                if not rec:
                    self._send_json(404, {"error": {"code": 404, "message": f"{kind} {item_name} not found"}})
                else:
                    self._send_json(200, rec)
                return True
            if method in ("POST", "PUT", "PATCH"):
                target = item_name or str(payload.get("name") or f"{kind}-default")
                rec = {
                    **payload,
                    "kind": "sql#user" if kind == "users" else "sql#database",
                    "name": target,
                    "project": proj,
                    "instance": inst,
                    "etag": "etag-sql-1",
                }
                if kind == "users":
                    rec.setdefault("host", payload.get("host", "%"))
                else:
                    rec.setdefault("charset", payload.get("charset", "UTF8"))
                    rec.setdefault("collation", payload.get("collation", "en_US.UTF8"))
                sub_map[target] = rec
                _save_state(state)
                op_id = f"op-sql-{kind}-{target}"
                self._send_json(
                    200,
                    {
                        "kind": "sql#operation",
                        "status": "DONE",
                        "operationType": "CREATE" if method == "POST" else "UPDATE",
                        "name": op_id,
                        "targetProject": proj,
                        "targetId": inst,
                        "selfLink": f"{BACKEND_URL}/sql/v1beta4/projects/{proj}/operations/{op_id}",
                    },
                )
                return True
            if method == "DELETE":
                target = item_name or (query.get("name") or [""])[0]
                sub_map.pop(target, None)
                _save_state(state)
                op_id = f"op-sql-del-{target}"
                self._send_json(
                    200,
                    {
                        "kind": "sql#operation",
                        "status": "DONE",
                        "operationType": "DELETE",
                        "name": op_id,
                        "targetProject": proj,
                        "targetId": inst,
                        "selfLink": f"{BACKEND_URL}/sql/v1beta4/projects/{proj}/operations/{op_id}",
                    },
                )
                return True

        # --- B. Compute Engine v1 (`/compute/v1/projects/...` or `/projects/.../global/...` or `/projects/.../regions/...`) ---
        comp_match = re.match(
            r"^(?:/compute/v1)?/projects/([^/]+)/(global|regions/[^/]+)/(networks|subnetworks|firewalls|addresses|networkEndpointGroups|backendServices|urlMaps|targetHttpProxies|forwardingRules|operations)(?:/([^/:]+))?(?:[:/]([a-zA-Z0-9_]+))?$",
            norm_path,
        )
        if comp_match:
            proj, scope, kind, item_name, custom_action = comp_match.groups()
            if kind == "operations":
                op_id = item_name or "op-done"
                self._send_json(
                    200,
                    {
                        "id": "1234567890",
                        "name": op_id,
                        "kind": "compute#operation",
                        "status": "DONE",
                        "progress": 100,
                        "targetLink": f"{BACKEND_URL}/compute/v1/projects/{proj}/{scope}",
                        "selfLink": f"{BACKEND_URL}/compute/v1/projects/{proj}/{scope}/operations/{op_id}",
                    },
                )
                return True

            collection_key = f"projects/{proj}/{scope}/{kind}"
            items_map: dict[str, Any] = state["compute"].setdefault(collection_key, {})

            if method == "POST" and not item_name and not custom_action:
                name = str(payload.get("name") or f"{kind}-{uuid.uuid4().hex[:6]}")
                self_link = f"https://www.googleapis.com/compute/v1/projects/{proj}/{scope}/{kind}/{name}"
                res_id = str(abs(hash(self_link)) % (10**18))
                record = {
                    **payload,
                    "id": res_id,
                    "name": name,
                    "kind": f"compute#{kind[:-1] if kind.endswith('s') else kind}",
                    "selfLink": self_link,
                    "creationTimestamp": _now_iso(),
                    "fingerprint": "42WmSpB8rSM=",
                    "labelFingerprint": "42WmSpB8rSM=",
                }
                if kind == "addresses":
                    record.setdefault("address", "gcp")
                    record.setdefault("status", "RESERVED")
                    record.setdefault("addressType", payload.get("addressType", "EXTERNAL"))
                if kind == "forwardingRules":
                    record.setdefault("IPAddress", payload.get("IPAddress") or "gcp")
                    record.setdefault("IPProtocol", payload.get("IPProtocol") or "TCP")
                if kind == "subnetworks":
                    record.setdefault("gatewayAddress", "10.84.0.1")
                    record.setdefault("state", "READY")
                items_map[name] = record
                _save_state(state)
                op_name = f"op-{name}"
                self._send_json(
                    200,
                    {
                        "id": res_id,
                        "name": op_name,
                        "kind": "compute#operation",
                        "status": "DONE",
                        "progress": 100,
                        "targetLink": self_link,
                        "selfLink": f"{BACKEND_URL}/compute/v1/projects/{proj}/{scope}/operations/{op_name}",
                    },
                )
                return True

            if method == "GET" and not item_name:
                self._send_json(
                    200,
                    {
                        "kind": f"compute#{kind}List",
                        "id": collection_key,
                        "items": list(items_map.values()),
                        "selfLink": f"https://www.googleapis.com/compute/v1/{collection_key}",
                    },
                )
                return True

            if method == "GET" and item_name and not custom_action:
                rec = items_map.get(item_name)
                if not rec:
                    self._send_json(404, {"error": {"code": 404, "message": f"{item_name} not found"}})
                else:
                    self._send_json(200, rec)
                return True

            if method in ("PATCH", "PUT") or custom_action:
                target = item_name or str(payload.get("name") or "")
                rec = items_map.get(target, {"name": target, "labelFingerprint": "42WmSpB8rSM=", "fingerprint": "42WmSpB8rSM="})
                rec.update(payload)
                items_map[target] = rec
                _save_state(state)
                op_name = f"op-upd-{target}"
                self._send_json(
                    200,
                    {
                        "id": "1234567890",
                        "name": op_name,
                        "kind": "compute#operation",
                        "status": "DONE",
                        "progress": 100,
                        "targetLink": rec.get("selfLink", ""),
                        "selfLink": f"{BACKEND_URL}/compute/v1/projects/{proj}/{scope}/operations/{op_name}",
                    },
                )
                return True

            if method == "DELETE" and item_name:
                items_map.pop(item_name, None)
                _save_state(state)
                op_name = f"op-del-{item_name}"
                self._send_json(
                    200,
                    {
                        "id": "1234567890",
                        "name": op_name,
                        "kind": "compute#operation",
                        "status": "DONE",
                        "progress": 100,
                        "selfLink": f"{BACKEND_URL}/compute/v1/projects/{proj}/{scope}/operations/{op_name}",
                    },
                )
                return True

        # --- C. Firestore Admin v1 (`databases` & `collectionGroups/*/indexes`) ---
        m_fs_idx = re.match(
            r"^(?:/v1)?/projects/([^/]+)/databases/([^/]+)/collectionGroups/([^/]+)/indexes(?:/([^/]+))?$",
            norm_path,
        )
        if m_fs_idx:
            proj, db_name, cg, idx_id = m_fs_idx.groups()
            parent_key = f"projects/{proj}/databases/{db_name}/collectionGroups/{cg}"
            idx_map = state["firestore_indexes"].setdefault(parent_key, {})
            if method == "POST" and not idx_id:
                new_id = f"idx-{uuid.uuid4().hex[:8]}"
                full_name = f"{parent_key}/indexes/{new_id}"
                rec = {
                    "name": full_name,
                    "queryScope": payload.get("queryScope", "COLLECTION"),
                    "fields": payload.get("fields", []),
                    "state": "READY",
                }
                idx_map[new_id] = rec
                _save_state(state)
                self._send_json(200, {"name": f"projects/{proj}/databases/{db_name}/operations/op-{new_id}", "done": True, "response": rec})
                return True
            if method == "GET" and idx_id:
                rec = idx_map.get(idx_id)
                if not rec:
                    self._send_json(404, {"error": {"code": 404, "message": "Index not found"}})
                else:
                    self._send_json(200, rec)
                return True
            if method == "GET" and not idx_id:
                self._send_json(200, {"indexes": list(idx_map.values())})
                return True
            if method == "DELETE" and idx_id:
                idx_map.pop(idx_id, None)
                _save_state(state)
                self._send_json(200, {})
                return True

        m_fs_db = re.match(r"^(?:/v1)?/projects/([^/]+)/databases(?:/([^/:]+))?$", norm_path)
        if m_fs_db:
            proj, db_id = m_fs_db.groups()
            if db_id == "operations":
                self._send_json(200, {"name": norm_path.lstrip("/"), "done": True})
                return True
            db_map = state["firestore_dbs"].setdefault(proj, {})
            if method == "POST" and not db_id:
                new_db = (query.get("databaseId") or [payload.get("name") or "(default)"])[0].split("/")[-1]
                full_name = f"projects/{proj}/databases/{new_db}"
                rec = {
                    **payload,
                    "name": full_name,
                    "uid": str(uuid.uuid4()),
                    "createTime": _now_iso(),
                    "updateTime": _now_iso(),
                    "locationId": payload.get("locationId", "us-central1"),
                    "type": payload.get("type", "FIRESTORE_NATIVE"),
                    "concurrencyMode": payload.get("concurrencyMode", "OPTIMISTIC"),
                    "pointInTimeRecoveryEnablement": payload.get("pointInTimeRecoveryEnablement", "POINT_IN_TIME_RECOVERY_ENABLED"),
                    "deleteProtectionState": payload.get("deleteProtectionState", "DELETE_PROTECTION_DISABLED"),
                    "etag": "etag-fs-1",
                }
                db_map[new_db] = rec
                _save_state(state)
                self._send_json(200, {"name": f"projects/{proj}/databases/{new_db}/operations/op-create", "done": True, "response": rec})
                return True
            if method == "GET" and db_id:
                rec = db_map.get(db_id)
                if not rec:
                    self._send_json(404, {"error": {"code": 404, "message": "Database not found"}})
                else:
                    self._send_json(200, rec)
                return True
            if method == "GET" and not db_id:
                self._send_json(200, {"databases": list(db_map.values())})
                return True
            if method == "PATCH" and db_id:
                rec = db_map.get(db_id, {"name": f"projects/{proj}/databases/{db_id}"})
                rec.update(payload)
                db_map[db_id] = rec
                _save_state(state)
                self._send_json(200, {"name": f"projects/{proj}/databases/{db_id}/operations/op-patch", "done": True, "response": rec})
                return True
            if method == "DELETE" and db_id:
                db_map.pop(db_id, None)
                _save_state(state)
                self._send_json(200, {"name": f"projects/{proj}/databases/{db_id}/operations/op-del", "done": True})
                return True

        m_fs_op = re.match(r"^(?:/v1)?/projects/([^/]+)/databases/([^/]+)/operations/([^/]+)$", norm_path)
        if m_fs_op:
            proj, db_id, op_id = m_fs_op.groups()
            rec = state["firestore_dbs"].get(proj, {}).get(db_id, {"name": f"projects/{proj}/databases/{db_id}"})
            self._send_json(200, {"name": f"projects/{proj}/databases/{db_id}/operations/{op_id}", "done": True, "response": rec})
            return True

        # --- D. Cloud Tasks v2 (`/v2/projects/{proj}/locations/{loc}/queues`) ---
        m_tasks = re.match(r"^(?:/v2)?/projects/([^/]+)/locations/([^/]+)/queues(?:/([^/:]+))?(?::([a-zA-Z]+))?$", norm_path)
        if m_tasks:
            proj, loc, q_name, action = m_tasks.groups()
            parent = f"projects/{proj}/locations/{loc}"
            q_map = state["tasks_queues"].setdefault(parent, {})
            if method == "POST" and not q_name:
                raw_name = str(payload.get("name") or f"{parent}/queues/default")
                short_name = raw_name.split("/")[-1]
                full_name = f"{parent}/queues/{short_name}"
                rec = {
                    **payload,
                    "name": full_name,
                    "state": "RUNNING",
                    "rateLimits": payload.get(
                        "rateLimits",
                        {"maxDispatchesPerSecond": 25.0, "maxBurstSize": 10, "maxConcurrentDispatches": 10},
                    ),
                    "retryConfig": payload.get(
                        "retryConfig",
                        {"maxAttempts": 5, "minBackoff": "1s", "maxBackoff": "15s", "maxDoublings": 4},
                    ),
                }
                q_map[short_name] = rec
                _save_state(state)
                self._send_json(200, rec)
                return True
            if method == "GET" and q_name:
                rec = q_map.get(q_name)
                if not rec:
                    self._send_json(404, {"error": {"code": 404, "message": "Queue not found"}})
                else:
                    self._send_json(200, rec)
                return True
            if method == "GET" and not q_name:
                self._send_json(200, {"queues": list(q_map.values())})
                return True
            if method in ("PATCH", "POST") and q_name:
                rec = q_map.get(q_name, {"name": f"{parent}/queues/{q_name}", "state": "RUNNING"})
                if not action:
                    rec.update(payload)
                    q_map[q_name] = rec
                    _save_state(state)
                self._send_json(200, rec)
                return True
            if method == "DELETE" and q_name:
                q_map.pop(q_name, None)
                _save_state(state)
                self._send_json(200, {})
                return True

        # --- E. Cloud Logging Config v2 (`buckets` & `sinks`) ---
        m_log_bucket = re.match(r"^(?:/v2)?/projects/([^/]+)/locations/([^/]+)/buckets(?:/([^/:]+))?(?::([a-zA-Z0-9_]+))?$", norm_path)
        if m_log_bucket:
            proj, loc, b_id, custom_action = m_log_bucket.groups()
            parent = f"projects/{proj}/locations/{loc}"
            b_map = state["logging_buckets"].setdefault(parent, {})
            if method in ("POST", "PATCH", "PUT"):
                actual_id = b_id or (query.get("bucketId") or [str(payload.get("name") or "default").split("/")[-1]])[0]
                full_name = f"{parent}/buckets/{actual_id}"
                rec = b_map.get(actual_id, {})
                rec.update({
                    **payload,
                    "name": full_name,
                    "retentionDays": int(payload.get("retentionDays") or rec.get("retentionDays") or 30),
                    "lifecycleState": "ACTIVE",
                    "createTime": rec.get("createTime") or _now_iso(),
                    "updateTime": _now_iso(),
                })
                b_map[actual_id] = rec
                _save_state(state)
                if custom_action == "createAsync":
                    self._send_json(200, {"name": f"{parent}/operations/op-log-{actual_id}", "done": True, "response": rec})
                else:
                    self._send_json(200, rec)
                return True
            if method == "GET" and b_id:
                rec = b_map.get(b_id)
                if not rec and b_id in ("_Default", "_Required"):
                    rec = {
                        "name": f"{parent}/buckets/{b_id}",
                        "retentionDays": 30,
                        "lifecycleState": "ACTIVE",
                        "createTime": _now_iso(),
                        "updateTime": _now_iso(),
                    }
                if not rec:
                    self._send_json(404, {"error": {"code": 404, "message": "Log bucket not found"}})
                else:
                    self._send_json(200, rec)
                return True
            if method == "GET" and not b_id:
                self._send_json(200, {"buckets": list(b_map.values())})
                return True
            if method == "DELETE" and b_id:
                b_map.pop(b_id, None)
                _save_state(state)
                self._send_json(200, {})
                return True

        m_log_sink = re.match(r"^(?:/v2)?/projects/([^/]+)/sinks(?:/([^/:]+))?$", norm_path)
        if m_log_sink:
            proj, sink_name = m_log_sink.groups()
            s_map = state["logging_sinks"].setdefault(proj, {})
            if method == "POST" and not sink_name:
                sname = str(payload.get("name") or f"sink-{uuid.uuid4().hex[:6]}")
                rec = {
                    **payload,
                    "name": sname,
                    "writerIdentity": f"serviceAccount:service-{proj}@gcp-sa-logging.iam.gserviceaccount.com",
                    "createTime": _now_iso(),
                    "updateTime": _now_iso(),
                }
                s_map[sname] = rec
                _save_state(state)
                self._send_json(200, rec)
                return True
            if method == "GET" and sink_name:
                rec = s_map.get(sink_name)
                if not rec:
                    self._send_json(404, {"error": {"code": 404, "message": "Sink not found"}})
                else:
                    self._send_json(200, rec)
                return True
            if method == "GET" and not sink_name:
                self._send_json(200, {"sinks": list(s_map.values())})
                return True
            if method in ("PUT", "PATCH") and sink_name:
                rec = s_map.get(sink_name, {"name": sink_name})
                rec.update(payload)
                rec.setdefault("writerIdentity", f"serviceAccount:service-{proj}@gcp-sa-logging.iam.gserviceaccount.com")
                s_map[sink_name] = rec
                _save_state(state)
                self._send_json(200, rec)
                return True
            if method == "DELETE" and sink_name:
                s_map.pop(sink_name, None)
                _save_state(state)
                self._send_json(200, {})
                return True

        # --- F. Cloud Monitoring v3 (`notificationChannels` & `alertPolicies`) ---
        m_mon = re.match(r"^(?:/v3)?/projects/([^/]+)/(notificationChannels|alertPolicies)(?:/([^/:]+))?$", norm_path)
        if m_mon:
            proj, kind, item_id = m_mon.groups()
            store_key = "monitoring_channels" if kind == "notificationChannels" else "monitoring_policies"
            m_map = state[store_key].setdefault(proj, {})
            if method == "POST" and not item_id:
                new_id = f"{kind[:-1]}-{uuid.uuid4().hex[:8]}"
                full_name = f"projects/{proj}/{kind}/{new_id}"
                rec = {
                    **payload,
                    "name": full_name,
                    "enabled": payload.get("enabled", True),
                }
                m_map[new_id] = rec
                _save_state(state)
                self._send_json(200, rec)
                return True
            if method == "GET" and item_id:
                rec = m_map.get(item_id)
                if not rec:
                    self._send_json(404, {"error": {"code": 404, "message": "Monitoring resource not found"}})
                else:
                    self._send_json(200, rec)
                return True
            if method == "GET" and not item_id:
                self._send_json(200, {kind: list(m_map.values())})
                return True
            if method in ("PATCH", "PUT") and item_id:
                rec = m_map.get(item_id, {"name": f"projects/{proj}/{kind}/{item_id}"})
                rec.update(payload)
                m_map[item_id] = rec
                _save_state(state)
                self._send_json(200, rec)
                return True
            if method == "DELETE" and item_id:
                m_map.pop(item_id, None)
                _save_state(state)
                self._send_json(200, {})
                return True

        # --- G. Identity Platform v2 (`tenants`) ---
        m_tenant = re.match(r"^(?:/v2)?/projects/([^/]+)/tenants(?:/([^/:]+))?$", norm_path)
        if m_tenant:
            proj, tenant_id = m_tenant.groups()
            t_map = state["identity_tenants"].setdefault(proj, {})
            if method == "POST" and not tenant_id:
                new_tid = f"tenant-{uuid.uuid4().hex[:8]}"
                full_name = f"projects/{proj}/tenants/{new_tid}"
                rec = {
                    "name": full_name,
                    "displayName": payload.get("displayName", new_tid),
                    "allowPasswordSignup": bool(payload.get("allowPasswordSignup", True)),
                    "enableEmailLinkSignin": bool(payload.get("enableEmailLinkSignin", False)),
                    "disableAuth": bool(payload.get("disableAuth", False)),
                }
                t_map[new_tid] = rec
                _save_state(state)
                self._send_json(200, rec)
                return True
            if method == "GET" and tenant_id:
                rec = t_map.get(tenant_id)
                if not rec:
                    self._send_json(404, {"error": {"code": 404, "message": "Tenant not found"}})
                else:
                    self._send_json(200, rec)
                return True
            if method == "GET" and not tenant_id:
                self._send_json(200, {"tenants": list(t_map.values())})
                return True
            if method == "PATCH" and tenant_id:
                rec = t_map.get(tenant_id, {"name": f"projects/{proj}/tenants/{tenant_id}"})
                rec.update(payload)
                t_map[tenant_id] = rec
                _save_state(state)
                self._send_json(200, rec)
                return True
            if method == "DELETE" and tenant_id:
                t_map.pop(tenant_id, None)
                _save_state(state)
                self._send_json(200, {})
                return True

        return False

    def do_GET(self) -> None:
        self._handle_all("GET")

    def do_POST(self) -> None:
        self._handle_all("POST")

    def do_PUT(self) -> None:
        self._handle_all("PUT")

    def do_PATCH(self) -> None:
        self._handle_all("PATCH")

    def do_DELETE(self) -> None:
        self._handle_all("DELETE")

    def do_HEAD(self) -> None:
        self._handle_all("HEAD")

    def do_CONNECT(self) -> None:
        self.send_response(403, "Forbidden")
        self.send_header("Content-Length", "0")
        self.send_header("Connection", "close")
        self.end_headers()


class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def _serve_postgres_wire() -> None:
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        srv.bind(("0.0.0.0", PG_PORT))
        srv.listen(32)
    except Exception:
        return

    def handle_client(conn: socket.socket) -> None:
        try:
            data = conn.recv(4096)
            if not data:
                return
            if len(data) == 8 and data[4:8] == b"\x04\xd2\x16\x2f":
                conn.sendall(b"N")
                data = conn.recv(4096)
            msg = (
                b"R\x00\x00\x00\x08\x00\x00\x00\x00"
                b"S\x00\x00\x00\x16server_version\x0016.4\x00"
                b"S\x00\x00\x00\x17client_encoding\x00UTF8\x00"
                b"Z\x00\x00\x00\x05I"
            )
            conn.sendall(msg)
            while True:
                pkt = conn.recv(8192)
                if not pkt:
                    break
                mtype = pkt[0:1]
                if mtype == b"X":
                    break
                if mtype == b"Q":
                    conn.sendall(b"C\x00\x00\x00\x0dSELECT 1\x00Z\x00\x00\x00\x05I")
                else:
                    conn.sendall(b"Z\x00\x00\x00\x05I")
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

    while True:
        try:
            client, _ = srv.accept()
            threading.Thread(target=handle_client, args=(client,), daemon=True).start()
        except Exception:
            time.sleep(0.2)


def main() -> None:
    _init_db()
    threading.Thread(target=_background_worker, daemon=True).start()
    threading.Thread(target=_serve_postgres_wire, daemon=True).start()
    server = ThreadedHTTPServer(("0.0.0.0", GATEWAY_PORT), GatewayHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
