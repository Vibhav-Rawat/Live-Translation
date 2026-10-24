# LiveTranslate

**Real-time speech translation, delivered directly to your earbuds.**

LiveTranslate is a Python-based live interpretation system designed to help people understand conversations spoken in another language—without interrupting the speakers.
Place your laptop near a conversation, select the language you want to hear, and LiveTranslate streams the incoming audio for speech recognition and translation. Translated phrases are converted into speech and played through your output device while live captions and a transcript provide a visual record.

The goal is simple: **make multilingual conversations easier to follow without requiring people to stop, repeat themselves, or translate every sentence manually.**

> **Status:** Early-stage project. Real-world latency, translation quality, and reliability depend on the language pair, network, and audio conditions.

#URL:

## How It Works

```text
        Live conversation
                |
                v
        Microphone input
                |
                v
    Soniox streaming API
  Speech recognition + translation
                |
                v
         Phrase planner
                |
         +------+------+
         |             |
         v             v
   Text-to-speech   Live captions
         |             |
         v             v
    Earbuds/audio   Saved transcript
```

### Core Features

* **Real-time speech translation:** Streams microphone audio to the configured Soniox API for ongoing speech recognition and translation, without requiring a complete recording before processing begins.
* **Audio file translation:** Process existing audio recordings using `--file`, making it possible to translate recorded conversations and other supported audio files.
* **Automatic transcript generation:** Save the original speech and its translation in Markdown (`.md`) and JSONL (`.jsonl`) formats for readable review and further processing.
* **Timestamped conversation records:** Organize transcript entries by session-relative timestamps, with source-language information and optional speaker labels where available.
* **Phrase-based speech playback:** Groups translated text into manageable phrases to balance responsiveness and intelligibility during live interpretation.
* **Configurable output language:** Choose the target language for translated speech.
* **Multiple text-to-speech options:** Supports online Edge TTS, a system voice, or captions without speech output.
* **Live captions:** Display incoming speech and translations directly in the terminal.
* **Flexible audio input:** Choose between a microphone for live conversations and an existing audio file for recorded speech.
* **Optional speaker diarization:** Supports speaker identification where available through the configured speech-processing service.
* **Experimental low-latency mode:** Explores faster playback by using translation text before the transcription or translation is finalized.
* **Configurable transcript storage:** Choose the output directory for saved session transcripts.
* **Demo mode:** Explore the processing pipeline using a scripted conversation without a microphone or Soniox API key.


## Latency and Continuous Conversation

LiveTranslate is designed to minimize the delay between someone speaking and the translated phrase reaching the listener.

However, streaming does not mean zero delay. The system must receive enough speech to recognize the words, determine a useful translation, prepare the audio, and play it back.

This is particularly challenging for languages such as Korean and Japanese, where important grammatical information can appear near the end of a sentence. Speaking too early may produce incomplete or awkward translations; waiting too long makes the conversation harder to follow.

LiveTranslate uses phrase planning to balance these competing needs.

You can experiment with:

| Option          | Effect                                                                     |
| --------------- | -------------------------------------------------------------------------- |
| `--max-words 4` | Speak shorter phrases sooner, potentially making playback less natural.    |
| `--idle-ms 250` | Flush an unfinished phrase after a shorter period of silence.              |
| `--hints ko,en` | Provide expected language hints, where supported by the API configuration. |
| `--early`       | Enable experimental playback using non-final translation text.             |
| `--debug`       | Inspect diagnostic timing information, where available.                    |

Actual end-to-end latency should be measured on your own setup. Microphone buffering, network response time, translation behavior, speech synthesis, and audio playback all contribute to the total delay.

## Requirements

* Python 3.12 recommended
* A microphone or supported audio file
* Speakers or earbuds for spoken translation
* Internet connection for Soniox and online Edge TTS
* A Soniox API key for live translation

The demo mode does not require a Soniox API key.

## Installation

### 1. Clone the repository

```bash
git clone <your-repository-url>
cd livetranslate
```

Replace `<your-repository-url>` with your GitHub repository URL.

### 2. Create a virtual environment

**Windows (PowerShell or Command Prompt):**

```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
```

**macOS / Linux:**

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

To install development and testing dependencies:

```bash
pip install -r requirements-dev.txt
```

