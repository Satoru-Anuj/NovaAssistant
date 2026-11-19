from pathlib import Path
import py_compile

path = Path("main.py")
source = path.read_text(encoding="utf-8")

marker = "# NOVA_LOCKED_IDLE_ACTIVE_V1"
anchor = "        # Smooth colour wheel for the RGB trails."

if marker in source:
    raise SystemExit("Patch already exists. No changes made.")

if source.count(anchor) != 1:
    raise SystemExit("Expected animation anchor was not found exactly once. No changes made.")

addition = '''        # NOVA_LOCKED_IDLE_ACTIVE_V1
        # Only the collapsed Idle/Active visuals change here.
        # The existing expanded Glass Bar renderer below is preserved.
        if not self.expanded:
            active_now = self.busy or self.status not in ("idle", "ready")
            speed_now = {"listening": 2.2, "thinking": 3.0, "speaking": 2.5}.get(
                self.status, 2.0
            )
            self.angle = (self.angle + (speed_now if active_now else 0.7)) % 360

            cx, cy = 52, 35
            pulse = (math.sin(math.radians(self.angle * 2.0)) + 1.0) / 2.0

            if not active_now:
                # STATE 1 — IDLE: clean circular ring, no infinity symbol.
                r = 21 + pulse * 1.2
                canvas.create_oval(
                    cx-r-4, cy-r-4, cx+r+4, cy+r+4,
                    outline="#142A38", width=2
                )
                canvas.create_oval(
                    cx-r, cy-r, cx+r, cy+r,
                    outline="#28748A", width=2
                )
                canvas.create_arc(
                    cx-r, cy-r, cx+r, cy+r,
                    start=self.angle, extent=85,
                    style="arc", outline="#B5F8FF", width=3
                )
                canvas.create_oval(
                    cx-3, cy-3, cx+3, cy+3,
                    fill="#D7FCFF", outline=""
                )
                canvas.create_text(
                    104, 29, text="N O V A",
                    fill="#C6EAF2", font=("Segoe UI", 10, "bold"),
                    anchor="w"
                )
                canvas.create_text(
                    104, 46, text="STANDBY",
                    fill="#658A9C", font=("Consolas", 8),
                    anchor="w"
                )
            else:
                # STATE 3 — ACTIVE: reactive cyan-blue plasma ring.
                r = 21 + pulse * (4 if self.status == "listening" else 6)
                for offset, colour, width in (
                    (7, "#103052", 6),
                    (3, "#075F91", 4),
                    (0, "#00BFEF", 2),
                ):
                    rr = r + offset
                    canvas.create_oval(
                        cx-rr, cy-rr, cx+rr, cy+rr,
                        outline=colour, width=width
                    )

                for i, colour in enumerate(
                    ("#A1FFFF", "#00D7FF", "#478BFF", "#8A78FF")
                ):
                    start = self.angle * (1 if i % 2 == 0 else -1) + i * 91
                    rr = r + 3 + (i % 2) * 4
                    canvas.create_arc(
                        cx-rr, cy-rr*0.82, cx+rr, cy+rr*0.82,
                        start=start, extent=95 + 25*pulse,
                        style="arc", outline=colour, width=2
                    )
                    a = math.radians(start + 95)
                    px = cx + math.cos(a) * rr
                    py = cy + math.sin(a) * rr * 0.82
                    canvas.create_oval(
                        px-2, py-2, px+2, py+2,
                        fill=colour, outline=""
                    )

                core = 6 + pulse * 2
                canvas.create_oval(
                    cx-core-4, cy-core-4, cx+core+4, cy+core+4,
                    fill="#073B5E", outline=""
                )
                canvas.create_oval(
                    cx-core, cy-core, cx+core, cy+core,
                    fill="#18DDF8", outline="#C3FCFF", width=1
                )
                label = {
                    "listening": "LISTENING",
                    "thinking": "THINKING",
                    "speaking": "SPEAKING",
                }.get(self.status, "ACTIVE")
                canvas.create_text(
                    104, 29, text="N O V A",
                    fill="#C6F9FF", font=("Segoe UI", 10, "bold"),
                    anchor="w"
                )
                canvas.create_text(
                    104, 46, text=label,
                    fill="#65DEFF", font=("Consolas", 8, "bold"),
                    anchor="w"
                )

            self.root.after(24, self.animate)
            return

'''

backup = Path("main.py.pre_ui_patch.backup")
if not backup.exists():
    backup.write_bytes(path.read_bytes())

updated = source.replace(anchor, addition + anchor, 1)
path.write_text(updated, encoding="utf-8")
try:
    py_compile.compile(str(path), doraise=True)
except Exception:
    path.write_text(source, encoding="utf-8")
    raise SystemExit("Syntax check failed; original main.py restored.")

print("Patch applied. Python syntax check passed.")
print("Expanded Glass Bar drawing code was left unchanged.")
print("Backup: main.py.pre_ui_patch.backup")