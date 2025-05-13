import os
import time
import json
import html
import requests
from web3 import Web3
from datetime import datetime
import subprocess

CONFIG_FILE = "config.json"

def create_virtual_env():
    if not os.path.exists(".venv"):
        print("Creating virtual environment...")
        subprocess.run("python3 -m venv .venv", shell=True)
    activate_script = ".venv/bin/activate"
    if os.name == "nt":
        activate_script = ".venv\\Scripts\\activate.bat"
    print(f"\n[!] Activate your virtual environment first:\nsource {activate_script}\n")
    time.sleep(3)

def get_user_config():
    print("\n=== Telegram Setup Guide ===")
    print("1. Create a bot: Talk to @BotFather on Telegram and use /newbot")
    print("2. Copy the API token it gives you.")
    print("3. To get your chat ID:")
    print("   - Start a chat with your bot")
    print("   - Visit: https://api.telegram.org/bot<YourToken>/getUpdates after sending a message")
    print("   - Copy the chat.id from the response\n")

    config = {}
    config["TELEGRAM_API_TOKEN"] = input("Enter Telegram Bot API Token: ").strip()
    config["CHAT_ID"] = input("Enter Telegram Chat ID: ").strip()
    config["DELAY_SECONDS"] = int(input("Enter delay in seconds (e.g., 1800 for 30 mins): ").strip())
    peer_ids = input("Enter Peer IDs (comma-separated): ").strip().split(",")
    config["PEER_IDS"] = [pid.strip() for pid in peer_ids]
    config["SCREEN_NAME"] = input("Enter your screen session name (e.g., gensyn): ").strip()
    return config

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return None
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

# === Constants that don’t change ===
ALCHEMY_RPC = "https://gensyn-testnet.g.alchemy.com/v2/kWjsfs1x2ODpQRf6C-fpPfel0rtlFhb9"
CONTRACT_ADDRESS = "0x69C6e1D608ec64885E7b185d39b04B491a71768C"

ABI = [
    {
        "name": "getTotalRewards",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "peerIds", "type": "string[]"}],
        "outputs": [{"name": "", "type": "int256[]"}]
    },
    {
        "name": "getTotalWins",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "peerId", "type": "string"}],
        "outputs": [{"name": "", "type": "uint256"}]
    },
    {
        "name": "getEoa",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "peerIds", "type": "string[]"}],
        "outputs": [{"name": "", "type": "address[]"}]
    }
]

def send_telegram_message(token, chat_id, message: str):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    return requests.post(url, json=payload)

def log_message(message: str):
    log_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("sent_messages_log.txt", "a") as log_file:
        log_file.write(f"{log_time} - Message Sent:\n{message}\n\n")

def get_last_screen_logs(screen_name="gensyn", lines=10):
    try:
        log_path = f"/tmp/{screen_name}_log.txt"
        subprocess.run(f"screen -S {screen_name} -X hardcopy {log_path}", shell=True, check=True)
        with open(log_path, "rb") as f:
            content = f.read().decode("utf-8", errors="ignore")
        last_lines = content.strip().split("\n")[-lines:]
        return "\n".join(last_lines)
    except Exception as e:
        return f"Log fetch error: {str(e)}"

def main():
    create_virtual_env()

    config = load_config()
    if config:
        print("\nConfig file found.")
        print("1 - Use existing config")
        print("2 - Create new config")
        choice = input("Select option: ").strip()
        if choice == "2":
            config = get_user_config()
            save_config(config)
    else:
        config = get_user_config()
        save_config(config)

    peer_ids = config["PEER_IDS"]
    token = config["TELEGRAM_API_TOKEN"]
    chat_id = config["CHAT_ID"]
    delay = config["DELAY_SECONDS"]
    screen_name = config["SCREEN_NAME"]

    w3 = Web3(Web3.HTTPProvider(ALCHEMY_RPC))
    contract = w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=ABI)

    while True:
        try:
            rewards = contract.functions.getTotalRewards(peer_ids).call()
            wins = [contract.functions.getTotalWins(pid).call() for pid in peer_ids]
            addresses = contract.functions.getEoa(peer_ids).call()

            messages = []
            for i, pid in enumerate(peer_ids):
                eoa = addresses[i]
                explorer_link = f"https://gensyn-testnet.explorer.alchemy.com/address/{eoa}?tab=internal_txns"
                msg = (
                    f"<b>Peer {i + 1}</b>\n"
                    f"Peer ID: <code>{pid}</code>\n"
                    f"EOA: <code>{eoa}</code>\n"
                    f"Total Reward: {rewards[i]}\n"
                    f"Total Wins: {wins[i]}\n"
                    f'<a href="{explorer_link}">View on Explorer</a>'
                )
                messages.append(msg)

            screen_log = get_last_screen_logs(screen_name)
            escaped_logs = html.escape(screen_log)
            full_message = "\n\n".join(messages) + f"\n\n<b>Last Logs:</b>\n<code>{escaped_logs}</code>"

            response = send_telegram_message(token, chat_id, full_message)
            log_message(full_message)

            if response.ok:
                print(f"✅ Message sent at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                print("❌ Telegram send error:", response.text)

        except Exception as e:
            error_message = f"Error fetching data:\n<code>{str(e)}</code>"
            send_telegram_message(token, chat_id, error_message)
            log_message(error_message)

        time.sleep(delay)

if __name__ == "__main__":
    main()
