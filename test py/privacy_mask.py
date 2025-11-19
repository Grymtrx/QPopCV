import tkinter as tk

# ----------------- CONFIG -----------------
HOLE_WIDTH = 600        # width of transparent window
HOLE_HEIGHT = 400       # height of transparent window
HOLE_OFFSET_Y = -250    # negative = move hole upwards
BACKGROUND_COLOR = "black"
TRANSPARENT_COLOR = "magenta"
# ------------------------------------------

root = tk.Tk()
root.attributes("-fullscreen", True)
root.attributes("-topmost", True)

# Set window color
root.configure(bg=BACKGROUND_COLOR)

# Make specific color transparent
root.wm_attributes("-transparentcolor", TRANSPARENT_COLOR)

# Get screen size
screen_w = root.winfo_screenwidth()
screen_h = root.winfo_screenheight()

# Calculate hole position
hole_x = (screen_w - HOLE_WIDTH) // 2
hole_y = ((screen_h - HOLE_HEIGHT) // 2) + HOLE_OFFSET_Y

# Create the transparent hole
hole = tk.Frame(root, width=HOLE_WIDTH, height=HOLE_HEIGHT, bg=TRANSPARENT_COLOR)
hole.place(x=hole_x, y=hole_y)

# Optional: close overlay with ESC key
root.bind("<Escape>", lambda e: root.destroy())

# Optional: make overlay click-through (Windows only)
try:
    import ctypes
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    WS_EX_TRANSPARENT = 0x20
    WS_EX_LAYERED = 0x80000
    style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
    ctypes.windll.user32.SetWindowLongW(hwnd, -20, style | WS_EX_LAYERED | WS_EX_TRANSPARENT)
except:
    pass  # fails silently if unsupported

root.mainloop()