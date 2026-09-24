from __future__ import annotations

import base64
import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass
class Response:
    status: int
    headers: dict[str, str]
    body: bytes

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8")) if self.body else None

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


class HttpClient:
    def __init__(self, base_url: str, timeout: float = 10):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        headers: dict[str, str] | None = None,
        json_body: Any | None = None,
        form: dict[str, str] | None = None,
    ) -> Response:
        supplied = {key: value for key, value in (headers or {}).items()}
        if token:
            supplied["Authorization"] = f"Bearer {token}"
        body: bytes | None = None
        if json_body is not None:
            body = json.dumps(json_body, separators=(",", ":")).encode("utf-8")
            supplied.setdefault("Content-Type", "application/json")
        elif form is not None:
            body = urllib.parse.urlencode(form).encode("ascii")
            supplied.setdefault("Content-Type", "application/x-www-form-urlencoded")
        url = path if path.startswith(("http://", "https://")) else self.base_url + "/" + path.lstrip("/")
        request = urllib.request.Request(url, data=body, headers=supplied, method=method.upper())
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return Response(
                    status=response.status,
                    headers={key.lower(): value for key, value in response.headers.items()},
                    body=response.read(),
                )
        except urllib.error.HTTPError as error:
            return Response(
                status=error.code,
                headers={key.lower(): value for key, value in error.headers.items()},
                body=error.read(),
            )


class CinderRouteApi:
    def __init__(self, base_url: str, token_url: str, auth: dict[str, Any]):
        self.http = HttpClient(base_url)
        self.token_http = HttpClient(token_url.rsplit("/", 1)[0])
        self.token_url = token_url
        self.auth = auth

    def token(self, role: str) -> str:
        client_id = self.auth.get(f"{role}_client_id")
        client_secret = self.auth.get(f"{role}_client_secret")
        if not client_id or not client_secret:
            raise ValueError(f"manifest auth is missing {role} client credentials")
        identifier = str(self.auth.get("resource_server_identifier", "cinderroute"))
        scopes = {
            "read": [f"{identifier}/read"],
            "write": [f"{identifier}/write"],
            "admin": [f"{identifier}/admin"],
        }[role]
        response = self.token_http.request(
            "POST",
            self.token_url,
            form={
                "grant_type": "client_credentials",
                "client_id": str(client_id),
                "client_secret": str(client_secret),
                "scope": " ".join(scopes),
            },
        )
        if response.status != 200:
            raise ValueError(f"Cognito token for {role} returned {response.status}: {response.text[:200]}")
        payload = response.json()
        token = payload.get("access_token") if isinstance(payload, dict) else None
        if not token:
            raise ValueError(f"Cognito token response for {role} has no access_token")
        return str(token)

    def health(self, ready: bool = True) -> Response:
        return self.http.request("GET", "/health/ready" if ready else "/health/live")

    def create_shipment(
        self,
        *,
        token: str | None,
        shipment_id: str,
        owner_id: str,
        reference: str,
        origin: str,
        destination: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> Response:
        return self.http.request(
            "POST",
            "/v1/shipments",
            token=token,
            headers={"Idempotency-Key": idempotency_key, "X-Correlation-ID": correlation_id},
            json_body={
                "shipmentId": shipment_id,
                "ownerId": owner_id,
                "reference": reference,
                "origin": origin,
                "destination": destination,
                "expectedVersion": 0,
            },
        )

    def add_checkpoint(
        self,
        *,
        token: str | None,
        shipment_id: str,
        checkpoint_id: str,
        location: str,
        status: str,
        occurred_at: str,
        expected_version: int,
        idempotency_key: str,
        correlation_id: str,
    ) -> Response:
        return self.http.request(
            "POST",
            f"/v1/shipments/{urllib.parse.quote(shipment_id, safe='')}/checkpoints",
            token=token,
            headers={"Idempotency-Key": idempotency_key, "X-Correlation-ID": correlation_id},
            json_body={
                "checkpointId": checkpoint_id,
                "location": location,
                "status": status,
                "occurredAt": occurred_at,
                "expectedVersion": expected_version,
            },
        )

    def get_shipment(self, shipment_id: str, token: str | None) -> Response:
        return self.http.request("GET", f"/v1/shipments/{urllib.parse.quote(shipment_id, safe='')}", token=token)

    def timeline(self, shipment_id: str, token: str | None) -> Response:
        return self.http.request("GET", f"/v1/shipments/{urllib.parse.quote(shipment_id, safe='')}/timeline", token=token)

    def rebuild(self, shipment_id: str, token: str | None) -> Response:
        return self.http.request(
            "POST",
            f"/v1/admin/projections/{urllib.parse.quote(shipment_id, safe='')}/rebuild",
            token=token,
            headers={"Idempotency-Key": f"rebuild-{shipment_id}"},
            json_body={},
        )


def decode_jwt_payload(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) < 2:
        return {}
    padded = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        value = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def redis_command(host: str, port: int, *parts: str, timeout: float = 5) -> Any:
    encoded = f"*{len(parts)}\r\n".encode()
    for part in parts:
        raw = str(part).encode()
        encoded += f"${len(raw)}\r\n".encode() + raw + b"\r\n"
    with socket.create_connection((host, int(port)), timeout=timeout) as connection:
        connection.sendall(encoded)
        stream = connection.makefile("rb")
        marker = stream.read(1)
        line = stream.readline().rstrip(b"\r\n")
        if marker == b"+":
            return line.decode()
        if marker == b":" :
            return int(line)
        if marker == b"-":
            raise RuntimeError(line.decode(errors="replace"))
        if marker == b"$":
            size = int(line)
            if size < 0:
                return None
            data = stream.read(size)
            stream.read(2)
            return data
        raise RuntimeError(f"unexpected Redis response marker: {marker!r}")


def dynamodb_value(value: Any) -> Any:
    if not isinstance(value, dict) or len(value) != 1:
        return value
    kind, raw = next(iter(value.items()))
    if kind == "S":
        return raw
    if kind == "N":
        return int(raw) if str(raw).lstrip("-").isdigit() else float(raw)
    if kind == "BOOL":
        return bool(raw)
    if kind == "NULL":
        return None
    if kind == "L":
        return [dynamodb_value(item) for item in raw]
    if kind == "M":
        return {key: dynamodb_value(item) for key, item in raw.items()}
    if kind in {"SS", "NS"}:
        return list(raw)
    return raw


def dynamodb_item(item: dict[str, Any]) -> dict[str, Any]:
    return {key: dynamodb_value(value) for key, value in item.items()}
