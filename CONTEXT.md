# ShelfSum product context

ShelfSum is a server-rendered Django application for one small-shop Business to record Products, stock activity, Sales, Purchases, and Expenses. Its important operational figures must be traceable to recorded facts.

## Language

**Business**  
The shop whose members, catalogue, stock, and financial records are isolated from every other shop. Avoid using _account_, _tenant_, or _company_ for this concept.

**Owner**  
The person responsible for a Business who can manage its Staff Members and all Business records. Avoid using _admin_ for this product role.

**Staff Member**  
A person permitted to record day-to-day activity for one Business without owner-only controls.

**Product**  
A stock-tracked item a Business purchases and sells. Use _Product_, not _item_ or _inventory_, in product language.

**Stock on Hand**  
The current whole-number quantity of a Product available to the Business.

**Stock Movement**  
An immutable increase or decrease that explains a change to Stock on Hand.

**Stock Adjustment**  
A deliberate correction to Stock on Hand with a recorded reason.

**Purchase**  
A completed acquisition of one or more Products that increases Stock on Hand.

**Sale**  
A completed disposal of one or more Products that decreases Stock on Hand and records revenue.

**Expense**  
A non-stock operating cost recorded by the Business.

**Estimated Profit**  
Sales revenue minus recorded cost snapshots and Expenses for a selected period. It is an operational estimate, not an accounting, tax, or cash-profit figure.

**Audit Event**  
An append-only record of who performed a consequential action and when.

**Demo Business**  
A read-only fictional Business that visitors can inspect without changing shared demonstration data.

## Core invariants

- Every Business-owned query is scoped through the authenticated person's membership before a supplied identifier is resolved.
- Stock on Hand equals the net effect of that Product's Stock Movements.
- Completing a Purchase or Sale creates its Stock Movements atomically.
- Completed stock-affecting records are not edited or deleted; corrections use explicit reversal behaviour.
- Money uses decimal arithmetic and quantities use whole numbers in the first release.
- The Demo Business is read-only at the server boundary.
