# ──────────────────────────────────────────────────────────────────────────────
# Timer settings (seconds)
# ──────────────────────────────────────────────────────────────────────────────

AFK_WARN_DELAY     =  30  # how long before the AFK warning fires 28 * 60
AFK_LOGOUT_DELAY   =  10000  # how long after the warning before logout message 2 * 60

# ──────────────────────────────────────────────────────────────────────────────
# Discord message templates
#
# Each string is sent as:  @user <message>
# Custom server emojis use the :emoji_name: syntax.
# ──────────────────────────────────────────────────────────────────────────────

# Sent when the user clicks "Test Discord" in settings.
CONNECTED = "is connected <:verify:1487594394008948816>"

# Sent when a queue pop is detected on screen.
QUEUE_POP = "<a:queuepopblink:1487592088148246559> Q Pop!"

# Sent after 28 minutes of watching (AFK warning).
AFK_WARNING = "<:afkzzz:1487591915120492634> AFK 28m. Move character (2m until logout)"

# Sent 2 minutes after the AFK warning if the timer was not reset.
AFK_LOGOUT = "<:logoutalert:1487592229060083914> Logged out!"
