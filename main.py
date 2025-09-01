import os
import time
import json
import html
import requests
import subprocess
from web3 import Web3
from datetime import datetime, timedelta, timezone, date

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

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return None

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=4)

def get_user_config():
    print("\n=== Setup Config ===")
    cfg = {}
    cfg["TELEGRAM_API_TOKEN"] = input("Enter Telegram Bot API Token: ").strip()
    cfg["CHAT_ID"] = input("Enter Telegram Chat ID: ").strip()
    cfg["EOA"] = input("Enter your EOA address: ").strip()
    cfg["TELEGRAM_ID"] = input("Enter your Telegram numeric ID: ").strip()
    delay = input("Enter delay in seconds (default 1800 = 30 mins): ").strip()
    cfg["DELAY_SECONDS"] = int(delay) if delay else 1800
    cfg["SCREEN_NAME"] = input("Enter screen session name (optional): ").strip()
    return cfg

def send_telegram_message(token, chat_id, msg):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.ok
    except Exception as e:
        print("Telegram send error:", e)
        return False

def get_last_logs(screen_name, lines=10):
    if not screen_name:
        return "(no screen session configured)"
    try:
        log_path = f"/tmp/{screen_name}_log.txt"
        subprocess.run(f"screen -S {screen_name} -X hardcopy {log_path}", shell=True, check=True)
        with open(log_path, "rb") as f:
            logs = f.read().decode("utf-8", errors="ignore")
        return "\n".join(logs.strip().split("\n")[-lines:])
    except Exception as e:
        return f"Log fetch error: {str(e)}"

def fetch_peer_ids(w3, contract, eoa):
    return contract.functions.getPeerId([eoa]).call()[0]

def fetch_user_data(telegram_id, peer_ids):
    url = "https://gswarm.dev/api/user/data"
    headers = {"Content-Type": "application/json", "X-Telegram-ID": str(telegram_id)}
    body = {"peerIds": peer_ids}
    r = requests.post(url, headers=headers, json=body, timeout=15)
    if r.ok:
        return r.json()
    return None

def format_last_seen(last_seen_str):
    try:
        dt = datetime.fromisoformat(last_seen_str)
        ist = dt.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=5, minutes=30)))
        diff = datetime.now(timezone.utc) - dt
        hours_ago = int(diff.total_seconds() // 3600)
        return f"{ist.strftime('%Y-%m-%d %H:%M:%S IST')} ({hours_ago}h ago)"
    except:
        return last_seen_str

def main():
    # load or setup config
    config = load_config()
    if config:
        print("Config file found.")
        use_existing = input("Use existing config? (y/n): ").strip().lower()
        if use_existing != "y":
            config = get_user_config()
            save_config(config)
    else:
        config = get_user_config()
        save_config(config)

    # web3 contract
    w3 = Web3(Web3.HTTPProvider(ALCHEMY_RPC))
    contract = w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=ABI)

    while True:
        try:
            # fetch peer IDs
            peer_ids = fetch_peer_ids(w3, contract, config["EOA"])
            data = fetch_user_data(config["TELEGRAM_ID"], peer_ids)

            messages = []
            if data and "ranks" in data:
                for r in data["ranks"]:
                    msg = (
                        f"<b>Peer</b>\n"
                        f"Peer ID: <code>{r['peerId']}</code>\n"
                        f"Rank: {r['rank']}\n"
                        f"Wins: {r['totalWins']}\n"
                        f"Rewards: {r['totalRewards']}\n"
                        f"Last Seen: {format_last_seen(r['lastSeen'])}"
                    )
                    messages.append(msg)

            stats_msg = ""
            if data and "stats" in data:
                s = data["stats"]
                stats_msg = f"\n<b>Stats:</b>\nTotal Nodes: {s['totalNodes']}, Ranked Nodes: {s['rankedNodes']}"

            logs = get_last_logs(config["SCREEN_NAME"])
            full_message = "\n\n".join(messages) + stats_msg + f"\n\n<b>Last Logs:</b>\n<code>{html.escape(logs)}</code>"

            ok = send_telegram_message(config["TELEGRAM_API_TOKEN"], config["CHAT_ID"], full_message)
            print(f"[{datetime.now()}] Sent: {ok}")

        except Exception as e:
            err = f"⚠️ Error: {html.escape(str(e))}"
            send_telegram_message(config["TELEGRAM_API_TOKEN"], config["CHAT_ID"], err)
            print("Error:", e)

        time.sleep(config["DELAY_SECONDS"])

if __name__ == "__main__":
    main()
