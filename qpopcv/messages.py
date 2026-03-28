# ──────────────────────────────────────────────────────────────────────────────
# Discord message templates
#
# Each string is sent as:  @user <message>
# Custom server emojis use the :emoji_name: syntax.
# ──────────────────────────────────────────────────────────────────────────────

# Sent when the user clicks "Test Discord" in settings.
CONNECTED = "is online :verify:"

# Sent when a queue pop is detected on screen.
QUEUE_POP = ":queuepopblink: Pop!"

# Sent after 28 minutes of watching (AFK warning).
AFK_WARNING = ":afkzzz: Move now!"

# Sent 2 minutes after the AFK warning if the timer was not reset.
AFK_LOGOUT = ":logoutalert: AFK'd out!"
