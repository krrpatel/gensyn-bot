import os
import time
import json
import html
import requests
import subprocess
from web3 import Web3
from datetime import datetime, timedelta
import pytz

CONFIG_FILE = "config.json"
VENV_DIR = ".venv"

# Gensyn Testnet Constants
ALCHEMY_RPC = "https://gensyn-testnet.g.alchemy.com/public"
CONTRACT_ADDRESS = "0xFaD7C5e93f28257429569B854151A1B8DCD404c2"

ABI = [
    {
        "name": "getPeerId",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "eoaAddresses", "type": "address[]"}],
        "outputs": [{"name": "", "type": "string[][]"}]
    }
]

def create_virtual_env():
    if not os.path.exists(VENV_DIR):
        print("Creating virtual environment...")
        subprocess.run(f"python3 -m venv {VENV_DIR}", shell=True)
    activate_script = f"{VENV_DIR}/bin/activate"
    if os.name == "nt":
        activate_script = f"{VENV_DIR}\\Scripts\\activate.bat"
    print(f"\n[!] Activate your virtual environment first:\nsource {activate_script}\n")
    time.sleep(2)

def get_user_config():
    print("\n=== Telegram Setup ===")
    config = {}
    config["TELEGRAM_API_TOKEN"] = input("Enter Telegram Bot API Token: ").strip()
    config["CHAT_ID"] = input("Enter Telegram Chat ID: ").strip()
    config["DELAY_SECONDS"] = int(input("Enter delay in seconds (e.g., 1800 for 30 mins): ").strip())
    config["EOA"] = input("Enter your EOA address: ").strip()
    config["SCREEN_NAME"] = input("Enter screen session name (for logs), e.g: gensyn: ").strip()
    config["NODE_NO"] = input("Enter Node No , e.g: 1,2,3: ")
    return config

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return None
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

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
    with open("sent_messages_log.txt", "a") as f:
        f.write(f"{log_time} - Message Sent:\n{message}\n\n")

def get_last_screen_logs(screen_name="gensyn", lines=10):
    try:
        log_path = f"/tmp/{screen_name}_log.txt"
        subprocess.run(f"screen -S {screen_name} -X hardcopy {log_path}", shell=True, check=True)
        with open(log_path, "rb") as f:
            content = f.read().decode("utf-8", errors="ignore")
        return "\n".join(content.strip().split("\n")[-lines:])
    except Exception as e:
        return f"Log fetch error: {str(e)}"

def get_peer_ids_from_eoa(w3, contract, eoa):
    try:
        result = contract.functions.getPeerId([eoa]).call()
        return result[0] if result else []
    except Exception as e:
        print(f"⚠️ Failed to get peer IDs for {eoa}: {e}")
        return []

def fetch_rank_data(telegram_id, peer_ids):
    url = "https://gswarm.dev/api/user/data"
    headers = {"Content-Type": "application/json", "X-Telegram-ID": str(telegram_id)}
    payload = {"peerIds": peer_ids}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=20)
        if r.ok:
            return r.json()
    except Exception as e:
        print(f"⚠️ API error: {e}")
    return None

def format_last_seen(last_seen_str):
    try:
        utc_time = datetime.fromisoformat(last_seen_str)
        ist = pytz.timezone("Asia/Kolkata")
        ist_time = utc_time.astimezone(ist)
        diff = datetime.now(ist) - ist_time
        mins = int(diff.total_seconds() // 60)
        if mins < 60:
            ago = f"{mins}m ago"
        else:
            hrs = mins // 60
            ago = f"{hrs}h ago"
        return ist_time.strftime("%Y-%m-%d %H:%M:%S IST") + f" ({ago})"
    except:
        return last_seen_str

def main():
    create_virtual_env()

    config = load_config()
    if config:
        print("\nConfig file found.\n1 - Use existing config\n2 - Create new config")
        if input("Select option: ").strip() == "2":
            config = get_user_config()
            save_config(config)
    else:
        config = get_user_config()
        save_config(config)

    w3 = Web3(Web3.HTTPProvider(ALCHEMY_RPC))
    contract = w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=ABI)

    while True:
        try:
            peer_ids = get_peer_ids_from_eoa(w3, contract, config["EOA"])
            if not peer_ids:
                raise Exception("No peer IDs found for EOA.")

            data = fetch_rank_data(config["CHAT_ID"], peer_ids)
            if not data:
                raise Exception("No data returned from API.")

            ranks = data.get("ranks", [])
            stats = data.get("stats", {})

            messages = []
            for i, rank in enumerate(ranks, 1):
                msg = (
                    f"<b>Peer {config['NODE_NO']}</b>\n"
                    f"Peer ID: <code>{rank['peerId']}</code>\n"
                    f"EOA: <code>{config['EOA']}</code>\n"
                    f"🏆 Rank: {rank['rank']}\n"
                    f"🎯 Wins: {rank['totalWins']}\n"
                    f"💰 Rewards: {rank['totalRewards']}\n"
                    f"⏰ Last Seen: {format_last_seen(rank['lastSeen'])}\n"
                    f"Stats:\n"
                    f"Total Nodes: {stats.get('totalNodes', 0)}, Ranked Nodes: {stats.get('rankedNodes', 0)}"
                )
                messages.append(msg)

            logs = get_last_screen_logs(config["SCREEN_NAME"])
            full_message = "\n\n".join(messages) + f"\n\n<b>Last Logs:</b>\n<code>{html.escape(logs)}</code>"

            response = send_telegram_message(config["TELEGRAM_API_TOKEN"], config["CHAT_ID"], full_message)
            log_message(full_message)

            if response.ok:
                print(f"✅ Message sent at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                print("❌ Telegram send error:", response.text)

        except Exception as e:
            err = f"⚠️ Error:\n<code>{html.escape(str(e))}</code>"
            send_telegram_message(config["TELEGRAM_API_TOKEN"], config["CHAT_ID"], err)
            log_message(err)

        time.sleep(config["DELAY_SECONDS"])

if __name__ == "__main__":
    main()
