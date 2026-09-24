use serde_json::Value;

pub(super) fn has_scope(claims: &Value, expected: &str) -> bool {
    claims
        .get("scope")
        .and_then(Value::as_str)
        .is_some_and(|scopes| {
            scopes
                .split_ascii_whitespace()
                .any(|scope| scope == expected)
        })
}

pub(super) fn audience_matches(claims: &Value, expected: &str) -> bool {
    if claims.get("client_id").and_then(Value::as_str) == Some(expected) {
        return true;
    }

    match claims.get("aud") {
        Some(Value::String(value)) => value == expected,
        Some(Value::Array(values)) => values.iter().any(|value| value.as_str() == Some(expected)),
        _ => false,
    }
}
