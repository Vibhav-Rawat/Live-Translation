"""Turns the token stream into utterances and saves a readable transcript."""
from __future__ import annotations

import datetime
import json
import os
import time
from collections import Counter
from dataclasses import dataclass, asdict
from typing import Callable, List, Optional

from .soniox_client import Token


@dataclass
class Utterance:
    t0: float                       # seconds since the program started
    original: str
    translation: str
    source_language: Optional[str] = None
    speaker: Optional[str] = None


def fmt_time(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


class UtteranceBuilder:
    """Collects FINAL tokens and emits one Utterance each time the speaker pauses (<end>)."""

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._t_start = clock()
        self._reset()

    def _reset(self) -> None:
        self._orig = ""
        self._tr = ""
        self._t0: Optional[float] = None
        self._langs: Counter = Counter()
        self._speakers: Counter = Counter()

    def add(self, token: Token) -> Optional[Utterance]:
        if token.is_end:
            return self.flush()
        if self._t0 is None:
            self._t0 = self._clock() - self._t_start
        if token.is_translation:
            self._tr += token.text
        else:
            self._orig += token.text
            if token.language:
                self._langs[token.language] += 1
            if token.speaker:
                self._speakers[token.speaker] += 1
        return None

    def flush(self) -> Optional[Utterance]:
        original, translation = self._orig.strip(), self._tr.strip()
        if not original and not translation:
            self._reset()
            return None
        utt = Utterance(
            t0=self._t0 or 0.0,
            original=original,
            translation=translation,
            source_language=self._langs.most_common(1)[0][0] if self._langs else None,
            speaker=self._speakers.most_common(1)[0][0] if self._speakers else None,
        )
        self._reset()
        return utt


def render_markdown(utterances: List[Utterance], target: str, when: Optional[datetime.datetime] = None) -> str:
    when = when or datetime.datetime.now()
    lines = [
        "# Conversation transcript",
        "",
        f"*{when:%d %B %Y, %H:%M} | translated into: {target}. Auto-generated, may contain errors.*",
        "",
    ]
    for u in utterances:
        who = f" Speaker {u.speaker}" if u.speaker else ""
        lang = f" ({u.source_language})" if u.source_language else ""
        lines.append(f"**[{fmt_time(u.t0)}]{who}**{lang}")
        lines.append("")
        if u.original:
            lines += [f"> \u201c{u.original}\u201d", ""]
        if u.translation:
            lines += [f"*Translation:* \u201c{u.translation}\u201d", ""]
    return "\n".join(lines)


class TranscriptRecorder:
    """Keeps utterances; appends each to a .jsonl as it happens (crash-safe), writes .md at the end."""

    def __init__(self, directory: str, target: str, enabled: bool = True):
        self.enabled = enabled
        self.target = target
        self.utterances: List[Utterance] = []
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.jsonl_path = os.path.join(directory, f"transcript_{stamp}.jsonl")
        self.md_path = os.path.join(directory, f"transcript_{stamp}.md")
        self._dir = directory
        self._fh = None

    def add(self, utt: Utterance) -> None:
        self.utterances.append(utt)
        if not self.enabled:
            return
        if self._fh is None:
            os.makedirs(self._dir, exist_ok=True)
            self._fh = open(self.jsonl_path, "a", encoding="utf-8")
        self._fh.write(json.dumps(asdict(utt), ensure_ascii=False) + "\n")
        self._fh.flush()

    def finish(self) -> Optional[str]:
        if self._fh:
            self._fh.close()
            self._fh = None
        if not self.enabled or not self.utterances:
            return None
        os.makedirs(self._dir, exist_ok=True)
        with open(self.md_path, "w", encoding="utf-8") as f:
            f.write(render_markdown(self.utterances, self.target))
        return self.md_path
