from pathlib import Path
import shutil
import py_compile

p = Path("nova_ai_editor.py")
s = p.read_text(encoding="utf-8")

backup = Path("nova_ai_editor_before_json_fix.py")
if not backup.exists():
    shutil.copy2(p, backup)

old = '''    response = _client().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": request},
        ],
        temperature=0.1,
        max_tokens=900,
    )
'''

new = '''    client = _client()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": request},
    ]

    # Try constrained JSON output first. Fall back for models that do not support it.
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.1,
            max_tokens=1600,
            response_format={"type": "json_object"},
        )
    except Exception as json_mode_error:
        error_text = str(json_mode_error).lower()
        unsupported_json_mode = any(
            marker in error_text
            for marker in ("response_format", "json_object", "unsupported", "not supported")
        )
        if not unsupported_json_mode:
            raise
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.1,
            max_tokens=1600,
        )
'''

if old not in s:
    raise SystemExit("PATCH STOPPED: Could not find the expected API call. No changes made.")

p.write_text(s.replace(old, new, 1), encoding="utf-8")
py_compile.compile(str(p), doraise=True)
print("SUCCESS: AI planner patched and syntax check passed.")
print(f"Backup: {backup}")
