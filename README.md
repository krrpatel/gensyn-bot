# Gensyn Bot

A Telegram bot that monitors smart contract rewards and logs from a Gensyn testnet worker and sends updates to your Telegram chat.

---

## Features

- Monitors peer IDs and retrieves reward, win, and EOA data from a deployed smart contract on Gensyn testnet.
- Fetches screen logs from a running terminal session (e.g., `screen -S gensyn`).
- Sends formatted updates via Telegram bot to a specified chat.
- Supports custom intervals and multiple peer IDs.

---

## Installation Steps

### 1. Clone the repository

```bash
git clone https://github.com/krrpatel/gensyn-bot.git
cd gensyn-bot
```
## 2. Create screen
```bash
screen -S gensynbot
```

### 3. Run the bot

```bash
python3 bot_run.py
```

The script will:

- Create a virtual environment if not already created.
- Prompt you for Telegram bot token, chat ID, delay interval, peer IDs, and screen session name.
- Start sending updates to your Telegram chat at regular intervals.

---

## Telegram Setup Guide

### Create a Bot:

1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Type `/newbot` and follow the instructions
3. Copy your **Telegram Bot Token**

### Get Your Chat ID:

1. Start a chat with your bot
2. Send any message to it
3. Open this URL in a browser:

```
https://api.telegram.org/bot<YourBotToken>/getUpdates
```

4. Look for `"chat":{"id":<YOUR_CHAT_ID>}` in the response

---

## Notes

- The script will save your configuration in `config.json`.
- Logs of sent messages are saved in `sent_messages_log.txt`.
- Uses a smart contract on Gensyn testnet via Alchemy RPC.

---

## License

This project is open-source under the [MIT License](LICENSE).

---
