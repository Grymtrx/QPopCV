# ──────────────────────────────────────────────────────────────────────────────
# Timer settings (seconds)
# ──────────────────────────────────────────────────────────────────────────────

AFK_WARN_DELAY     = 28 * 60   # how long before the AFK warning fires
AFK_LOGOUT_DELAY   = 2 * 60    # how long after the warning before logout message

# ──────────────────────────────────────────────────────────────────────────────
# Discord message templates
#
# Each string is sent as:  @user <message>
# Custom server emojis use the :emoji_name: syntax.
# ──────────────────────────────────────────────────────────────────────────────

# Sent when the user clicks "Test Discord" in settings.
CONNECTED = "is connected :verify:"

# Sent when a queue pop is detected on screen.
QUEUE_POP = ":queuepopblink: Q Pop!"

# Sent after 28 minutes of watching (AFK warning).
AFK_WARNING = ":afkzzz: AFK 28m. Move character (2m until logout)"

# Sent 2 minutes after the AFK warning if the timer was not reset.
AFK_LOGOUT = ":logoutalert: Logged out!"