On Linux, you may also need the PortAudio system library. On Debian or Ubuntu:

```bash
sudo apt install libportaudio2
```

### 4. Configure your API key

Create a `.env` file based on the example:

```bash
cp .env.example .env
```

On Windows, you can copy `.env.example` to `.env` manually or use:

```powershell
Copy-Item .env.example .env
```

Add your Soniox API key and any desired configuration to `.env`.

Get an API key from the [Soniox Console](https://console.soniox.com/). Check the [Soniox pricing page](https://soniox.com/pricing) for current rates; API costs can change.

**Security:** Never commit your real `.env` file or API key to GitHub.

## Run the Demo

Try the pipeline without configuring a microphone or Soniox API key:

```bash
python -m livetranslate --demo
```

The demo replays a scripted Korean conversation through the local pipeline so you can explore the captioning, phrase planning, speech output, and transcript workflow.

Use the system voice if you want to avoid the online Edge TTS service:

```bash
python -m livetranslate --demo --tts system
```

The demo uses scripted input. It does **not** establish the accuracy, latency, or reliability of live translation.

## Run Live Translation

### 1. Find your audio devices

```bash
python -m livetranslate --list-devices
```

Identify the microphone and the output device connected to your earbuds.

### 2. Start translating

For example, to translate Korean speech into English:

```bash
python -m livetranslate --target en --hints ko,en
```

If you need to select specific devices:

```bash
python -m livetranslate --target en --hints ko,en --device-in 1 --device-out 5
```

Device numbers vary by computer, so replace `1` and `5` with the values shown on your system.

### 3. Stop the session

Press `Ctrl+C` to stop the program. The application is designed to save the session transcript in the `sessions/` directory.

### Translate an Existing Audio File

LiveTranslate can process an existing audio recording instead of capturing audio from your microphone. This lets you translate recorded conversations, language-learning material, interviews, or other supported audio files and save the results as a transcript.

#### Run audio file translation

```powershell
python -m livetranslate --file "path\to\your\audio.wav" --target en --tts none
```

Replace the example path with the location of your audio file. Set `--target` to the language you want the speech translated into.

**Example:**

```powershell
python -m livetranslate --file "recording.wav" --target en --tts none
```

The application streams the audio through the speech-processing pipeline, receives recognition and translation results, and saves the resulting transcript.

#### Transcript output

By default, transcripts are saved in the `sessions/` directory.

The application supports:

* **Markdown (`.md`)** — a readable transcript containing the original speech and its translation.
* **JSONL (`.jsonl`)** — structured transcript records that can be processed programmatically.

Transcript entries can include the original text, translated text, source-language information, speaker labels when available, and timestamps relative to the start of the session.

To choose a different output directory, use `--save-dir`:

```powershell
python -m livetranslate --file "recording.wav" --target en --tts none --save-dir sessions
```

The `--tts none` option disables spoken translation, making this command useful when your primary goal is to generate a written transcript.

**Note:** The timestamps currently represent when the application processes an utterance relative to the session start; they are not guaranteed to be precise word-level timestamps from the original recording. Recognition and translation quality depend on the audio, language, network connection, and speech-processing service.


## Command-Line Options

| Option                     | Description                                          |
| -------------------------- | ---------------------------------------------------- |
| `--target en`              | Select the language you want to hear.                |
| `--hints ko,en`            | Supply expected language hints.                      |
| `--list-devices`           | List available audio devices.                        |
| `--device-in N`            | Select the audio input device.                       |
| `--device-out N`           | Select the audio output device.                      |
| `--tts edge`               | Use online Edge TTS.                                 |
| `--tts system`             | Use the system speech engine.                        |
| `--tts none`               | Disable spoken output.                               |
| `--voice en-US-AriaNeural` | Select an Edge TTS voice, if supported.              |
| `--max-words N`            | Configure the phrase-length threshold.               |
| `--idle-ms N`              | Configure the silence timeout for flushing a phrase. |
| `--diarize`                | Enable speaker diarization, where supported.         |
| `--early`                  | Enable experimental early translation playback.      |
| `--no-transcript`          | Disable transcript saving.                           |
| `--debug`                  | Print diagnostic information, where implemented.     |

For the complete list of available arguments, run:

```bash
python -m livetranslate --help
```

## Transcripts

When transcript saving is enabled, session output is stored in the `sessions/` directory.

The application supports:

* **Markdown (`.md`):** A human-readable conversation record.
* **JSONL (`.jsonl`):** A structured, line-oriented format suitable for further processing.

Depending on the implementation, records may include timestamps, original speech, translations, and speaker labels.

Because transcripts can contain private conversations, review the saved files before sharing them publicly.

## Project Structure

```text
livetranslate/
├── __init__.py
├── __main__.py
├── cli.py
├── config.py
├── audio_in.py
├── audio_out.py
├── soniox_client.py
├── speech_planner.py
├── pipeline.py
├── tts.py
├── transcript.py
└── display.py

tests/
    Unit and integration tests

.env.example
.gitignore
requirements.txt
requirements-dev.txt
README.md
```

The exact test files and configuration depend on the current repository contents.

### Architecture Overview

| Component           | Responsibility                                                                        |
| ------------------- | ------------------------------------------------------------------------------------- |
| `audio_in.py`       | Captures microphone input or streams audio from a file.                               |
| `soniox_client.py`  | Manages the streaming connection and processes recognition/translation results.       |
| `speech_planner.py` | Determines when translated text should be converted into a spoken phrase.             |
| `pipeline.py`       | Coordinates incoming text, phrase planning, captions, transcripts, and speech output. |
| `tts.py`            | Provides speech synthesis options.                                                    |
| `audio_out.py`      | Handles audio playback.                                                               |
| `transcript.py`     | Builds and saves conversation transcripts.                                            |
| `display.py`        | Displays live captions.                                                               |
| `cli.py`            | Parses command-line options and initializes the application.                          |
| `config.py`         | Loads configuration and environment settings.                                         |

## Testing

Install the development dependencies:

```bash
pip install -r requirements-dev.txt
```

Run the test suite:

```bash
python -m pytest
```

Tests are intended to validate components without requiring physical audio devices or a live translation session, where the relevant tests use mocks or a test server.

**Test status:** Add the actual test results here after running the suite. Do not describe the tests as passing until you have verified that they do.

## Limitations

* **Network dependency:** Live translation requires an internet connection and sends audio to Soniox for processing.
* **Speech synthesis dependency:** Edge TTS uses an online service through the community `edge-tts` package. Its behavior and availability may change.
* **Translation quality:** Results depend on the language pair, speech clarity, context, and recognition quality.
* **Overlapping speakers:** Simultaneous speech can reduce recognition and translation accuracy.
* **Phrase boundaries:** Shorter phrases may reduce delay but can sound less natural or omit context.
* **Early mode:** Non-final translations may change, so early playback can result in inaccurate or repeated speech if revisions are not handled correctly.
* **One-way interpretation:** The current design translates for the person running the application. Two-way interpretation would require an additional setup.
* **Privacy and cost:** Audio processing and online speech synthesis may involve third-party services. Review their terms, data handling policies, and pricing before using the system for sensitive conversations.

This project is an experimental tool, not a replacement for a qualified interpreter in medical, legal, or other high-stakes situations.

## Roadmap

Planned improvements include:

* A mobile client built with Flutter.
* A secure backend for issuing short-lived credentials instead of embedding long-lived API keys in a client.
* Improved handling of changing non-final translations.
* More comprehensive latency measurements and real-world evaluation.
* Better recovery from network interruptions and audio-device failures.
* Optional device pairing and more flexible interpretation workflows.

These are planned improvements, not claims about functionality already implemented.

## Technologies

* **Python** — application logic and orchestration
* **WebSockets** — streaming communication with the speech API
* **Soniox** — streaming speech recognition and translation
* **SoundDevice** — audio input and output
* **Edge TTS / system speech engine** — spoken translation
* **Pytest** — automated testing

## Motivation

Language barriers can make ordinary conversations unnecessarily difficult. LiveTranslate explores how streaming speech recognition, translation, and speech synthesis can be combined into a tool that lets someone follow a conversation in another language while the conversation continues.

The main engineering challenge is not simply translating text. It is deciding **when a translation is reliable enough to speak**, while keeping the delay short enough for the listener to follow the conversation.

That balance between latency, accuracy, and intelligibility is the central problem this project aims to address.
