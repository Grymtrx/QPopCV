# ⚡ QPopCV

A lightweight desktop app that **monitors your screen for WoW Solo Shuffle queue pops** and instantly sends a **Discord ping** to your phone so you can step away from your PC while waiting.

![Solo Shuffle Q Pop](https://i.imgur.com/KRNfpee.png)

![Mobile Noti](https://i.imgur.com/FAwYL5B.png)



## Requirements
- **Windows**
- A **Discord Webhook URL**
- Your **Discord User ID**
- WoW open with the **Queue pop visible on screen**

## Setup
Join the community here for setup instructions:  
👉 **[QPopCV Discord](https://discord.gg/vXvjcrUFm8)**

## Speed (End-to-End Latency)
Measured from queue pop appearing → notification on phone:

- **App detection:** 0.005s – 0.15s  
- **HTTP request to Discord:** ~0.711s  
- **Discord → phone push:** ~1.8s  
- **Total:** ~2.5- 3s seconds


----

## Legality / Blizzard TOS Compliance

QPopCV is designed to operate **within the boundaries of Blizzard’s Terms of Service**.  
It does **not** automate gameplay, modify the client, or provide any in-game advantage.

**Why QPopCV is TOS/EULA Safe:**

- **No memory reading or writing**  
  QPopCV never interacts with WoW’s process, RAM, or network packets.

- **No automation**  
  The app only *observes* your screen for a visual queue pop.  
  It does **not click**, **accept queues**, or perform any action in-game.

- **Uses standard screen capture APIs**  
  Screen reading is explicitly allowed as long as it does not manipulate or alter the game.

- **No injected code, no DLLs, no addons**  
  QPopCV is an external desktop tool that does not integrate with the game client.

- **No unfair competitive advantage**  
  It only mirrors the same information already visible to the player.

- **Similar to accessibility tools**  
  It functions like Windows Magnifier, OBS, or Discord screen-share — all common, allowed tools.

> **Disclaimer:**  
> While QPopCV is designed to comply with Blizzard's policies, I am **not responsible** for any actions taken against your WoW account. Use at your own discretion.

