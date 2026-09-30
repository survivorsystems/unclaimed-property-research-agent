# Repository instructions

## Current stage

This is the Clearfront-based Unclaimed Property Research Agent fork. An offline-tested default-deny public-source boundary is implemented under `clearfront/public_sources/`; no production source adapter or worker exists. Upstream collectors/provider code/tests remain preserved, but normal imports of collectors and legacy entrypoints are quarantined in package initialization. Read `docs/public-source-safety-boundary.md` and the baseline `docs/clearfront-adaptation-audit.md` before substantial work. Distinguish implemented behavior from plans.

## Reuse and provenance

Inspect existing implementation and approved upstream code before rebuilding. Prefer reuse, adapters, and composition. Do not adopt a dependency just because it appears in planning documents. Inspect implementation, maintenance, security, and license before adoption. Preserve upstream history, MIT copyright notices, the dataset's CC BY-SA notice at `clearfront/tools/data/NOTICE`, and the `upstream` remote. Never push to upstream or publish inherited Clearfront package/plugin/MCP identities as this project.

## Research and operation

- Use only legitimately public information from explicitly approved sources.
- Do not research with passwords/credentials, private accounts/messages, breach/leak data, restricted investigator databases, access-control circumvention, or account-registration/password-reset probing.
- Do not run/deploy/install/register inherited CLI, REPL, web, MCP, Docker, or graph workflows as this project's worker. Do not remove/bypass the import quarantine to re-enable their unrestricted registries. There is intentionally no environment-variable bypass. Retain it until approved provider/transport/entrypoint adapters are separately implemented and verified.
- Do not install external OSINT binaries or enable providers merely to complete a documentation audit.
- Keep source receipts, material-claim provenance, observation timestamps, and contradictory evidence. Multiple tools finding the same underlying source are not independent corroboration.
- Preserve separate candidates for same-name people. Require multiple relevant identity attributes; treat inferred relationships and search snippets as leads, not established identity facts.
- Property value and opportunity must never influence identity confidence.
- AI may research, summarize, assist with confidence, and draft. It must never approve candidates or outreach, impersonate a reviewer, or call the human-review RPC.

## Existing infrastructure

Oddly Functional's `research_agent` schema remains the system of record. Do not drop, recreate, rename, overwrite, or destructively migrate its objects. Read-only inspection is appropriate for audits. Any later additive schema changes require a separate reviewed implementation task and preservation of current access restrictions. Leave unrelated schemas and projects untouched.

Keep trusted database/provider configuration outside model inputs and browser code. Do not expose secrets, read secret values for reports, or commit `.env` or other secret-bearing files. The current `service_role` can bypass RLS; application instructions alone do not restrict its authority. Plan a narrowly scoped worker storage boundary before live execution.

## Engineering

Keep external sources, extraction vendors, model providers, and storage behind explicit interfaces. Apify or Scrapling must not be mandatory. Preserve testability, source-policy enforcement at dispatch (including nested calls), typed errors, budgets, idempotency, and durable job/run state. Do not use agent conversations, graphs, or local report files as the sole system of record.

For boundary work, use the standard-library offline suite: `python -m unittest discover -s tests -p test_public_source_boundary.py -v`. Tests may prove legacy module imports/console launches are refused before their source or SDKs load. Do not run the historical upstream suite by disabling the guard. No model/provider key is needed for the boundary. Before later API-backed work, follow the applicable credential-setup skill without printing secrets.
