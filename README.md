# ⚡ QPopCV

A lightweight desktop app that **monitors your screen for WoW Solo Shuffle queue pops** and instantly sends a **Discord ping** to your phone so you can step away from your PC while waiting.

![Solo Shuffle Q Pop](https://i.imgur.com/KRNfpee.png)
![Mobile Noti](https://i.imgur.com/uk64CQt.png)



## Requirements
- **Windows**
- A **Discord Webhook URL**
- Your **Discord User ID**
- WoW open with the **Queue pop visible on screen**



## Install
1. **Download the latest release**  
- [QPopCV Releases](https://github.com/Grymtrx/QPopCV/releases)



## Setup

### 1. Add your Discord Webhook URL  
You may use:
- The **public webhook** in the [QPopCV Discord](https://discord.gg/vXvjcrUFm8):
- **Or create your own private webhook** in any Discord server/channel you own.

### 2. Add your Discord User ID  
1. Discord → **Settings → Advanced → Enable Developer Mode**  
 ![Dev Mode ON](https://i.imgur.com/23nOrhM.png)

2. Right-click your profile → **Copy User ID**  
 ![Discord User ID](https://i.imgur.com/3ggfUt7.png)

Paste this into the QPopCV app so the webhook @mentions you.

### 3. Configure mobile notifications
- Enable **Mobile Push Notifications** on Discord  
- In the channel with the webhook, set notifications to **@mentions only**

This ensures you only receive alerts when *your* queue pops.

> **Important:**  
> Quit Discord from the **system tray** if you want notifications routed to your phone instead of your desktop.

Join the community here:  
👉 **[QPopCV Discord](https://discord.gg/vXvjcrUFm8)**



## Speed (End-to-End Latency)
Measured from queue pop appearing → notification on phone:

- **App detection:** 0.005s – 0.15s  
- **HTTP request to Discord:** ~0.711s  
- **Discord → phone push:** ~1.8s  
- **Total:** ~2.5- 3s seconds
