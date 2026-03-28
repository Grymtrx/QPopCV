# ──────────────────────────────────────────────────────────────────────────────
# Discord message templates
#
# Each string is sent as:  @user <message>
# Custom server emojis use the :emoji_name: syntax.
# ──────────────────────────────────────────────────────────────────────────────

# Sent when the user clicks "Test Discord" in settings.
CONNECTED = "is connected :verify:"

# Sent when a queue pop is detected on screen.
QUEUE_POP = ":queuepopblink: Your Queue has popped!"

# Sent after 28 minutes of watching (AFK warning).
AFK_WARNING = ":afkzzz: Move character to prevent AFK logout. Watch time nearing 30 minutes."

# Sent 2 minutes after the AFK warning if the timer was not reset.
AFK_LOGOUT = ":logoutalert: Your character has most likely auto-logged out. Return to PC."
