import os
import time
import json
import html
import requests
import subprocess
from web3 import Web3
from datetime import datetime, date, timezone, timedelta

CONFIG_FILE = "config.json"
VENV_DIR = ".venv"

# Constants
ALCHEMY_RPC = "https://gensyn-testnet.g.alchemy.com/v2/TD5tr7mo4VfXlSaolFlSr3tL70br2M9J"
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
    time.sleep(3)

def get_user_config():
    print("\n=== Telegram Setup ===")
    config = {}
    config["TELEGRAM_API_TOKEN"] = input("Enter Telegram Bot API Token: ").strip()
    config["CHAT_ID"] = input("Enter Telegram Chat ID: ").strip()
    config["SCREEN_NAME"] = input("Enter screen session name, e.g: gensyn: ").strip()
    config["NODE_NO"] = input("Enter Node No , e.g: 1,2,3: ")
    config["TELEGRAM_ID"] = input("Enter Telegram ID linked to gensyn: ").strip()
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

def get_time_ago(utc_str):
    dt_utc = datetime.fromisoformat(utc_str)
    dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    dt_ist = dt_utc.astimezone(timezone(timedelta(hours=5, minutes=30)))
    ago = datetime.now(timezone.utc) - dt_utc
    hours = int(ago.total_seconds() // 3600)
    mins = int((ago.total_seconds() % 3600) // 60)
    ago_str = f"{hours}h {mins}m ago" if hours else f"{mins}m ago"
    return dt_ist.strftime("%Y-%m-%d %H:%M:%S IST") + f" ({ago_str})"

def get_last_screen_logs(screen_name="gensyn", lines=10):
    try:
        log_path = f"/tmp/{screen_name}_log.txt"
        subprocess.run(f"screen -S {screen_name} -X hardcopy {log_path}", shell=True, check=True)
        with open(log_path, "rb") as f:
            content = f.read().decode("utf-8", errors="ignore")
        return "\n".join(content.strip().split("\n")[-lines:])
    except Exception as e:
        return f"Log fetch error: {str(e)}"

def get_peer_ids_from_eoa(eoa):
    w3 = Web3(Web3.HTTPProvider(ALCHEMY_RPC))
    contract = w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=ABI)
    peer_ids_nested = contract.functions.getPeerId([eoa]).call()
    return peer_ids_nested[0] if peer_ids_nested else []

def fetch_user_data(telegram_id, peer_ids):
    url = "https://gswarm.dev/api/user/data"
    headers = {
        "Content-Type": "application/json",
        "X-Telegram-ID": str(telegram_id),
    }
    resp = requests.post(url, headers=headers, json={"peerIds": peer_ids})
    if resp.ok:
        return resp.json()
    return None

def main():
    create_virtual_env()
    config = load_config()
    if not config:
        config = get_user_config()
        save_config(config)

    eoa = input("Enter EOA address: ").strip()
    peer_ids = get_peer_ids_from_eoa(eoa)
    print(f"Found Peer IDs: {peer_ids}")

    user_data = fetch_user_data(config["TELEGRAM_ID"], peer_ids)
    if not user_data:
        print("⚠️ Could not fetch user data")
        return

    messages = []
    for r in user_data.get("ranks", []):
        last_seen = get_time_ago(r["lastSeen"])
        msg = (
            f"<b>Peer {config['NODE_NO']}</b>\n"
            f"Peer ID: <code>{r['peerId']}</code>\n"
            f"EOA: <code>{eoa}</code>\n"
            f"🏆 Rank: {r['rank']}\n"
            f"🎯 Wins: {r['totalWins']}\n"
            f"💰 Rewards: {r['totalRewards']}\n"
            f"⏰ Last Seen: {last_seen}"
        )
        messages.append(msg)

    stats = user_data.get("stats", {})
    stats_msg = f"\n<b>Stats:</b>\nTotal Nodes: {stats.get('totalNodes')}, Ranked Nodes: {stats.get('rankedNodes')}"

    logs = get_last_screen_logs(config["SCREEN_NAME"])
    full_message = "\n\n".join(messages) + stats_msg + f"\n\n<b>Last Logs:</b>\n<code>{html.escape(logs)}</code>"

    response = send_telegram_message(config["TELEGRAM_API_TOKEN"], config["CHAT_ID"], full_message)
    if response.ok:
        print("✅ Telegram message sent!")
    else:
        print("❌ Telegram error:", response.text)

if __name__ == "__main__":
    main()
