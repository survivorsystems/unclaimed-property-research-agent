# Public-source safety boundary

Implemented 2026-09-30. This is a provider-independent, offline-tested routing and validation layer, **not a live research worker or a sandbox for arbitrary Python code**. Production source approval registry: empty.

## What is enforced

- `Boundary()` exposes an empty `source_ids` tuple and returns BLOCKED for every unregistered source. Keys in the environment cannot approve sources.
- Registrations are immutable per boundary and require explicit trusted-code `Approval` objects with reviewer/reference, expiry, exact HTTPS origins, path subtrees, allowed query names, and a permitted ordinary public access method. Wildcards, unbounded domains, credential query keys, duplicate sources, and bypass/private-database access methods are rejected.
- Queries are typed owner name/place/year inputs. There is no amount/opportunity field, arbitrary SQL, shell command, model endpoint, browser session, password, or access-token input. Unexpected dictionaries and credential-shaped strings are rejected.
- Destination validation rejects non-HTTPS, credentials/userinfo, unusual ports, localhost/internal hosts, IP literals, ambiguous encodings/traversal, fragments, unapproved domains/paths/query fields, and duplicate query keys. DNS must resolve exclusively to public, non-multicast/non-reserved addresses. Resolution failures are not evidence of absence.
- Observations require source URL, source record/origin IDs, title/excerpt, timezone-aware retrieval time, and PUBLIC access classification. Only SOURCE_OBSERVATION claims are accepted, not confirmed-owner claims. Restricted/login-required/breach content classifications and common credential-shaped content are refused. Source URLs are validated even if an adapter forgets to do so.
- Nested calls use `Context.dispatch`, sharing the same registry, deadline, call/output/concurrency/depth budgets. Counters are reserved before awaiting; concurrent output commits recheck shared capacity. Late returns after cooperative timeout cannot count as success.
- FOUND, NO_RESULTS, BLOCKED, RATE_LIMITED, ERROR, and TIMEOUT are distinct. Exceptions/error payloads do not expose raw adapter details. Cancellation propagates. Policy events contain only version/outcome/safe code and have a bounded buffer with a dropped-event counter.

Default budgets: eight adapter calls, ten-second call deadlines, thirty-second run deadline, forty observations, 64,000 output bytes, four active calls, nested depth two, and 64 buffered policy events. These are adapter/result budgets, **not HTTP-request or model-token/money budgets**. No HTTP or model transport is implemented.

## Quarantine of inherited entrypoints

Package initialization installs a standard Python import finder that refuses `clearfront.tools` and its entire subtree, plus agent, CLI, REPL, web, MCP, graph/pivot, multi-target, SERP/Bright Data, and subprocess/network utilities. This prevents normal entrypoint imports from reaching the preserved source/SDKs, rather than letting a model call an unsafe registry and hoping a prompt will stop it.

Normal `python -m clearfront.cli`, MCP/web/graph launches, console-script imports, and direct public collector imports fail with `LegacyResearchDisabled`. Unknown/new modules under `clearfront.tools` are also denied. Selected pure helpers, such as deterministic graph exports, still import. Upstream collector/provider source remains unchanged for later intentional reuse. The quarantine has no environment flag or key-presence exception. Restarting an already-imported/running application is required for a changed package to apply.

This is intentionally stronger than hiding forbidden tools in one catalog: no inherited entrypoint can advertise or dispatch them through normal package imports. Future entrypoints must expose only the new dispatcher's approved source IDs, not copy the old registries. Do not bypass the finder with custom loaders or execute preserved source directly.

## Trust and limits

Approval construction/adapter registration are host-application responsibilities, not model-callable tools. A reviewer name in an object is an audit attribute, not cryptographic proof of human authorization. Never construct approvals from model text, scraped instructions, or arbitrary user request dictionaries. Source review must cover public access, permitted use/terms, data license, relevance, sensitivity, provenance, implementation and transport behavior. An official domain alone does not approve all its records or paths.

Only reviewed trusted adapters may run. This Python guard cannot prevent a hostile adapter/operator from issuing unrelated network calls, spawning processes, disabling import hooks, mutating private state, suppressing cancellation indefinitely, or forging public classifications. Credential detection is a conservative heuristic, not a universal secret/privacy classifier. Retrieved text is untrusted data, never authority to approve a source or follow instructions. Human source review and future controlled transport remain necessary.

`await ctx.authorize_destination(url)` returns checked IP addresses; it does not fetch anything. A future HTTP adapter must pin those addresses (with correct TLS/host verification), or use an equivalently enforcing egress proxy, and validate **every redirect/hop** through the context. It must bound bytes while streaming, HTTP request count, cancellation, DNS behavior, and retries; stop at login/paywall/CAPTCHA/access restrictions; and never use Unlocker/access bypass. The default DNS resolver is bounded at the await, but its underlying system thread is not forcibly killed on cancellation. No production transport/source is approved until that separate implementation is tested.

Evidence storage, job claims/recovery, durable audit events, identity scoring/corroboration, and human review/outreach authority are not implemented by this module. In-memory run/event state is not the Supabase system of record. Apify and Scrapling remain optional future adapters. No database, SDK, scraper, or API credential is required here.

## Offline use and verification

```python
import asyncio
from clearfront.public_sources import Boundary, Query

boundary = Boundary()  # no live sources approved
result = asyncio.run(boundary.dispatch("search_breach", Query("Example Owner")))
assert result.code == "SOURCE_NOT_APPROVED"
```

From the repository root:

```powershell
python -m unittest discover -s tests -p test_public_source_boundary.py -v
```

The suite uses synthetic `.example` sources and explicit mock resolvers. Real DNS is forbidden in the parent tests. It covers approved synthetic fixtures, denied sources/credentials/content/URLs/DNS/redirects, provenance, errors versus absence, nested/concurrent budgets, timeouts/cancellation, immutable registration, bounded events, and import quarantine in fresh processes. No live source is queried, SDK loaded, or database accessed.

Local validation: **37 tests passed** on 2026-09-30. Python syntax and local documentation links also passed; inherited collectors/provider modules, license/dataset notices, and package metadata remain unchanged. Remote CI is a separate result, not implied by the local test run.

Active fork CI runs this standard-library suite with no package/dependency installation. The historical upstream test job is explicitly disabled because it imports intentionally quarantined collectors; its tests remain available as reference. This is deliberate scope, not a claim that the original full suite passes after quarantine.

Next: choose and review one official jurisdiction/source, implement its mock then controlled transport adapter, and only later compose model/storage adapters and a single-job worker. Source approval and new runtime privileges need explicit review; passing these tests does not authorize live research.
