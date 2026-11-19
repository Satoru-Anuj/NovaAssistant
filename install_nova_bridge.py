from pathlib import Path
import ast
import shutil

folder = Path(__file__).resolve().parent
widget = folder / "nova_widget.py"

source = widget.read_text(encoding="utf-8-sig")
start = "    # These signals are ready for connection to Nova"
end = "    tray = QSystemTrayIcon(make_tray_icon(), app)"

a = source.find(start)
b = source.find(end, a)

if a < 0 or b < 0:
    raise SystemExit("Expected section not found. Widget unchanged.")

backup = folder / "nova_widget_before_connection.py"
shutil.copy2(widget, backup)

replacement = (
    "    from pathlib import Path\n"
    "    import subprocess\n"
    "\n"
    "    assistant_process = [None]\n"
    "\n"
    "    def launch_assistant():\n"
    "        process = assistant_process[0]\n"
    "        if process is None or process.poll() is not None:\n"
    "            assistant_file = Path(__file__).with_name('main.py')\n"
    "            assistant_process[0] = subprocess.Popen(\n"
    "                [sys.executable, str(assistant_file), '--background'],\n"
    "                cwd=str(assistant_file.parent)\n"
    "            )\n"
    "\n"
    "    widget.microphoneClicked.connect(launch_assistant)\n"
    "    widget.audioToggleRequested.connect(launch_assistant)\n"
    "\n"
)

updated = source[:a] + replacement + source[b:]
ast.parse(updated)
widget.write_text(updated, encoding="utf-8")
print("Button connection added. Syntax OK.")