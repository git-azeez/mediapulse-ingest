# Global External Load Balancer Contract

- Component: Global External HTTP(S) Load Balancer.
- Backend: Serverless Network Endpoint Group (NEG) attached to Cloud Run API service.
- Health Check: HTTP `/health/ready` probe on port 8080.
