
import tkinter as tk
import math
import random

SIZE = 300
CENTER = SIZE // 2

root = tk.Tk()
root.title("Nova Orb")
root.geometry(f"{SIZE}x{SIZE}+500+200")
root.overrideredirect(True)
root.attributes("-topmost", True)
root.configure(bg="#050914")

# Make the background transparent on Windows
try:
    root.wm_attributes("-transparentcolor", "#050914")
except tk.TclError:
    pass

canvas = tk.Canvas(
    root,
    width=SIZE,
    height=SIZE,
    bg="#050914",
    highlightthickness=0
)
canvas.pack()

angle = 0
pulse = 0
particles = [
    (random.randint(90, 210), random.randint(90, 210),
     random.randint(1, 3))
    for _ in range(35)
]


def draw_orb():
    global angle, pulse

    canvas.delete("all")

    # Pulsing energy core
    pulse = (pulse + 0.08) % (2 * math.pi)
    radius = 43 + math.sin(pulse) * 5

    # Outer holographic rings
    for ring in range(3):
        r = 70 + ring * 12
        points = []

        for i in range(101):
            a = math.radians(i * 3.6 + angle * (1 if ring % 2 == 0 else -1))
            x = CENTER + math.cos(a) * r
            y = CENTER + math.sin(a) * r * (0.35 + ring * 0.12)
            points.extend([x, y])

        canvas.create_line(
            points,
            fill=["#00E5FF", "#168BFF", "#744CFF"][ring],
            width=2,
            smooth=True
        )

    # Glowing core layers
    for r, color in [
        (radius + 17, "#123F78"),
        (radius + 10, "#087CA7"),
        (radius + 4, "#00BFFF"),
        (radius, "#79F7FF"),
    ]:
        canvas.create_oval(
            CENTER-r, CENTER-r,
            CENTER+r, CENTER+r,
            fill=color,
            outline=""
        )

    # Bright inner energy
    canvas.create_oval(
        CENTER-19, CENTER-19,
        CENTER+19, CENTER+19,
        fill="#E8FFFF",
        outline="#FFFFFF",
        width=2
    )

    # Floating particles
    for x, y, size in particles:
        glow = random.choice(["#00E5FF", "#168BFF", "#A7FFFF"])
        canvas.create_oval(
            x, y, x+size, y+size,
            fill=glow,
            outline=""
        )

    angle = (angle + 2) % 360
    root.after(35, draw_orb)


# Drag the orb around your desktop
def start_drag(event):
    root.drag_x = event.x
    root.drag_y = event.y


def drag(event):
    x = root.winfo_x() + event.x - root.drag_x
    y = root.winfo_y() + event.y - root.drag_y
    root.geometry(f"+{x}+{y}")


canvas.bind("<Button-1>", start_drag)
canvas.bind("<B1-Motion>", drag)

# Right-click to close
canvas.bind("<Button-3>", lambda event: root.destroy())

draw_orb()
root.mainloop()

import tkinter as tk
import math
import random

SIZE = 300
CENTER = SIZE // 2

root = tk.Tk()
root.title("Nova - Holographic Orb")
root.geometry("300x300+500+200")
root.overrideredirect(True)
root.attributes("-topmost", True)
root.configure(bg="#050914")

try:
    root.wm_attributes("-transparentcolor", "#050914")
except tk.TclError:
    pass

canvas = tk.Canvas(
    root,
    width=SIZE,
    height=SIZE,
    bg="#050914",
    highlightthickness=0
)
canvas.pack()

angle = 0
pulse = 0
particles = [
    (
        random.randint(90, 210),
        random.randint(90, 210),
        random.randint(1, 3)
    )
    for _ in range(35)
]


def draw_orb():
    global angle, pulse

    canvas.delete("all")
    pulse += 0.09
    radius = 40 + math.sin(pulse) * 5

    # Rotating holographic rings
    for ring in range(3):
        points = []
        r = 68 + ring * 13

        for i in range(101):
            a = math.radians(
                i * 3.6 + angle * (1 if ring % 2 == 0 else -1)
            )
            x = CENTER + math.cos(a) * r
            y = CENTER + math.sin(a) * r * (0.35 + ring * 0.12)
            points.extend([x, y])

        canvas.create_line(
            points,
            fill=["#00E5FF", "#168BFF", "#744CFF"][ring],
            width=2,
            smooth=True
        )

    # Glowing energy core
    for r, color in [
        (radius + 17, "#123F78"),
        (radius + 10, "#087CA7"),
        (radius + 4, "#00BFFF"),
        (radius, "#79F7FF"),
    ]:
        canvas.create_oval(
            CENTER-r, CENTER-r,
            CENTER+r, CENTER+r,
            fill=color,
            outline=""
        )

    canvas.create_oval(
        CENTER-19, CENTER-19,
        CENTER+19, CENTER+19,
        fill="#E8FFFF",
        outline="#FFFFFF",
        width=2
    )

    # Floating particles
    for x, y, size in particles:
        canvas.create_oval(
            x, y, x+size, y+size,
            fill=random.choice(["#00E5FF", "#168BFF", "#A7FFFF"]),
            outline=""
        )

    angle = (angle + 2) % 360
    root.after(35, draw_orb)


# Drag the floating orb with the mouse
def start_drag(event):
    root.drag_x = event.x
    root.drag_y = event.y


def drag(event):
    x = root.winfo_x() + event.x - root.drag_x
    y = root.winfo_y() + event.y - root.drag_y
    root.geometry(f"+{x}+{y}")


canvas.bind("<Button-1>", start_drag)
canvas.bind("<B1-Motion>", drag)

# Right-click to close Nova Orb
canvas.bind("<Button-3>", lambda event: root.destroy())

draw_orb()
root.mainloop()
