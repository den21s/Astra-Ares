import test from "node:test";
import assert from "node:assert/strict";
import {
  mkdtempSync,
  mkdirSync,
  writeFileSync,
  readFileSync,
  readlinkSync,
  realpathSync,
  rmSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { spawnSync } from "node:child_process";

test("profile import preserves primary settings and references existing credentials", () => {
  const root = mkdtempSync(join(tmpdir(), "ares-profile-test-"));
  try {
    const source = join(root, "source"),
      target = join(root, "target"),
      catalog = join(root, "models.json");
    mkdirSync(source);
    const original =
      'model = "gpt-6.1-sol"\nmodel_provider = "test"\nnotify = ["retained-hook"]\n[model_providers.test]\nname = "test"\nbase_url = "http://127.0.0.1:1234/v1"\nwire_api = "responses"\n[mcp_servers.fixture]\ncommand = "retained-command"\n';
    writeFileSync(join(source, "config.toml"), original);
    writeFileSync(
      join(source, "auth.json"),
      '{"OPENAI_API_KEY":"synthetic-secret"}',
    );
    writeFileSync(
      catalog,
      JSON.stringify({
        models: [{ slug: "gpt-6.1-sol", use_responses_lite: true }],
      }),
    );
    const args = [
      resolve("scripts/init-cch-profile.py"),
      "--source",
      source,
      "--target",
      target,
      "--model-catalog",
      catalog,
    ];
    const result = spawnSync("python3", args, { encoding: "utf8" });
    assert.equal(result.status, 0, result.stderr);
    assert.equal(readFileSync(join(source, "config.toml"), "utf8"), original);
    const config = readFileSync(join(target, "config.toml"), "utf8");
    assert.match(config, /model = "Sol-6.1-Jev"/);
    assert.match(config, /name = "OpenAI"/);
    assert.match(config, /retained-command/);
    assert.match(config, /retained-hook/);
    assert.equal(
      readlinkSync(join(target, "auth.json")),
      realpathSync(join(source, "auth.json")),
    );
    assert(!config.includes("synthetic-secret"));
    const retry = spawnSync("python3", args, { encoding: "utf8" });
    assert.notEqual(retry.status, 0);
    assert.equal(readFileSync(join(target, "config.toml"), "utf8"), config);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});
