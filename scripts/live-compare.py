#!/usr/bin/env python3
"""Small synthetic correctness/usage comparison using the built native CLI.

This measures tokens and evaluator overhead, not account-specific dollar costs.
Both arms use the same pinned binary, provider, catalog and three tasks. It is a
smoke benchmark, not evidence of coding quality across representative workloads.
"""
import json
import os
from pathlib import Path
import subprocess
import time
import tomllib

ROOT = Path(__file__).resolve().parent.parent
HOME = Path.home() / '.local/share/astra-ares'
TASKS = [
    'Synthetic benchmark. Do not use tools or read files. Reply exactly OK.',
    'Synthetic concurrency benchmark. Do not use tools or read files. Three workers process the same idempotency key. Each worker has three ordered slots R,C,W; there are 1680 distinct interleavings preserving each worker order, all equally counted. Initially the shared ledger is absent. R records locally whether the ledger is absent. C increments a shared atomic grant counter if and only if that worker recorded absent. W marks the ledger present if and only if that worker recorded absent. C and W do nothing otherwise, but still occupy their slots. Sequential consistency holds and slots are indivisible. Determine the exact number of interleavings ending with one, two, or three grants. You must account for the read/write race and count schedules exactly, not estimate probabilities. Return ONLY a JSON object with integer keys "one", "two", "three".',
    'Synthetic benchmark. Do not use tools or read files. Reply exactly DONE.',
]
EXPECTED = ['OK', {'one': 60, 'two': 324, 'three': 1296}, 'DONE']


def main():
    config = tomllib.loads((Path.home() / '.codex/config.toml').read_text())
    provider = config['model_provider']
    settings = dict(config['model_providers'][provider])
    settings['name'] = 'OpenAI'
    settings['supports_websockets'] = False
    common = ['-c', 'model_provider=' + json.dumps(provider), '-c', 'model_catalog_json=' + json.dumps(str(HOME / 'models.json')), '-c', 'model_reasoning_effort="medium"']
    for key, value in settings.items():
        common += ['-c', f'model_providers.{provider}.{key}=' + ('true' if value is True else 'false' if value is False else json.dumps(value))]
    output = ROOT / 'work/live-compare.json'
    results = {}
    for arm, adaptive in [('fixed-medium', False), ('adaptive', True)]:
        sid = None
        previous = {}
        rows = []
        results[arm] = rows
        for index, task in enumerate(TASKS):
            launcher = ['node', str(ROOT / 'bin/astra-ares.mjs')] if adaptive else [str(HOME / 'bin/codex')]
            command = launcher + common + ['-m', 'Sol-6.1-Jev' if adaptive else 'gpt-6.1-sol', 'exec', '--ignore-user-config', '--skip-git-repo-check', '--json']
            if sid:
                command += ['resume', sid, task]
            else:
                command += ['-C', str(ROOT / 'work/live-empty'), task]
            env = {**os.environ, 'CODEX_HOME': str(HOME / 'codex-home')}
            started = time.monotonic()
            process = subprocess.run(command, env=env, cwd=ROOT, capture_output=True, text=True, input='', timeout=180)
            (ROOT / f'work/compare-{arm}-{index}.jsonl').write_text(process.stdout)
            (ROOT / f'work/compare-{arm}-{index}.stderr').write_text(process.stderr)
            row = {'step': index + 1, 'seconds': round(time.monotonic() - started, 2), 'returncode': process.returncode}
            message = ''
            for line in process.stdout.splitlines():
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if event.get('type') == 'thread.started':
                    sid = event['thread_id']
                if event.get('type') == 'item.completed' and event.get('item', {}).get('type') == 'agent_message':
                    message = event['item'].get('text', '')
                if event.get('type') == 'turn.completed':
                    total = event['usage']
                    row['usage'] = {key: value - previous.get(key, 0) for key, value in total.items()}
                    previous = total
                if event.get('type') == 'turn.failed':
                    row['error'] = event.get('error')
            try:
                actual = json.loads(message) if index == 1 else message.strip()
            except ValueError:
                actual = message
            row.update(threadId=sid, answer=actual, correct=actual == EXPECTED[index])
            rows.append(row)
            output.write_text(json.dumps(results, indent=2) + '\n')
            print(json.dumps({'arm': arm, **row}), flush=True)
            if process.returncode:
                raise SystemExit('Native benchmark failed; inspect private work evidence')
        if adaptive:
            decisions = []
            for log in (HOME / 'runs').glob('*/decisions.jsonl'):
                for line in log.read_text().splitlines():
                    event = json.loads(line)
                    if event.get('threadId') == sid and event.get('type') == 'decision':
                        decisions.append(event)
            results['adaptiveDecisions'] = [{key: event.get(key) for key in ['effort', 'reused', 'usage', 'jevMs', 'confirmation']} for event in decisions]
            output.write_text(json.dumps(results, indent=2) + '\n')
    if not all(row['correct'] for arm in ['fixed-medium', 'adaptive'] for row in results[arm]):
        raise SystemExit('Correctness differs; do not infer savings at equal quality')


if __name__ == '__main__':
    main()
