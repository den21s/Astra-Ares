import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { ResponsesEvaluator } from "../src/responses-evaluator.mjs";
import { validateConfig, readKey } from "../src/config.mjs";

const state = {
  model: "gpt-6.1-sol",
  supportedEfforts: ["low", "medium", "high"],
  latestUserPrompt: "Reply OK",
  publicNotes: [],
  recentToolCalls: [],
};
const options = {
  apiKey: "private-fixture-key",
  baseUrl: "http://127.0.0.1:1234/v1",
  decisionModel: "fixture-router",
  contextTokenLimit: 28000,
};
function reply(choice = { effort: "low", lease: "2" }, changes = {}) {
  return {
    model: "fixture-router",
    status: "completed",
    output: [
      {
        type: "message",
        content: [{ type: "output_text", text: JSON.stringify(choice) }],
      },
    ],
    usage: {
      input_tokens: 100,
      input_tokens_details: { cached_tokens: 50 },
      output_tokens: 10,
    },
    ...changes,
  };
}
test("Responses evaluator uses explicit endpoint, offered schema and reports evaluator overhead", async () => {
  const evaluator = new ResponsesEvaluator({
    ...options,
    fetchImpl: async (url, request) => {
      assert.equal(url, options.baseUrl + "/responses");
      const body = JSON.parse(request.body);
      assert.equal(body.store, false);
      assert.equal(body.model, options.decisionModel);
      assert.deepEqual(
        body.text.format.schema.properties.effort.enum,
        state.supportedEfforts,
      );
      assert.equal(body.reasoning.effort, "low");
      assert.equal(request.redirect, "error");
      return Response.json(reply());
    },
  });
  const result = await evaluator.decide(state);
  assert.equal(result.effort, "low");
  assert.equal(result.leaseSteps, 2);
  assert.equal(result.usage.cachedInputTokens, 50);
  assert.equal(result.cost, null);
});
test("invalid decisions, incomplete responses and model substitution never become settings", async () => {
  for (const body of [
    reply({ effort: "max", lease: "2" }),
    reply({ effort: "low", lease: "99" }),
    reply(undefined, { status: "incomplete" }),
    reply(undefined, { model: "different" }),
    reply(undefined, {
      output: [
        { type: "message", content: [{ type: "refusal", refusal: "No" }] },
      ],
    }),
  ]) {
    await assert.rejects(
      new ResponsesEvaluator({
        ...options,
        fetchImpl: async () => Response.json(body),
      }).decide(state),
    );
  }
});
test("errors do not echo credential or untrusted provider body and never silently retry", async () => {
  let calls = 0;
  const e = new ResponsesEvaluator({
    ...options,
    fetchImpl: async () => {
      calls++;
      return new Response("private-fixture-key", { status: 503 });
    },
  });
  await assert.rejects(
    e.decide(state),
    (error) => error.message === "Responses evaluator HTTP 503",
  );
  assert.equal(calls, 1);
});
test("cancellation and context overflow prevent sending a decision request", async () => {
  let calls = 0;
  const e = new ResponsesEvaluator({
    ...options,
    fetchImpl: async () => {
      calls++;
      return Response.json(reply());
    },
  });
  const controller = new AbortController();
  controller.abort();
  await assert.rejects(e.decide(state, { signal: controller.signal }));
  await assert.rejects(
    new ResponsesEvaluator({
      ...options,
      contextTokenLimit: 1,
      fetchImpl: e.fetchImpl,
    }).decide(state),
  );
  assert.equal(calls, 0);
});
test("Codex credential reference reads rotations without copying or echoing credentials", () => {
  const dir = mkdtempSync(join(tmpdir(), "ares-auth-test-"));
  const file = join(dir, "auth.json");
  try {
    const config = validateConfig({
      provider: "responses",
      baseUrl: options.baseUrl,
      decisionModel: options.decisionModel,
      contextTokenLimit: 28000,
      codexAuthFile: file,
    });
    writeFileSync(file, JSON.stringify({ OPENAI_API_KEY: "first" }));
    assert.equal(readKey(config), "first");
    writeFileSync(file, JSON.stringify({ OPENAI_API_KEY: "second" }));
    assert.equal(readKey(config), "second");
    writeFileSync(file, "secret malformed");
    assert.throws(
      () => readKey(config),
      (error) => !error.message.includes("secret"),
    );
    assert.throws(() => validateConfig({ ...config, provider: "local" }));
    assert.throws(() => validateConfig({ ...config, apiKey: "another" }));
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("routing affinity remains separate from the main thread account", async () => {
  const evaluator = new ResponsesEvaluator({
    ...options,
    fetchImpl: async (_url, request) => {
      const body = JSON.parse(request.body);
      assert.equal(body.prompt_cache_key, "ares-evaluator:fixture-thread");
      assert.equal(
        request.headers["session-id"],
        "ares-evaluator:fixture-thread",
      );
      return Response.json(reply());
    },
  });
  await evaluator.decide(state, { trace: { threadId: "fixture-thread" } });
});
