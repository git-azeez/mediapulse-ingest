# VPC Network & Firewall

## Network Topology

- Create one custom-mode VPC (`google_compute_network`) with `auto_create_subnetworks = false`.
- Create an ingress subnet (`google_compute_subnetwork`) and a private subnet (`google_compute_subnetwork`) with `private_ip_google_access = true`.
- Record the exact resource IDs in `manifest.network`:
  - `network.vpc_id`
  - `network.ingress_subnet_id`
  - `network.private_subnet_id`

## Firewall Rules

- Ingress HTTP firewall rule (`google_compute_firewall`) allowing TCP port `80` and `8080` to target tags `["mediapulse-ingress", "mediapulse-api"]`.
- Internal database firewall rule (`google_compute_firewall`) allowing TCP port `5432` only from the ingress and private subnet CIDRs to target tag `["mediapulse-db"]`.
