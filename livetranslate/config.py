"""Settings and .env loading."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Union

DEFAULT_URL = "wss://stt-rt.soniox.com/transcribe-websocket"

Device = Union[int, str, None]


def load_dotenv(path: str = ".env") -> None:
    """Tiny .env reader (KEY=value lines). Real environment variables win."""
    p = Path(path)
    if not p.is_file():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass
class Settings:
    api_key: str
    target: str                                  # language YOU want to hear, e.g. "en"
    hints: List[str] = field(default_factory=list)   # languages likely spoken, e.g. ["ko", "en"]
    model: str = "stt-rt-v5"
    url: str = DEFAULT_URL
    tts: str = "edge"                            # edge | system | none
    voice: Optional[str] = None
    device_in: Device = None
    device_out: Device = None
    file: Optional[str] = None
    diarize: bool = False
    save_dir: str = "sessions"
    save_transcript: bool = True
    # how translated text is chopped into spoken phrases
    max_words: int = 6
    idle_ms: int = 600
    # experimental: speak text before it is final, once it stops changing
    early: bool = False
    early_agree: int = 3
    # Soniox latency knobs (None = server default)
    endpoint_delay_ms: Optional[int] = None
    latency_level: Optional[int] = None
    max_non_final_ms: Optional[int] = None
    live_caption: bool = True
    debug: bool = False
