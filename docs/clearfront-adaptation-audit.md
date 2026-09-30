# Clearfront adaptation audit

Audit started: 2026-09-29. Documentation finalized: 2026-09-30. Status: **implementation inspected; adaptation proposed, not implemented**.

## 1. Recommendation and scope

Use Clearfront as a preserved architectural starting point, not as an immediately deployable owner-research system. Reuse bounded orchestration, provider separation, cache and export utilities through adapters. Replace the unrestricted collection policy, identifier/owner resolution, confidence semantics, evidence contract, and local-only persistence. Keep Supabase as the durable system of record and the existing dashboard as the human-review surface.

This initial change adds project documentation and repository instructions only. It does not run research, install dependencies/binaries, configure provider keys, implement adapters, register a skill/MCP server, change the dashboard, or modify any database object or row. All inherited tools remain in the source tree and are **not yet made safe by runtime enforcement**.

## 2. Upstream and license provenance

| Item | Verified starting point |
| --- | --- |
| Upstream | [scottmartinanderson/clearfront](https://github.com/scottmartinanderson/clearfront) |
| Fork | [survivorsystems/unclaimed-property-research-agent](https://github.com/survivorsystems/unclaimed-property-research-agent) |
| Audited upstream commit | [`4fa50326283c77fad0d84e93d0367b50944fb8e3`](https://github.com/scottmartinanderson/clearfront/commit/4fa50326283c77fad0d84e93d0367b50944fb8e3) |
| Package metadata | `clearfront`, version `2.7.3`, Python `>=3.10` |
| Git history | Fork and clone preserve upstream history; no source flattening or copying into the toolbox |
| Remotes | `origin`: our fork; `upstream`: original repository, for deliberate upstream review |
| Original source | Inherited implementation, tests, packaging, publisher metadata, configuration, and license files remain unchanged in this adaptation |
| New material | README project preamble, this audit, and root `AGENTS.md` |

The [MIT license](../LICENSE) permits modification and redistribution, including commercial reuse, subject to retaining its copyright and permission notice. It contains copyright notices for Scott Martin Anderson and OpenOSINT, both dated 2026. No change to those notices is warranted.

The bundled `clearfront/tools/data/wmn-data-unique.json` is a separate work under CC BY-SA 4.0. Preserve [the dataset NOTICE](../clearfront/tools/data/NOTICE), which identifies the WhatsMyName origin and attribution. Redistribution/adaptation of that dataset carries its attribution and applicable share-alike obligations; do not relabel the dataset as MIT. This audit does not modify it or decide to adopt it for owner research. Downstream tools, APIs, and government datasets have their own terms; the upstream MIT license does not license those services or all their data.

The inherited PyPI, MCP registry, plugin publisher identity, homepage, and branding are retained as provenance, **not permission to publish under those identities**. Rename distribution metadata in a later packaging task before any release. Maintain small adaptation commits; review upstream changes on a separate branch with safety/regression checks before merging.

## 3. Inspection basis and repository map

Findings below are based on the checked-out implementation at the pinned commit, not a test run or security certification. Source links are repository-relative for convenient navigation; [the immutable upstream tree](https://github.com/scottmartinanderson/clearfront/tree/4fa50326283c77fad0d84e93d0367b50944fb8e3) fixes the audit baseline.

| Area | Implementation inspected |
| --- | --- |
| Agent/provider loops | [`agent.py`](../clearfront/agent.py), [`prompts.py`](../clearfront/prompts.py), [`effort.py`](../clearfront/effort.py) |
| Tool dispatch and parallel sweeps | [`tools/`](../clearfront/tools), [`pivot.py`](../clearfront/pivot.py), [`multi_target.py`](../clearfront/multi_target.py), [`utils.py`](../clearfront/utils.py) |
| Correlation and caching | [`correlation.py`](../clearfront/correlation.py), [`extractors.py`](../clearfront/extractors.py), [`corroboration.py`](../clearfront/corroboration.py), [`tool_cache.py`](../clearfront/tool_cache.py), [`regexes.py`](../clearfront/regexes.py) |
| Search vendors | [`serp.py`](../clearfront/serp.py), [`brightdata.py`](../clearfront/brightdata.py), [`search_footprint.py`](../clearfront/tools/search_footprint.py), [`scrape_url.py`](../clearfront/tools/scrape_url.py) |
| Persistence/reporting | [`session_history.py`](../clearfront/session_history.py), [`json_output.py`](../clearfront/json_output.py), [`pdf_report.py`](../clearfront/pdf_report.py), [`repl.py`](../clearfront/repl.py) |
| Interfaces | [`cli.py`](../clearfront/cli.py), [`mcp_server.py`](../clearfront/mcp_server.py), [`web_server.py`](../clearfront/web_server.py), [`web/index.html`](../clearfront/web/index.html) |
| Build and operations | [`pyproject.toml`](../pyproject.toml), [`uv.lock`](../uv.lock), [CI](../.github/workflows/ci.yml), [Dependabot](../.github/dependabot.yml), [`Dockerfile`](../Dockerfile), [`docker-compose.yml`](../docker-compose.yml), [environment example](../.env.example), [security policy](../SECURITY.md), [disclaimer](../DISCLAIMER.md) |
| Tests | [`tests/`](../tests): provider, tool/cache/corroboration, graph/export, security, effort, entrypoint, and authorization-description regression tests |

No production research worker exists in the existing toolbox. Its schema/workflow contracts were also read at toolbox commit `bca61c1ae867808fa4629b9017c341682c069a07`: [database schema](https://github.com/survivorsystems/researchagents-skills/blob/bca61c1ae867808fa4629b9017c341682c069a07/docs/database-schema.md) and [workflow contract](https://github.com/survivorsystems/researchagents-skills/blob/bca61c1ae867808fa4629b9017c341682c069a07/docs/workflow-contract.md). The dashboard is a separate application and is not replaced by this fork. Its internals were not re-audited in this task.

## 4. Actual architecture

### Orchestration, workflows, and tool calling

`agent.py` implements `OISAgent` (Anthropic), `OllamaAgent`, and `OpenAICompatibleAgent` (Chat Completions-compatible endpoints). It uses plain Python loops and provider SDKs, not a durable workflow engine or the OpenAI Agents SDK. `AgentResponse` contains narrative text, `ToolCall` records, and an optional error. Conversation history and run context are in memory.

The agent registry has 30 collection tools plus `investigate_graph`. Tool arguments are provider-specific dictionaries; handlers return formatted strings. Tool schemas and handlers are hard-coded. There is no injected public-source allowlist or owner-evidence output contract. Anthropic, Ollama, and OpenAI tool-turn processors await each call sequentially. A tool calling real services does not prevent unsupported model interpretations or report hallucinations.

`effort.py` provides faster/balanced/deeper round ceilings (deeper configurable with `OIS_MAX_TOOL_ROUNDS`, default 12; faster/balanced capped at 4/8). At the limit, loops request a final answer with tools disabled. A round limit is not a total-call, token, money, byte, or wall-clock budget. The default prompt encourages aggressive outward expansion and explicitly recommends prohibited breach/account-discovery tools. Replace the task and policy prompts; enforce authorization in dispatch, not only in prompt text.

`pivot.py` implements breadth-first identifier expansion. It runs routed tools concurrently **for each dequeued entity**, rather than concurrently across a whole depth layer. Defaults are depth 2, 40 investigated entities, 60 calls, 30-second per-tool timeout; the agent wrapper uses smaller defaults. It enqueues discoveries with extractor confidence at least 0.6. New graph nodes are inserted before the queue-size check, so `max_entities` is not a hard bound on total extracted graph nodes. Tool failures/timeouts become empty strings and raw tool results are not returned with the graph. Nested routes include banned tools, so disabling only a top-level exposed tool is insufficient.

`multi_target.py` runs up to ten fresh agents via `asyncio.gather`. This is parallel execution, not a durable distributed queue: no claim lock, worker lease, recovery checkpoint, or transactional evidence commit. Reuse the isolated-per-target idea, but add bounded concurrency and durable per-job attempts.

### Source integrations and search/query infrastructure

Clearfront is mainly a digital-footprint/security toolbox. It has no implemented unclaimed-property importer, county assessor/recorder adapter, Secretary of State adapter, address-history model, or verified owner/business-resolution workflow.

| Inherited group | Tools | Adaptation decision |
| --- | --- | --- |
| General public discovery | `search_footprint`, `search_dorks_live`, `search_wayback` | Possible adapter material after source/query/content-policy review; search hits are leads, archived content needs temporal context |
| Identifier/profile discovery | `search_username`, `search_maigret`, `search_gravatar`, `search_github`, `search_phone` | Not default owner research; narrowly scope any later adoption. Public profile existence does not identify a property owner; GitHub tool includes secret-exposure search |
| Prohibited collection | `search_email`, `search_breach`, `search_paste`, `search_hudsonrock`, `search_emailrep`, inherited `scrape_url` | Exclude from this project's dispatcher. Holehe-based account existence, breach/paste/stealer/reputation signals, and Web Unlocker bypass behavior conflict with our scope |
| Security/infrastructure | `search_whois`, `search_ip`, `search_exposure`, `search_domain`, `search_shodan`, `search_virustotal`, `search_censys`, `search_ip2location`, `search_abuseipdb`, `search_dns`, `search_crypto`, `search_harvester`, `search_crt`, `search_greynoise`, `search_exif` | Keep as preserved upstream code, outside the initial worker's allowlist. Some public business-domain metadata might justify a separately approved adapter later |
| Query generation | `generate_dorks` | Replace its digital-footprint/security templates with scoped owner/business/place/date discovery queries; do not enable inherited templates wholesale |

The current search selection is Serper when configured, then Bright Data SERP, otherwise the `ddgs` DuckDuckGo fallback. Selection is based on environment-key presence, not authorization. `search_footprint` runs entity-specific queries, serializes title/URL/snippet data into text, deduplicates URLs in a run, and reports query errors. It does not establish source independence, identity, or primary-record authenticity. Its Serper snippets are truncated to 200 characters. Preserve the distinction between an indexed snippet and a fetched source document.

`search_username` verifies page responses/username appearance and has a bundled WhatsMyName fallback; `search_maigret` defaults to 500 top sites. Thus README claims of 3,400+ sources are not a guarantee that every run checks 3,400 sources, nor that those sources are government records or owner evidence. Account/page verification is not person verification.

The inherited `scrape_url` explicitly uses Bright Data Web Unlocker to bypass bot protection/CAPTCHA. **Do not adopt that handler.** A future ordinary public-page fetcher must honor approved access methods and stop at access restrictions. Broad browser/scraper coverage is not authorization to bypass a site.

### Resolution, graph, evidence, and confidence

`correlation.py` has typed email/username/domain/IP/phone/hash/URL/person/org/ASN nodes, relationships, and deterministic JSON/GraphML/Mermaid exports. There is no property/address/relative/history taxonomy. Node equality uses `(entity_type, normalized_value)` and duplicate node confidence uses the maximum value. Same-name people can collapse into one node. URL normalization lowercases paths, which can incorrectly merge case-sensitive identifiers. The seed detector in `pivot.py` defaults unknown values, including full names, to USERNAME; `regexes.detect_entity_kind` treats multiword input as PERSON instead. Do not use those heuristics as our candidate identity model.

`extractors.py` parses tool-specific text prefixes using preset confidence constants. Those numbers characterize discoveries, not a calibrated probability that a person owns property. Edge deduplication can discard a second source/tool attribution; EntityGraph exports omit relationship confidence, and the generic D3 exporter retains endpoints rather than material-claim evidence on edges.

There are **two different graph paths**: deterministic text-extractor/BFS graphs, and a separately LLM-authored graph after web reporting. The latter derives nodes and links from tool outputs plus report narrative; its prompt favors dense connections and co-occurrence. Graph failures are best-effort and can be silently suppressed. Neither graph is a durable evidence ledger or proof of identity. Future graphs must be derived from persisted, evidence-linked claims, with explicit fact/inference/direction/time fields, not invented relationship edges or density targets.

`corroboration.py` appends a higher-confidence note when different tools report the same normalized profile. It calls that independent corroboration, but those tools may be describing the same underlying page. **Replace this semantics:** count independent originating records, not tools, repeated snippets, syndicated copies, or graph node degree.

The prompts do recognize name ambiguity and separate assessment from observation, but also characterize URL verification as high reliability and tell the analyst to treat tool returns as facts. Collection outputs and self-published statements are not automatically true. There is no implemented identity rubric, weighted attribute comparison, contradiction penalty, candidate ranking contract, calibrated numerical owner score, or human-approval separation in the upstream agent. Do not multiply graph constants by 100 to populate our required candidate score.

`json_output.py` only wraps a tool name, target, export timestamp, nonempty output lines, and optional error. It lacks individual claim IDs, retrieved source receipts, source-origin independence, source valid dates, structured contradictions, and candidate attribution. Its export timestamp is not necessarily the actual source retrieval time.

### Persistence and reporting

There is no implemented database-backed job/run/evidence repository. `session_history.py` stores JSON under the user's `.clearfront/history`, prunes to 50 sessions, and includes prompts, targets, tool names, and a report path. Its comment says sensitive raw outputs/keys are not stored, but prompts/targets themselves can contain personal or accidentally secret information. It is unsuitable for the durable audit trail.

REPL and multi-target report writers save local Markdown and optional ReportLab PDFs. Multi-target filenames use date plus sanitized target; repeated same-day runs can overwrite an earlier report. Filenames may also disclose targets. Export rendering escapes markup, and the web route bounds input size, useful defensive patterns; reporting must instead use run IDs, approved storage/retention, deterministic evidence citations, and explicit failures. Reports/PDFs should be rebuildable views of stored research, not the only copy.

Web board routes lazily import `clearfront.boards`, but **no `clearfront/boards.py` or corresponding tracked module exists at the pinned commit**. Board persistence cannot be credited as implemented working storage. This is a static implementation inconsistency, not an executed endpoint failure in this audit.

### Server, frontend, authentication, and observability

`web_server.py` is a FastAPI local console with tool-run/stream endpoints, SSE model chat, health/tool catalogs, report/graph exports, setup, and board routes. It duplicates model loops and has a separate runner registry/catalog from `agent.py` and MCP. Avoid maintaining another copy of the owner workflow in its server. The frontend is a single Alpine/Tailwind page with a 3D force graph, security-exposure actions, API-key setup, local settings, and external CDN/font resources. It is not the existing human-review dashboard.

The console intentionally has **no authentication**. Local entrypoints enable a Host-header guard; CORS is limited to localhost origins. Public-bind guards disable local-file extraction, setup, and board routes, reject private backend URLs, and hide the Maps key. These are useful protections, not login, authorization, tenancy, cost control, or our source policy. Public run/chat routes still provide capabilities. Docker binds `0.0.0.0`; Compose exposes port 8080 and mounts a writable `.env`. Do not deploy this console publicly or assume its CORS/public-bind checks are access control.

The setup route writes allowlisted configuration into plaintext `.env`. The UI's OpenAI settings include a key saved in `localStorage` and transmitted in chat/setup payloads. Keep future worker secrets in trusted runtime configuration; never in browser local storage or LLM inputs. No dashboard credentials were copied into this fork.

MCP serves tools over stdio. Its authorized-use clause is descriptive text appended to tool descriptions, not a target authorization check. It logs full arguments and exposes the same broad collection scope plus `investigate_multi`; there is no inherited public-only policy enforcement or distributed storage. CLI and REPL can invoke tools outside the AI loop. Every entrypoint and nested route must pass through a single policy boundary if retained.

Python logging reports tools/targets/errors, but has no implemented per-property/job/run correlation, durable span/event trail, redaction policy, budget metrics, or worker health/recovery protocol. Some handlers return error text as a successful tool string; pivot catches errors as empty results, and graph rendering suppresses errors. Preserve useful logs/timeouts, replace ambiguous success/error semantics with typed statuses, and keep redacted operational logs separate from access-controlled evidence.

## 5. Dependencies, configuration, and maintenance posture

Core declared dependencies are `mcp`, `anthropic`, `requests`, `python-whois`, `rich`, `prompt_toolkit`, `python-dotenv`, `aiohttp`, `dnspython`, `ddgs`, `fastapi`, `uvicorn`, and `httpx`. Optional extras add `openai`, `ollama`, `shodan`, `censys-platform`, ReportLab, SSE tooling, Playwright, and development tools. Python minimum is 3.10; Docker uses 3.11 and CI tests 3.12. Anthropic is a core dependency even if another provider is used; isolate future model adapters rather than require every upstream integration.

Dependencies generally have version ranges, with `uv.lock` present. CI installs editable `.[all,web,dev]` with pip, so it does **not** enforce that lockfile. Docker additionally installs Holehe, Sherlock, and Sublist3r without pinned versions. Other wrappers require external binaries (for example Maigret, PhoneInfoga, theHarvester, exiftool). Do not assume installing the Python package installs all supported collectors. Do not install these as part of the audit; review needed dependency licenses and pin a minimal worker-specific runtime before adoption.

| Configuration family | Inherited names and external services | Future treatment |
| --- | --- | --- |
| Models | `ANTHROPIC_API_KEY`; `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL`; `OLLAMA_HOST`, `OLLAMA_MODEL`; `OIS_MAX_TOOL_ROUNDS` | Provider choice and credential setup deferred; approved server endpoints, explicit budgets; no model API used for this audit |
| Search/extraction | `SERPER_API_KEY`; `BRIGHTDATA_API_KEY`, `BRIGHTDATA_SERP_ZONE`, `BRIGHTDATA_UNLOCKER_ZONE`; DuckDuckGo | Optional provider adapters; no Unlocker adoption; key presence must not enable an unapproved provider |
| Breach/reputation | `HIBP_API_KEY`, `EMAILREP_API_KEY`; HIBP, Hudson Rock, paste searches, Holehe | Outside owner-research scope; never add these to our eventual worker environment guide |
| Infrastructure/security | `IPINFO_TOKEN`, `IP2LOCATION_API_KEY`, `SHODAN_API_KEY`, `VIRUSTOTAL_API_KEY`, `CENSYS_PAT`, `CENSYS_ORG_ID`, `ABUSEIPDB_API_KEY` | Not required for initial worker; do not propagate unrelated keys |
| Other | `GITHUB_TOKEN`, `GOOGLE_MAPS_API_KEY`; GitHub public API, DNS/WHOIS/crt.sh, archives, profile/crypto services | Separate need/terms/security review; mapping/geolocation is not owner confirmation |
| Storage | No implemented Supabase worker config or storage adapter | Add later, server-only and explicitly scoped to `research_agent`; no secrets in this public repository |

The inherited `.env.example` contains placeholder keys for unrelated tools and does not cover every runtime setting. It is preserved as upstream reference, not a setup file for this project. Create a narrow blank example only when the approved worker's configuration is implemented.

Upstream has a security/disclaimer policy, Dependabot, a weekly CI schedule, and regression tests for injection/SSRF/public-bind restrictions, exporters, caching, effort, and provider/tool parity. These are positive maintenance signals, not a comprehensive security/identity audit. README broad-source and hallucination-prevention claims overstate guarantees visible in implementation. Releases, dependency advisories, vendor prices, provider availability, and full transitive-license compatibility were not certified here. Upstream workflows/publisher files were preserved, not manually dispatched or republished. A pull request may trigger the fork's inherited CI independently; its results are separate from this static audit.

## 6. Existing Supabase audit and mapping

The live Oddly Functional `research_agent` schema was inspected read-only: table definitions, nullability/defaults, constraints and foreign keys, indexes, RLS/policies, grants, functions/triggers, and exact row counts. All six tables contained **zero rows** at audit time. No DDL, insert, update, delete, migration, exposure change, or review RPC execution was performed. Unrelated schemas, Storage, Auth, and the dashboard's authentication were outside this audit.

All six tables have RLS enabled. `anon` and `authenticated` have no schema usage/table privileges or policies. `service_role` has explicit trusted-server privileges. The schema is addressable through the existing Data API configuration; “private” describes the access restrictions, not an assertion that it is excluded from exposed schemas. Do not broaden browser grants based on generic custom-schema examples.

`set_updated_at()` and `apply_human_review_decision()` are SECURITY INVOKER functions with empty search paths. Timestamp triggers cover property records, jobs, and candidates. The human-review function locks a candidate, applies APPROVE/REJECT/RESEARCH_MORE transactionally, appends a HUMAN event, and queues more research when requested. It leaves outreach disabled in every branch. It accepts an actor identifier supplied by the trusted caller; it is not a database-level proof that a human made the request. The worker must not call it.

| Existing object | Current fields/constraints relevant to adaptation | Proposed mapping from Clearfront or new worker |
| --- | --- | --- |
| `property_records` | `owner_name`, optional co-owner, reported address/city/state/zip, holder/type/amount/date, source identifiers/URLs, `raw_source_payload`, `retrieved_at`, workflow and opportunity | New importer/normalizer reads source record. Preserve original values and source receipt; identity input excludes amount and opportunity. `(source_system, source_record_id)` provides ingestion idempotency |
| `research_jobs` | Property, `job_type`, `job_status`, priority, `trigger_reason`, attempt count, timing, last error | Replace a free-form target invocation with an explicit queued job ID. Priority is scheduling, not identity evidence; no durable claiming/lease logic currently exists |
| `research_runs` | Job/property composite scope, `worker_identifier`, model labels, status/timing, object-shaped `input_snapshot`/`output_summary`, errors/usage | One attempt per execution. Wrap provider response and tool trace into a versioned result, source receipts, rubric/policy version, token/call/timing usage, and typed failures. No secrets in snapshots |
| `owner_candidates` | `candidate_name`, PERSON/BUSINESS, location summary, required 0-100 score/label/match state, summary, public-contact JSON, review/outreach fields | Explicit separate hypothesized owners, not one node per normalized name. New explainable rubric, ranking within property, evidence-linked summary; initial review PENDING and outreach false. Never inherit graph confidence or overwrite prior human decisions |
| `evidence` | Required property and candidate; optional run; type/category/name/URL/title, `finding_summary`, SUPPORTING/CONFLICTING/NEUTRAL, `structured_metadata`, `retrieved_at` | One material observation/relationship per source receipt and candidate attribution. Store claim kind, observed attributes, valid dates, source-origin/dedup keys, excerpt locator/digest, parser/policy version, and inference support IDs in a proposed versioned metadata vocabulary |
| `workflow_events` | Required property and actor identifier; optional candidate/job; event type, HUMAN/AGENT/SYSTEM, object metadata | Transactional start/finish/failure and policy/budget/retry events with run ID in metadata. Preserve human decisions. This is lightweight audit history, not full event sourcing |

Composite foreign keys prevent candidate/evidence/run relationships crossing properties. Business/audit FKs use `ON DELETE RESTRICT`; archive rather than cascade-delete. Existing score/check constraints and separate approval fields should be retained.

Important storage gaps and decisions:

- `evidence.owner_candidate_id` is required. Store discoveries not yet assigned to a plausible candidate in a versioned `research_runs.output_summary` collection; do not invent a candidate solely to satisfy a foreign key. Persist the evidence association once attribution is meaningful. A dedicated discovery table is a future reviewed option, not required now.
- Current text evidence types/JSON metadata can hold richer claims and temporal relationships without immediate schema changes. Proposed metadata keys here are **not an implemented or validated contract**. Keep related source/claim IDs so several citations from one underlying record do not boost confidence.
- Required candidate confidence cannot be omitted. Define an explicit unknown/unassessed representation in the future rubric (with an honest label and MANUAL_REVIEW_REQUIRED), or separately review an additive schema change; do not invent a calibrated percentage.
- Run summaries can initially carry graph/report projections and unresolved questions; canonical claims remain evidence rows. Long source bodies may later need approved private object storage with receipt/hash/access/retention rules. Do not put every response in an unlimited JSON blob or enable a Storage bucket now.
- Multi-table start/finish transitions require a transaction. Several ordinary REST writes are not a single transaction. No worker claim/complete RPC exists. A trusted repository can use a scoped SQL transaction or future separately reviewed SECURITY INVOKER RPCs. Lock/conditionally claim QUEUED jobs, preserve attempt counts/runs, and append events atomically; do not hold a database transaction open during network/model calls.
- Start with one worker, but still claim atomically. Before parallel workers, separately review leases/heartbeats/crash recovery/idempotency constraints. The existing `research_jobs` table is deliberately not a distributed queue.
- RLS does not restrict `service_role` like a browser role. Current grants also allow writes/deletes and caller-supplied HUMAN events. A future scoped worker role or trusted storage gateway must exclude approval/outreach and unrelated tables. Database check constraints ensure shape/attribution, not that an actual human authorized outreach. Never hand the model a general SQL tool or privileged storage credentials.

Current Supabase documentation was checked: [custom schemas](https://supabase.com/docs/guides/api/using-custom-schemas) and [database functions/security](https://supabase.com/docs/guides/database/functions). The [Data API exposure change](https://supabase.com/changelog/45329-breaking-change-tables-not-exposed-to-data-and-graphql-api-automatically) concerns defaults for new `public` tables, not these custom-schema grants. The [September Postgres minor-release notice](https://supabase.com/changelog/postgres-15-19-17-11-breaking-changes) flags extension/operator-specific upgrade concerns; no extension adoption or upgrade was undertaken. Recheck current platform guidance when implementing storage; this task makes no project-wide remediation claim.

## 7. Target architecture and workflow (proposed)

```text
Existing property + queued job
  -> trusted repository: atomic claim + run/event
  -> owner/property normalizer (retain originals, exclude financial scoring inputs)
  -> bounded research planner -> policy-enforcing dispatcher
                               -> approved source adapters
  -> source receipts -> separate candidate hypotheses -> attributed claims
  -> attribute/time comparison + contradictions + independent-origin evaluation
  -> versioned explainable identity assessment + ranked candidates
  -> trusted repository: atomic result/evidence/job/event completion
  -> existing human-review dashboard (no automatic approval or outreach)
```

Use a separate Python worker/local single-job entrypoint first, composing selected Clearfront internals. Do not turn the inherited local web console into the public admin app or run external research subprocesses inside the dashboard. Source adapters, model adapter, evidence/resolution logic, storage repository, and report projection should be independently replaceable. A graph is a diagnostic projection, not a required service or database.

### Proposed source adapter contract

Each approved adapter declares source ID/category, permitted origins/access method, version, capabilities, and request/concurrency/response-size budgets. Inputs are typed owner/business/place/time queries, not arbitrary shell commands or unrestricted URLs. Outputs distinguish FOUND, NO_RESULTS, BLOCKED, RATE_LIMITED, and ERROR, with typed observations, originating record IDs/URLs, source title, retrieval UTC, source-valid dates, excerpt/locator, receipt digest, and request trace. An HTTP 200 empty result from an unavailable service is not evidence of absence.

Use sources in this order: official APIs/structured government datasets; downloadable official records; searchable official sites; reputable public-record sources; appropriate broader web; ordinary scraper/browser extraction only when cleaner methods are unavailable and the access is allowed. Approval includes terms, public accessibility, license, jurisdiction/sensitivity, maintenance, and identity relevance. Search vendors do not approve every destination they return.

Apify and Scrapling are optional extraction implementations behind this contract. Neither is installed, cloned, integrated, or required in this phase. Do not adopt `govdata-ai`, OSINT methodology repos, Dify, Resend, OpenSign, or other tools just because they appear in earlier planning. Evaluate only when a defined need arises. Outreach/signature systems are out of scope for the initial research worker.

### Claims, candidates, uncertainty, and scoring

- **Observed fact:** accurately describe what a particular retrieved record says, including dates and limitations. Source authenticity and claim truth remain evaluated, not guaranteed by retrieval.
- **Inferred relationship:** explicitly state the inference and link supporting claim IDs. A shared name/address or co-occurrence is not automatically a family/business relationship.
- **Candidate match:** a separate property-scoped hypothesis, supported by comparisons of several relevant attributes (such as full name, historical address, geography/time, business identifiers). Do not globally merge names or collect unrelated relatives opportunistically.
- **Contradiction:** retain mismatching attributes, impossible timelines, incompatible identities, and conflicting records alongside supportive material; flag unresolved material conflicts for review.
- **Unresolved question:** record missing/blocked/unverified information and a scoped next research step. No results or retrieval failure does not prove that someone lacks an attribute.

The future rubric must be deterministic/versioned or human-assisted with explainable factors, evidence IDs, alternative candidates, source independence, recency/temporal compatibility, and conflict handling. Numerical scores are workflow assessments, not calibrated probabilities unless separately validated. Broad repetition never promotes an inference into fact. Search snippets and mirrored records from a common origin count as one source family. Severe conflicts and name-only matches cannot receive HIGH_CONFIDENCE. Property value/opportunity/priority and personal reputation/security signals are excluded. HIGH_CONFIDENCE still means a proposed match for human review, never legal entitlement or outreach approval.

Reports should contain property/source identity, a candidate comparison, known observations, explicitly labeled inferences, supportive/conflicting evidence with record URLs/locators, unresolved questions, scoring rationale/version, source failures, scope/budget/run provenance, and a human-review disposition. Public contact details are permitted only when legitimately published and relevant; do not guess contacts or probe registration flows. Reports must be generated from stored structured results, not be the only evidence record.

## 8. Reuse versus replacement

| Decision | Components | Conditions |
| --- | --- | --- |
| Reuse nearly unchanged | Per-run `ToolCache` normalized keys/hit accounting; deterministic serialization/export helpers; exception/timeout patterns | Retain provenance and test isolation; cache is not durable state or source independence. Error-string cache exclusions are not a complete error contract |
| Wrap/adapt | Provider loops and `AgentResponse`/`ToolCall`; bounded BFS/parallel-target concepts; approved search backend results; Markdown/PDF renderer | Inject approved tools/typed results, add budget/cancellation/error controls, remove automatic unsafe routing, cite persisted evidence, avoid filename collisions |
| Replace | Owner identity model; heuristic graph confidence/corroboration; task/source prompts; string-only evidence; local session/report durability | Add candidate IDs, address/time/relationship semantics, independent-origin claims, explainable rubric, and Supabase repository |
| Keep outside worker | Unrestricted upstream registry, breach/account/exposure tools, Unlocker scraping, inherited web UI/setup and MCP publishing identity | Preserve upstream files for comparison; never expose by default. A future approved surface must delegate to the same enforcing dispatcher |
| Keep existing infrastructure | Six research tables, timestamp/review functions, separate human-review dashboard | No destructive migration; transaction and privilege additions considered only in a later scoped task |

## 9. Prioritized risks and acceptance gates

| Priority | Risk observed/inferred from implementation | Required gate before live operation |
| --- | --- | --- |
| Critical | Unrestricted and nested dispatch can execute prohibited collection | Default-deny dispatch with source/target/content checks; tests cover every entrypoint and nested call; no forbidden tool advertised or invoked |
| Critical | Same-name merge, fixed confidence, repeated-tool corroboration can overstate identity | Separate candidates, temporal/attribute evidence, independent-origin dedup, contradiction handling, versioned rubric tests |
| Critical | Public local console has no auth; broad worker DB credentials could impersonate reviewers | Retain dashboard boundary, no public upstream console, no credentials/model SQL tool, narrowly restricted worker storage authority |
| High | Volatile runs, pruned history, reports overwrite, no job claim/recovery | Durable attempt IDs, atomic claim/finish/events, idempotent writes, preserved prior decisions, explicit recovery/retry protocol |
| High | Tool failures returned as strings/empty graphs; limited source provenance | Typed outcomes/source receipts, distinguish errors from absence, preserve provenance/blocked queries and all contradictions |
| High | Scraped text can prompt-inject; URL guards do not prove all redirect/DNS/provider behavior safe | Treat documents as untrusted data; enforce destinations/content/size/time outside the model, check redirects/resolution, redact unexpected secrets and stop restricted access |
| Medium | Multiple hard-coded registries/loops drift; publisher identity still upstream | One approved dispatcher/contracts, parity tests, deliberate release metadata/task-specific configuration before publication |
| Medium | Broad/range/unpinned dependencies and dataset/service licenses | Minimal pinned runtime, reproducible locked install, advisory/license review, retained notices, source-specific data permissions |

These priorities describe adaptation gaps, not a claim that each is an exploited vulnerability. No offensive probes or live private-person investigations were performed.

## 10. Recommended adaptation sequence

1. **Preserve and document (this change).** Fork/clone/upstream remote, pinned provenance, project README/instructions, code audit and read-only database mapping. No runtime or DB changes.
2. **Build the safety boundary offline.** Implement an injected default-deny dispatcher and source registry; prohibit inherited unsafe paths including nested graph/multi-target paths. Add typed error/budget contracts and fixture-only tests. Keep existing operational entrypoints quarantined until all retained surfaces obey policy.
3. **Add one approved source adapter.** Choose a real official source/jurisdiction with the user, inspect existing components and terms, then prefer structured API/download access. Record receipts and implement a mock adapter first; search/fetch vendors remain optional. No automatic broad scrape adoption.
4. **Implement candidate/evidence contracts and assessment.** Names/addresses/dates/business attributes, separate hypotheses, inference support IDs, contradiction/source-family rules, unknown states, versioned rubric and report projection. Offline tests for duplicate-source repetition, common names, moves, business/person ambiguity, material conflict, and amount-invariant confidence.
5. **Implement the trusted Supabase repository and single-job runner.** Re-inspect live schema, decide narrowly scoped worker privileges and atomic transaction/RPC approach in a separate reviewed task. Preserve tables/functions/constraints/dashboard contracts. Add failure/retry/idempotency tests, no autonomous review/outreach paths. Provider selection and secure credential setup occur only when required for this implementation.
6. **Verify end to end on fixtures/test infrastructure.** Prove durable claim/run/evidence/event commits, safe crash recovery, typed failures, report citations, and reviewer visibility. Ensure reviewed candidates are not silently reset/overwritten and confidence cannot grant outreach.
7. **Run one explicitly approved bounded live test.** Use a legitimate property/source record, approved provider/access method, cost/call/time limits, and human review. Only then consider parallel execution, optional Apify/Scrapling adapters, or additional sources.

The smallest next implementation is step 2, **not** a full worker, replatformed dashboard, database rebuild, or live search of an individual. Choosing the first jurisdiction/source and the model provider can wait until their respective implementation steps.

## 11. Validation and limits of this phase

Static validation passed: 88 inherited Python files parsed without imports/execution, JSON/TOML metadata parsed, 51 local Markdown links resolved, and Git whitespace/scope checks passed. Exactly three documentation files changed; the original README is retained byte-for-byte after newline normalization, and inherited implementation/tests/packaging/license/dataset files are unchanged. The schema comparison was read-only. The inherited test suite was inspected but not run locally, and no upstream dependency was installed locally. No claim of passing live research, AI/provider calls, board endpoints, worker transactions, scoring, authorization enforcement, or dashboard integration is made.

This audit preserves the original implementation for intentional adaptation and documents its gaps. README/AGENTS warnings are guidance only; they do not disable inherited capabilities. Runtime safety, typed adapters, source approval, durable job execution, and owner-confidence evaluation remain future work.
