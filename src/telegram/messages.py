"""Safe delivery helpers for Telegram's message size and HTML constraints."""

import re
from typing import Any, List, Optional, Sequence, Tuple


# Telegram accepts at most 4096 characters. Keeping a small margin also leaves
# room for HTML tags that are reopened at a chunk boundary.
TELEGRAM_SAFE_MESSAGE_LENGTH = 4000

_HTML_TOKEN = re.compile(
    r"(</?[A-Za-z][^<>]*>|&(?:#[0-9]+|#x[0-9A-Fa-f]+|[A-Za-z][A-Za-z0-9]+;))"
)
_HTML_TAG_NAME = re.compile(r"^</?([A-Za-z][A-Za-z0-9-]*)")
_VOID_TAGS = {"br", "hr", "img"}


def _preferred_cut(text: str, limit: int) -> int:
    """Choose a lossless boundary near ``limit`` instead of splitting words."""
    if len(text) <= limit:
        return len(text)

    for delimiter in ("\n", " "):
        boundary = text.rfind(delimiter, 0, limit)
        if boundary >= limit // 2:
            return boundary + 1
    return limit


def _split_plain_text(text: str, max_length: int) -> List[str]:
    chunks: List[str] = []
    remaining = text
    while remaining:
        cut = _preferred_cut(remaining, max_length)
        chunks.append(remaining[:cut])
        remaining = remaining[cut:]
    return chunks or [""]


def _updated_open_tags(
    open_tags: Sequence[Tuple[str, str]], tag: str
) -> List[Tuple[str, str]]:
    """Return the HTML formatting stack after a Telegram HTML tag."""
    updated = list(open_tags)
    name_match = _HTML_TAG_NAME.match(tag)
    if not name_match:
        return updated

    name = name_match.group(1).lower()
    if tag.startswith("</"):
        for index in range(len(updated) - 1, -1, -1):
            if updated[index][0] == name:
                del updated[index:]
                break
    elif not tag.rstrip().endswith("/>") and name not in _VOID_TAGS:
        updated.append((name, tag))
    return updated


def _closing_tags(open_tags: Sequence[Tuple[str, str]]) -> str:
    return "".join(f"</{name}>" for name, _ in reversed(open_tags))


def _opening_tags(open_tags: Sequence[Tuple[str, str]]) -> str:
    return "".join(tag for _, tag in open_tags)


def _split_html(text: str, max_length: int) -> List[str]:
    """Split HTML while closing and reopening formatting at each boundary."""
    chunks: List[str] = []
    current = ""
    open_tags: List[Tuple[str, str]] = []

    def finish_chunk() -> None:
        nonlocal current
        if current:
            chunks.append(current + _closing_tags(open_tags))
            current = _opening_tags(open_tags)

    tokens = _HTML_TOKEN.split(text)
    for token in tokens:
        if not token:
            continue

        if token.startswith("<"):
            prospective_tags = _updated_open_tags(open_tags, token)
            # A previous chunk may have reopened tags. If the next token closes
            # one before any visible text is added, omit that empty formatting.
            if token.startswith("</") and current == _opening_tags(open_tags):
                current = _opening_tags(prospective_tags)
                open_tags = prospective_tags
                continue
            required_length = len(current) + len(token) + len(_closing_tags(prospective_tags))
            if current and required_length > max_length:
                finish_chunk()
            current += token
            open_tags = prospective_tags
            continue

        if token.startswith("&") and token.endswith(";"):
            if len(current) + len(token) + len(_closing_tags(open_tags)) > max_length:
                finish_chunk()
            current += token
            continue

        remaining = token
        while remaining:
            available = max_length - len(current) - len(_closing_tags(open_tags))
            if available <= 0:
                finish_chunk()
                available = max_length - len(current) - len(_closing_tags(open_tags))

            cut = _preferred_cut(remaining, available)
            current += remaining[:cut]
            remaining = remaining[cut:]
            if remaining:
                finish_chunk()

    if current:
        chunks.append(current + _closing_tags(open_tags))
    return chunks or [""]


def split_telegram_message(
    text: str,
    *,
    parse_mode: Optional[str] = None,
    max_length: int = TELEGRAM_SAFE_MESSAGE_LENGTH,
) -> List[str]:
    """Return Telegram-safe chunks without dropping text or splitting HTML tags."""
    if max_length < 32:
        raise ValueError("max_length must be at least 32")
    if len(text) <= max_length:
        return [text]
    if parse_mode and parse_mode.upper() == "HTML":
        return _split_html(text, max_length)
    return _split_plain_text(text, max_length)


async def send_message_chunks(
    message: Any,
    text: str,
    *,
    parse_mode: Optional[str] = None,
) -> None:
    """Send a complete response as one or more Telegram-safe messages."""
    for chunk in split_telegram_message(text, parse_mode=parse_mode):
        await message.answer(chunk, parse_mode=parse_mode)
