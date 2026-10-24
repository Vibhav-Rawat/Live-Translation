"""Console output: a live caption line while someone talks, and a clean log of finished sentences."""
from __future__ import annotations

import os
import shutil
import sys

from .transcript import Utterance, fmt_time


class Display:
    def __init__(self, live_caption: bool = True, stream=None):
        self.stream = stream or sys.stdout
        self.live = live_caption and getattr(self.stream, "isatty", lambda: False)()
        self._partial = False
        if os.name == "nt":
            os.system("")  # lets Windows terminals understand the ANSI codes below

    def _write(self, s: str) -> None:
        self.stream.write(s)
        self.stream.flush()

    def _clear_partial(self) -> None:
        if self._partial:
            self._write("\r\x1b[2K")
            self._partial = False

    def update_partial(self, original: str, translation: str) -> None:
        if not self.live:
            return
        text = (translation or original).strip()
        if not text:
            return
        width = max(20, shutil.get_terminal_size((100, 20)).columns - 4)
        self._write("\r\x1b[2K" + "\u2026 " + text[-width:])
        self._partial = True

    def show(self, utt: Utterance) -> None:
        self._clear_partial()
        who = f" Speaker {utt.speaker}" if utt.speaker else ""
        lang = f" ({utt.source_language})" if utt.source_language else ""
        head = f"[{fmt_time(utt.t0)}]{who}{lang}"
        if utt.original:
            self._write(f"{head}  {utt.original}\n")
        if utt.translation:
            self._write(f"{' ' * len(head)}  -> {utt.translation}\n")

    def info(self, message: str) -> None:
        self._clear_partial()
        self._write(message + "\n")

    def close(self) -> None:
        self._clear_partial()
