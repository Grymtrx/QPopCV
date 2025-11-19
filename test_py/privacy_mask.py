import tkinter as tk

# ----------------- CONFIG -----------------
HOLE_WIDTH = 420        # width of transparent window
HOLE_HEIGHT = 260       # height of transparent window
HOLE_OFFSET_Y = -425    # negative = move hole upwards
BACKGROUND_COLOR = "black"
TRANSPARENT_COLOR = "magenta"
FADE_DURATION = 1000     # ms
FADE_STEPS = 40          # smoothness
# ------------------------------------------

root = tk.Tk()
root.attributes("-fullscreen", True)
root.attributes("-topmost", True)
root.attributes("-alpha", 0)   # start fully transparent

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


# ------------- FADING FUNCTIONS -------------
def fade_in(step=0):
    alpha = step / FADE_STEPS
    root.attributes("-alpha", alpha)
    if step < FADE_STEPS:
        root.after(int(FADE_DURATION / FADE_STEPS), fade_in, step + 1)


def fade_out(step=FADE_STEPS):
    alpha = step / FADE_STEPS
    root.attributes("-alpha", alpha)
    if step > 0:
        root.after(int(FADE_DURATION / FADE_STEPS), fade_out, step - 1)
    else:
        root.destroy()
# ---------------------------------------------


# Close overlay with ESC or SPACE → triggers fade out
root.bind("<Escape>", lambda e: fade_out())
root.bind("<space>", lambda e: fade_out())

# Start fade-in animation
fade_in()

root.mainloop()
