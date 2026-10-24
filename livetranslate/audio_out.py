"""Plays 16-bit mono PCM through the chosen output device (your earbuds)."""
from __future__ import annotations

import queue
import threading
import time
from typing import Callable, Optional


class Player:
    def __init__(self, device=None, samplerate: int = 24000):
        import sounddevice as sd

        # one long-lived stream: opening a stream per phrase would add delay
        self._stream = sd.RawOutputStream(samplerate=samplerate, channels=1, dtype="int16", device=device)
        self._stream.start()
        self._q: "queue.Queue" = queue.Queue()
        self._busy = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def play(self, pcm: bytes, on_start: Optional[Callable[[], None]] = None) -> None:
        self._q.put((pcm, on_start))

    def pending(self) -> int:
        return self._q.qsize() + (1 if self._busy else 0)

    def _run(self) -> None:
        while True:
            item = self._q.get()
            if item is None:
                return
            pcm, on_start = item
            self._busy = True
            try:
                if on_start:
                    on_start()
                self._stream.write(pcm)
            except Exception:
                pass
            finally:
                self._busy = False

    def drain(self, timeout: float = 5.0) -> None:
        end = time.monotonic() + timeout
        while self.pending() and time.monotonic() < end:
            time.sleep(0.05)

    def close(self) -> None:
        self._q.put(None)
        try:
            self._stream.stop()
            self._stream.close()
        except Exception:
            pass
