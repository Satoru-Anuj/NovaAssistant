from __future__ import annotations

import json
import os
import threading
import ctypes
import time
from pathlib import Path

import pyttsx3
import speech_recognition as sr
import webview
from dotenv import load_dotenv
from groq import Groq

BASE_DIR = Path(__file__).resolve().parent
UI_FILE = BASE_DIR / "ui" / "index.html"
MEMORY_FILE = BASE_DIR / "nova_memory.json"
load_dotenv(BASE_DIR / ".env", override=True)

API_KEY = os.getenv("GROQ_API_KEY", "").strip()
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b").strip() or "openai/gpt-oss-20b"
client = Groq(api_key=API_KEY) if API_KEY else None

SYSTEM_PROMPT = (
    "You are Nova, a friendly desktop AI assistant. Give helpful, clear answers "
    "in a natural speaking style. Keep spoken replies reasonably concise."
)


class NovaBridge:
    """Small JavaScript bridge for window sizing and UI actions."""

    def __init__(self, app: "NovaAssistant"):
        self.app = app

    def resize(self, expanded: bool):
        win = self.app.window
        if not win or self.app.closing:
            return False
        try:
            if expanded:
                win.resize(340, 128)
            else:
                win.resize(340, 128)
            return True
        except Exception as exc:
            print("Window resize warning:", exc)
            return False

    def close(self):
        self.app.request_close()
        return True

    def get_status(self):
        return self.app.status

    def send_text(self, text: str):
        text = str(text or "").strip()
        if not text:
            return False
        self.app.submit_text(text)
        return True


class NovaAssistant:
    def __init__(self):
        self.window = None
        self.bridge = NovaBridge(self)
        self.status = "idle"
        self.status_lock = threading.Lock()
        self.history_lock = threading.Lock()
        self.busy = threading.Event()
        self.stop_event = threading.Event()
        self.closing = False
        self.recognizer = sr.Recognizer()
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.65
        self.history = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.load_memory()

    def load_memory(self):
        try:
            if not MEMORY_FILE.exists():
                return

            data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))

            if isinstance(data, dict):
                saved = data.get("history", [])
            elif isinstance(data, list):
                saved = data
            else:
                print("Memory load warning: unsupported JSON format.")
                return

            if not isinstance(saved, list):
                print("Memory load warning: history is not a list.")
                return

            for item in saved[-24:]:
                if (
                    isinstance(item, dict)
                    and item.get("role") in ("user", "assistant")
                    and isinstance(item.get("content"), str)
                ):
                    self.history.append({
                        "role": item["role"],
                        "content": item["content"]
                    })

        except (OSError, ValueError, TypeError) as error:
            print("Memory load warning:", error)

    def save_memory(self):
        try:
            with self.history_lock:
                turns = [
                    item for item in self.history
                    if item.get("role") in ("user", "assistant")
                ][-24:]
                temp = MEMORY_FILE.with_suffix(".tmp")
                temp.write_text(
                    json.dumps({"history": turns}, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                temp.replace(MEMORY_FILE)
        except (OSError, ValueError, TypeError) as exc:
            print("Memory save warning:", exc)

    def set_status(self, status: str):
        with self.status_lock:
            self.status = status
        win = self.window
        if win and not self.closing:
            try:
                win.evaluate_js(f"window.NovaUI && window.NovaUI.setStatus({json.dumps(status)})")
            except Exception:
                # The UI may still be loading. Its startup code reads the status later.
                pass

    def submit_text(self, text: str):
        if self.closing or self.busy.is_set():
            return
        self.busy.set()
        self.set_status("thinking")
        threading.Thread(target=self.handle_command, args=(text,), daemon=True).start()

    def listen_loop(self):
        if not API_KEY:
            print("GROQ_API_KEY is missing from .env; voice commands are disabled.")
            self.set_status("idle")
            return
        try:
            with sr.Microphone() as source:
                print("Adjusting microphone. Please wait...")
                self.recognizer.adjust_for_ambient_noise(source, duration=0.8)
                print("Nova is ready. Say 'Nova' followed by your command.")
                while not self.stop_event.is_set():
                    if self.busy.is_set():
                        time.sleep(0.15)
                        continue
                    try:
                        audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=7)
                        if self.stop_event.is_set():
                            break
                        self.set_status("listening")
                        spoken = self.recognizer.recognize_google(audio, language="en-IN").strip()
                        print("Heard:", spoken)
                        words = spoken.split()
                        if not words or words[0].lower().strip(".,!?;:") != "nova":
                            self.set_status("idle")
                            continue
                        command = " ".join(words[1:]).strip(" ,.!?;:")
                        if not command:
                            self.busy.set()
                            threading.Thread(
                                target=self.speak,
                                args=("Yes bro? What do you need?",),
                                daemon=True,
                            ).start()
                            continue
                        self.busy.set()
                        self.set_status("thinking")
                        threading.Thread(target=self.handle_command, args=(command,), daemon=True).start()
                    except sr.WaitTimeoutError:
                        self.set_status("idle")
                    except sr.UnknownValueError:
                        self.set_status("idle")
                    except sr.RequestError as exc:
                        print("Speech recognition error:", exc)
                        self.set_status("idle")
                        time.sleep(1)
        except Exception as exc:
            print("Microphone error:", exc)
            self.set_status("idle")

    def handle_command(self, command: str):
        print("You:", command)
        try:
            if client is None:
                reply = "My Groq API key is missing from the .env file."
            else:
                with self.history_lock:
                    messages = list(self.history) + [{"role": "user", "content": command}]
                result = client.chat.completions.create(model=MODEL, messages=messages)
                reply = result.choices[0].message.content or "Sorry bro, I couldn't generate a reply."
                with self.history_lock:
                    self.history.extend([
                        {"role": "user", "content": command},
                        {"role": "assistant", "content": reply},
                    ])
                self.save_memory()
        except Exception as exc:
            print("Groq error:", exc)
            reply = "Sorry bro, I had trouble connecting to my AI."
        print("Nova:", reply)
        if not self.closing:
            self.set_status("speaking")
            self.speak(reply)

    def speak(self, message: str):
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", 175)
            engine.say(message)
            engine.runAndWait()
            engine.stop()
        except Exception as exc:
            print("Speech error:", exc)
        finally:
            self.busy.clear()
            if not self.closing:
                self.set_status("idle")

    def request_close(self):
        if self.closing:
            return
        self.closing = True
        self.stop_event.set()
        try:
            if self.window:
                self.window.destroy()
        except Exception:
            pass

    def run(self):
        if not UI_FILE.exists():
            raise FileNotFoundError(f"Nova UI not found: {UI_FILE}")
        try:
            screen_width = ctypes.windll.user32.GetSystemMetrics(0)
            start_x = max(0, (screen_width - 292) // 2)
        except Exception:
            start_x = 500
        self.window = webview.create_window(
            "NOVA",
            str(UI_FILE),
            js_api=self.bridge,
            width=340,
            height=128,
            x=start_x,
            y=24,
            frameless=True,
            on_top=True,
            shadow=False,
            easy_drag=False,
            background_color="#050711",
            min_size=(340, 128),
        )
        print("Nova 3D is starting...")
        print("Say 'Nova' followed by your command.")
        print("Right-click the island or press Escape to exit.")
        threading.Thread(target=self.listen_loop, daemon=True).start()
        webview.start(debug=False, http_server=False)
        self.stop_event.set()


if __name__ == "__main__":
    NovaAssistant().run()

