# Existing Responses account integration (this fork)

This fork adds `gpt-6.1-sol` / **Sol 6.1 Ares** and a Responses-based evaluator. Both the coding model and evaluator can use the same explicitly configured gateway/account. It does not require a Jev, OpenRouter, or Vercel account. The coding model stays fixed; the evaluator chooses effort and lease duration.

This is a separately built CLI based on upstream's pinned **0.155.0-alpha.9.2**, not an extension loaded into stock Codex. Keep stock Codex installed. No cost saving is promised: include evaluator input/output, cache misses, latency and correctness in comparisons.

## Configure the evaluator

Use an exact model supported by your account. The deployment tested `gpt-5.6-terra` with low evaluator effort; this is an integration check, not a claim that it is your cheapest available model.

```sh
node bin/ares.mjs configure --provider responses \
  --base-url http://YOUR-GATEWAY/v1 \
  --decision-model gpt-5.6-terra --context-token-limit 28000 \
  --codex-auth-file "$HOME/.codex/auth.json"
```

The auth reference supports an existing API-key login (`OPENAI_API_KEY` in Codex auth.json). It does not copy the key into Ares config. The key is read at launcher startup, so credential rotations are picked up on the next launch. Alternatively configure a private key using `--key-stdin` or the standard credential fields. Endpoint and model are explicit; no provider/model fallback occurs. A failed or refused evaluation stops the turn visibly.

The evaluator receives the same bounded public task/progress/tool context described in the upstream README, through the gateway you select. Its response must match a strict schema and the exact requested model ID. Refusals, unsupported efforts, invalid leases and incomplete generations cannot become applied settings. Cost is recorded as `null` because gateway-specific prices are not known; evaluator token usage and latency are recorded separately.

## Isolated coding profile

Get the model catalog from trusted upstream Codex metadata for the installed stock version. Do not invent a catalog by renaming another model: the native checkpoint requires genuine model capabilities. The tested installation uses the `gpt-6.1-sol` entry from `openai/codex` tag `rust-v0.163.0`, downloaded from `codex-rs/models-manager/models.json`.

```sh
python3 scripts/init-cch-profile.py --model-catalog /absolute/path/to/models.json
```

This snapshots the current primary config into Ares's independent profile, selects `Sol-6.1-Jev`, and links existing auth, instructions, skills, rules, hooks and plugins. The primary config is never modified. Review future stock-Codex upgrades separately; the old pinned runtime may not recognize every newer setting. The importer refuses to overwrite an existing target configuration.

The selected custom provider retains its endpoint and credentials. Its compatibility `name` becomes `OpenAI`, because the pinned native code gates configuration updates on that name. This does **not** change the endpoint or claim that a gateway is OpenAI-operated. Native `use_responses_lite` metadata is also required.

Start an experimental session:

```sh
astra-ares -C /path/to/project
# Select Sol 6.1 Ares if needed.
```

Stock `codex` and already-running desktop sessions keep using their existing runtime. Desktop replacement is a separate operation and has not been performed for this integration.

When passing per-invocation `-c` overrides for `exec`, put them at the root, before `exec`, so they merge with the launcher's required feature flags. On this pinned CLI, config overrides placed only after `exec` can shadow root overrides.

## Verification

```sh
npm test
JEV_TEST_BINARY="$HOME/.local/share/astra-ares/bin/codex" npm run test:native
node bin/ares.mjs doctor --probe
```

The native suites use the real patched binary and local fixtures. They prove prefix preservation at the request boundary, application acknowledgement, cancellation, resume and model selection (including 6.1), not gateway cache hit rate or dollar savings.

These live scripts spend account usage and send only their generated synthetic tasks:

```sh
python3 scripts/cache-probe.py --mode fixed --output work/fixed.json
python3 scripts/cache-probe.py --mode update --output work/update.json
python3 scripts/cache-probe.py --mode request --output work/request.json
python3 scripts/live-compare.py
```

The cache probe waits for a warm medium prefix before testing changes, preserves original output items, pins request-level medium in update mode, and records per-request usage. The fixed arm is essential: a cache miss after changing effort does not establish that the change caused the miss. On this gateway, misses also appeared with unchanged effort. Matching a prefix does not guarantee cache residency or routing.

The comparison uses the same native binary in both arms and an exact-answer concurrency oracle (one/two/three grants in 60/324/1296 of 1680 interleavings). It includes the evaluator's usage and refuses to claim equal quality if an answer fails. Three synthetic turns are not a representative coding benchmark.

Configuration updates are limited to supported standard single-agent requests. Automatic compaction/truncation and standalone compaction have compatibility restrictions; long-session compaction is not accepted by these smoke tests. See [official reasoning documentation](https://developers.openai.com/api/docs/guides/reasoning#change-reasoning-mid-conversation).

## Measured outcome

See the [2026-10-19 experiment](experiment-2026-10-19.md). Dynamic low → high → low worked, but this small exact-answer benchmark cost more than fixed medium, even after fixing the false model-switch instructions injected on resume. Keep the adaptive CLI opt-in.
