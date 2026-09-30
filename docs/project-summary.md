# Unclaimed Property Research Agent: project summary

As of 2026-09-30. This summarizes work completed in this project, not a certification of live services' current health. The latest safety implementation is on the review branch, not merged/deployed by this task. Earlier infrastructure/dashboard facts come from committed project records and the previous schema audit; this task does not redeploy or re-audit them.

## 1. Toolbox and engineering foundation — implemented

The original [researchagents-skills toolbox](https://github.com/survivorsystems/researchagents-skills) contains repository structure, research principles, architecture/workflow contracts, integration/skill/template planning, licensing/upstream notes, and Supabase migrations/validation SQL. It is reusable infrastructure, not the production application.

Rules established: public information only; reuse and adapters before rebuilding; multiple relevant identity attributes; source provenance and retained contradictions; opportunity independent of identity confidence; explicit human control; durable workflow state; no secrets in Git. Listed future components are evaluation candidates, not installed or working integrations.

## 2. Supabase research foundation — implemented

Oddly Functional has a separate `research_agent` schema with `property_records`, `research_jobs`, `research_runs`, `owner_candidates`, `evidence`, and `workflow_events`. Versioned migrations include constraints/indexes and composite foreign keys, non-cascading deletion, timestamp triggers/function, and a transactional human-review function.

RLS is enabled on the six tables. Browser `anon`/`authenticated` roles have no research schema/table/review privileges. Trusted server access can address the schema through the Data API. The previous Clearfront audit confirmed all six tables existed and contained zero rows at that audit time; this is not a new row-count claim.

`apply_human_review_decision` implements APPROVE, REJECT, and RESEARCH_MORE atomically with audit attribution. More-research requests queue a job; they do not execute research. Every branch keeps outreach disabled. Service-role authority is broad, so a future worker needs a narrower trusted storage boundary; current schema constraints alone do not prove a human made a privileged call.

## 3. Human-review dashboard — implemented separately and deployed

The separate private `survivorsystems/researchagent-dashboard` repository was built and deployed on Vercel. Project records describe Supabase email/password authentication, a server-side administrator allowlist, a property queue/details screen, candidate/confidence/evidence/source/workflow views, and transactional approve/reject/research-more actions. Server credentials stay outside browser code.

Earlier work addressed dashboard access/environment configuration, followed by the user's environment update and redeployment. Historical validation reported ten tests plus type/lint checks passing. This task did not re-run those checks, redeploy the dashboard, change passwords, or verify today's sign-in state. The dashboard does not run research jobs or approve/send outreach.

## 4. Clearfront fork and actual-code audit — completed

Created [survivorsystems/unclaimed-property-research-agent](https://github.com/survivorsystems/unclaimed-property-research-agent), cloned it separately from the toolbox/dashboard, and added the original repository as `upstream`. Baseline commit: `4fa50326283c77fad0d84e93d0367b50944fb8e3`. Upstream MIT copyright/permission notices and the separate WhatsMyName dataset CC BY-SA notice/history were preserved.

The [adaptation audit](clearfront-adaptation-audit.md) examined actual agent/provider loops, collectors, search vendors, correlation/graphs, confidence/evidence, persistence, reporting, API/UI/authentication, dependencies and CI. It mapped the implementation to the six existing tables and laid out a staged build order. Documentation was published in [PR #1](https://github.com/survivorsystems/unclaimed-property-research-agent/pull/1), without merging it as part of that task.

Key conclusions: reuse orchestration/cache/export patterns; replace broad collection policy, name-based identity merging, fixed graph confidence and repeated-tool corroboration; retain Supabase durability and the separate dashboard. Clearfront's local web console has no authentication and its local reports/history are not a durable job/evidence system. No unsafe collector was run during the audit and no database object/row was changed.

## 5. Public-source safety boundary — implemented and tested offline

Added [the boundary and operational guide](public-source-safety-boundary.md). The new standard-library dispatcher starts with an empty approval registry; validates source review/expiry, exact destinations and public DNS, typed queries/observations and provenance; rejects credential-shaped or classified nonpublic content; distinguishes blocked/error/no-results outcomes; and shares bounded call/output/time/concurrency/depth budgets across nested calls.

Preserved legacy collectors and CLI/REPL/web/MCP/agent/graph entrypoints are import-quarantined before their code/SDKs load. There is no environment-based bypass. Offline CI runs the boundary tests; the preserved upstream collector tests are not active because those imports are intentionally denied. This application guard is not a malicious-code sandbox or live HTTP transport.

No production source is approved, no provider credential is configured/used, no scraper installed, and no live research or database write performed in this phase. See the safety guide for transport/DNS/cancellation limits and future adapter requirements.

Local validation: 37 offline tests passed, plus Python syntax, documentation-link, whitespace and inherited-code/license preservation checks. No full upstream-suite or live-service success is claimed.

## 6. Still to build

- One explicitly approved official source/jurisdiction and its controlled transport/extraction adapter.
- Property ingestion/normalization and separate owner/business candidate hypotheses.
- Persisted evidence/claim contracts, temporal comparisons, independent-source semantics, contradictions, and explainable identity-confidence/ranking rubric.
- Narrow worker storage authority, atomic durable claim/run/complete transactions, idempotency, retries and crash recovery.
- Approved model adapter and credential setup if needed; a bounded single-job worker integrated with dashboard review.
- A controlled end-to-end fixture test, then one explicitly approved live property research test.
- Optional additional source adapters, parallel workers, outreach approval/delivery, and agreements/signatures only after their own scoped approval/implementation.

**Bottom line:** the engineering foundation, database and human-review surface exist; the Clearfront adaptation is audited and now has a tested default-deny safety layer. We do not yet have an end-to-end live owner-research agent. The next practical step is selecting one official source, not a database rebuild or automatic outreach.
