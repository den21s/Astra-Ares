# Adaptive effort experiment — 2026-10-19

Environment: Apple Silicon macOS, stock Codex 0.163.0 preserved, separately built patched Codex 0.155.0-alpha.9.2, `gpt-6.1-sol` through the existing cch Responses account. Evaluator: `gpt-5.6-terra`, low effort, through that same configured account. No new external evaluator account was enabled.

## Result

The integration works, but this small benchmark did **not** save money. Keep it as an explicitly launched experiment; stock Codex remains the default. No account-specific dollar saving is claimed.

Both arms answered all three synthetic tasks correctly. The middle task counts the exact interleavings of an idempotency race: 60 schedules produce one grant, 324 two grants, and 1296 three grants. The other tasks are trivial exact-string replies. Dynamic effort selected low → high → low; each selection was acknowledged by the actual native step before sampling.

| After resume fix                   | Fixed medium | Adaptive main model |
| ---------------------------------- | -----------: | ------------------: |
| Input tokens                       |       62,560 |              62,913 |
| Cached input tokens                |       45,184 |              28,544 |
| Output tokens, including reasoning |          294 |                 647 |
| Reasoning tokens, included above   |          264 |                 617 |
| Total elapsed time                 |      36.51 s |             45.25 s |
| Correct answers                    |        3 / 3 |               3 / 3 |

The adaptive arm additionally consumed **15,945 evaluator input tokens** (9,984 cached) and **60 evaluator output tokens**. These evaluator times are already included in total elapsed time. The lease choices were one generation each, so this sample amortized none of those evaluations across multiple generations.

This is a smoke comparison, not a broad coding-quality or statistically controlled cost study. Cache routing/residency fluctuated even in unchanged-effort controls, and generation length varies. It would be incorrect to attribute the full cache difference to effort changes. The benchmark's main-model output was nevertheless higher in the adaptive arm, and evaluator requests were additional work. Routine replies already consumed zero reasoning at medium; high added reasoning on a question medium answered correctly.

## Resume bug found and fixed

Before the fix, resuming the adaptive alias injected a 21,924-character `<model_switch>` developer message even though the underlying model stayed `gpt-6.1-sol`. That inflated subsequent requests by roughly 4,000 tokens each. Three-turn totals were 71,225 adaptive input tokens versus 62,701 fixed input tokens before the fix.

The model world-state comparison mixed a logical selector (`Sol-6.1-Jev`) with its physical model ID (`gpt-6.1-sol`). The fork now canonicalizes both identifiers before deciding whether model instructions changed. Real model changes still produce their instruction update. A native resume regression failed on the old executable, passed after rebuilding, and the new real rollout contains no false `<model_switch>` message.

## Cache probe limits

Early CLI measurements showed 99.14% cached input before a first switch to high and 53.94% afterward. That observation alone did not identify a cause. Later fixed-medium requests also dropped to around 41% in the smaller API probe. Native `configuration_update` calls were accepted by the gateway, but both fixed and updated configurations experienced misses. Native local fixtures prove an unchanged request prefix; they do not guarantee backend cache retention or routing.

## Verification performed

- 72 JavaScript tests passed, including evaluator validation, cancellation, credential references, preserved primary profile settings and routing affinity.
- Actual patched-executable context, session, four model-selection suites (including 6.1), and macOS desktop **fixtures** passed. These desktop fixtures do not mean the real desktop application was replaced or tested.
- The complete distributed patch applied cleanly to pristine archived upstream files; checksums were updated.
- A real evaluator probe and the installed `astra-ares` command using its imported profile completed successfully.
- The six-call fixed/adaptive comparison passed the exact-answer oracle after the resume fix.
- Formatting and diff checks passed. Build processes exited under the resource guard; existing peer processes were preserved.

Raw synthetic usage records, launcher output and native fixture evidence are retained locally under ignored `work/`. Credentials and full task histories are not committed. Reproduction commands and configuration details are in [cch-integration.md](cch-integration.md).
