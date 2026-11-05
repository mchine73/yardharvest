# -*- coding: utf-8 -*-
"""Add authored strings to BOTH client catalogs in one locked step.

    python scripts/i18n_catalog_add.py fragment.json
    python scripts/i18n_catalog_add.py fragment.json --replace

The fragment mirrors the catalogs themselves, English and Spanish side by side:

    {"en": {"groups": {"title": "Neighborhood Groups"}},
     "es": {"groups": {"title": "Grupos del vecindario"}}}

Why not just edit common.json: several conversions can run at once, and a
read-modify-write of a 2,000-key file by two writers loses one of them
silently. This takes a lock file, re-reads both catalogs inside it, and writes
both or neither.

It refuses, and writes nothing, when:
  * the English and Spanish halves name different keys (the parity test would
    fail later, further from the cause);
  * a Spanish value is empty;
  * a key already exists with a DIFFERENT value - pass --replace when the
    change is intended. An identical value is a no-op, so re-running is safe.

It warns, but writes, when a Spanish value is identical to the English: that
is sometimes right ("Error", a brand name) and catalogs.test.js keeps the
allowlist, so the decision is made there.
"""
import argparse
import io
import json
import os
import sys
import time

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(errors='replace')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCALES = os.path.join(ROOT, 'frontend', 'src', 'i18n', 'locales')
CATALOG = os.path.join(LOCALES, '%s', 'common.json')
LOCK = os.path.join(LOCALES, '.catalog.lock')


def leaves(obj, prefix=''):
    for k, v in obj.items():
        key = prefix + '.' + k if prefix else k
        if isinstance(v, dict):
            for item in leaves(v, key):
                yield item
        else:
            yield key, v


def get(doc, dotted):
    node = doc
    for part in dotted.split('.'):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def put(doc, dotted, value):
    parts = dotted.split('.')
    node = doc
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


class Lock(object):
    def __enter__(self):
        deadline = time.time() + 60
        while True:
            try:
                self.fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                return self
            except FileExistsError:
                # A writer that died holding the lock leaves the file behind;
                # nothing legitimately holds it for more than a second.
                try:
                    if time.time() - os.path.getmtime(LOCK) > 120:
                        os.remove(LOCK)
                        continue
                except OSError:
                    pass
                if time.time() > deadline:
                    raise SystemExit('catalog lock busy for 60s: %s' % LOCK)
                time.sleep(0.2)

    def __exit__(self, *exc):
        os.close(self.fd)
        os.remove(LOCK)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('fragment')
    ap.add_argument('--replace', action='store_true',
                    help='allow changing the value of an existing key')
    args = ap.parse_args()

    frag = json.load(io.open(args.fragment, encoding='utf-8'))
    en_new = dict(leaves(frag.get('en', {})))
    es_new = dict(leaves(frag.get('es', {})))

    problems = []
    for k in sorted(set(en_new) ^ set(es_new)):
        problems.append('only on one side: %s' % k)
    for k, v in es_new.items():
        if not isinstance(v, str) or not v.strip():
            problems.append('empty Spanish value: %s' % k)
    if problems:
        print('\n'.join(problems))
        return 1

    with Lock():
        docs = dict((lang, json.load(io.open(CATALOG % lang, encoding='utf-8')))
                    for lang in ('en', 'es'))
        added = same = changed = 0
        for lang, new in (('en', en_new), ('es', es_new)):
            for k, v in new.items():
                old = get(docs[lang], k)
                if isinstance(old, dict):
                    problems.append('%s %s is a section, not a string' % (lang, k))
                elif old is None:
                    put(docs[lang], k, v)
                    added += 1
                elif old == v:
                    same += 1
                elif args.replace:
                    put(docs[lang], k, v)
                    changed += 1
                else:
                    problems.append('%s %s already exists as %r' % (lang, k, old))
        if problems:
            print('\n'.join(problems))
            print('nothing written')
            return 1
        for lang in ('en', 'es'):
            io.open(CATALOG % lang, 'w', encoding='utf-8', newline='').write(
                json.dumps(docs[lang], indent=2, ensure_ascii=False))

    for k in sorted(en_new):
        if en_new[k] == es_new[k]:
            print('note: Spanish identical to English for %s - fine only if the '
                  'word really is the same (catalogs.test.js SAME_IN_BOTH)' % k)
    print('%d added, %d changed, %d already present (per language, summed)'
          % (added, changed, same))
    return 0


if __name__ == '__main__':
    sys.exit(main())
