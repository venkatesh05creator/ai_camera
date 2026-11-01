"""
jarvis_voice.py - Production-Ready Cross-Platform Live Voice & Audio Loop
Integrated with Project JARVIS & Aegis AI Camera Assistant.

Features:
- Speech recognition with automatic ambient noise calibration
- Non-truncating full-response TTS (Windows SAPI / macOS 'say' / Linux espeak)
- Wake word activation ("Jarvis", "Aegis", or direct input)
- Seamless fallback to interactive console if microphone hardware is unavailable
- Direct routing through JarvisOrchestrator
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from typing import Optional

# Ensure project root is on Python path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

try:
    import speech_recognition as sr
except ImportError:
    sr = None


def speak(text: str) -> None:
    """Speaks output aloud using cross-platform native TTS with full response preservation."""
    if not text:
        return

    # Clean markdown formatting, emojis, and symbols for clean spoken speech
    clean_text = re.sub(r"[*#_`~>]", "", text)
    clean_text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", clean_text)
    clean_text = re.sub(r"https?://\S+", "", clean_text)
    clean_text = clean_text.strip()

    print(f"\n[JARVIS]: {text}\n")

    if sys.platform == "darwin":
        try:
            subprocess.run(["say", "-v", "Samantha", clean_text], check=False)
            return
        except Exception:
            pass

    # Windows Native PowerShell SAPI Fallback (guaranteed without external C++ DLL dependencies)
    if sys.platform == "win32":
        try:
            # Escape single quotes for PowerShell string
            escaped = clean_text.replace("'", "''").replace('"', '""')
            ps_cmd = (
                f"$speak = New-Object -ComObject SAPI.SpVoice; "
                f"$speak.Rate = 1; "
                f"$speak.Speak('{escaped}')"
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], check=False, timeout=30)
            return
        except Exception:
            pass

    # Generic pyttsx3 fallback
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.say(clean_text)
        engine.runAndWait()
    except Exception:
        pass


def dispatch_query(query: str) -> str:
    """Dispatches user query to the central JarvisOrchestrator."""
    from backend.app.agents.jarvis_orchestrator import JarvisOrchestrator

    res = JarvisOrchestrator.dispatch(
        query=query,
        user_id="owner_001",
        has_live_frame=False,
    )
    return res.speech_text or res.answer


def listen_loop() -> None:
    """Main voice interaction loop."""
    print("\n" + "=" * 65)
    print("  J.A.R.V.I.S MARK VII - VOICE ASSISTANT PIPELINE ONLINE")
    print("  Compatible with Windows, macOS, and Linux")
    print("  Commands:")
    print("    • 'What is in front of the camera?'")
    print("    • 'How many planets are in our solar system?'")
    print("    • 'Search for the latest information about this technology'")
    print("    • 'Analyze Nifty / Stock market briefing'")
    print("    • 'Can you open WhatsApp?' / 'Play synthwave on YouTube'")
    print("=" * 65 + "\n")

    if sr is None:
        print("[Notice]: 'speech_recognition' library not installed. Falling back to console mode.")
        run_text_console()
        return

    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 0.8

    try:
        mic = sr.Microphone()
        with mic as source:
            print("Calibrating ambient noise floor... ", end="", flush=True)
            recognizer.adjust_for_ambient_noise(source, duration=1.0)
            print("OK! Microphone ready.\n")
    except Exception as e:
        print(f"\n[Hardware Warning]: Could not access microphone hardware: {e}")
        print("Falling back to Interactive Console Mode.\n")
        run_text_console()
        return

    while True:
        try:
            with mic as source:
                print("Listening... ", end="", flush=True)
                audio = recognizer.listen(source, timeout=8, phrase_time_limit=10)
            print("Processing... ", end="", flush=True)

            query = recognizer.recognize_google(audio).strip()
            print(f"\nYou: \"{query}\"")

            q_clean = query.lower()
            # Wake word strip
            for wake_word in ["jarvis", "aegis", "hey jarvis", "ok jarvis"]:
                if q_clean.startswith(wake_word):
                    q_clean = q_clean[len(wake_word):].strip(" ,.!?")

            if not q_clean:
                speak("Yes sir, I am listening and ready for your command.")
                continue

            reply = dispatch_query(q_clean)
            speak(reply)

        except sr.WaitTimeoutError:
            continue
        except sr.UnknownValueError:
            continue
        except KeyboardInterrupt:
            print("\nShutting down J.A.R.V.I.S voice pipeline. Systems secured. Goodbye!")
            break
        except Exception as e:
            print(f"\n[Notice]: {e}")
            time.sleep(0.5)


def run_text_console() -> None:
    """Interactive text fallback console."""
    print("Type your command below (type 'exit' or Ctrl+C to quit):\n")
    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit", "bye", "shutdown"]:
                print("Systems standing down. Goodbye!")
                break

            reply = dispatch_query(user_input)
            speak(reply)
        except (KeyboardInterrupt, EOFError):
            print("\nExiting. Systems safe.")
            break


if __name__ == "__main__":
    listen_loop()
