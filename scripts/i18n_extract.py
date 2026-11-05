# -*- coding: utf-8 -*-
"""Lift the mechanical half of a conversion: find strings, name keys, rewrite.

    python scripts/i18n_extract.py src/pages/Pricing.jsx --section pricing
    python scripts/i18n_extract.py src/pages/Pricing.jsx --section pricing --apply

Dry-run by default: it prints what it would change and writes nothing.

What it does NOT do is translate. It rewrites the JSX to call t(), adds the
English values to the en catalog, and writes a stub of {key: english} for the
Spanish to be authored into. Machine-translating a product's copy is how you
get a catalog full of plausible lies — pybabel's fuzzy matching already did
that to this project once, turning "Dues reminder" into "Lista de espera".

Deliberately conservative, because it edits source:

  * only a text node that is the whole content between two tags, with no
    braces or newlines inside it — anything interpolated is left for a human,
    since word order is the thing a translator must control;
  * only the attributes that are read aloud or shown (title, placeholder,
    aria-label, alt);
  * nothing that looks like a class list, a path, a slug, or a lone tag name.

Run the inventory afterwards. What this leaves behind is the interesting
part: interpolation and markup, which need <Trans> or named placeholders.
"""
import argparse
import html
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(errors='replace')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONT = os.path.join(ROOT, 'frontend')
CATALOG = os.path.join(FRONT, 'src', 'i18n', 'locales', '%s', 'common.json')

# A JSX text node: between two tags, nothing interpolated, starts like prose.
# The surrounding \s* matters more than it looks — a formatter puts the text
# on its own line inside a multi-line tag, so most real copy arrives as
# ">\n    Our Story\n  <" and a pattern anchored tight to the brackets misses
# it. The capture itself still forbids newlines, so this is one line of text.
RE_TEXT = re.compile(r'>\s*([A-Z][^<>{}\n]{2,160}?)\s*<')
# A paragraph the formatter wrapped across lines. Same shape, but the capture
# may contain newlines, which are collapsed to single spaces on the way into
# the catalog. Tried second, so single-line text is matched by the stricter
# pattern first.
RE_WRAPPED = re.compile(r'>\s*([A-Z][^<>{}]{20,400}?)\s*<')
RE_ATTR = re.compile(r'\b(title|placeholder|aria-label|alt)="([A-Z][^"\n]{2,160})"')

CLASSY = re.compile(r'\b(?:bi|bg|btn|nav|col|row|alert|badge|card|form|spinner|'
                    r'me|ms|mb|mt|ps|pe|py|px|fw|fs|d|justify|align|flex|gap|'
                    r'text|rounded|border|shadow|position|overflow|w|h)-')
NOT_PROSE = re.compile(r'^(?:[\w./#:-]*[./#:_-][\w./#:-]*$|https?:)', re.I)
TAGS = frozenset(('small', 'img', 'body', 'div', 'span', 'style', 'head',
                  'html', 'table', 'br', 'hr', 'li', 'ul', 'ol', 'p'))


def key_for(text, taken):
    """A camelCase key from the words of the string."""
    words = re.findall(r"[A-Za-z']+", text)[:5]
    if not words:
        words = ['x']
    head = words[0].lower()
    key = head + ''.join(w.capitalize() for w in words[1:])
    key = re.sub(r"[^A-Za-z0-9]", '', key)[:40] or 'x'
    if key[0].isdigit():
        key = 'n' + key
    base, i = key, 2
    while key in taken:
        key = '%s%d' % (base, i)
        i += 1
    return key


def wanted(text):
    t = text.strip()
    if len(t) < 3 or t.lower() in TAGS:
        return False
    if NOT_PROSE.match(t) or CLASSY.search(t):
        return False
    # Needs at least one real word.
    return bool(re.search(r"[A-Za-z]{3,}", t))


