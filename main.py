import asyncio
import edge_tts
import pygame
import tempfile
import re

import os
import sys
import math
import time
import json
import threading
import tkinter as tk
from pathlib import Path

import pyttsx3
import speech_recognition as sr
from dotenv import load_dotenv
from groq import Groq
import nova_video_editor as video_editor

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)

API_KEY = os.getenv("GROQ_API_KEY", "").strip()
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
client = Groq(api_key=API_KEY) if API_KEY else None

BG = "#050914"
MEMORY_FILE = BASE_DIR / "nova_memory.json"
CW, CH = 480, 140


class NovaOrb:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("NOVA")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=BG)
        self.root.geometry("220x88+500+30")

        self.expanded = False
        self.closing = False
        self.listening = True
        self.busy = False
        self.audio_enabled = True
        self.speech_lock = threading.Lock()
        self.speech_engine = None
        self.speaking = False
        self.status = "idle"
        self.write_ui_state()
        self.angle = 0.0
        self.phase = 0.0
        self.drag_x = self.drag_y = 0
        self.resize_job = None
        self.resize_step = 0
        self.target_size = (220, 88)

        self.history = [{
            "role": "system",
            "content": (
                "You are Nova, a friendly desktop AI assistant. "
                "Give helpful, clear answers in a natural speaking style. "
                "Keep spoken replies reasonably concise."
            )
        }]
        self.memories = []
        self.load_memory()

        self.canvas = tk.Canvas(
            self.root, width=CW, height=CH, bg=BG,
            highlightthickness=0, bd=0
        )
        self.canvas.pack(fill="both", expand=True)

        self.recognizer = sr.Recognizer()
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.8

        self.canvas.bind("<Enter>", self.expand)
        self.canvas.bind("<Leave>", self.collapse)
        self.canvas.bind("<Button-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.drag)
        self.canvas.bind("<Button-3>", lambda _e: self.close())
        self.root.bind("<Escape>", lambda _e: self.close())
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.animate()

        print("Nova is starting...")
        print("Say 'Nova' followed by your command.")
        print("Right-click the island or press Escape to exit.")

        self.root.after(150, self.poll_control_file)
        threading.Thread(target=self.listen_loop, daemon=True).start()

    def load_memory(self):
        self.memories = []
        try:
            if not MEMORY_FILE.exists():
                return
            data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                # Legacy format: a list of saved facts.
                self.memories = [
                    item for item in data if isinstance(item, str)
                ]
            elif isinstance(data, dict):
                saved_memories = data.get("memories", [])
                if isinstance(saved_memories, list):
                    self.memories = [
                        item for item in saved_memories
                        if isinstance(item, str)
                    ]
                saved_history = data.get("history", [])
                if isinstance(saved_history, list):
                    self.history.extend([
                        item for item in saved_history[-24:]
                        if isinstance(item, dict)
                        and item.get("role") in ("user", "assistant")
                        and isinstance(item.get("content"), str)
                    ])
        except (OSError, ValueError, TypeError) as error:
            print("Memory load warning:", error)

    def save_memory(self):
        self.save_memories()

    def start_drag(self, event):
        self.drag_x, self.drag_y = event.x, event.y

    def drag(self, event):
        x = self.root.winfo_x() + event.x - self.drag_x
        y = self.root.winfo_y() + event.y - self.drag_y
        self.root.geometry(f"+{x}+{y}")

    def expand(self, _event=None):
        if self.closing or self.expanded:
            return
        self.expanded = True
        self.resize_to(480, 140)

    def collapse(self, _event=None):
        if self.closing or not self.expanded:
            return
        if self.resize_job:
            self.root.after_cancel(self.resize_job)
        self.resize_job = self.root.after(250, self.collapse_if_outside)

    def collapse_if_outside(self):
        self.resize_job = None
        if self.closing:
            return
        x, y = self.root.winfo_pointerxy()
        widget = self.root.winfo_containing(x, y)
        if widget is None or not str(widget).startswith(str(self.canvas)):
            self.expanded = False
            self.resize_to(220, 88)

    def resize_to(self, width, height):
        self.target_size = (width, height)
        self.resize_step = 0
        if self.resize_job:
            try:
                self.root.after_cancel(self.resize_job)
            except tk.TclError:
                pass
        self.resize_frame()

    def resize_frame(self):
        if self.closing:
            return
        self.resize_step += 1
        target_w, target_h = self.target_size
        current_w, current_h = self.root.winfo_width(), self.root.winfo_height()
        t = min(1, self.resize_step / 10)
        eased = 1 - (1 - t) ** 3
        w = int(current_w + (target_w - current_w) * eased)
        h = int(current_h + (target_h - current_h) * eased)
        self.root.geometry(
            f"{max(1,w)}x{max(1,h)}+{self.root.winfo_x()}+{self.root.winfo_y()}"
        )
        if self.resize_step < 10:
            self.resize_job = self.root.after(15, self.resize_frame)
        else:
            self.resize_job = None

    def palette(self):
        return {
            "idle": ("#00D9FF", "#287BFF", "#9A5BFF"),
            "listening": ("#37F7C5", "#00C9FF", "#42A5FF"),
            "thinking": ("#B35CFF", "#6B6CFF", "#00CFFF"),
            "speaking": ("#FF4FD8", "#A45BFF", "#00D9FF")
        }.get(self.status, ("#00D9FF", "#287BFF", "#9A5BFF"))

    def capsule(self, x1, y1, x2, y2, r, fill, outline):
        c = self.canvas
        c.create_rectangle(x1+r, y1, x2-r, y2, fill=fill, outline="")
        c.create_rectangle(x1, y1+r, x2, y2-r, fill=fill, outline="")
        for x in (x1, x2-2*r):
            for y in (y1, y2-2*r):
                c.create_oval(x, y, x+2*r, y+2*r, fill=fill, outline="")
        c.create_line(x1+r, y1, x2-r, y1, fill=outline)
        c.create_line(x1+r, y2, x2-r, y2, fill=outline)

    def animate(self):
        # The Qt widget is the only visible Nova interface.
        # Keep the Tk backend renderer disabled.
        return

    def write_ui_state(self):
        try:
            data = "\n".join((
                f"mic={'on' if self.listening else 'off'}",
                f"audio={'on' if self.audio_enabled else 'off'}",
                ""
            ))
            (BASE_DIR / "nova_ui_state.txt").write_text(data, encoding="utf-8")
        except OSError as error:
            print("UI state warning:", error)

    def set_status(self, status):
        if self.closing:
            return

        self.status = status
        try:
            Path(__file__).with_name("nova_status.txt").write_text(
                str(status), encoding="utf-8"
            )
        except OSError:
            pass

    def say_wake_response(self):
        if self.busy or self.closing:
            return
        self.busy = True
        threading.Thread(
            target=self.speak,
            args=("Yes bro? What do you need?",), daemon=True
        ).start()

    def handle_command(self, command):
        print("You:", command)

        try:
            app_reply = self.handle_memory_command(command)

            if app_reply is None:
                app_reply = video_editor.handle_voice_command(command)

            if app_reply is None:
                app_reply = self.open_desktop_app(command)

            if app_reply is not None:
                reply = app_reply
            elif client is None:
                reply = "My Groq API key is missing."
            else:
                result = client.chat.completions.create(
                    model=MODEL,
                    messages=(
                        self.history[:1]
                        + ([{"role": "system", "content": self.memory_context()}]
                           if self.memories else [])
                        + self.history[1:]
                        + [{"role": "user", "content": command}]
                    )
                )

                reply = (
                    result.choices[0].message.content
                    or "Sorry bro, I couldn't generate a reply."
                )

                self.history.extend([
                    {"role": "user", "content": command},
                    {"role": "assistant", "content": reply}
                ])

        except Exception as error:
            print("Groq error:", error)
            reply = "Sorry bro, I had trouble connecting to my AI."

        print("Nova:", reply)

        try:
            response_path = Path(__file__).with_name("nova_response.txt")
            temporary_path = response_path.with_suffix(".tmp")
            temporary_path.write_text(
                str(reply).replace("\\r", " ").replace("\\n", " "),
                encoding="utf-8"
            )
            temporary_path.replace(response_path)
        except OSError as error:
            print("Response display update failed:", error)

        if not self.closing:
            self.root.after(0, self.set_status, "speaking")
            self.speak(reply)

    def clean_for_speech(self, message):
        """Remove Markdown formatting before speech."""
        text = str(message)
        text = re.sub(r"```[\s\S]*?```", "Code is shown on screen.", text)
        text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        text = re.sub(r"https?://\S+", "", text)
        text = re.sub(r"`([^`]*)`", r"\1", text)
        text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
        text = re.sub(r"(?m)^\s*>\s?", "", text)
        text = re.sub(r"(?m)^\s*[-*+]\s+", "", text)
        text = re.sub(r"(?m)^\s*\d+[.)]\s+", "", text)
        text = re.sub(r"[*_~#]+", "", text)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def speak(self, message):
        engine = None
        try:
            if not self.audio_enabled:
                print("Voice output is muted.")
                return

            text = self.clean_for_speech(message)
            hindi = any("\u0900" <= ch <= "\u097f" for ch in text)

            with self.speech_lock:
                self.speaking = True

                if hindi:
                    async def speak_hindi():
                        with tempfile.NamedTemporaryFile(
                            suffix=".mp3", delete=False
                        ) as audio_file:
                            audio_path = audio_file.name
                        try:
                            voice = edge_tts.Communicate(
                                text, "hi-IN-SwaraNeural"
                            )
                            await voice.save(audio_path)
                            pygame.mixer.init()
                            pygame.mixer.music.load(audio_path)
                            pygame.mixer.music.play()
                            while pygame.mixer.music.get_busy():
                                time.sleep(0.1)
                            pygame.mixer.music.unload()
                        finally:
                            try:
                                os.remove(audio_path)
                            except OSError:
                                pass

                    try:
                        asyncio.run(speak_hindi())
                    except Exception as error:
                        print("Hindi voice error; using English voice:", error)
                        engine = pyttsx3.init()
                        self.speech_engine = engine
                        engine.setProperty("rate", 175)
                        engine.say(text)
                        engine.runAndWait()
                else:
                    engine = pyttsx3.init()
                    self.speech_engine = engine
                    engine.setProperty("rate", 175)
                    engine.say(text)
                    engine.runAndWait()

        except Exception as error:
            print("Speech error:", error)
        finally:
            if engine is not None:
                try:
                    engine.stop()
                except Exception:
                    pass
            self.speaking = False
            self.speech_engine = None
            self.busy = False
            if not self.closing:
                self.root.after(0, self.set_status, "idle")

    def extract_wake_command(self, spoken):
        text = re.sub(r"[^a-zA-Z0-9\\s]", " ", spoken.lower())
        text = " ".join(text.split())

        if text in ("nova", "nava", "hey nova", "hey nava"):
            return ""

        for wake in ("hey nova ", "hey nava ", "nova ", "nava "):
            if text.startswith(wake):
                return text[len(wake):].strip()

        return None

    def listen_loop(self):
        # Reopen the microphone automatically if its stream fails.
        while not self.closing:
            if not self.listening:
                time.sleep(0.2)
                continue

            try:
                with sr.Microphone() as source:
                    print("Microphone connected. Calibrating...")
                    self.recognizer.adjust_for_ambient_noise(
                        source, duration=1.0
                    )
                    print("Nova is listening.")

                    while not self.closing and self.listening:
                        try:
                            audio = self.recognizer.listen(
                                source,
                                timeout=1,
                                phrase_time_limit=8
                            )
                        except sr.WaitTimeoutError:
                            continue

                        if self.closing or not self.listening:
                            break

                        # Verify the enrolled speaker before transcription.
                        try:
                            from nova_voice_auth import verify_audio
                            verified, score = verify_audio(audio)
                        except Exception as error:
                            print(f'Speaker verification error; ignoring audio: {error}')
                            continue

                        if not verified:
                            if score is None:
                                print('Speaker not verified; ignoring audio.')
                            else:
                                print(f'Speaker rejected (similarity {score:.3f}).')
                            continue

                        try:
                            spoken = self.recognizer.recognize_google(
                                audio, language="en-IN"
                            ).strip()
                        except sr.UnknownValueError:
                            continue
                        except sr.RequestError as error:
                            print("Speech recognition service error:", error)
                            time.sleep(1)
                            continue

                        if not spoken:
                            continue

                        print("Heard:", spoken)

                        if re.search(
                            r"\\b(stop|stop talking|cancel|be quiet|shut up)\\b",
                            spoken, re.IGNORECASE
                        ):
                            if self.speaking:
                                engine = self.speech_engine
                                if engine is not None:
                                    try:
                                        engine.stop()
                                        print("Nova speech interrupted.")
                                    except Exception as error:
                                        print("Stop warning:", error)
                            self.busy = False
                            continue

                        if self.busy:
                            continue

                        command = self.extract_wake_command(spoken)

                        # Ignore speech unless the explicit wake phrase is heard.
                        if command is None:
                            continue

                        if not command:
                            self.root.after(0, self.wake_response)
                            continue

                        self.busy = True
                        self.root.after(0, self.set_status, "thinking")

                        threading.Thread(
                            target=self.handle_command,
                            args=(command,),
                            daemon=True
                        ).start()

            except Exception as error:
                if self.closing:
                    break
                print("Microphone/listener error; reconnecting:", error)
                time.sleep(1.5)

        print("Nova listener stopped.")

    def wake_response(self):
        if self.busy or self.closing:
            return

        self.busy = True
        threading.Thread(
            target=self.speak,
            args=("Yes bro? What do you need?",),
            daemon=True
        ).start()

    def memory_context(self):
        if not self.memories:
            return ""
        return (
            "The user has explicitly saved these memories for future chats. "
            "Use them when relevant, and do not invent additional personal facts:\n"
            + "\n".join("- " + item for item in self.memories)
        )

    def handle_memory_command(self, command):
        import re

        text = command.strip()
        text = re.sub(r"^[\s,]+|[\s,!?\.]+$", "", text)
        text = re.sub(r"^(?:nova[\s,]+)", "", text, flags=re.I).strip()

        remember_patterns = [
            r"^(?:please\s+)?remember(?:\s+that)?\s+(.+)$",
            r"^(?:please\s+)?save(?:\s+that)?\s+(.+?)\s+to\s+(?:your\s+)?memory$",
            r"^(?:please\s+)?save\s+(?:this\s+)?(?:fact|memory)\s*:\s*(.+)$",
        ]

        for pattern in remember_patterns:
            match = re.match(pattern, text, re.I)
            if match:
                fact = match.group(1).strip().rstrip(".!?")
                if re.search(r"\b(password|passcode|api key|secret key)\b", fact, re.I):
                    return "I won't save passwords, API keys, or secret credentials."
                if not fact:
                    return "Tell me what you'd like me to remember."
                if any(item.casefold() == fact.casefold() for item in self.memories):
                    return "I already have that saved in my memory."
                self.memories.append(fact)
                self.memories = self.memories[-100:]
                try:
                    self.save_memories()
                    return "Got it. I've saved that in my memory for next time."
                except OSError as error:
                    self.memories.remove(fact)
                    print("Memory save error:", error)
                    return "I couldn't save that to the memory file."

        if re.search(
            r"\b(what do you remember|show my memories|list my memories|"
            r"what have you saved|what is in your memory)\b", text, re.I
        ):
            if not self.memories:
                return "I don't have any saved memories yet. Tell me, remember that, followed by a fact."
            return "Here's what I remember: " + "; ".join(self.memories)

        if re.search(
            r"\b(forget all memories|forget everything|clear all memories)\b",
            text, re.I
        ):
            old_memories = self.memories[:]
            self.memories = []
            try:
                self.save_memories()
                return "I've cleared all saved memories."
            except OSError:
                self.memories = old_memories
                return "I couldn't update the memory file."

        forget = re.match(r"^(?:please\s+)?forget(?:\s+that)?\s+(.+)$", text, re.I)
        if forget:
            target = forget.group(1).strip().casefold()
            remaining = [item for item in self.memories if target not in item.casefold()]
            if len(remaining) == len(self.memories):
                return "I couldn't find a saved memory matching that."
            old_memories = self.memories
            self.memories = remaining
            try:
                self.save_memories()
                return "I've forgotten the matching saved memory."
            except OSError:
                self.memories = old_memories
                return "I couldn't update the memory file."

        return None

    def open_desktop_app(self, command):
        import re

        # Windows master-volume controls
        text = command.lower().strip()
        if any(x in text for x in ("volume", "mute", "unmute")):
            try:
                from pycaw.pycaw import AudioUtilities
                device = AudioUtilities.GetSpeakers()
                audio = device.EndpointVolume

                if "unmute" in text:
                    audio.SetMute(0, None)
                    return "Volume unmuted."
                if "mute" in text:
                    audio.SetMute(1, None)
                    return "Volume muted."

                match = re.search(r"(?:volume\s*(?:to|at|of)?\s*)(\d{1,3})\s*%?", text)
                if match:
                    level = int(match.group(1))
                    if not 0 <= level <= 100:
                        return "Choose a volume from 0 to 100."
                    audio.SetMasterVolumeLevelScalar(level / 100, None)
                    return f"Volume set to {level}%."

                level = round(audio.GetMasterVolumeLevelScalar() * 100)
                return f"Your volume is {level}%."
            except Exception as error:
                print("Volume control error:", error)
                return "I couldn't control the Windows volume."

        import subprocess
        import os
        import webbrowser
        import urllib.parse
        import re

        text = command.lower().strip()
        text = re.sub(r"[^a-z0-9\s]", "", text)
        text = re.sub(r"^(nova\s+)?(please\s+)?(can you\s+|could you\s+)?", "", text)
        text = re.sub(r"^(please\s+)?(open|launch|start|go to|visit)\s+", "", text)

        if text.startswith(("search for ", "search google for ", "google search for ")):
            q = text.split(" for ", 1)[-1].strip()
            webbrowser.open("https://www.google.com/search?q=" + urllib.parse.quote_plus(q))
            return "Searching Google for " + q
        if "camera" in text:
            os.startfile("microsoft.windows.camera:")
            return "Opening Camera."
        if "store" in text:
            os.startfile("ms-windows-store:")
            return "Opening Microsoft Store."
        if "edge" in text:
            os.startfile("microsoft-edge:")
            return "Opening Microsoft Edge."

        if text.startswith("search "):
            q = text[len("search "):].strip()
            if q:
                webbrowser.open("https://www.google.com/search?q=" + urllib.parse.quote_plus(q), new=2)
                return "Searching Google for " + q + "."

        if "notepad" in text:
            subprocess.Popen(["notepad.exe"])
            return "Opening Notepad."

        if "calculator" in text or text == "calc":
            subprocess.Popen(["calc.exe"])
            return "Opening Calculator."

        sites = {
            "gmail": "https://mail.google.com/",
            "youtube": "https://www.youtube.com/",
            "google": "https://www.google.com/",
            "google drive": "https://drive.google.com/",
            "google maps": "https://maps.google.com/",
            "google classroom": "https://classroom.google.com/",
        }

        if "new tab" in text or "new chrome tab" in text:
            webbrowser.open("about:blank", new=2)
            return "Opening a new tab."

        for name, url in sorted(sites.items(), key=lambda item: len(item[0]), reverse=True):
            if text == name or text == name + " website":
                webbrowser.open(url, new=2)
                return "Opening " + name.title() + "."

        for phrase in ("search google for ", "google search for ", "search for "):
            if phrase in text:
                query = text.split(phrase, 1)[1].strip()
                if query:
                    webbrowser.open(
                        "https://www.google.com/search?q=" + urllib.parse.quote_plus(query),
                        new=2
                    )
                    return "Searching Google for " + query

        if "chrome" in text:
            candidates = [
                os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
            ]
            for browser in candidates:
                if os.path.isfile(browser):
                    subprocess.Popen([browser])
                    return "Opening Google Chrome."
            webbrowser.open("https://www.google.com/", new=2)
            return "Opening your default browser."

        # Windows media controls
        import ctypes
        media_commands = {
            "play pause": 0xB3,
            "pause": 0xB3,
            "resume": 0xB3,
            "next track": 0xB0,
            "skip track": 0xB0,
            "previous track": 0xB1,
            "last track": 0xB1,
        }
        for phrase, key in media_commands.items():
            if text == phrase or text == "media " + phrase:
                ctypes.windll.user32.keybd_event(key, 0, 0, 0)
                ctypes.windll.user32.keybd_event(key, 0, 2, 0)
                return {
                    "play pause": "Toggling play/pause.",
                    "pause": "Toggling play/pause.",
                    "resume": "Toggling play/pause.",
                    "next track": "Skipping to the next track.",
                    "skip track": "Skipping to the next track.",
                    "previous track": "Going to the previous track.",
                    "last track": "Going to the previous track.",
                }[phrase]

        return None

    def save_memories(self):
        try:
            turns = [
                item for item in self.history
                if item.get("role") in ("user", "assistant")
            ][-24:]
            data = {
                "memories": self.memories,
                "history": turns
            }
            temp = MEMORY_FILE.with_suffix(".tmp")
            temp.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            temp.replace(MEMORY_FILE)
        except (OSError, ValueError, TypeError) as error:
            print("Memory save warning:", error)

    def poll_control_file(self):
        if self.closing:
            return
        control_file = BASE_DIR / "nova_ui_control.txt"
        try:
            if control_file.exists():
                command = control_file.read_text(encoding="utf-8").strip()
                control_file.unlink(missing_ok=True)
                if command == "mic_toggle":
                    self.listening = not self.listening
                    print("Microphone listening:", "ON" if self.listening else "OFF")
                    self.set_status("listening" if self.listening else "idle")
                    self.write_ui_state()
                elif command == "audio_toggle":
                    self.audio_enabled = not self.audio_enabled
                    print("Voice output:", "ON" if self.audio_enabled else "MUTED")
                    self.write_ui_state()
        except OSError as error:
            print("Control-file warning:", error)
        finally:
            if not self.closing:
                self.root.after(150, self.poll_control_file)

    def close(self):
        if self.closing:
            return
        self.closing = True
        self.listening = False
        try:
            self.root.destroy()
        except tk.TclError:
            pass


if __name__ == "__main__":
    app = NovaOrb()
    if "--background" in sys.argv:
        app.root.withdraw()
    app.root.mainloop()






