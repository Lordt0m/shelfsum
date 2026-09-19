# Provider deployment fact check

As of 2026-09-19. Scope: Render Blueprints, Neon pooled PostgreSQL, psycopg 3.3.5, and Django 5.2 behavior relevant to ShelfSum.

## Adjudication

### 1. Render `generateValue: true`

**Documented facts.** Render says that, when the variable does not already exist, `generateValue: true` adds it with a randomized, base64-encoded 256-bit value and shows a 44-character padded-base64 example. Render also says service environment variables are available at build time and runtime. Sources: [Render Blueprint YAML Reference](https://render.com/docs/blueprint-spec#generating-random-secrets), [Your First Render Deploy](https://render.com/docs/your-first-deploy).

**Adjudication.** “Exactly 44 characters” is not an explicit Render contract. It is a mathematical inference for the usual padded Base64 encoding of 32 random bytes (256 bits); the documentation guarantees the encoding and entropy, not a fixed serialized length/variant. “Available during the first build” is a strong inference from the two documented behaviors (the value is created during initial Blueprint sync, and service env vars are build-time inputs), but Render does not state the provisioning-before-build ordering in the `generateValue` paragraph itself.

**ShelfSum impact.** `render.yaml` uses `generateValue: true` for `SECRET_KEY`, while `config/settings.py` rejects production secrets shorter than 50 characters. A canonical padded Base64 encoding of 256 bits is 44 characters, so the documented example would fail that local validation during `build.sh` (`collectstatic` imports settings). Treat this as a real deployment risk until a live Render value is verified or the validation policy is changed; do not describe “44 characters” as a guaranteed Render API contract.

### 2. Neon pooled URLs, PgBouncer, and `prepare_threshold`

**Documented facts.** Neon’s pooled `-pooler` endpoint uses PgBouncer and Neon documents `pool_mode=transaction`, `max_prepared_statements=1000`, and transaction-pooling limitations such as SQL-level `PREPARE`/`DEALLOCATE`. Neon also documents protocol-level prepared statements as supported. Sources: [Neon connection pooling](https://neon.com/docs/connect/connection-pooling), [Neon compute management / scale-to-zero](https://neon.com/docs/manage/endpoints/).

Psycopg’s current prepared-statement documentation says prepared statements are supported with PgBouncer from psycopg 3.2 onward when PgBouncer is at least 1.22, `max_prepared_statements > 0`, and the client libpq is PostgreSQL 17 or newer; otherwise it recommends disabling preparation or deallocation as applicable. Psycopg’s release notes list the PgBouncer compatibility change under psycopg 3.2; psycopg 3.3.5 itself lists prepared-statement discard fixes. Sources: [Psycopg prepared statements](https://www.psycopg.org/psycopg3/docs/advanced/prepare.html), [Psycopg release notes](https://www.psycopg.org/psycopg3/docs/news.html).

**Adjudication.** The claim that psycopg 3.3.5/Django *requires* `prepare_threshold=None` for Neon pooled connections is unsupported as a universal rule. It is a compatibility fallback when the documented PgBouncer/libpq prerequisites are not met, or when using a pooler whose prepared-statement support is unknown. With Neon’s documented PgBouncer configuration and a compatible psycopg/libpq build, leaving the threshold enabled is supported. This repository pins `psycopg[binary]==3.3.5`, but the requirements file alone does not prove which libpq capability the deployed wheel provides, so the prerequisites should be verified rather than assumed.

Django does not prescribe `prepare_threshold=None`; its PostgreSQL backend passes `OPTIONS` through to the driver. Django does explicitly require disabling server-side cursors when using transaction pooling unless each cursor is kept inside one transaction. Source: [Django 5.2 database documentation](https://docs.djangoproject.com/en/5.2/ref/databases/).

### 3. `CONN_MAX_AGE=600` and Neon scale-to-zero

**Documented facts.** Django defines `CONN_MAX_AGE` as the maximum lifetime of persistent connections, closes connections once they exceed that age or become unusable, and advises a lower value when the database terminates idle connections. Django advises disabling persistent connections under ASGI and using pooling instead. Neon says scale-to-zero transitions a compute to idle after five minutes of inactivity; frequent connection requests or background processes can keep it active, and Neon recommends connection pooling to limit persistent connections. Sources: [Django 5.2 database documentation](https://docs.djangoproject.com/en/5.2/ref/databases/), [Neon compute management / scale-to-zero](https://neon.com/docs/manage/endpoints/), [Neon scale-to-zero with long-running applications](https://neon.com/blog/using-neons-auto-suspend-with-long-running-applications).

**Adjudication.** `CONN_MAX_AGE=600` is not by itself a material contradiction of Neon scale-to-zero. An idle client connection does not prove ongoing query activity, and Neon’s own scale-to-zero guidance says suspension can occur even while clients are connected; however, recurring requests/background activity during that 600-second reuse window can keep the compute active and eliminate scale-to-zero savings. The safe conclusion is workload-dependent: 600 seconds is a performance-oriented persistent-connection choice, not a Neon-recommended universal value.

**Practical recommendation for this project.** Keep `CONN_HEALTH_CHECKS=True` (already present) so Django can recover when a server-side connection is gone. Reconsider `600` for low-traffic or ASGI deployments (Django’s documented guidance favors a low value or `0` there), and use Neon’s pooled URL for concurrency if needed. Do not change it solely on the theory that any persistent client connection prevents scale-to-zero; measure connection/request patterns and verify the deployed libpq/PgBouncer prepared-statement prerequisites.