def add_hook(src):
    """Insert the import and the useTranslation() call.

    Placed on the line after the component opens, because a hook has to run
    inside the component — a `const { t }` at module scope is undefined when
    the array beside it is built, which is the mistake that broke GardenDetail
    once already.
    """
    m = re.search(r"^import .*? from 'react';$", src, re.M)
    if m:
        src = (src[:m.end()] + "\nimport { useTranslation } from 'react-i18next';"
               + src[m.end():])
    else:
        src = "import { useTranslation } from 'react-i18next';\n" + src
    m = re.search(r'^export default function \w+\([^)]*\) \{$', src, re.M)
    if not m:
        return src, '  NOTE: could not find the component to add the hook to.'
    src = src[:m.end()] + '\n  const { t } = useTranslation();' + src[m.end():]
    return src, '  added useTranslation import + hook'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('path', help='file, relative to frontend/ or absolute')
    ap.add_argument('--section', required=True, help='catalog section to write into')
    ap.add_argument('--apply', action='store_true', help='actually rewrite')
    ap.add_argument('--stub', help='where to write the {key: english} stub')
    ap.add_argument('--add-hook', action='store_true',
                    help='insert the useTranslation import and hook')
    args = ap.parse_args()

    path = args.path if os.path.isabs(args.path) else os.path.join(FRONT, args.path)
    src = io.open(path, encoding='utf-8').read()
    original = src

    en_doc = json.load(io.open(CATALOG % 'en', encoding='utf-8'))
    section = en_doc.get(args.section, {})
    # Reuse a key whose English already matches, rather than making a twin.
    by_text = dict((v, k) for k, v in section.items() if isinstance(v, str))
    taken = set(section)

    found, reused = {}, 0

    def remember(text):
        nonlocal reused
        # JSX parses &amp; / &rarr; into characters; a catalog string does not.
        # Carrying the entity across would render the literal "&amp;" on the
        # page, so decode on the way into the catalog.
        text = html.unescape(text.strip())
        if text in by_text:
            reused += 1
            return by_text[text]
        if text in found:
            return found[text]
        k = key_for(text, taken)
        taken.add(k)
        found[text] = k
        by_text[text] = k
        return k

    def sub_text(m):
        text = m.group(1)
        if not wanted(text):
            return m.group(0)
        return ">{t('%s.%s')}<" % (args.section, remember(text))

    def sub_attr(m):
        attr, text = m.group(1), m.group(2)
        if not wanted(text):
            return m.group(0)
        return "%s={t('%s.%s')}" % (attr, args.section, remember(text))

    def sub_wrapped(m):
        text = re.sub(r'\s+', ' ', m.group(1)).strip()
        if not wanted(text) or '\n\n' in m.group(1):
            return m.group(0)
        return ">{t('%s.%s')}<" % (args.section, remember(text))

    src = RE_TEXT.sub(sub_text, src)
    src = RE_WRAPPED.sub(sub_wrapped, src)
    src = RE_ATTR.sub(sub_attr, src)

    hook_note = ''
    if found and 'react-i18next' not in src:
        if args.add_hook:
            src, hook_note = add_hook(src)
        else:
            hook_note = ('  NOTE: no useTranslation in this file — pass '
                         '--add-hook, or it throws at runtime.')
    if hook_note:
        print(hook_note)

    print('%s  ->  section "%s"' % (os.path.relpath(path, FRONT), args.section))
    print('  %d new string(s), %d reused from the catalog' % (len(found), reused))
    for text, k in list(found.items())[:40]:
        print('    %-28s %s' % (k, text[:70]))
    if len(found) > 40:
        print('    ... and %d more' % (len(found) - 40))

    if not args.apply:
        print('\n  (dry run — nothing written; pass --apply)')
        return 0

    if not found:
        print('  nothing to do')
        return 0

    io.open(path, 'w', encoding='utf-8', newline='').write(src)

    section.update(dict((k, text) for text, k in found.items()))
    en_doc[args.section] = section
    json.dump(en_doc, io.open(CATALOG % 'en', 'w', encoding='utf-8', newline=''),
              indent=2, ensure_ascii=False)

    stub = args.stub or os.path.join(ROOT, 'i18n_stub_%s.json' % args.section)
    io.open(stub, 'w', encoding='utf-8', newline='').write(
        json.dumps(dict((k, text) for text, k in found.items()),
                   indent=2, ensure_ascii=False))
    print('\n  rewrote %s' % os.path.relpath(path, FRONT))
    print('  en catalog updated; Spanish stub -> %s' % os.path.relpath(stub, ROOT))
    print('  changed %d bytes' % abs(len(src) - len(original)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
