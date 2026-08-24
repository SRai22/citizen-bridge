# Shared contracts

This directory is the source of truth for interfaces shared by Citizen Bridge
services:

- `proto/` contains versioned gRPC APIs.
- `events/` contains JSON Schemas for Kafka event payloads.
- `constants/` contains dependency-free Python constants.
- `lib/` contains small cross-service runtime helpers.

## Proto evolution policy

All proto changes require review by the owners of affected producers and
consumers. Packages carry a major version such as `citizen_bridge.auth.v1`.

Adding a field with a new field number, adding a message, or adding an RPC is
backward-compatible. Removing or renaming a field or RPC, reusing a field
number, or changing a field's type is breaking. Breaking changes require a new
major package and coordinated updates to every consumer in the same release
train. Removed field numbers and names must be marked `reserved`.

Generated code is not committed. Each service generates bindings from these
files during its build.
