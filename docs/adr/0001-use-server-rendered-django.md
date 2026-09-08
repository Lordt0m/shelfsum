# 0001: Use server-rendered Django

Status: Accepted

## Context

ShelfSum must provide strong backend evidence, remain usable on a low-resource Windows computer, and avoid unnecessary frontend and deployment complexity.

## Decision

Use Django 5.2 LTS with server-rendered templates. JavaScript may progressively enhance an already usable interface but is not required for core workflows. Use Django's built-in authentication and test client where they fit.

## Consequences

- Product behaviour and permission checks stay visible at the request, service, and persistence boundaries.
- One deployable application replaces a separate frontend/backend build.
- A REST API is not part of the initial release; API evidence belongs in the second flagship project.
