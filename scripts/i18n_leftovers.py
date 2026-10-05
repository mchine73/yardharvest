# -*- coding: utf-8 -*-
"""Find user-facing English that the inventory's ">text<" regexes cannot see.

The inventory in i18n_inventory.py answers "how much is left to do" across the
whole app. This answers a narrower and harder question: "is THIS file actually
finished?" Four separate times during the Spanish rollout a file was reported
clean, shipped, and then showed English on screen, because the string lived in
one of these shapes:

  adjacent   JSX text with an expression on one side:
             ">Dues Overview - {duesSeason}</h6>" or ">{n} flagged for review<".
             Every >text< regex needs both delimiters and matches neither.
  entity     "Billing &amp; Payouts" - an HTML entity is in no letters-and-
             punctuation character class.
  call       toast('Message deleted'), confirmDialog('Delete this event?') and
             the options beside them (title, confirmText, placeholder). These
             are JS string literals, not JSX, so a markup-shaped regex never
             looked at them - and they are the strings a reader sees most,
             one per action they take.
  fallback   `err.response?.data?.error || 'Error saving photo'` - the branch
             that runs when the server returned no message. The least-tested
             string on the page, shown at the worst possible moment.
  wrapped    A paragraph the formatter broke across lines, so no single line
             holds the whole sentence.

Usage:
    .venv/Scripts/python.exe scripts/i18n_leftovers.py                 # all
    .venv/Scripts/python.exe scripts/i18n_leftovers.py GardenAdmin     # match
    .venv/Scripts/python.exe scripts/i18n_leftovers.py --quiet         # count

Exit status is 1 when anything is found, so it can gate a commit.

It reports, never edits. Expect some noise: a className fragment or a data
slug will slip through. Noise you dismiss is the right failure direction here
- the alternative, which this rollout kept hitting, is a confident zero.
"""
import argparse
import os
import re
import sys

# The strings this reports are the ones with typography in them - an ellipsis,
# a dash, an accent - so on a cp1252 console the report itself crashes.
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(errors='replace')

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'frontend', 'src')

# Words, so a className or a path does not read as prose.
WORDS = re.compile(r"\b[A-Za-z][a-z]{2,}\b")

# Things that look like prose but are not.
#
# The slug branch requires a separator (. / : # _ -). Without one it matched
# any single word, so one-word labels - "Upcoming", "Past", "All", "Reply" -
# were dropped as identifiers. Three of those were live on the events filter,
# which is how the hole was found.
NOT_PROSE = re.compile(
    r'^(?:'
    r'[\w./#:-]*[./#:_-][\w./#:-]*$'    # paths, slugs, ids
    r'|(?:bi|bg|btn|nav|col|row|text|alert|badge|form|card|d|me|ms|mb|mt|py|px)-'
    r'|https?:'
    r')', re.I)

# Bootstrap/utility class soup, which is mostly short words joined by dashes.
CLASSY = re.compile(r'\b(?:bi|bg|btn|nav|col|row|alert|badge|card|form|spinner|'
                    r'me|ms|mb|mt|ps|pe|py|px|fw|fs|d|justify|align|flex|gap|'
                    r'text|rounded|border|shadow|position|overflow|w|h)-')

# `} else {`, `} catch (err) {` and friends read as "text with an expression
# on both sides". Nothing else filters them, because they are words.
KEYWORDS = frozenset((
    'else', 'catch', 'finally', 'try', 'return', 'await', 'then', 'case',
    'default', 'typeof', 'instanceof', 'new', 'delete', 'void', 'yield',
    # Tag names, which show up as CSS selectors inside a style block built as
    # a template literal (handlePrintQR does exactly this). A bare tag name is
    # never prose on its own.
    'small', 'img', 'body', 'div', 'span', 'style', 'head', 'html', 'table',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
))

CALLS = ('toast', 'confirmDialog', 'promptDialog', 'showFinanceToast', 'alert')
OPTS = ('title', 'confirmText', 'cancelText', 'placeholder', 'label', 'error',
        'success', 'successMsg', 'hint', 'loading', 'alt', 'aria-label')

