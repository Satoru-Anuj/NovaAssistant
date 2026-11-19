from pathlib import Path
from datetime import datetime
import shutil
import subprocess
import sys

path = Path("main.py")
if not path.exists():
    raise SystemExit("ERROR: main.py was not found. Run this from NovaAssistant.")

source = path.read_text(encoding="utf-8")
original = source
backup = Path(f"main_before_hindi_patch_{datetime.now():%Y%m%d_%H%M%S}.py")

def replace_once(old, new, label):
    global source
    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            f"{label}: expected exactly one matching block, found {count}. "
            "No changes have been written."
        )
    source = source.replace(old, new, 1)

# Add a language flag without changing existing UI behaviour.
replace_once(
    "        self.speaking = False\n        self.status = \"idle\"\n",
    "        self.speaking = False\n        self.current_language = 'en'\n        self.status = \"idle\"\n",
    "language state"
)

# Let the AI know which language the user spoke.
replace_once(
    '    def handle_command(self, command):\n',
    '    def handle_command(self, command, language="en"):\n',
    "handle_command signature"
)

replace_once(
    '                        + [{"role": "user", "content": command}]\n',
    '                        + [{"role": "system", "content": (\n'
    '                            "Reply entirely in natural Hindi using Devanagari script."\n'
    '                            if language == "hi" else "Reply in English."\n'
    '                        )}]\n'
    '                        + [{"role": "user", "content": command}]\n',
    "language instruction"
)

# Keep the original English TTS; use Edge TTS for Devanagari Hindi.
old_speak = '''    def speak(self, message):
        engine = None
        try:
            if not self.audio_enabled:
                print("Voice output is muted.")
                return
            with self.speech_lock:
                engine = pyttsx3.init()
                self.speech_engine = engine
                self.speaking = True
                engine.setProperty("rate", 175)
                engine.say(self.clean_for_speech(message))
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
'''
new_speak = '''    def speak(self, message):
        engine = None
        audio_path = None
        try:
            if not self.audio_enabled:
                print("Voice output is muted.")
                return

            clean_text = self.clean_for_speech(message)
            is_hindi = bool(re.search(r"[\\\\u0900-\\\\u097F]", clean_text))

            with self.speech_lock:
                self.speaking = True

                if is_hindi:
                    import asyncio
                    import tempfile
                    import edge_tts
                    import pygame

                    with tempfile.NamedTemporaryFile(
                        delete=False, suffix=".mp3", dir=str(BASE_DIR)
                    ) as temp_audio:
                        audio_path = temp_audio.name

                    async def make_hindi_audio():
                        voice = edge_tts.Communicate(
                            clean_text, voice="hi-IN-SwaraNeural"
                        )
                        await voice.save(audio_path)

                    asyncio.run(make_hindi_audio())

                    if not pygame.mixer.get_init():
                        pygame.mixer.init()

                    pygame.mixer.music.load(audio_path)
                    pygame.mixer.music.play()
                    while pygame.mixer.music.get_busy() and not self.closing:
                        time.sleep(0.1)
                    pygame.mixer.music.stop()
                    try:
                        pygame.mixer.music.unload()
                    except Exception:
                        pass
                else:
                    engine = pyttsx3.init()
                    self.speech_engine = engine
                    engine.setProperty("rate", 175)
                    engine.say(clean_text)
                    engine.runAndWait()

        except Exception as error:
            print("Speech error:", error)
        finally:
            if engine is not None:
                try:
                    engine.stop()
                except Exception:
                    pass

            if audio_path:
                try:
                    import pygame
                    if pygame.mixer.get_init():
                        pygame.mixer.music.stop()
                        try:
                            pygame.mixer.music.unload()
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    Path(audio_path).unlink(missing_ok=True)
                except OSError:
                    pass

            self.speaking = False
            self.speech_engine = None
            self.busy = False
            if not self.closing:
                self.root.after(0, self.set_status, "idle")
'''
replace_once(old_speak, new_speak, "speech function")

