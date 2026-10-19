#!/usr/bin/env python3
"""Create an independent Ares profile using an existing Responses account.

The input model catalog must come from trusted upstream Codex metadata. No API
key is copied: the isolated profile references the existing rotating auth file.
Existing user settings, hooks and MCP definitions are preserved in the snapshot.
"""
import argparse
import json
import os
from pathlib import Path
import re
import tomllib


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path.home() / '.codex')
    parser.add_argument('--target', type=Path, default=Path.home() / '.local/share/astra-ares/codex-home')
    parser.add_argument('--model-catalog', type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    target = args.target.resolve()
    if source == target:
        raise SystemExit('Source and target must be different profiles')
    original = (source / 'config.toml').read_text()
    parsed = tomllib.loads(original)
    model = parsed.get('model')
    if model != 'gpt-6.1-sol':
        raise SystemExit('This integration currently requires gpt-6.1-sol')
    catalog_path = args.model_catalog.resolve()
    catalog = json.loads(catalog_path.read_text())
    metadata = next((item for item in catalog.get('models', []) if item.get('slug') == model), None)
    if not metadata or not metadata.get('use_responses_lite'):
        raise SystemExit('Trusted model metadata with Responses Lite support is required')
    provider = parsed.get('model_provider', 'openai')
    provider_info = parsed.get('model_providers', {}).get(provider, {})
    if not provider_info.get('base_url') or provider_info.get('wire_api') != 'responses':
        raise SystemExit('An explicit compatible Responses provider is required')
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Modify only top-level model/catalog settings and the selected provider's
    # compatibility name. Keep all other settings exactly as in the source.
    parts = re.split(r'(?m)(?=^\[)', original, maxsplit=1)
    top = re.sub(r'(?m)^model\s*=.*$', 'model = "Sol-6.1-Jev"', parts[0])
    top = re.sub(r'(?m)^model_catalog_json\s*=.*\n?', '', top)
    top += '\nmodel_catalog_json = ' + json.dumps(str(catalog_path)) + '\n\n'
    text = top + (parts[1] if len(parts) > 1 else '')
    section = re.compile(r'(?ms)(^\[model_providers\.' + re.escape(provider) + r'\]\n)(.*?)(?=^\[|\Z)')
    def compatible(match):
        body = re.sub(r'(?m)^name\s*=.*$', 'name = "OpenAI"', match[2])
        if not re.search(r'(?m)^name\s*=', body):
            body = 'name = "OpenAI"\n' + body
        return match[1] + body
    text, count = section.subn(compatible, text)
    if count != 1:
        raise SystemExit('Selected provider must have a dedicated TOML table')
    tomllib.loads(text)
    dest = target / 'config.toml'
    if dest.exists():
        raise SystemExit('Target config exists; inspect it before replacing it')
    fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as out:
        out.write(text)
    for name in ['auth.json', 'AGENTS.md', 'skills', 'rules', 'hooks', 'hooks.json', 'plugins']:
        origin = source / name
        link = target / name
        if origin.exists() and not link.exists():
            link.symlink_to(origin, target_is_directory=origin.is_dir())
    print(f'Created independent profile: {target}')


if __name__ == '__main__':
    main()
