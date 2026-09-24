group "default" {
  targets = ["api", "projector", "relay", "archiver"]
}

target "common" {
  context    = "."
  dockerfile = "Dockerfile.runtime"
}

target "api" {
  inherits = ["common"]
  target   = "api-runtime"
  tags     = ["mediapulse/api:1.0.0", "cinderrouter/api:1.0.0"]
}

target "projector" {
  inherits = ["common"]
  target   = "projector-runtime"
  tags     = ["mediapulse/projector:1.0.0", "mediapulse/processor:1.0.0", "cinderrouter/projector:1.0.0"]
}

target "relay" {
  inherits = ["common"]
  target   = "relay-runtime"
  tags     = ["mediapulse/relay:1.0.0", "mediapulse/outbox-relay:1.0.0", "cinderrouter/relay:1.0.0"]
}

target "archiver" {
  inherits = ["common"]
  target   = "archiver-runtime"
  tags     = ["mediapulse/archiver:1.0.0", "mediapulse/audit-archiver:1.0.0", "cinderrouter/archiver:1.0.0"]
}
