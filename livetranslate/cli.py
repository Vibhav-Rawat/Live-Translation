"""Command line entry point:  python -m livetranslate --target en"""
from __future__ import annotations

import argparse
import os
import signal
import sys
import threading
from typing import List, Optional

from . import demo
from .audio_in import FileSource, MicSource, list_devices
from .config import DEFAULT_URL, Settings, load_dotenv
from .display import Display
from .pipeline import Pipeline
from .soniox_client import Metrics, SonioxError, run_forever
from .transcript import TranscriptRecorder
from .tts import make_speaker


def _device(value: Optional[str]):
    if value is None:
        return None
    return int(value) if value.isdigit() else value


def _csv(value: Optional[str]) -> List[str]:
    return [v.strip() for v in value.split(",") if v.strip()] if value else []


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="livetranslate",
        description="Live speech translation into your earbuds. Whatever is spoken near the mic "
                    "in another language is translated into --target and spoken to you.",
    )
    p.add_argument("-t", "--target", help="YOUR language code, e.g. en, ko, hi, es (or set LT_TARGET)")
    p.add_argument("--hints", help="languages likely to be spoken, comma separated, e.g. ko,en (improves accuracy)")
    p.add_argument("--tts", choices=["edge", "system", "none"], default="edge",
                   help="voice: edge (online, natural), system (offline), none (captions only)")
    p.add_argument("--voice", help="edge-tts voice name, e.g. en-US-AriaNeural (see: edge-tts --list-voices)")
    p.add_argument("--device-in", help="microphone id or name (see --list-devices)")
    p.add_argument("--device-out", help="earbuds/speaker id or name (see --list-devices)")
    p.add_argument("--list-devices", action="store_true", help="show audio devices and exit")
    p.add_argument("--file", help="stream an audio file instead of the microphone (for testing)")
    p.add_argument("--demo", action="store_true",
                   help="replay a scripted Korean conversation (no mic, no API key) to test captions, voice and earbuds")
    p.add_argument("--demo-speed", type=float, default=1.0, help=argparse.SUPPRESS)
    p.add_argument("--diarize", action="store_true", help="label who is speaking (Speaker 1, 2...)")
    p.add_argument("--no-transcript", action="store_true", help="don't save a transcript")
    p.add_argument("--save-dir", default="sessions", help="where transcripts are saved")
    p.add_argument("--no-live-caption", action="store_true", help="don't show the live caption line")
    p.add_argument("--model", default="stt-rt-v5")
    g = p.add_argument_group("speed tuning")
    g.add_argument("--max-words", type=int, default=6, help="speak after this many words if no pause (lower = faster, choppier)")
    g.add_argument("--idle-ms", type=int, default=600, help="speak a half-finished phrase after this much silence")
    g.add_argument("--early", action="store_true", help="EXPERIMENTAL: speak words before they're final once they stop changing")
    g.add_argument("--early-agree", type=int, default=3, help="--early: how many updates in a row must agree")
    g.add_argument("--endpoint-delay-ms", type=int, help="Soniox max_endpoint_delay_ms (500-3000)")
    g.add_argument("--latency-level", type=int, help="Soniox endpoint_latency_adjustment_level (0-3)")
    g.add_argument("--max-non-final-ms", type=int, help="Soniox max_non_final_tokens_duration_ms")
    p.add_argument("--debug", action="store_true", help="print timing info")
    return p


def run_demo(args) -> int:
    settings = Settings(
        api_key="demo", target="en", tts=args.tts, voice=args.voice,
        device_out=_device(args.device_out), save_dir=args.save_dir,
        save_transcript=not args.no_transcript, max_words=args.max_words, idle_ms=args.idle_ms,
        live_caption=not args.no_live_caption, debug=args.debug,
    )
    speaker = make_speaker(settings)
    display = Display(settings.live_caption)
    recorder = TranscriptRecorder(settings.save_dir, settings.target, settings.save_transcript)
    pipeline = Pipeline(settings, speaker, recorder, display)
    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    display.info("DEMO: a scripted Korean conversation, translated into English. No mic, no API key.")
    display.info("You should see captions and hear English in your output device. Ctrl+C to stop.\n")
    pipeline.start()
    try:
        demo.play(pipeline.on_batch, stop, args.demo_speed)
    finally:
        pipeline.close()
        if not stop.is_set():
            speaker.drain(10)
        path = recorder.finish()
        display.close()
        speaker.close()
        if path:
            print(f"Transcript saved: {path}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Korean/Hindi/etc. on Windows consoles
    except Exception:
        pass
    load_dotenv()
    args = build_parser().parse_args(argv)

    if args.list_devices:
        print(list_devices())
        return 0

    if args.demo:
        return run_demo(args)

    api_key = os.environ.get("SONIOX_API_KEY", "").strip()
    if not api_key:
        print("Missing SONIOX_API_KEY. Put it in a .env file (see .env.example) or set the environment variable.")
        return 2
    target = args.target or os.environ.get("LT_TARGET", "").strip()
    if not target:
        print("Tell me your language with --target (e.g. --target en) or set LT_TARGET in .env.")
        return 2

    settings = Settings(
        api_key=api_key,
        target=target,
        hints=_csv(args.hints),
        model=args.model,
        url=os.environ.get("SONIOX_WS_URL", DEFAULT_URL),
        tts=args.tts,
        voice=args.voice,
        device_in=_device(args.device_in),
        device_out=_device(args.device_out),
        file=args.file,
        diarize=args.diarize,
        save_dir=args.save_dir,
        save_transcript=not args.no_transcript,
        max_words=args.max_words,
        idle_ms=args.idle_ms,
        early=args.early,
        early_agree=args.early_agree,
        endpoint_delay_ms=args.endpoint_delay_ms,
        latency_level=args.latency_level,
        max_non_final_ms=args.max_non_final_ms,
        live_caption=not args.no_live_caption,
        debug=args.debug,
    )

    source = FileSource(settings.file) if settings.file else MicSource(settings.device_in)
    speaker = make_speaker(settings)
    display = Display(settings.live_caption)
    recorder = TranscriptRecorder(settings.save_dir, settings.target, settings.save_transcript)
    metrics = Metrics()
    pipeline = Pipeline(settings, speaker, recorder, display, metrics)

    stop = threading.Event()

    def on_interrupt(*_):
        stop.set()
        source.close()  # lets the last bit of audio flush, then the session ends cleanly

    signal.signal(signal.SIGINT, on_interrupt)

    display.info(f"Listening... anything not in '{target}' will be translated and spoken to you. Ctrl+C to stop.")
    pipeline.start()
    code = 0
    try:
        run_forever(settings, source, pipeline.on_batch, stop, on_status=display.info, metrics=metrics)
    except SonioxError as e:
        display.info(f"\nStopped: {e}")
        if e.code == 401:
            display.info("Check SONIOX_API_KEY.")
        elif e.code == 402:
            display.info("Your Soniox balance or budget is used up.")
        code = 1
    except Exception as e:  # network down etc.
        display.info(f"\nStopped: {e}")
        code = 1
    finally:
        pipeline.close()
        if not stop.is_set():
            speaker.drain(8)  # file finished: let the last phrases play
        path = recorder.finish()
        display.close()
        speaker.close()
        source.close()
        if path:
            print(f"Transcript saved: {path}")
    return code


if __name__ == "__main__":
    sys.exit(main())
