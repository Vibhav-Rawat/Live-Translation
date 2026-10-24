"""Glue: token batches in -> spoken phrases, captions and transcript out."""
from __future__ import annotations

import threading
from typing import Optional

from .config import Settings
from .soniox_client import Batch, Metrics
from .speech_planner import EarlyCommitter, SpeechPlanner
from .transcript import Utterance, UtteranceBuilder


class Pipeline:
    def __init__(self, settings: Settings, speaker, recorder, display,
                 metrics: Optional[Metrics] = None, builder: Optional[UtteranceBuilder] = None):
        self.s = settings
        self.speaker = speaker
        self.recorder = recorder
        self.display = display
        self.metrics = metrics or Metrics()
        self.builder = builder or UtteranceBuilder()
        idle_ms = min(settings.idle_ms, 300) if settings.early else settings.idle_ms
        self.planner = SpeechPlanner(max_words=settings.max_words, idle_ms=idle_ms)
        self.early = EarlyCommitter(settings.early_agree) if settings.early else None
        self._stop = threading.Event()
        self._ticker = threading.Thread(target=self._tick, daemon=True)

    def start(self) -> None:
        self._ticker.start()

    def _tick(self) -> None:
        while not self._stop.wait(0.1):
            self._speak(self.planner.poll())

    def _speak(self, phrases) -> None:
        for phrase in phrases:
            if self.s.debug:
                lag = self.metrics.server_lag_ms
                print(f"[debug] speak {phrase!r} (server lag ~{lag} ms)")
            self.speaker.speak(phrase)

    def _commit(self, utt: Optional[Utterance]) -> None:
        if utt:
            self.recorder.add(utt)
            self.display.show(utt)

    def on_batch(self, batch: Batch) -> None:
        phrases = []
        finals = [t for t in batch.tokens if t.is_final]
        nonfinal = [t for t in batch.tokens if not t.is_final]

        if finals and self.early:
            self.early.reset_history()  # finals shift the non-final region; start agreeing again
        for t in finals:
            self._commit(self.builder.add(t))
            if t.is_end:
                if self.early:
                    self.early.skip = 0
                phrases += self.planner.feed(t.text)
            elif t.is_translation:  # only translations are spoken; your own language is left alone
                text = self.early.on_final_translation(t.text) if self.early else t.text
                if text:
                    phrases += self.planner.feed(text)

        nf_translation = "".join(t.text for t in nonfinal if t.is_translation)
        nf_original = "".join(t.text for t in nonfinal if not t.is_translation and not t.is_end)
        self.display.update_partial(nf_original, nf_translation)
        if self.early:
            if nf_translation:
                new = self.early.on_nonfinal(nf_translation)
                if new:
                    phrases += self.planner.feed_text(new)
            else:
                self.early.reset_history()

        self._speak(phrases)

    def close(self) -> None:
        self._stop.set()
        self._commit(self.builder.flush())
