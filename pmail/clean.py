"""Strip an email down to the words an AI needs.

Keeps: the text the sender wrote, and every link written as `text (url)`.
Drops: HTML, styling, layout tables, images, invisible padding, tracking
parameters on links, quoted earlier replies and signatures.
"""

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import html2text

# Characters senders use to pad preview text; they carry no meaning.
_INVISIBLE = dict.fromkeys(map(ord, "͏­​‌‍⁠﻿  　"), " ")

_TRACKING_PARAMS = re.compile(r"^(utm_\w+|mc_cid|mc_eid|_hsenc|_hsmi|mkt_tok|fbclid|gclid|oly_\w+|vero_\w+)$", re.I)

_QUOTE_STARTS = [
    re.compile(r"^-{3,}\s*Original Message\s*-{3,}\s*$", re.I),
    re.compile(r"^On .{4,300}wrote:\s*$", re.S),
    re.compile(r"^From: .+\n(Sent|Date): .+", re.I),
]
_SIGNOFF_LINES = re.compile(
    r"^(Sent with Proton Mail secure email\.?|Sent from Proton Mail (for )?\w+\.?|Sent from my \w+.*)$", re.I
)


def _converter() -> html2text.HTML2Text:
    h = html2text.HTML2Text()
    h.body_width = 0
    h.ignore_images = True
    h.ignore_emphasis = True
    h.ignore_tables = True
    h.protect_links = True
    h.unicode_snob = True
    h.skip_internal_links = True
    h.single_line_break = False
    return h


def strip_tracking(url: str) -> str:
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    if not parts.query:
        return url
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not _TRACKING_PARAMS.match(k)]
    return urlunsplit(parts._replace(query=urlencode(query, doseq=True)))


_LINK_TAIL = re.compile(r"\]\(<?((?:https?|mailto):[^)>\s]+)>?(?:\s+\"[^\"]*\")?\)")


def _format_link(text: str, url: str) -> str:
    text, url = text.strip(), strip_tracking(url.strip())
    while text.startswith("[") and text.endswith("]"):
        text = text[1:-1].strip()
    if not text:
        return ""
    if text.rstrip("/") == url.rstrip("/") or text == url.split("://", 1)[-1].rstrip("/"):
        return url
    return f"{text} ({url})"


def flatten_links(text: str) -> str:
    """Rewrite markdown links `[text](url)` as `text (url)`.

    Brackets are matched by counting, so link text may itself contain brackets
    or other links (job cards and product tiles nest them).
    """
    start = 0
    while match := _LINK_TAIL.search(text, start):
        depth, i = 0, match.start() - 1
        while i >= 0:
            if text[i] == "]":
                depth += 1
            elif text[i] == "[":
                if depth == 0:
                    break
                depth -= 1
            i -= 1
        if i < 0:  # no opening bracket: not a link
            start = match.end()
            continue
        replacement = _format_link(text[i + 1:match.start()], match.group(1))
        text = text[:i] + replacement + text[match.end():]
        start = i  # rescan from here; an enclosing link may now be complete
    return text


def html_to_text(html: str) -> str:
    md = _converter().handle(html)
    md = re.sub(r"!\[[^\]]*\]\(<?[^)>]*>?\)", "", md)  # any image html2text kept
    md = re.sub(r"<(https?://[^>\s]+)>", lambda m: strip_tracking(m.group(1)), md)
    md = re.sub(r"^\s{0,3}#{1,6}\s*", "", md, flags=re.M)  # heading markers
    md = re.sub(r"^(\s*)[*+]\s+", r"\1- ", md, flags=re.M)  # bullets
    md = re.sub(r"\\([\\`*_{}\[\]()#+\-.!>|])", r"\1", md)  # markdown escapes
    return md


def strip_quoted(text: str) -> str:
    """Cut the quoted copy of earlier messages; the thread already holds them."""
    lines = text.split("\n")
    for i in range(len(lines)):
        two = "\n".join(lines[i:i + 2])
        one = lines[i].strip()
        if any(p.match(one) for p in _QUOTE_STARTS[:2]) or _QUOTE_STARTS[2].match(two) or (
            one.startswith("On ") and _QUOTE_STARTS[1].match(" ".join(l.strip() for l in lines[i:i + 3]))
        ):
            kept = "\n".join(lines[:i]).rstrip()
            return kept or text  # a message that is only a quote stays whole
    # Trailing block of "> " lines with nothing after it.
    end = len(lines)
    while end > 0 and (lines[end - 1].startswith(">") or not lines[end - 1].strip()):
        end -= 1
    if end and end < len(lines) and any(l.startswith(">") for l in lines[end:]):
        return "\n".join(lines[:end])
    return text


def strip_signature(text: str) -> str:
    lines = [l for l in text.split("\n") if not _SIGNOFF_LINES.match(l.strip())]
    for i in range(len(lines) - 1, max(-1, len(lines) - 16), -1):
        if lines[i].rstrip() == "--" and i > 0:
            lines = lines[:i]
            break
    return "\n".join(lines)


def tidy(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").translate(_INVISIBLE)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)  # bold markers some senders put in plain text
    text = re.sub(r"^[\s|\-_=*]*$", "", text, flags=re.M)  # rules and empty table rows
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"[ \t]+$", "", text, flags=re.M)
    text = re.sub(r"^[ \t]+", "", text, flags=re.M)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def clean_body(plain: str | None, html: str | None) -> str:
    if plain and plain.strip():
        text = plain
    elif html:
        text = html_to_text(html)
    else:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n").translate(_INVISIBLE)
    text = flatten_links(text)  # plain-text parts use markdown links too (LinkedIn, newsletters)
    text = re.sub(r"https?://[^\s<>()\"']+", lambda m: strip_tracking(m.group(0)), text)
    text = strip_quoted(text)
    text = strip_signature(text)  # before tidy, which would drop the "--" delimiter
    return tidy(text)