PATTERNS = [
    # text with an expression on one side
    # The class carries $ € £ and digits because a currency symbol inside the
    # run (">Pay ${amount}") ended the match before it reached the brace, and
    # that is exactly where a price label lives.
    ('adjacent', re.compile(r'>\s*([A-Z][A-Za-z ’\',.%:!?$€£0-9-]{2,60}?)\s*\{')),
    ('adjacent', re.compile(r'\}\s*([A-Za-z][A-Za-z ’\',.%:!?$€£0-9-]{2,60}?)\s*<')),
    # text with an expression on BOTH sides: "} — checked out by {". Requiring
    # a tag on one side is how that one stayed English.
    ('adjacent', re.compile(r'\}\s*[—–-]?\s*([A-Za-z][A-Za-z ’\',.%:!?$€£0-9]{4,60}?)\s*\{')),
    # an HTML entity inside the text
    ('entity', re.compile(r'>\s*([A-Za-z][^<>{}\n]*?&[a-z]+;[^<>{}\n]*?)\s*[<{]')),
    # user-facing JS literals
    ('call', re.compile(r"\b(?:%s)\(\s*'([^'\n]{3,})'" % '|'.join(CALLS))),
    ('call', re.compile(r'\b(?:%s)\(\s*"([^"\n]{3,})"' % '|'.join(CALLS))),
    ('call', re.compile(r"\b(?:%s)\s*:\s*'([A-Z][^'\n]{2,})'" % '|'.join(OPTS))),
    # The same names as a JSX attribute: hint="Upload a photo…". Covering the
    # object-literal form only is how one survived on the Settings tab.
    ('attr', re.compile(r'\b(?:%s)="([A-Z][^"\n]{2,})"' % '|'.join(OPTS))),
    # the no-message-from-the-server branch
    ('fallback', re.compile(r"\|\|\s*'([A-Z][^'\n]{2,60})'")),
    # {saving ? 'Creating…' : 'Create Shift'} - a button label living in a
    # ternary, with neither a > nor a < anywhere near it. This is the shape
    # that put an English "Create Shift" on an otherwise Spanish screen.
    # Allow a leading space: {user ? ' Be the first!' : ''} is a fragment
    # appended to a translated sentence, and it renders.
    ('ternary', re.compile(r"\?\s*'(\s?[A-Z][^'\n]{1,60})'\s*:")),
    ('ternary', re.compile(r":\s*'(\s?[A-Z][^'\n]{1,60})'\s*[}\)]")),
    # setMsg('Checked out successfully!') - a state setter whose value is
    # rendered a few lines later. Not a call to any dialog helper, so the
    # 'call' patterns never looked at it, and two of these were live.
    ('state', re.compile(r"\bset[A-Z]\w*\(\s*'([A-Z][^'\n]{3,})'")),
]

# A line that is nothing but words: a paragraph the formatter wrapped. No
# brackets and no punctuation that only appears in code - otherwise every
# `case 'plots': return renderPlots();` reads as a wrapped sentence, and a
# detector whose output you have to skim is one you stop reading.
WRAPPED = re.compile(r'^[A-Za-z][A-Za-z ’\',.;!?&-]{14,}$')
CODEY = re.compile(r'^(?:if|for|while|return|case|default|await|const|let|var|'
                   r'function|import|export|else|try|catch|throw|new|delete)\b')


def scan(path):
    with open(path, encoding='utf-8') as fh:
        body = fh.read()

    # Blanked, not deleted: removing a line renumbers every line after it, so
    # the reported line stops matching the file - worse than no line number.
    def blank(m):
        return re.sub(r'[^\n]', ' ', m.group(0))

    body = re.sub(r'/\*[\s\S]*?\*/', blank, body)
    body = re.sub(r'^\s*//.*$', blank, body, flags=re.M)
    # A <Trans>'s children ARE the English source for its key.
    body = re.sub(r'<Trans[\s\S]*?</Trans>', blank, body)

    lines = body.split('\n')
    hits = []

    for kind, rx in PATTERNS:
        for m in rx.finditer(body):
            text = m.group(1).strip()
            if (not text or NOT_PROSE.match(text) or CLASSY.search(text)
                    or len(WORDS.findall(text)) < 1
                    or text.strip().lower() in KEYWORDS):
                continue
            hits.append((body.count('\n', 0, m.start()) + 1, kind, text))

    for i, raw in enumerate(lines, 1):
        line = raw.strip()
        if (WRAPPED.match(line) and len(WORDS.findall(line)) >= 3
                and not line.endswith(',') and not CODEY.match(line)):
            hits.append((i, 'wrapped', line))

    seen, out = set(), []
    for line, kind, text in sorted(hits):
        if (kind, text) in seen:
            continue
        seen.add((kind, text))
        out.append((line, kind, text))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('match', nargs='?', help='only files whose path contains this')
    ap.add_argument('--quiet', action='store_true', help='totals only')
    args = ap.parse_args()

    total, files = 0, 0
    for root, _dirs, names in os.walk(SRC):
        if 'i18n' in root.split(os.sep) or '__tests__' in root:
            continue
        for name in sorted(names):
            if not name.endswith(('.jsx', '.js')) or name.endswith('.test.jsx'):
                continue
            path = os.path.join(root, name)
            rel = os.path.relpath(path, SRC)
            if args.match and args.match.lower() not in rel.lower():
                continue
            hits = scan(path)
            if not hits:
                continue
            files += 1
            total += len(hits)
            if args.quiet:
                print('%-58s %d' % (rel, len(hits)))
                continue
            print('\n%s' % rel)
            for line, kind, text in hits:
                print('  %5d  %-9s %s' % (line, kind, text[:96]))

    print('\n%d leftover string(s) across %d file(s)' % (total, files))
    return 1 if total else 0


if __name__ == '__main__':
    sys.exit(main())
