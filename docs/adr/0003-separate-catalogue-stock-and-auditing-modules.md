# 0003: Separate catalogue, stock, and auditing modules

Status: Accepted

## Context

Product creation touches catalogue data, current stock, immutable movement history, and an Audit Event. Putting all four responsibilities in model signals would hide ordering, make failures difficult to test, and couple unrelated future workflows.

## Decision

Keep one deployable Django monolith with explicit `catalogue`, `inventory`, and `auditing` modules. Let a public catalogue service orchestrate Product creation inside a database transaction. Keep stock mutation in an inventory service and Demo Business write protection in a shared Business rule.

## Consequences

- Request tests can use the view boundary while invariant tests use a public service seam.
- A failed stock or audit write rolls the whole Product creation back.
- Purchases, Sales, and later Stock Adjustments can reuse inventory and auditing behaviour without model signals.
- The application has more small modules, so their ownership must remain documented and imports must not become circular.
