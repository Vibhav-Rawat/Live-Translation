import json
import threading
import time

from websockets.sync.server import serve


class ListSource:
    """Pretends to be a mic: a few silent chunks, then ends."""

    audio_format = "pcm_s16le"
    sample_rate = 16000
    num_channels = 1

    def __init__(self, chunks=8, reconnectable=False):
        self.n = chunks
        self.reconnectable = reconnectable

    def chunks(self):
        for _ in range(self.n):
            yield b"\x00" * 3200
            time.sleep(0.02)

    def clear(self):
        pass

    def close(self):
        pass


def tok(text, final=True, status="original", **kw):
    d = {"text": text, "is_final": final, "translation_status": status}
    d.update(kw)
    return d


def start_server(handler):
    server = serve(handler, "127.0.0.1", 0)
    port = server.socket.getsockname()[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"ws://127.0.0.1:{port}"


def read_until_end_of_audio(ws):
    """Receive frames until the client sends the empty text frame."""
    first_audio = False
    while True:
        msg = ws.recv()
        if msg == "":
            return
        if isinstance(msg, bytes) and not first_audio:
            first_audio = True
            yield


def send(ws, tokens, total_ms=0, finished=False):
    ws.send(json.dumps({"tokens": tokens, "final_audio_proc_ms": total_ms,
                        "total_audio_proc_ms": total_ms, "finished": finished}))
