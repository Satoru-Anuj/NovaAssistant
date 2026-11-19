
import tkinter as tk
import cv2
from PIL import Image, ImageTk
from tkinter import ttk, filedialog, messagebox, simpledialog
from pathlib import Path
import threading
import queue

import nova_video_editor as editor


BG = "#111218"
PANEL = "#1b1c24"
PANEL_LIGHT = "#252732"
ACCENT = "#45d7ff"
TEXT = "#edf0f8"
MUTED = "#969bad"


class NovaStudio:
    def __init__(self, root):
        self.root = root
        self.root.title("Nova Studio | Video Editor")
        self.root.geometry("1180x760")
        self.root.minsize(900, 600)
        self.root.configure(bg=BG)
        self.root.after(80, self.animate_studio)
        self.root.after(150, self.process_events)
        

        self.video_path = None
        self.busy = False
        self.events = queue.Queue()
        
        self.animation_step = 0
        self.playhead_position = 42
        self.animation_running = True
        self.preview_cap = None
        self.preview_after_id = None
        self.preview_playing = False
        self.preview_photo = None


        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "TButton",
            background=PANEL_LIGHT,
            foreground=TEXT,
            padding=8,
            borderwidth=0,
        )
        style.map(
            "TButton",
            background=[("active", "#343746")],
        )
        style.configure(
            "TLabel",
            background=PANEL,
            foreground=TEXT,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Studio.TEntry",
            fieldbackground=PANEL_LIGHT,
            foreground=TEXT,
            padding=9,
        )

        self.build_topbar()
        self.build_workspace()
        self.build_timeline()
        self.build_bottom_bar()

        self.root.after(150, self.process_events)

    def panel_title(self, parent, title):
        tk.Label(
            parent,
            text=title.upper(),
            bg=PANEL,
            fg=ACCENT,
            font=("Segoe UI", 9, "bold"),
            anchor="w",
        ).pack(fill="x", padx=12, pady=(12, 8))

    def build_topbar(self):
        bar = tk.Frame(self.root, bg="#191a21", height=58)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        tk.Label(
            bar,
            text="âœ¦ NOVA STUDIO",
            bg="#191a21",
            fg=ACCENT,
            font=("Segoe UI", 17, "bold"),
        ).pack(side="left", padx=18)

        tk.Label(
            bar,
            text="VIDEO WORKSPACE",
            bg="#191a21",
            fg=MUTED,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=8)

        ttk.Button(
            bar, text="ï¼‹ Import Video",
            command=self.choose_video,
        ).pack(side="right", padx=14, pady=10)

    def build_workspace(self):
        workspace = tk.Frame(self.root, bg=BG)
        workspace.pack(fill="both", expand=True, padx=10, pady=10)

        workspace.grid_columnconfigure(0, minsize=210, weight=1)
        workspace.grid_columnconfigure(1, minsize=350, weight=3)
        workspace.grid_columnconfigure(2, minsize=190, weight=1)
        workspace.grid_rowconfigure(0, weight=1)

        self.build_media_panel(workspace)
        self.build_preview_panel(workspace)
        self.build_tools_panel(workspace)


    def build_media_panel(self, parent):
        panel = tk.Frame(parent, bg=PANEL)
        panel.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        self.panel_title(panel, "Media Library")

        ttk.Button(
            panel, text="ï¼‹ Import Media",
            command=self.choose_video,
        ).pack(fill="x", padx=10, pady=4)

        self.media_list = tk.Listbox(
            panel,
            bg=PANEL_LIGHT,
            fg=TEXT,
            selectbackground="#176783",
            selectforeground="white",
            relief="flat",
            borderwidth=0,
            font=("Segoe UI", 10),
            activestyle="none",
        )
        self.media_list.pack(
            fill="both", expand=True, padx=10, pady=8
        )
        self.media_list.bind(
            "<<ListboxSelect>>", self.select_media
        )

        self.media_hint = tk.Label(
            panel,
            text="Import a video to begin",
            bg=PANEL,
            fg=MUTED,
            wraplength=180,
            justify="left",
        )
        self.media_hint.pack(fill="x", padx=12, pady=(0, 12))

    def build_preview_panel(self, parent):
        panel = tk.Frame(parent, bg=PANEL)
        panel.grid(row=0, column=1, sticky="nsew", padx=6)

        self.panel_title(panel, "Program Monitor")

        self.preview = tk.Frame(panel, bg="#08090d")
        self.preview.pack(
            fill="both", expand=True, padx=12, pady=(0, 8)
        )

        self.preview_icon = tk.Label(
            self.preview,
            text="â–¶",
            bg="#08090d",
            fg=ACCENT,
            font=("Segoe UI", 42),
        )
        self.preview_icon.pack(pady=(35, 4))

        self.preview_text = tk.Label(
            self.preview,
            text="No video loaded",
            bg="#08090d",
            fg=MUTED,
            font=("Segoe UI", 11),
        )
        self.preview_text.pack()

        self.time_label = tk.Label(
            panel,
            text="00:00:00  /  00:00:00",
            bg=PANEL,
            fg=TEXT,
            font=("Consolas", 11),
        )
        self.time_label.pack(pady=6)

        controls = tk.Frame(panel, bg=PANEL)
        controls.pack(pady=(0, 12))

        ttk.Button(
            controls, text="â®",
            command=lambda: self.add_log(
                "Timeline navigation will be added next."
            ),
        ).pack(side="left", padx=3)

        ttk.Button(
            controls, text="â–¶ Play",
            command=self.play_preview,
        ).pack(side="left", padx=3)

        ttk.Button(
            controls, text="â­",
            command=lambda: self.add_log(
                "Timeline navigation will be added next."
            ),
        ).pack(side="left", padx=3)

    def build_tools_panel(self, parent):
        panel = tk.Frame(parent, bg=PANEL)
        panel.grid(row=0, column=2, sticky="nsew", padx=(6, 0))

        self.panel_title(panel, "Editing Tools")

        tools = [
            ("Trim", "trim"),
            ("Speed", "speed"),
            ("Crop", "crop"),
            ("Resize", "resize"),
            ("Brightness", "brighten"),
            ("Extract Audio", "extract audio"),
            ("Volume", "volume"),
            ("Export MP4", "convert to mp4"),
        ]

        for label, command in tools:
            ttk.Button(
                panel,
                text=label,
                command=lambda c=command: self.tool_command(c),
            ).pack(fill="x", padx=10, pady=4)

        tk.Label(
            panel,
            text="TOOLS APPLY TO\nTHE SELECTED VIDEO",
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI", 8),
            justify="center",
        ).pack(pady=14)


    def build_timeline(self):
        panel = tk.Frame(self.root, bg=PANEL, height=190)
        panel.pack(fill="x", padx=10, pady=(0, 8))
        panel.pack_propagate(False)

        header = tk.Frame(panel, bg=PANEL)
        header.pack(fill="x", padx=12, pady=(10, 6))

        tk.Label(
            header, text="TIMELINE",
            bg=PANEL, fg=ACCENT,
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left")

        ttk.Button(
            header, text="ï¼‹ Add Video Track",
            command=lambda: self.add_log(
                "Video track selected."
            ),
        ).pack(side="right", padx=3)

        ttk.Button(
            header, text="ï¼‹ Add Audio Track",
            command=lambda: self.add_log(
                "Audio track selected."
            ),
        ).pack(side="right", padx=3)

        self.timeline_canvas = tk.Canvas(
            panel,
            bg="#101117",
            height=105,
            highlightthickness=0,
        )
        self.timeline_canvas.pack(
            fill="both", expand=True, padx=12, pady=(0, 10)
        )

        self.timeline_canvas.bind(
            "<Configure>", lambda event: self.draw_timeline()
        )

    def draw_timeline(self):
        canvas = self.timeline_canvas
        canvas.delete("all")

        width = max(canvas.winfo_width(), 400)

        duration = 60.0
        position = 0.0
        if self.video_path:
            cap = cv2.VideoCapture(str(self.video_path))
            fps = cap.get(cv2.CAP_PROP_FPS)
            count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            cap.release()
            if fps > 0 and count > 0:
                duration = count / fps
        position = min(float(getattr(self, "preview_position", 0.0)), duration)

        def stamp(seconds):
            seconds = int(max(0, seconds))
            return f"{seconds // 60:02d}:{seconds % 60:02d}"

        canvas.create_text(12, 10, text=stamp(0), anchor="w",
                           fill=MUTED, font=("Consolas", 9))
        canvas.create_text(width // 2, 10, text=stamp(duration / 2),
                           fill=MUTED, font=("Consolas", 9))
        canvas.create_text(width - 12, 10, text=stamp(duration),
                           anchor="e", fill=MUTED, font=("Consolas", 9))

        # Track labels and lanes
        canvas.create_text(
            12, 42, text="V1",
            anchor="w", fill=ACCENT,
            font=("Segoe UI", 9, "bold"),
        )
        canvas.create_text(
            12, 78, text="A1",
            anchor="w", fill="#c5a3ff",
            font=("Segoe UI", 9, "bold"),
        )

        start_x = 42
        end_x = max(width - 12, start_x + 20)

        canvas.create_rectangle(
            start_x, 29, end_x, 54,
            fill="#234f65", outline="#3188a5",
        )
        canvas.create_rectangle(
            start_x, 64, end_x, 87,
            fill="#44345c", outline="#8062a6",
        )

        if self.video_path:
            canvas.create_text(
                start_x + 8, 41,
                text=self.video_path.name,
                anchor="w", fill="white",
                font=("Segoe UI", 9),
            )
            canvas.create_text(
                start_x + 8, 75,
                text="Audio track",
                anchor="w", fill="white",
                font=("Segoe UI", 9),
            )

        # Playhead follows the actual video position.
        playhead_x = start_x + (end_x - start_x) * (position / duration if duration > 0 else 0)
        canvas.create_line(
            playhead_x, 19, playhead_x, 91,
            fill="#ff647c", width=2,
        )
        canvas.create_polygon(
            playhead_x - 5, 18,
            playhead_x + 5, 18,
            playhead_x, 25,
            fill="#ff647c", outline="",
        )


    def build_bottom_bar(self):
        bar = tk.Frame(self.root, bg="#191a21")
        bar.pack(fill="x", side="bottom")

        self.status_label = tk.Label(
            bar,
            text="READY  |  No video selected",
            bg="#191a21",
            fg=MUTED,
            font=("Segoe UI", 9),
            anchor="w",
        )
        self.status_label.pack(
            side="left", padx=14, pady=10
        )

        self.command_entry = ttk.Entry(
            bar, style="Studio.TEntry"
        )
        self.command_entry.pack(
            side="right", padx=(6, 12), pady=7,
            fill="x", expand=True,
        )
        self.command_entry.bind(
            "<Return>", lambda event: self.submit_command()
        )

        ttk.Button(
            bar, text="Run Command",
            command=self.submit_command,
        ).pack(side="right", padx=4, pady=7)

    def choose_video(self):
        selected = filedialog.askopenfilename(
            title="Import video",
            filetypes=[
                ("Video files", "*.mp4 *.mov *.mkv *.avi *.webm *.wmv"),
                ("All files", "*.*"),
            ],
        )
        if not selected:
            return

        self.video_path = Path(selected)
        self.media_list.delete(0, "end")
        self.media_list.insert("end", self.video_path.name)
        self.media_hint.configure(text=str(self.video_path))
        cap = cv2.VideoCapture(str(self.video_path))
        ok, frame = cap.read()
        cap.release()
        if ok:
            self.preview_position = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            self.time_label.configure(text=f"{int(self.preview_position)//3600:02d}:{(int(self.preview_position)%3600)//60:02d}:{int(self.preview_position)%60:02d}")
            self.draw_timeline()
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(frame)
            image.thumbnail((720, 405))
            self.preview_photo = ImageTk.PhotoImage(image)
            self.preview_icon.pack_forget()
            self.preview_text.configure(image=self.preview_photo, text="")
            self.preview_text.pack(expand=True)
        else:
            self.preview_text.configure(text=self.video_path.name, image="")
        self.status_label.configure(
            text=f"LOADED  |  {self.video_path.name}"
        )
        self.draw_timeline()
        self.add_log(f"Imported: {self.video_path}")

    def select_media(self, event=None):
        selection = self.media_list.curselection()
        if selection and self.video_path:
            self.preview_text.configure(
                text=self.video_path.name
            )

    def add_log(self, message):
        self.status_label.configure(text=str(message)[:100])

    def play_preview(self):
        if not self.video_path:
            messagebox.showinfo("Nova Studio", "Import a video first.")
            return

        if self.preview_playing:
            self.preview_playing = False
            if self.preview_after_id:
                try:
                    self.root.after_cancel(self.preview_after_id)
                except tk.TclError:
                    pass
                self.preview_after_id = None
            self.add_log("Preview paused.")
            return

        if self.preview_cap is None or not self.preview_cap.isOpened():
            self.preview_cap = cv2.VideoCapture(str(self.video_path))
            if not self.preview_cap.isOpened():
                self.preview_cap.release()
                self.preview_cap = None
                messagebox.showerror("Playback error", "Could not open this video.")
                return
            self.preview_cap.set(cv2.CAP_PROP_POS_MSEC, max(0, getattr(self, "preview_position", 0)) * 1000)

        self.preview_playing = True
        self._preview_tick()

    def _preview_tick(self):
        if not self.preview_playing:
            return
        cap = self.preview_cap
        if cap is None or not cap.isOpened():
            self.preview_playing = False
            return

        ok, frame = cap.read()
        if not ok:
            self.preview_playing = False
            cap.release()
            self.preview_cap = None
            self.preview_after_id = None
            self.add_log("Playback finished.")
            return

        self.preview_position = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_no = cap.get(cv2.CAP_PROP_POS_FRAMES)
        if fps > 0:
            self.preview_position = max(0, (frame_no - 1) / fps)

        total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        duration = total_frames / fps if fps > 0 and total_frames > 0 else 0
        current = max(0, int(self.preview_position))
        total = max(0, int(duration))
        self.time_label.configure(
            text=f"{current//3600:02d}:{(current%3600)//60:02d}:{current%60:02d}  /  "
                 f"{total//3600:02d}:{(total%3600)//60:02d}:{total%60:02d}"
        )

        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(frame)
        image.thumbnail((720, 405))
        self.preview_photo = ImageTk.PhotoImage(image)
        self.preview_icon.pack_forget()
        self.preview_text.configure(image=self.preview_photo, text="")
        self.preview_text.pack(expand=True)
        self.draw_timeline()

        delay = max(1, int(1000 / fps)) if fps > 0 else 33
        self.preview_after_id = self.root.after(delay, self._preview_tick)

    def _preview_tick(self):
        if not getattr(self, "preview_playing", False):
            return
        cap = getattr(self, "preview_cap", None)
        if cap is None:
            self.preview_playing = False
            return

        ok, frame = cap.read()
        if not ok:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = cap.read()
        if ok:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(frame)
            image.thumbnail((720, 405))
            self.preview_photo = ImageTk.PhotoImage(image)
            self.preview_icon.pack_forget()
            self.preview_text.configure(image=self.preview_photo, text="")
            fps = cap.get(cv2.CAP_PROP_FPS)
            delay = max(1, int(1000 / fps)) if fps > 0 else 33
            self.preview_after_id = self.root.after(delay, self._preview_tick)
        else:
            self.preview_playing = False
            cap.release()
            self.preview_cap = None

    def tool_command(self, command):
        self.command_entry.delete(0, 'end')
        self.command_entry.insert(0, command)
        self.submit_command()

    def submit_command(self):
        command = self.command_entry.get().strip().lower()
        if not command:
            return

        self.command_entry.delete(0, "end")

        if not self.video_path:
            messagebox.showinfo(
                "Nova Studio", "Import a video first."
            )
            return

        path = str(self.video_path)

        try:
            if "extract audio" in command:
                task = (editor.extract_audio, (path,))
            elif "trim" in command:
                start = simpledialog.askfloat(
                    "Trim", "Start time in seconds:", minvalue=0
                )
                if start is None:
                    return
                end = simpledialog.askfloat(
                    "Trim", "End time in seconds:", minvalue=0
                )
                if end is None or end <= start:
                    messagebox.showwarning(
                        "Trim", "End must be greater than start."
                    )
                    return
                task = (editor.trim_video, (path, start, end))
            elif "speed" in command or "slow" in command:
                factor = simpledialog.askfloat(
                    "Speed", "Speed factor (0.5 = slower, 2 = faster):",
                    initialvalue=2.0 if "fast" in command else 0.5,
                    minvalue=0.1, maxvalue=10,
                )
                if factor is None:
                    return
                task = (editor.change_speed, (path, factor))
            elif "crop" in command:
                w = simpledialog.askinteger(
                    "Crop", "Width in pixels:", minvalue=2
                )
                if w is None:
                    return
                h = simpledialog.askinteger(
                    "Crop", "Height in pixels:", minvalue=2
                )
                if h is None:
                    return
                task = (editor.crop_video, (path, w, h))
            elif "resize" in command:
                w = simpledialog.askinteger(
                    "Resize", "Width in pixels:", minvalue=2
                )
                if w is None:
                    return
                h = simpledialog.askinteger(
                    "Resize", "Height in pixels:", minvalue=2
                )
                if h is None:
                    return
                task = (editor.resize_video, (path, w, h))
            elif "bright" in command:
                amount = simpledialog.askfloat(
                    "Brightness", "Adjustment from -1 to 1:",
                    minvalue=-1, maxvalue=1,
                )
                if amount is None:
                    return
                task = (editor.adjust_brightness, (path, amount))
            elif "mute" in command:
                task = (editor.adjust_volume, (path, 0.0))
            elif "volume" in command:
                amount = simpledialog.askfloat(
                    "Volume", "Multiplier (1 = unchanged):",
                    initialvalue=1.5, minvalue=0, maxvalue=10,
                )
                if amount is None:
                    return
                task = (editor.adjust_volume, (path, amount))
            elif "mp4" in command or "convert" in command:
                task = (editor.convert_to_mp4, (path,))
            else:
                messagebox.showinfo(
                    "Commands",
                    "Try: trim, speed, crop, resize, brighten, "
                    "extract audio, volume, mute, or convert to mp4.",
                )
                return

            function, args = task
            threading.Thread(
                target=self.run_edit,
                args=(function, args),
                daemon=True,
            ).start()

        except Exception as exc:
            messagebox.showerror("Nova Studio", str(exc))

    def run_edit(self, function, args):
        try:
            result = function(*args)
            result_text = str(result)
            marker = ": "
            exported = result_text.rsplit(marker, 1)[-1] if marker in result_text else ""
            output = Path(exported.strip().strip('"')) if exported else None

            def finish():
                self.status_label.configure(text=f"EXPORTED  |  {result_text}"[:180])
                if output and output.is_file():
                    self.load_exported_video(output)

            self.root.after(0, finish)
        except Exception as exc:
            error = str(exc)
            self.root.after(0, lambda: messagebox.showerror("Export error", error))

    def load_exported_video(self, path):
        self.preview_playing = False
        if self.preview_after_id:
            try:
                self.root.after_cancel(self.preview_after_id)
            except tk.TclError:
                pass
            self.preview_after_id = None
        if self.preview_cap is not None:
            self.preview_cap.release()
            self.preview_cap = None

        self.video_path = Path(path)
        self.preview_position = 0.0
        cap = cv2.VideoCapture(str(self.video_path))
        ok, frame = cap.read()
        fps = cap.get(cv2.CAP_PROP_FPS)
        count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        cap.release()

        self.media_list.delete(0, "end")
        self.media_list.insert("end", self.video_path.name)
        self.media_hint.configure(text=str(self.video_path))
        if ok:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(frame)
            image.thumbnail((720, 405))
            self.preview_photo = ImageTk.PhotoImage(image)
            self.preview_icon.pack_forget()
            self.preview_text.configure(image=self.preview_photo, text="")
            self.preview_text.pack(expand=True)

        duration = count / fps if fps > 0 and count > 0 else 0
        total = int(duration)
        self.time_label.configure(
            text=f"00:00:00  /  {total//3600:02d}:{(total%3600)//60:02d}:{total%60:02d}"
        )
        self.draw_timeline()
        self.add_log(f"Loaded edited copy: {self.video_path.name}")

    def process_events(self):
        self.root.after(150, self.process_events)
    def animate_studio(self):
        try:
            self.animation_step = (self.animation_step + 1) % 120

            pulse = (self.animation_step % 60) / 60
            if pulse > 0.5:
                pulse = 1 - pulse

            shade = int(45 + pulse * 45)
            glow = f"#00{shade:02x}{min(255, shade + 35):02x}"

            if hasattr(self, "preview"):
                self.preview.configure(
                    highlightthickness=1,
                    highlightbackground=glow
                )

            if hasattr(self, "timeline_canvas") and self.video_path:
                canvas = self.timeline_canvas
                width = canvas.winfo_width()

                if width > 100:
                    self.playhead_position += 2

                    if self.playhead_position > width - 15:
                        self.playhead_position = 42

                    canvas.delete("animated_playhead")
                    x = self.playhead_position

                    canvas.create_line(
                        x, 19, x, 91,
                        fill="#ff647c",
                        width=2,
                        tags="animated_playhead"
                    )
                    canvas.create_polygon(
                        x - 5, 18, x + 5, 18, x, 25,
                        fill="#ff647c",
                        outline="",
                        tags="animated_playhead"
                    )
                    canvas.tag_raise("animated_playhead")

            self.root.after(80, self.animate_studio)

        except tk.TclError:
            pass

if __name__ == "__main__":
    root = tk.Tk()
    app = NovaStudio(root)
    root.mainloop()


