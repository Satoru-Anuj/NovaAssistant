
"""
Nova Video Editor — standalone window.
Uses the existing nova_video_editor.py module.
Does not modify Nova's main UI.
"""

import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from pathlib import Path

import speech_recognition as sr
import nova_video_editor as editor


class NovaVideoEditorWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("Nova Video Editor")
        self.root.geometry("760x560")
        self.root.minsize(650, 480)
        self.root.configure(bg="#10151f")

        self.video_path = None
        self.busy = False
        self.events = queue.Queue()

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("TFrame", background="#10151f")
        style.configure(
            "TLabel", background="#10151f", foreground="#e8f1ff"
        )
        style.configure(
            "Header.TLabel",
            font=("Segoe UI", 17, "bold"),
            foreground="#63d9ff",
        )
        style.configure("TButton", font=("Segoe UI", 10), padding=7)
        style.configure("TEntry", padding=7)

        outer = ttk.Frame(root, padding=16)
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer, text="NOVA VIDEO EDITOR",
            style="Header.TLabel"
        ).pack(anchor="w")

        ttk.Label(
            outer,
            text="Type an edit or use the microphone. "
                 "Original files remain unchanged.",
        ).pack(anchor="w", pady=(3, 12))

        file_row = ttk.Frame(outer)
        file_row.pack(fill="x", pady=(0, 10))

        ttk.Button(
            file_row, text="Choose Video",
            command=self.choose_video
        ).pack(side="left")

        self.file_label = ttk.Label(
            file_row, text="No video selected"
        )
        self.file_label.pack(
            side="left", padx=10, fill="x", expand=True
        )

        self.log = tk.Text(
            outer,
            height=17,
            wrap="word",
            bg="#0a0e16",
            fg="#dce9ff",
            insertbackground="white",
            relief="flat",
            padx=10,
            pady=10,
            font=("Consolas", 10),
            state="disabled",
        )
        self.log.pack(fill="both", expand=True, pady=(0, 10))

        self.add_log("Nova Video Editor is ready.")
        self.add_log(
            "Choose a video, then type: trim video, speed up video, "
            "crop video, resize video, convert to mp4, extract audio, "
            "brighten video, or mute video."
        )
        self.add_log(f"Exports folder: {editor.EXPORT_DIR}")


    def add_log(self, message):
        self.log.configure(state="normal")
        self.log.insert("end", str(message) + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def choose_video(self):
        path = filedialog.askopenfilename(
            title="Choose a video",
            filetypes=[
                ("Video files", "*.mp4 *.mov *.mkv *.avi *.webm *.wmv"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.video_path = Path(path)
            self.file_label.configure(text=self.video_path.name)
            self.add_log(f"Selected: {self.video_path}")

    def run_task(self, function, *args):
        if self.busy:
            self.add_log("Please wait for the current task to finish.")
            return

        self.busy = True
        self.add_log("Working...")

        def worker():
            try:
                result = function(*args)
                self.events.put(("done", result))
            except Exception as exc:
                self.events.put(("error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def process_events(self):
        try:
            while True:
                kind, result = self.events.get_nowait()
                self.busy = False

                if kind == "done":
                    self.add_log(f"Finished: {result}")
                else:
                    self.add_log(f"Error: {result}")
                    messagebox.showerror("Video Editor", result)
        except queue.Empty:
            pass

        self.root.after(150, self.process_events)

    def submit_command(self):
        command = self.command_entry.get().strip()
        if not command:
            return

        self.command_entry.delete(0, "end")
        self.add_log(f"You: {command}")
        self.handle_command(command)

    def handle_command(self, command):
        if not self.video_path:
            self.add_log("Choose a video first.")
            return

        command = command.lower().strip()
        path = str(self.video_path)

        if command in ("help", "commands"):
            self.add_log(
                "Try: trim video, extract audio, speed up video, "
                "slow down video, crop video, resize video, "
                "convert to mp4, brighten video, increase volume, "
                "or mute video."
            )
            return

        if "extract audio" in command:
            self.run_task(editor.extract_audio, path)
        elif "trim" in command:
            self.ask_trim(path)
        elif "speed" in command or "slow down" in command:
            self.ask_speed(path, command)
        elif "crop" in command:
            self.ask_crop(path)
        elif "resize" in command:
            self.ask_resize(path)
        elif "convert" in command or "mp4" in command:
            self.run_task(editor.convert_to_mp4, path)
        elif "bright" in command:
            self.ask_brightness(path)
        elif "volume" in command or "mute" in command:
            self.ask_volume(path, command)
        else:
            self.add_log("Command not recognised. Type 'help' for options.")


    def ask_trim(self, path):
        start = simpledialog.askfloat(
            "Trim Video", "Start time in seconds:", minvalue=0
        )
        if start is None:
            return

        end = simpledialog.askfloat(
            "Trim Video", "End time in seconds:", minvalue=0
        )
        if end is None or end <= start:
            self.add_log("End time must be greater than start time.")
            return

        self.run_task(editor.trim_video, path, start, end)

    def ask_speed(self, path, command):
        speed = simpledialog.askfloat(
            "Video Speed",
            "Speed factor (0.5 = slower, 2 = faster):",
            initialvalue=0.5 if "slow" in command else 2.0,
            minvalue=0.1,
            maxvalue=10,
        )
        if speed is not None:
            self.run_task(editor.change_speed, path, speed)

    def ask_crop(self, path):
        width = simpledialog.askinteger(
            "Crop Video", "Crop width in pixels:", minvalue=2
        )
        if width is None:
            return

        height = simpledialog.askinteger(
            "Crop Video", "Crop height in pixels:", minvalue=2
        )
        if height is None:
            return

        self.run_task(editor.crop_video, path, width, height)

    def ask_resize(self, path):
        width = simpledialog.askinteger(
            "Resize Video", "New width in pixels:", minvalue=2
        )
        if width is None:
            return

        height = simpledialog.askinteger(
            "Resize Video", "New height in pixels:", minvalue=2
        )
        if height is None:
            return

        self.run_task(editor.resize_video, path, width, height)

    def ask_brightness(self, path):
        amount = simpledialog.askfloat(
            "Brightness",
            "Adjustment (-1 to 1; 0 means unchanged):",
            minvalue=-1,
            maxvalue=1,
        )
        if amount is not None:
            self.run_task(editor.adjust_brightness, path, amount)

    def ask_volume(self, path, command):
        if "mute" in command:
            amount = 0.0
        else:
            amount = simpledialog.askfloat(
                "Audio Volume",
                "Volume multiplier (1 = unchanged, 2 = double):",
                initialvalue=1.5,
                minvalue=0,
                maxvalue=10,
            )
            if amount is None:
                return

        self.run_task(editor.adjust_volume, path, amount)


    def build_controls(self):
        row = ttk.Frame(self.root, padding=(16, 0, 16, 14))
        row.pack(fill="x")

        self.command_entry = ttk.Entry(row)
        self.command_entry.pack(side="left", fill="x", expand=True)
        self.command_entry.bind(
            "<Return>", lambda event: self.submit_command()
        )

        ttk.Button(
            row, text="Run", command=self.submit_command
        ).pack(side="left", padx=(8, 0))

        ttk.Button(
            row, text="🎙 Voice", command=self.listen_voice
        ).pack(side="left", padx=(8, 0))

    def listen_voice(self):
        if self.busy:
            self.add_log("Please wait for the current task.")
            return

        self.busy = True
        self.add_log("Listening...")

        def worker():
            recognizer = sr.Recognizer()
            try:
                with sr.Microphone() as source:
                    audio = recognizer.listen(
                        source, timeout=5, phrase_time_limit=8
                    )
                command = recognizer.recognize_google(
                    audio, language="en-IN"
                )
                self.events.put(("voice", command))
            except Exception as exc:
                self.events.put(("error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def process_events(self):
        try:
            while True:
                kind, result = self.events.get_nowait()

                if kind == "voice":
                    self.busy = False
                    self.add_log(f"You said: {result}")
                    self.handle_command(result)
                elif kind == "done":
                    self.busy = False
                    self.add_log(f"Finished: {result}")
                else:
                    self.busy = False
                    self.add_log(f"Error: {result}")
        except queue.Empty:
            pass

        self.root.after(150, self.process_events)


if __name__ == "__main__":
    root = tk.Tk()
    app = NovaVideoEditorWindow(root)
    app.build_controls()
    root.after(150, app.process_events)
    root.mainloop()
