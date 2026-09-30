"""Offline boundary regression tests: stdlib only; no SDKs, DB, or HTTP."""

import asyncio
from datetime import datetime, timedelta, timezone
import importlib
from pathlib import Path
import socket
import unittest
from unittest.mock import patch

from clearfront.public_sources import (
    Access, Adapter, Approval, Boundary, Budget, Observation, Outcome,
    Query, Result, Scope, Violation,
)
from clearfront.public_sources.quarantine import (
    LegacyResearchDisabled, QUARANTINED_MODULES, install_quarantine,
)


def approval(source_id="official-fixture", **changes):
    values = dict(
        source_id=source_id, scopes=(Scope("https://records.example", "/records/", {"q"}),),
        reviewed_by="fixture-reviewer", review_reference="offline-fixture-only",
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    values.update(changes)
    return Approval(**values)


def observation(**changes):
    values = dict(
        source_url="https://records.example/records/123", source_record_id="123",
        origin_record_id="official-fixture:123", title="Synthetic official record",
        excerpt="Example Owner is listed at Example City.",
        retrieved_at=datetime.now(timezone.utc),
    )
    values.update(changes)
    return Observation(**values)


async def fixture(ctx, query):
    return Result(Outcome.FOUND, (observation(),))


class BoundaryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Any accidental real DNS resolution fails the test; mocks are explicit.
        self.dns_guard = patch.object(socket, "getaddrinfo", side_effect=AssertionError("Real DNS forbidden"))
        self.dns_guard.start()
        self.addCleanup(self.dns_guard.stop)
        self.query = Query("Example Owner", "Example City", 2001)

    def boundary(self, collect=fixture, *, resolver=lambda host: ("8.8.8.8",), spec=None):
        return Boundary((Adapter(spec or approval(), collect),), resolver=resolver)

    async def test_default_registry_denies_every_legacy_and_unknown_source(self):
        boundary = Boundary()
        self.assertEqual(boundary.source_ids, ())
        names = [p.stem for p in Path("clearfront/tools").glob("*.py")]
        names += ["investigate_graph", "investigate_multi", "official-fixture", "scrape_url"]
        for name in names:
            with self.subTest(name=name):
                result = await boundary.dispatch(name, self.query)
                self.assertEqual((result.outcome, result.code), (Outcome.BLOCKED, "SOURCE_NOT_APPROVED"))

    async def test_approved_fixture_preserves_provenance_not_identity_claim(self):
        result = await self.boundary().dispatch("official-fixture", self.query)
        self.assertEqual(result.outcome, Outcome.FOUND)
        self.assertEqual(result.observations[0].origin_record_id, "official-fixture:123")
        self.assertEqual(result.observations[0].claim_kind, "SOURCE_OBSERVATION")

    async def test_unapproved_source_never_invokes_adapter(self):
        async def forbidden(ctx, query):
            self.fail("Adapter executed before authorization")
        result = await self.boundary(forbidden).dispatch("unknown", self.query)
        self.assertEqual(result.outcome, Outcome.BLOCKED)

    async def test_key_presence_does_not_authorize_sources(self):
        with patch.dict("os.environ", {"HIBP_API_KEY": "fixture-key", "BRIGHTDATA_API_KEY": "fixture-key"}):
            self.assertEqual((await Boundary().dispatch("search_breach", self.query)).outcome, Outcome.BLOCKED)

    async def test_expired_approval_does_not_execute(self):
        spec = approval(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        self.assertEqual((await self.boundary(spec=spec).dispatch("official-fixture", self.query)).code,
                         "APPROVAL_EXPIRED")

    async def test_queries_are_typed_and_exclude_credentials_and_amount(self):
        for query in ({"owner_name": "Example", "password": "fake"}, Query("password=fixture"),
                      Query("sk-" + "A" * 24), Query("Example", year=True), Query("Example\nInjected")):
            self.assertEqual((await self.boundary().dispatch("official-fixture", query)).outcome, Outcome.BLOCKED)
        with self.assertRaises(TypeError):
            Query("Example", reported_amount=1000000)

    async def test_no_results_distinct_from_errors(self):
        async def empty(ctx, query):
            return Result(Outcome.NO_RESULTS)
        async def failed(ctx, query):
            raise RuntimeError("password=fixture-secret")
        self.assertEqual((await self.boundary(empty).dispatch("official-fixture", self.query)).outcome,
                         Outcome.NO_RESULTS)
        result = await self.boundary(failed).dispatch("official-fixture", self.query)
        self.assertEqual((result.outcome, result.code), (Outcome.ERROR, "ADAPTER_ERROR"))
        self.assertNotIn("fixture-secret", repr(result))

    async def test_unavailable_results_discard_untrusted_payloads(self):
        for outcome in (Outcome.BLOCKED, Outcome.RATE_LIMITED, Outcome.ERROR):
            async def collect(ctx, query):
                return Result(outcome, (observation(excerpt="password=fixture-secret"),), "fixture-secret")
            result = await self.boundary(collect).dispatch("official-fixture", self.query)
            self.assertEqual(result.outcome, outcome)
            self.assertEqual(result.observations, ())
            self.assertNotIn("fixture-secret", repr(result))

    async def test_adapters_cannot_report_nonpublic_or_secret_content(self):
        for item in (observation(access=Access.REQUIRES_LOGIN), observation(access=Access.RESTRICTED),
                     observation(access=Access.BREACH_OR_LEAK), observation(access="PUBLIC"),
                     observation(excerpt="-----BEGIN PRIVATE KEY-----"),
                     observation(excerpt="Bearer fixture-secret")):
            async def collect(ctx, query):
                return Result(Outcome.FOUND, (item,))
            result = await self.boundary(collect).dispatch("official-fixture", self.query)
            self.assertEqual(result.outcome, Outcome.BLOCKED)
            self.assertEqual(result.observations, ())

    async def test_observation_must_have_valid_provenance(self):
        for item in (observation(origin_record_id=""), observation(claim_kind="CONFIRMED_OWNER"),
                     observation(retrieved_at=datetime(2000, 1, 1)), observation(excerpt="")):
            async def collect(ctx, query):
                return Result(Outcome.FOUND, (item,))
            self.assertEqual((await self.boundary(collect).dispatch("official-fixture", self.query)).outcome,
                             Outcome.BLOCKED)

    async def test_inconsistent_or_malformed_adapter_results_blocked(self):
        for value in ("raw text", Result("FOUND"), Result(Outcome.FOUND),
                      Result(Outcome.NO_RESULTS, (observation(),)), Result(Outcome.FOUND, [observation()]),
                      Result(Outcome.FOUND, ("not an observation",))):
            async def collect(ctx, query):
                return value
            self.assertEqual((await self.boundary(collect).dispatch("official-fixture", self.query)).outcome,
                             Outcome.BLOCKED)

    async def check_url(self, url, *, resolver=lambda host: ("8.8.8.8",)):
        async def collect(ctx, query):
            await ctx.authorize_destination(url)
            return Result(Outcome.NO_RESULTS)
        return await self.boundary(collect, resolver=resolver).dispatch("official-fixture", self.query)

    async def test_approved_origin_path_query(self):
        result = await self.check_url("https://records.example/records/123?q=Example+Owner")
        self.assertEqual(result.outcome, Outcome.NO_RESULTS)

    async def test_urls_reject_origin_confusion_private_hosts_and_traversal(self):
        urls = [
            "http://records.example/records/123", "file:///records/123",
            "https://records.example.attacker.example/records/123",
            "https://sub.records.example/records/123", "https://user@records.example/records/123",
            "https://records.example:8443/records/123", "https://records.example./records/123",
            "https://records.example/records-admin/123", "https://records.example/private/123",
            "https://records.example/records/../private", "https://records.example/records/%2e%2e/private",
            "https://records.example/records/%252e%252e/private",
            "https://records.example/records//123", "https://records.example/records/123;admin",
            "https://records.example/records/123#private", "https://records.example/records/123?token=secret",
            "https://records.example/records/123?q=One&q=Two",
            "https://records.example/records/123?q=password%3Dfixture",
            "https://127.0.0.1/records/123", "https://169.254.169.254/records/123",
            "https://metadata.internal/records/123", "https://localhost/records/123",
            "https://records.example\\@private.example/records/123",
            "https://records.example/records/123\n", "https://records.example/records/%2fprivate",
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual((await self.check_url(url)).outcome, Outcome.BLOCKED)

    async def test_dns_must_resolve_exclusively_to_public_addresses(self):
        for ips in ((), ("127.0.0.1",), ("10.0.0.1",), ("169.254.169.254",), ("::1",),
                    ("fc00::1",), ("224.0.0.1",), ("ff02::1",), ("0.0.0.0",),
                    ("8.8.8.8", "192.168.1.1"), ("invalid",)):
            with self.subTest(ips=ips):
                self.assertEqual((await self.check_url("https://records.example/records/123",
                                 resolver=lambda host: ips)).outcome, Outcome.BLOCKED)

    async def test_dns_failure_is_not_no_results(self):
        def broken(host):
            raise OSError("private resolver detail")
        result = await self.check_url("https://records.example/records/123", resolver=broken)
        self.assertEqual(result.code, "DESTINATION_RESOLUTION_FAILED")

    async def test_redirect_destination_requires_independent_authorization(self):
        async def collect(ctx, query):
            await ctx.authorize_destination("https://records.example/records/123")
            await ctx.authorize_destination("https://private.example/login")
            return Result(Outcome.NO_RESULTS)
        result = await self.boundary(collect).dispatch("official-fixture", self.query)
        self.assertEqual(result.code, "DESTINATION_NOT_APPROVED")

    async def test_nested_calls_deny_unapproved_sources(self):
        async def collect(ctx, query):
            return await ctx.dispatch("search_breach", query)
        result = await self.boundary(collect).dispatch("official-fixture", self.query)
        self.assertEqual(result.outcome, Outcome.BLOCKED)

    async def test_nested_calls_share_call_budget(self):
        async def recurse(ctx, query):
            return await ctx.dispatch("official-fixture", query)
        boundary = self.boundary(recurse)
        run = boundary.new_run(Budget(max_calls=2))
        result = await boundary.dispatch("official-fixture", self.query, run=run)
        self.assertEqual(result.outcome, Outcome.BLOCKED)
        self.assertEqual(run.calls, 2)
        self.assertEqual(run.active, 0)

    async def test_nested_depth_is_bounded(self):
        async def recurse(ctx, query):
            return await ctx.dispatch("official-fixture", query)
        boundary = self.boundary(recurse)
        run = boundary.new_run(Budget(max_depth=1))
        result = await boundary.dispatch("official-fixture", self.query, run=run)
        self.assertEqual(result.outcome, Outcome.BLOCKED)
        self.assertEqual(run.calls, 2)

    async def test_concurrent_calls_cannot_overdraw_budget(self):
        async def empty(ctx, query):
            await asyncio.sleep(0)
            return Result(Outcome.NO_RESULTS)
        boundary = self.boundary(empty)
        run = boundary.new_run(Budget(max_calls=2))
        results = await asyncio.gather(*(boundary.dispatch("official-fixture", self.query, run=run)
                                         for _ in range(6)))
        self.assertEqual(sum(r.outcome == Outcome.NO_RESULTS for r in results), 2)
        self.assertEqual(run.calls, 2)

    async def test_active_call_budget(self):
        async def empty(ctx, query):
            await asyncio.sleep(0)
            return Result(Outcome.NO_RESULTS)
        boundary = self.boundary(empty)
        run = boundary.new_run(Budget(max_active_calls=1))
        results = await asyncio.gather(*(boundary.dispatch("official-fixture", self.query, run=run)
                                         for _ in range(2)))
        self.assertEqual(sum(r.outcome == Outcome.BLOCKED for r in results), 1)

    async def test_timeout_is_explicit_and_cleans_active_counter(self):
        async def slow(ctx, query):
            await asyncio.sleep(1)
        boundary = self.boundary(slow)
        run = boundary.new_run(Budget(timeout_seconds=0.01))
        result = await boundary.dispatch("official-fixture", self.query, run=run)
        self.assertEqual(result.outcome, Outcome.TIMEOUT)
        self.assertEqual(run.active, 0)

    async def test_cancellation_propagates_and_records_safe_event(self):
        async def cancelled(ctx, query):
            raise asyncio.CancelledError()
        boundary = self.boundary(cancelled)
        run = boundary.new_run()
        with self.assertRaises(asyncio.CancelledError):
            await boundary.dispatch("official-fixture", self.query, run=run)
        self.assertEqual(run.active, 0)
        self.assertEqual(run.events[-1]["code"], "CANCELLED")

    async def test_expired_run_budget(self):
        boundary = self.boundary()
        run = boundary.new_run()
        run.deadline = 0
        self.assertEqual((await boundary.dispatch("official-fixture", self.query, run=run)).code,
                         "RUN_BUDGET_EXCEEDED")

    async def test_result_size_and_count_budgets(self):
        boundary = self.boundary()
        self.assertEqual((await boundary.dispatch("official-fixture", self.query,
                         run=boundary.new_run(Budget(max_result_bytes=20)))).outcome, Outcome.BLOCKED)
        run = boundary.new_run(Budget(max_observations=1))
        self.assertEqual((await boundary.dispatch("official-fixture", self.query, run=run)).outcome,
                         Outcome.FOUND)
        self.assertEqual((await boundary.dispatch("official-fixture", self.query, run=run)).code,
                         "RESULT_BUDGET_EXCEEDED")

    async def test_result_urls_are_checked_even_if_adapter_forgets(self):
        async def collect(ctx, query):
            return Result(Outcome.FOUND, (observation(source_url="https://private.example/records/123"),))
        self.assertEqual((await self.boundary(collect).dispatch("official-fixture", self.query)).outcome,
                         Outcome.BLOCKED)

    async def test_events_do_not_contain_inputs_or_error_details(self):
        boundary = self.boundary()
        run = boundary.new_run()
        await boundary.dispatch("official-fixture", Query("password=fixture-secret"), run=run)
        self.assertNotIn("fixture-secret", repr(run.events))
        self.assertNotIn("password", repr(run.events))

    async def test_concurrent_results_cannot_overdraw_shared_output_budget(self):
        boundary = self.boundary()
        run = boundary.new_run(Budget(max_observations=1))
        results = await asyncio.gather(*(boundary.dispatch("official-fixture", self.query, run=run)
                                         for _ in range(4)))
        self.assertEqual(sum(r.outcome == Outcome.FOUND for r in results), 1)
        self.assertEqual(run.observations, 1)

    async def test_ignored_cancellation_cannot_return_late_success(self):
        async def ignores_timeout(ctx, query):
            try:
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                return Result(Outcome.NO_RESULTS)
        boundary = self.boundary(ignores_timeout)
        run = boundary.new_run(Budget(timeout_seconds=0.01))
        self.assertEqual((await boundary.dispatch("official-fixture", self.query, run=run)).outcome,
                         Outcome.TIMEOUT)

    async def test_repeated_denials_cannot_grow_event_buffer_without_limit(self):
        boundary = Boundary()
        run = boundary.new_run(Budget(max_events=2))
        for _ in range(5):
            await boundary.dispatch("unknown", self.query, run=run)
        self.assertEqual(len(run.events), 2)
        self.assertEqual(run.dropped_events, 3)


class ConfigurationTests(unittest.TestCase):
    def test_immutable_registry_and_duplicate_sources(self):
        adapter = Adapter(approval(), fixture)
        with self.assertRaises(Violation):
            Boundary((adapter, adapter))
        with self.assertRaises(TypeError):
            Boundary((adapter,))._registry["other"] = adapter

    def test_invalid_approval_scope_and_access_modes(self):
        for kwargs in (dict(scopes=()), dict(reviewed_by=""), dict(access_method="WEB_UNLOCKER"),
                       dict(access_method="PRIVATE_DATABASE"), dict(expires_at=datetime(2000, 1, 1))):
            with self.assertRaises(Violation):
                approval(**kwargs)
        for args in (("https://*.example", "/records/"), ("https://records.example/", "/records/"),
                     ("https://records.example", "/records"), ("https://records.example", "/../records/")):
            with self.assertRaises(Violation):
                Scope(*args)
        with self.assertRaises(Violation):
            Scope("https://records.example", "/records/", {"token"})

    def test_invalid_budgets(self):
        for kwargs in (dict(max_calls=0), dict(max_depth=True), dict(timeout_seconds=float("nan")),
                       dict(timeout_seconds=0), dict(run_seconds=301)):
            with self.assertRaises(Violation):
                Budget(**kwargs)

    def test_every_preserved_entrypoint_and_collector_is_quarantined_before_import(self):
        names = set(QUARANTINED_MODULES)
        names.update("clearfront.tools." + path.stem for path in Path("clearfront/tools").glob("*.py"))
        for name in sorted(names):
            with self.subTest(name=name), self.assertRaises(LegacyResearchDisabled):
                importlib.import_module(name)

    def test_quarantine_installation_is_idempotent(self):
        import sys
        before = len(sys.meta_path)
        install_quarantine()
        self.assertEqual(len(sys.meta_path), before)

    def test_preserved_graph_exports_still_import(self):
        module = importlib.import_module("clearfront.correlation")
        self.assertEqual(module.EntityGraph().to_dict(), {"nodes": [], "links": []})

    def test_console_web_mcp_and_graph_fail_before_sdk_loading_in_fresh_process(self):
        import subprocess
        import sys
        for name in ("clearfront.cli", "clearfront.mcp_server", "clearfront.web_server", "clearfront.pivot"):
            with self.subTest(name=name):
                result = subprocess.run([sys.executable, "-m", name], capture_output=True, text=True,
                                        timeout=10, check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("LegacyResearchDisabled", result.stderr)


if __name__ == "__main__":
    unittest.main()
