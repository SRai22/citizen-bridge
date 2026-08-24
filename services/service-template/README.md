# Python service template

Copy this directory for a new service, replace `service-template` in
`pyproject.toml`, and register generated gRPC handlers in `app/grpc/server.py`.
The template exposes `GET /health` and starts HTTP and gRPC in one process.
