from pathlib import Path
import py_compile

p = Path("nova_studio_qt.py")
s = p.read_text(encoding="utf-8")

bad = '''                match = re.search(
                    r"(?:saved to|output(?: file)?(?: saved)?(?: to)?):?\\\\s*[\\\\"']?(.+?)[\\\\"']?\\\\s*$",
                    result,
                    re.IGNORECASE
                )'''

good = '''                match = re.search(
                    r"""(?:saved to|output(?: file)?(?: saved)?(?: to)?):?\\s*["']?(.+?)["']?\\s*$""",
                    result,
                    re.IGNORECASE
                )'''

if bad not in s:
    print("Exact broken line pattern not found. No changes made.")
    print("Inspect lines 842-850 with:")
    print("(Get-Content .\\nova_studio_qt.py)[841..849]")
    raise SystemExit(1)

s = s.replace(bad, good, 1)
p.write_text(s, encoding="utf-8")
py_compile.compile(str(p), doraise=True)
print("SUCCESS: syntax fixed and nova_studio_qt.py compiles.")