# Preserve Devanagari characters when matching wake phrases.
old_wake = '''    def extract_wake_command(self, spoken):
        # Accept either "Nova <command>" or "Hey Nova <command>".
        text = re.sub(r"[^a-zA-Z0-9\\\\s]", " ", spoken.lower())
        text = " ".join(text.split())

        if text in ("nova", "hey nova"):
            return ""

        if text.startswith("hey nova "):
            return text[len("hey nova "):].strip()

        if text.startswith("nova "):
            return text[len("nova "):].strip()

        return None
'''
new_wake = '''    def extract_wake_command(self, spoken):
        # Accept English and Hindi wake phrases.
        text = re.sub(r"[^a-zA-Z0-9\\\\u0900-\\\\u097F\\\\s]", " ", spoken.lower())
        text = " ".join(text.split())

        for wake in ("hey nova", "nova", "हे नोवा", "नोवा"):
            if text == wake:
                return ""
            if text.startswith(wake + " "):
                return text[len(wake):].strip()

        return None
'''
replace_once(old_wake, new_wake, "wake phrase matching")

# A Hindi wake phrase should get a Hindi acknowledgement.
old_wake_response = '''    def wake_response(self):
        if self.busy or self.closing:
            return
        self.busy = True
        threading.Thread(
            target=self.speak,
            args=("Yes bro? What do you need?",), daemon=True
        ).start()
'''
new_wake_response = '''    def wake_response(self):
        if self.busy or self.closing:
            return
        self.busy = True
        message = "जी, बताइए?" if self.current_language == "hi" else "Yes bro? What do you need?"
        threading.Thread(
            target=self.speak,
            args=(message,), daemon=True
        ).start()
'''
replace_once(old_wake_response, new_wake_response, "wake acknowledgement")

# Try Hindi recognition first, then fall back to English.
old_recognition = '''                        try:
                            spoken = self.recognizer.recognize_google(
                                audio, language="en-IN"
                            ).strip()
                        except sr.UnknownValueError:
                            continue
                        except sr.RequestError as error:
                            print("Speech recognition service error:", error)
                            time.sleep(1)
                            continue
'''
new_recognition = '''                        spoken = ""
                        language = "en"

                        try:
                            hindi_spoken = self.recognizer.recognize_google(
                                audio, language="hi-IN"
                            ).strip()
                        except (sr.UnknownValueError, sr.RequestError):
                            hindi_spoken = ""

                        if hindi_spoken and re.search(r"[\\\\u0900-\\\\u097F]", hindi_spoken):
                            spoken = hindi_spoken
                            language = "hi"
                        else:
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
'''
replace_once(old_recognition, new_recognition, "speech recognition")

# Remember the recognized language and pass it to the response thread.
replace_once(
    '                        print("Heard:", spoken)\n',
    '                        print("Heard:", spoken)\n'
    '                        self.current_language = language\n',
    "recognized language state"
)

replace_once(
    '                            args=(command,),\n',
    '                            args=(command, language),\n',
    "command thread language"
)

# Back up first, write atomically, then compile-check.
shutil.copy2(path, backup)
temporary = path.with_suffix(".hindi.tmp")
try:
    temporary.write_text(source, encoding="utf-8")
    temporary.replace(path)

    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(path)],
        capture_output=True, text=True
    )
    if result.returncode:
        shutil.copy2(backup, path)
        print("PATCH FAILED: syntax check failed; original main.py restored.")
        print(result.stderr)
        raise SystemExit(result.returncode)

    print("Hindi patch applied successfully.")
    print(f"Backup created: {backup}")
    print("Syntax check passed.")
except Exception:
    if path.exists() and path.read_text(encoding="utf-8") != original:
        shutil.copy2(backup, path)
    raise
finally:
    if temporary.exists():
        temporary.unlink()


