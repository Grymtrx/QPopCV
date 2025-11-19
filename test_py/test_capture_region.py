import pyautogui

# Get screen size
screen_w, screen_h = pyautogui.size()

# Top-center 1/3 of the screen
region_x = int(screen_w / 3)        # start at 1/3 from the left
region_y = 0                        # top of the screen
region_w = int(screen_w / 3)        # width = 1/3 of screen width
region_h = int(screen_h / 2)        # height = 1/2 of screen height

region = (region_x, region_y, region_w, region_h)

print(f"Screen: {screen_w}x{screen_h}")
print(f"Capture region: {region}")

# Take screenshot of that region
img = pyautogui.screenshot(region=region)
img.save("test_capture_region.png")
print("Saved test_capture_region.png")

# Optional: show it
img.show()
