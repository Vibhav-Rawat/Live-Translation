"""Decides WHEN to speak: chops the stream of translated tokens into short phrases.

Waiting for whole sentences adds seconds of delay, so we speak as soon as we have a
natural chunk: sentence end, a clause break with a few words, or N words.
"""
from __future__ import annotations

import re
import threading
import time
from collections import deque
from typing import Callable, Deque, List

END_TOKEN = "<end>"
SENTENCE_END = (".", "!", "?", "\u3002", "\uff01", "\uff1f", "\u2026", "\u0964", "\u061f")
CLAUSE_END = (",", ";", ":", "\uff0c", "\uff1b", "\uff1a", "\u3001", "\u060c")
CLOSERS = "\"'\u201d\u2019)]}"
NO_SPACE_SCRIPT = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\u0e00-\u0e7f]")  # kana, Han, Thai
DIGIT_DOT = re.compile(r"\d\.$")


class SpeechPlanner:
    def __init__(self, max_words: int = 6, min_clause_words: int = 3, idle_ms: int = 600,
                 cjk_chars: int = 16, clock: Callable[[], float] = time.monotonic):
        self.max_words = max_words
        self.min_clause_words = min_clause_words
        self.idle_s = idle_ms / 1000
        self.cjk_chars = cjk_chars
        self._clock = clock
        self._buf = ""
        self._last = clock()
        self._defer_dot = False  # saw "3." -> might be a decimal number, wait for the next token
        self._lock = threading.Lock()

    # -- helpers ---------------------------------------------------------
    def _units(self) -> int:
        return len(self._buf.split())

    def _flush_into(self, out: List[str]) -> None:
        phrase = " ".join(self._buf.split())
        self._buf = ""
        self._defer_dot = False
        if phrase and any(c.isalnum() for c in phrase):  # don't speak a stray quote mark
            out.append(phrase)

    # -- public ----------------------------------------------------------
    def feed(self, text: str) -> List[str]:
        """Feed one translated token (may be a word piece). Returns phrases ready to speak."""
        out: List[str] = []
        with self._lock:
            if text == END_TOKEN:
                self._flush_into(out)
                return out
            self._last = self._clock()
            if self._defer_dot:
                self._defer_dot = False
                if not text[:1].isdigit():
                    self._flush_into(out)
            # too many words already: flush before a token that starts a new word
            if self._buf and text[:1].isspace() and self._units() >= self.max_words:
                self._flush_into(out)
            self._buf += text
            tail = self._buf.rstrip().rstrip(CLOSERS)
            if tail.endswith(SENTENCE_END):
                if DIGIT_DOT.search(tail):
                    self._defer_dot = True
                else:
                    self._flush_into(out)
            elif tail.endswith(CLAUSE_END) and self._units() >= self.min_clause_words:
                self._flush_into(out)
            elif NO_SPACE_SCRIPT.search(self._buf) and len(self._buf.strip()) >= self.cjk_chars:
                self._flush_into(out)
        return out

    def feed_text(self, text: str) -> List[str]:
        """Feed a multi-word string (used by early mode)."""
        out: List[str] = []
        pieces = re.findall(r"\s*\S+", text) or ([text] if text else [])
        for piece in pieces:
            out += self.feed(piece)
        return out

    def poll(self) -> List[str]:
        """Call regularly: flushes a half-finished phrase that has been waiting too long."""
        out: List[str] = []
        with self._lock:
            if self._buf.strip() and self._clock() - self._last >= self.idle_s:
                self._flush_into(out)
        return out

    def flush(self) -> List[str]:
        out: List[str] = []
        with self._lock:
            self._flush_into(out)
        return out


class EarlyCommitter:
    """EXPERIMENTAL. Speak translated words before they are final, once they stop changing.

    Soniox sends non-final tokens that can still be revised. If the same prefix shows up in
    `agree` responses in a row, we treat it as stable. When the final tokens arrive later we
    skip the part that was already spoken.
    """

    def __init__(self, agree: int = 3):
        self.agree = max(2, agree)
        self.history: Deque[str] = deque(maxlen=self.agree)
        self.skip = 0  # characters already spoken early that finals haven't covered yet

    def reset_history(self) -> None:
        self.history.clear()

    def on_final_translation(self, text: str) -> str:
        """Returns the part of a final token's text that was NOT already spoken early."""
        if self.skip <= 0:
            return text
        take = min(self.skip, len(text))
        self.skip -= take
        return text[take:]

    def on_nonfinal(self, text: str) -> str:
        """Called once per response with the whole current non-final translation text."""
        self.history.append(text)
        if len(self.history) < self.agree:
            return ""
        prefix = _common_prefix(list(self.history))
        cut = prefix.rfind(" ")  # never speak a possibly-unfinished last word
        if cut < 0:
            cut = len(prefix) - 2 if (" " not in prefix and len(prefix) > 6) else 0
        stable = prefix[:cut]
        if len(stable) <= self.skip:
            return ""
        new = stable[self.skip:]
        self.skip = len(stable)
        return new


def _common_prefix(items: List[str]) -> str:
    first = min(items)
    last = max(items)
    i = 0
    while i < len(first) and i < len(last) and first[i] == last[i]:
        i += 1
    return first[:i]
