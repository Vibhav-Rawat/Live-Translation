"""Audio sources: the microphone (live) or an audio file (testing / demos)."""
from __future__ import annotations

import queue
import threading
import time
from typing import Iterator

SAMPLE_RATE = 16000
CHUNK_MS = 100
CHUNK_FRAMES = SAMPLE_RATE * CHUNK_MS // 1000  # 1600 frames = 3200 bytes of 16-bit mono


def list_devices() -> str:
    import sounddevice as sd

    return str(sd.query_devices())


class MicSource:
    """Live microphone, 16 kHz mono 16-bit, sent in 100 ms chunks."""

    audio_format = "pcm_s16le"
    sample_rate = SAMPLE_RATE
    num_channels = 1
    reconnectable = True

    def __init__(self, device=None):
        import sounddevice as sd

        self._q: "queue.Queue[bytes]" = queue.Queue(maxsize=300)
        self._closed = threading.Event()
        self._stream = sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=CHUNK_FRAMES,
            device=device,
            callback=self._callback,
        )
        self._stream.start()

    def _callback(self, indata, frames, time_info, status):
        data = bytes(indata)
        try:
            self._q.put_nowait(data)
        except queue.Full:  # badly behind: drop the oldest chunk
            try:
                self._q.get_nowait()
                self._q.put_nowait(data)
            except (queue.Empty, queue.Full):
                pass

    def clear(self) -> None:
        """Throw away audio that piled up (used after a reconnect so we don't lag behind)."""
        while True:
            try:
                self._q.get_nowait()
            except queue.Empty:
                return

    def chunks(self) -> Iterator[bytes]:
        while True:
            if self._closed.is_set() and self._q.empty():
                return
            try:
                yield self._q.get(timeout=0.2)
            except queue.Empty:
                continue

    def close(self) -> None:
        self._closed.set()
        try:
            self._stream.stop()
            self._stream.close()
        except Exception:
            pass


class FileSource:
    """Streams an audio file at (roughly) real-time speed. Handy for testing without a mic."""

    audio_format = "auto"
    sample_rate = None
    num_channels = None
    reconnectable = False

    def __init__(self, path: str, realtime: bool = True, chunk_bytes: int = 3840):
        self.path = path
        self.realtime = realtime
        self.chunk_bytes = chunk_bytes
        self._closed = threading.Event()

    def clear(self) -> None:
        pass

    def chunks(self) -> Iterator[bytes]:
        with open(self.path, "rb") as fh:
            while not self._closed.is_set():
                data = fh.read(self.chunk_bytes)
                if not data:
                    return
                yield data
                if self.realtime:
                    time.sleep(0.12)

    def close(self) -> None:
        self._closed.set()
