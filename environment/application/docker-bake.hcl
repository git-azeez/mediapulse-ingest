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
  tags     = ["cinderrouter/api:1.0.0"]
}

target "projector" {
  inherits = ["common"]
  target   = "projector-runtime"
  tags     = ["cinderrouter/projector:1.0.0"]
}

target "relay" {
  inherits = ["common"]
  target   = "relay-runtime"
  tags     = ["cinderrouter/relay:1.0.0"]
}

target "archiver" {
  inherits = ["common"]
  target   = "archiver-runtime"
  tags     = ["cinderrouter/archiver:1.0.0"]
}
