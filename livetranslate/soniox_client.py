"""Soniox real-time WebSocket client: streams audio up, yields token batches down.

Protocol (from the Soniox docs):
  * connect to wss://stt-rt.soniox.com/transcribe-websocket with an Authorization: Bearer header
  * first message: JSON config (model, audio format, translation, ...)
  * then binary audio frames; an empty TEXT frame ends the stream
  * responses are JSON: {"tokens": [...], "total_audio_proc_ms": ..., "finished": bool}
    or an error object with "error_code".
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from websockets.exceptions import ConnectionClosed, ConnectionClosedOK
from websockets.sync.client import connect

from .config import Settings

END_TOKEN = "<end>"
FATAL_CODES = {400, 401, 402, 403}


@dataclass
class Token:
    text: str
    is_final: bool
    status: Optional[str] = None  # "original" | "translation" | "none"
    language: Optional[str] = None
    source_language: Optional[str] = None
    speaker: Optional[str] = None
    start_ms: Optional[int] = None
    confidence: Optional[float] = None

    @property
    def is_end(self) -> bool:
        return self.text == END_TOKEN

    @property
    def is_translation(self) -> bool:
        return self.status == "translation"


@dataclass
class Batch:
    tokens: List[Token] = field(default_factory=list)
    final_audio_proc_ms: int = 0
    total_audio_proc_ms: int = 0
    finished: bool = False


@dataclass
class Metrics:
    """Rough timing info for --debug."""

    started: Optional[float] = None
    server_lag_ms: Optional[int] = None


class SonioxError(Exception):
    def __init__(self, code: int, kind: str, message: str):
        super().__init__(f"{code} {kind}: {message}")
        self.code = code
        self.kind = kind
        self.message = message

    @property
    def retryable(self) -> bool:
        return self.code not in FATAL_CODES


class ConnectionLost(Exception):
    pass


def build_start_request(s: Settings, source) -> dict:
    req: dict = {
        "model": s.model,
        "audio_format": source.audio_format,
        "translation": {"type": "one_way", "target_language": s.target},
        # endpoint detection finalizes tokens as soon as the speaker pauses -> lower delay
        "enable_endpoint_detection": True,
    }
    if source.audio_format != "auto":
        req["sample_rate"] = source.sample_rate
        req["num_channels"] = source.num_channels
    if s.hints:
        req["language_hints"] = s.hints
    if s.diarize:
        req["enable_speaker_diarization"] = True
    if s.endpoint_delay_ms is not None:
        req["max_endpoint_delay_ms"] = s.endpoint_delay_ms
    if s.latency_level is not None:
        req["endpoint_latency_adjustment_level"] = s.latency_level
    if s.max_non_final_ms is not None:
        req["max_non_final_tokens_duration_ms"] = s.max_non_final_ms
    return req


def parse_batch(msg: dict) -> Batch:
    tokens = []
    for t in msg.get("tokens", []):
        text = t.get("text")
        if not text:
            continue
        tokens.append(
            Token(
                text=text,
                is_final=bool(t.get("is_final")),
                status=t.get("translation_status"),
                language=t.get("language"),
                source_language=t.get("source_language"),
                speaker=t.get("speaker"),
                start_ms=t.get("start_ms"),
                confidence=t.get("confidence"),
            )
        )
    return Batch(
        tokens=tokens,
        final_audio_proc_ms=int(msg.get("final_audio_proc_ms") or 0),
        total_audio_proc_ms=int(msg.get("total_audio_proc_ms") or 0),
        finished=bool(msg.get("finished")),
    )


class SonioxSession:
    def __init__(self, settings: Settings, source, on_batch: Callable[[Batch], None],
                 stop: threading.Event, metrics: Optional[Metrics] = None):
        self.s = settings
        self.source = source
        self.on_batch = on_batch
        self.stop = stop
        self.metrics = metrics or Metrics()
        self.got_data = False

    def _send_audio(self, ws) -> None:
        try:
            for chunk in self.source.chunks():
                ws.send(chunk)
            ws.send("")  # empty text frame = end of audio
        except Exception:
            pass  # connection dropped; the receive loop deals with it

    def run_once(self) -> None:
        headers = {"Authorization": f"Bearer {self.s.api_key}"}
        with connect(self.s.url, additional_headers=headers, open_timeout=10, max_size=None) as ws:
            ws.send(json.dumps(build_start_request(self.s, self.source)))
            self.metrics.started = time.monotonic()
            threading.Thread(target=self._send_audio, args=(ws,), daemon=True).start()
            stop_deadline = None
            while True:
                if self.stop.is_set():
                    stop_deadline = stop_deadline or time.monotonic() + 4.0
                    if time.monotonic() > stop_deadline:
                        return  # server never said "finished"; give up waiting
                try:
                    raw = ws.recv(timeout=0.5)
                except TimeoutError:
                    continue
                except ConnectionClosedOK:
                    return
                except ConnectionClosed as e:
                    raise ConnectionLost(str(e)) from e
                msg = json.loads(raw)
                if msg.get("error_code"):
                    raise SonioxError(
                        int(msg["error_code"]),
                        str(msg.get("error_type") or "error"),
                        str(msg.get("error_message") or ""),
                    )
                batch = parse_batch(msg)
                self.got_data = True
                if self.metrics.started is not None and batch.total_audio_proc_ms:
                    elapsed = (time.monotonic() - self.metrics.started) * 1000
                    self.metrics.server_lag_ms = max(0, int(elapsed - batch.total_audio_proc_ms))
                self.on_batch(batch)
                if batch.finished:
                    return


def run_forever(settings: Settings, source, on_batch: Callable[[Batch], None],
                stop: threading.Event, on_status: Callable[[str], None] = print,
                metrics: Optional[Metrics] = None, backoff_start: float = 1.0) -> None:
    """Run a session; reconnect on transient problems (mic sources only)."""
    backoff = backoff_start
    while True:
        session = SonioxSession(settings, source, on_batch, stop, metrics)
        try:
            session.run_once()
            if stop.is_set() or not source.reconnectable:
                return
            on_status("Connection ended; reconnecting...")
        except SonioxError as e:
            if not e.retryable or not source.reconnectable or stop.is_set():
                raise
            on_status(f"Soniox error {e.code} ({e.kind}); reconnecting...")
        except (ConnectionLost, OSError) as e:
            if not source.reconnectable or stop.is_set():
                raise
            on_status(f"Connection problem ({e}); reconnecting...")
        if session.got_data:
            backoff = backoff_start
        source.clear()  # drop stale audio so we don't fall behind after the gap
        if stop.wait(backoff):
            return
        backoff = min(backoff * 2, 8.0)
