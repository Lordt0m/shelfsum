# ShelfSum module and invariant map

Use this map to find the owner of a boundary. Keep interfaces small: callers provide the Business, actor, validated intent, and required record; the owning module hides transaction, audit, and persistence detail.

## Invariants

| ID | Invariant | Primary owner | Proof expectation | Revisit when |
| --- | --- | --- | --- | --- |
| INV-01 | Resolve every Business-owned identifier only inside the authenticated membership's Business. | `businesses.access` plus owning query/service | Cross-Business request and service tests | Any Business-owned route or service is added |
| INV-02 | Stock on Hand equals the net effect of immutable Stock Movements. | `inventory` | Reconciliation and mutation-bypass tests | Any stock-affecting workflow changes |
| INV-03 | Purchase, Sale, adjustment, reversal, stock, movement, and audit effects succeed or fail atomically. | Owning application service | Success plus downstream-failure rollback tests | A multi-record workflow changes |
| INV-04 | Completed stock-affecting records remain immutable; correction uses an explicit reversal. | Owning domain model/queryset/service | Direct, bulk, repeated-action, and reversal tests | Status or correction behaviour changes |
| INV-05 | Demo Business writes are rejected at both request and service boundaries. | `businesses.rules` plus every mutating entry point | Crafted-request and direct-service tests | Any write path is added |
| INV-06 | Money uses decimal arithmetic; first-release quantities use whole units. | Forms, models, and services | Boundary, precision, and invalid-input tests | Money or quantity representation changes |

## Interfaces

| ID | Caller -> owner | Contract | Preconditions | Failure proof | Current anchors |
| --- | --- | --- | --- | --- | --- |
| IF-01 | protected view -> `businesses.access` | Establish active membership and `request.business` before object lookup. | Authenticated active member | Stable redirect/403 and isolation tests | `businesses/access.py` |
| IF-02 | mutating view/service -> `businesses.rules` | Reject Demo Business and unauthorized or inactive actors. | Business and actor are explicit | Request and direct-service denial tests | `businesses/rules.py` |
| IF-03 | `catalogue` -> `inventory` | Create opening stock only through the stock-adjustment service. | Matching Business and Product; valid whole quantity | Atomic rollback, no negative stock, immutable trace | `catalogue/services.py`, `inventory/services.py` |
| IF-04 | domain service -> `auditing` | Record each consequential change inside the same transaction. | A valid changed object and actor | Audit failure rolls back the whole operation | `auditing/services.py` |
| IF-05 | catalogue view -> Product queryset | List, lookup, search, and stock-activity availability remain Business-scoped. | Current Business is explicit | Cross-Business records never appear | `catalogue/models.py`, `catalogue/views.py` |
| IF-06 | Owner membership views -> `businesses.services` | Add or deactivate Staff Members atomically with an Audit Event while preserving one-Business membership. | Active Owner, current Business, registered unassigned target | Owner, Demo, duplicate, assignment, and cross-Business denial tests | `businesses/services.py`, `businesses/views.py` |

Update this file only when ownership, a public seam, or an invariant changes. Implementation detail that does not affect callers belongs in code and tests.
