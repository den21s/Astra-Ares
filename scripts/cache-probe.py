#!/usr/bin/env python3
"""Live synthetic cache probe via the user's configured Codex Responses route.

No credentials or conversation payloads are written to evidence. Reports token
usage, not dollar savings; account-specific gateway prices are not assumed.
"""
import argparse
import json
import os
from pathlib import Path
import time
import tomllib
import urllib.error
import urllib.request
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--codex-home', type=Path, default=Path(os.environ.get('CODEX_HOME', Path.home() / '.codex')))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mode', choices=['fixed', 'update', 'request'], default='update')
    args = parser.parse_args()
    config = tomllib.loads((args.codex_home / 'config.toml').read_text())
    provider = config.get('model_provider', 'openai')
    endpoint = config['model_providers'][provider]['base_url'].rstrip('/')
    auth = json.loads((args.codex_home / 'auth.json').read_text())
    key = auth.get('OPENAI_API_KEY')
    if not isinstance(key, str) or not key.strip():
        raise SystemExit('This probe requires an existing Codex API-key login')
    model = config['model']
    run = str(uuid.uuid4())
    history = [{'role': 'user', 'content': f'Synthetic cache test {run}. Reply exactly OK without tools.\n' + '\n'.join(f'Record {i:04d}: amber birch cedar delta elm forest granite harbor iris juniper.' for i in range(320))}]
    results = []
    phases = ['medium'] * 6
    warmed = False
    switches = ['high', 'high', 'low', 'low', 'medium', 'high', 'low']
    active = 'medium'
    while phases:
        desired = phases.pop(0)
        if args.mode == 'fixed':
            desired = 'medium'
        if desired != active:
            if args.mode == 'update':
                history.append({'type': 'configuration_update', 'reasoning': {'effort': desired}})
            active = desired
        if results:
            history.append({'role': 'user', 'content': 'Reply exactly OK.'})
        body = {'model': model, 'reasoning': {'effort': active if args.mode == 'request' else 'medium'}, 'input': history, 'store': False, 'stream': False, 'include': ['reasoning.encrypted_content'], 'prompt_cache_key': run}
        started = time.monotonic()
        request = urllib.request.Request(endpoint + '/responses', data=json.dumps(body).encode(), headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key, 'session-id': run, 'thread-id': run})
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                result = json.load(response)
        except urllib.error.HTTPError as error:
            # Do not log arbitrary provider error bodies: they can echo inputs.
            raise SystemExit(f'Responses request failed with HTTP {error.code}') from None
        if result.get('model') != model:
            raise SystemExit('Provider substituted the requested model')
        if result.get('status') != 'completed':
            raise SystemExit(f'Responses did not complete: {result.get("status")}')
        usage = result['usage']
        cached = usage.get('input_tokens_details', {}).get('cached_tokens', 0)
        row = {'step': len(results) + 1, 'requestEffort': body['reasoning']['effort'], 'effectiveEffortRequested': active, 'inputTokens': usage['input_tokens'], 'cachedTokens': cached, 'cacheWriteTokens': usage.get('input_tokens_details', {}).get('cache_write_tokens', 0), 'outputTokens': usage['output_tokens'], 'reasoningTokens': usage.get('output_tokens_details', {}).get('reasoning_tokens', 0), 'cachePercent': round(100 * cached / usage['input_tokens'], 2), 'responseEffort': result.get('reasoning', {}).get('effort'), 'seconds': round(time.monotonic() - started, 2)}
        results.append(row)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({'model': model, 'provider': provider, 'mode': args.mode, 'results': results}, indent=2) + '\n')
        print(json.dumps(row), flush=True)
        history.extend(result.get('output', []))
        if not warmed and row['cachePercent'] > 95:
            warmed = True
            phases = switches.copy()
    if not warmed:
        raise SystemExit('Baseline did not warm; no effort-change conclusion is valid')


if __name__ == '__main__':
    main()
