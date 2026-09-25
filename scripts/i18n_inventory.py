"""Inventory the translatable strings in the React app.

Reports only — it never edits a file. The point is to turn "translate the
frontend" into a worklist you can sequence and check off, and to separate the
strings that extract mechanically from the ones that need a human decision.

    .venv/Scripts/python.exe scripts/i18n_inventory.py
    .venv/Scripts/python.exe scripts/i18n_inventory.py --page Plots --show

Four buckets, in ascending order of how much thought each costs:

  text        Plain text between tags. Lift straight into t('...').
  attr        placeholder / title / aria-label / alt. Same, but easy to miss
              because they are invisible until someone uses a screen reader.
  interp      A template literal with ${...} inside. Must become t('key',
              {name}) with a NAMED placeholder — never string concatenation,
              because Spanish does not keep English's word order and a
              sentence glued together from fragments cannot be reordered by
              the translator.
  trans       A sentence with markup inside it (a <Link>, a <strong>). Needs
              the <Trans> component. These are the ones that blow estimates:
              they look like one string and are really three.

The counts are a floor, not a census: a regex cannot see a string built at
runtime. Treat the total as "at least this much".
"""
import argparse
import os
import re
import sys
from collections import Counter

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'frontend', 'src')

# Text between tags, starting with a capital or digit so we skip {expressions}
# and lone punctuation.
RE_TEXT = re.compile(r'>\s*([A-Z0-9][A-Za-z0-9 ,.\'&?!:%()/-]{3,}?)\s*<')
RE_ATTR = re.compile(r'(?:placeholder|title|aria-label|alt)="([A-Z][^"]{3,})"')
RE_INTERP = re.compile(r'`([^`]*\$\{[^}]+\}[^`]*)`')
RE_TRANS = re.compile(r'<(?:p|li|span|label|small|div|h[1-6])[^>]*>[^<{]*<(?:Link|a|strong|em|b|code)\b')

# Strings that are not prose: css-ish values, single words that are almost
# always identifiers, and the import/export noise at the top of a file.
# NOTE: deliberately case-SENSITIVE. With re.I, '[A-Z_]+' matches any word and
# silently skips every string in the codebase — the inventory then reports a
# confident zero, which is far worse than reporting nothing at all.
RE_SKIP = re.compile(r'^(?:[A-Z_]{2,}$|\d+(?:px|rem|%)?$|https?:|/|#)')


def scan(path):
    with open(path, encoding='utf-8') as fh:
        body = fh.read()
    # Comments are not shipped to anyone.
    body = re.sub(r'/\*.*?\*/', '', body, flags=re.S)
    body = re.sub(r'^\s*//.*$', '', body, flags=re.M)

    found = {
        'text': [m for m in RE_TEXT.findall(body) if not RE_SKIP.match(m)],
        'attr': RE_ATTR.findall(body),
        'interp': [m for m in RE_INTERP.findall(body)
                   if re.search(r'[A-Za-z]{4,}\s', m)],
        'trans': RE_TRANS.findall(body),
    }
    return found


def walk(only=None):
    rows = []
    for root, _dirs, files in os.walk(SRC):
        if 'i18n' in root.split(os.sep):
            continue
        for name in sorted(files):
            if not name.endswith(('.jsx', '.js')):
                continue
            if name.endswith(('.test.js', '.test.jsx')):
                continue
            if only and only.lower() not in name.lower():
                continue
            path = os.path.join(root, name)
            found = scan(path)
            total = sum(len(v) for v in found.values())
            if total:
                rows.append((os.path.relpath(path, SRC), found, total))
    return sorted(rows, key=lambda r: -r[2])


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--page', help='only files whose name contains this')
    ap.add_argument('--show', action='store_true',
                    help='print the strings, not just the counts')
    ap.add_argument('--limit', type=int, default=30,
                    help='how many files to list (default 30)')
    args = ap.parse_args()

    rows = walk(args.page)
    if not rows:
        print('Nothing matched.')
        return 0

    totals = Counter()
    for _path, found, _t in rows:
        for k, v in found.items():
            totals[k] += len(v)

    print('%-46s %6s %6s %6s %6s %7s' % ('FILE', 'text', 'attr', 'interp',
                                         'trans', 'total'))
    print('-' * 82)
    for path, found, total in rows[:args.limit]:
        print('%-46s %6d %6d %6d %6d %7d' % (
            path[:46], len(found['text']), len(found['attr']),
            len(found['interp']), len(found['trans']), total))
        if args.show:
            for kind in ('text', 'attr', 'interp', 'trans'):
                for s in found[kind]:
                    print('      [%s] %s' % (kind, s[:100]))
    if len(rows) > args.limit:
        print('... and %d more files' % (len(rows) - args.limit))

    print('-' * 82)
    grand = sum(totals.values())
    print('%-46s %6d %6d %6d %6d %7d' % (
        '%d files' % len(rows), totals['text'], totals['attr'],
        totals['interp'], totals['trans'], grand))
    print()
    print('Mechanical (text + attr) : %d' % (totals['text'] + totals['attr']))
    print('Needs a decision         : %d  (%d interpolated, %d with markup)'
          % (totals['interp'] + totals['trans'], totals['interp'], totals['trans']))
    print()
    print('A floor, not a census — a regex cannot see a string built at runtime.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
