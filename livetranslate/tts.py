"""Voices. Speaks translated phrases into your earbuds.

  edge   - Microsoft Edge online voices via the `edge-tts` package (free, many languages)
  system - the voice built into your OS via pyttsx3 (offline, robotic)
  none   - captions only
"""
from __future__ import annotations

import asyncio
import queue
import threading
import time
from typing import List, Optional

PREFERRED_LOCALE = {
    "en": "en-US", "zh": "zh-CN", "pt": "pt-BR", "es": "es-ES", "fr": "fr-FR", "de": "de-DE",
    "ar": "ar-SA", "hi": "hi-IN", "ko": "ko-KR", "ja": "ja-JP", "ru": "ru-RU", "it": "it-IT",
}


def pick_edge_voice(lang: str, voices: List[dict]) -> Optional[str]:
    """Pick an edge-tts voice for a language code like 'en', 'ko', 'pt-BR'."""
    lang_l = lang.lower()
    base = lang_l.split("-")[0]
    prefix = lang_l if "-" in lang_l else base + "-"
    cands = [v for v in voices if v["Locale"].lower().startswith(prefix)]
    if not cands:
        return None
    pref = PREFERRED_LOCALE.get(base) if "-" not in lang_l else None
    cands.sort(key=lambda v: v["Locale"] != pref)  # stable: keeps the service's order otherwise
    return cands[0]["ShortName"]


class Speaker:
    """Base class: speak() must return immediately."""

    def speak(self, text: str) -> None:
        raise NotImplementedError

    def drain(self, timeout: float = 5.0) -> None:
        pass

    def close(self) -> None:
        pass


class NullSpeaker(Speaker):
    def speak(self, text: str) -> None:
        pass


class ListSpeaker(Speaker):
    """Collects phrases (used in tests)."""

    def __init__(self):
        self.phrases: List[str] = []

    def speak(self, text: str) -> None:
        self.phrases.append(text)


class SystemSpeaker(Speaker):
    def __init__(self, lang: str = "en"):
        self.lang = lang.lower()
        self._q: "queue.Queue" = queue.Queue()
        self._busy = False
        threading.Thread(target=self._run, daemon=True).start()

    def speak(self, text: str) -> None:
        self._q.put(text)

    def _run(self) -> None:
        import pyttsx3

        engine = pyttsx3.init()
        try:
            for v in engine.getProperty("voices"):
                if self.lang in (str(getattr(v, "languages", "")) + v.id).lower():
                    engine.setProperty("voice", v.id)
                    break
        except Exception:
            pass
        while True:
            text = self._q.get()
            if text is None:
                return
            self._busy = True
            try:
                engine.say(text)
                engine.runAndWait()
            except Exception:
                pass
            finally:
                self._busy = False

    def drain(self, timeout: float = 5.0) -> None:
        end = time.monotonic() + timeout
        while (not self._q.empty() or self._busy) and time.monotonic() < end:
            time.sleep(0.05)

    def close(self) -> None:
        self._q.put(None)


async def _synth(text: str, voice: str, rate: str) -> bytes:
    import edge_tts

    com = edge_tts.Communicate(text, voice, rate=rate)
    parts = []
    async for chunk in com.stream():
        if chunk["type"] == "audio":
            parts.append(chunk["data"])
    return b"".join(parts)


def decode_mp3(mp3: bytes) -> bytes:
    import miniaudio

    dec = miniaudio.decode(mp3, output_format=miniaudio.SampleFormat.SIGNED16, nchannels=1, sample_rate=24000)
    return bytes(dec.samples)


class EdgeSpeaker(Speaker):
    """Synthesizes the next phrase while the previous one is still playing."""

    def __init__(self, voice: str, lang: str, device_out=None, debug: bool = False):
        from .audio_out import Player

        self.voice = voice
        self.lang = lang
        self.debug = debug
        self._player = Player(device_out)
        self._q: "queue.Queue" = queue.Queue()
        self._busy = False
        self._fallback: Optional[SystemSpeaker] = None
        threading.Thread(target=self._run, daemon=True).start()

    def speak(self, text: str) -> None:
        self._q.put((text, time.monotonic()))

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        while True:
            item = self._q.get()
            if item is None:
                return
            text, queued_at = item
            self._busy = True
            try:
                backlog = self._q.qsize() + self._player.pending()
                rate = "+25%" if backlog >= 2 else "+0%"  # only speed up to catch up
                mp3 = loop.run_until_complete(_synth(text, self.voice, rate))
                pcm = decode_mp3(mp3)

                def started(q=queued_at, t=text):
                    if self.debug:
                        print(f"[debug] voice started {int((time.monotonic() - q) * 1000)} ms after phrase was ready: {t!r}")

                self._player.play(pcm, started)
            except Exception as e:
                if self._fallback is None:
                    print(f"[voice] online voice failed ({e}); falling back to the system voice")
                    self._fallback = SystemSpeaker(self.lang)
                self._fallback.speak(text)
            finally:
                self._busy = False

    def drain(self, timeout: float = 8.0) -> None:
        end = time.monotonic() + timeout
        while (not self._q.empty() or self._busy) and time.monotonic() < end:
            time.sleep(0.05)
        self._player.drain(max(0.0, end - time.monotonic()))

    def close(self) -> None:
        self._q.put(None)
        self._player.close()


def make_speaker(settings) -> Speaker:
    if settings.tts == "none":
        return NullSpeaker()
    if settings.tts == "system":
        return SystemSpeaker(settings.target)
    voice = settings.voice
    if not voice:
        try:
            import edge_tts

            voices = asyncio.run(edge_tts.list_voices())
            voice = pick_edge_voice(settings.target, voices)
        except Exception as e:
            print(f"[voice] couldn't reach the online voice service ({e}); using the system voice")
            return SystemSpeaker(settings.target)
    if not voice:
        print(f"[voice] no online voice for '{settings.target}'; using the system voice")
        return SystemSpeaker(settings.target)
    return EdgeSpeaker(voice, settings.target, settings.device_out, settings.debug)
