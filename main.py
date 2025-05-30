import os
import time
import json
import html
import requests
import subprocess
from web3 import Web3
from datetime import datetime, date

CONFIG_FILE = "config.json"
EOA_CACHE_FILE = "eoa_cache.json"
VENV_DIR = ".venv"

# Constants
ALCHEMY_RPC = "https://gensyn-testnet.g.alchemy.com/v2/TD5tr7mo4VfXlSaolFlSr3tL70br2M9J"
CONTRACT_ADDRESS = "0x69C6e1D608ec64885E7b185d39b04B491a71768C"

ABI = [
    {
        "name": "getEoa",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "peerIds", "type": "string[]"}],
        "outputs": [{"name": "", "type": "address[]"}]
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
    config["DELAY_SECONDS"] = int(input("Enter delay in seconds (e.g., 1800 for 30 mins): ").strip())
    words = input("Enter Peer Names (comma-separated, e.g., sly loud alpaca, blue fast tiger): ").strip().split(",")
    config["PEER_NAMES"] = [w.strip() for w in words]
    config["SCREEN_NAME"] = input("Enter screen session name, e.g: gensyn: ").strip()
    config["NODE_NO"] = int(input("Enter Node No , e.g: 1,2,3: "))
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

def fetch_peer_data(peer_name):
    url_name = peer_name.replace(" ", "%20")
    url = f"https://dashboard-math.gensyn.ai/api/v1/peer?name={url_name}"
    try:
        response = requests.get(url)
        if response.ok:
            return response.json()
    except:
        pass
    return None

def fetch_eoa_mapping(w3, contract, peer_ids):
    today = str(date.today())
    if os.path.exists(EOA_CACHE_FILE):
        with open(EOA_CACHE_FILE) as f:
            data = json.load(f)
            if data.get("date") == today:
                return data.get("mapping", {})

    addresses = contract.functions.getEoa(peer_ids).call()
    mapping = {pid: eoa for pid, eoa in zip(peer_ids, addresses)}
    with open(EOA_CACHE_FILE, "w") as f:
        json.dump({"date": today, "mapping": mapping}, f, indent=4)
    return mapping

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
            messages = []
            peer_infos = []
            peer_ids = []

            for name in config["PEER_NAMES"]:
                data = fetch_peer_data(name)
                if data:
                    peer_infos.append((name, data))
                    peer_ids.append(data["peerId"])

            eoa_map = fetch_eoa_mapping(w3, contract, peer_ids)

            for i, (name, info) in enumerate(peer_infos):
                peer_id = info["peerId"]
                eoa = eoa_map.get(peer_id, "N/A")
                explorer_link = f"https://gensyn-testnet.explorer.alchemy.com/address/{eoa}?tab=internal_txns"
                status = "🟢 Online" if info["online"] else "🔴 Offline"

                msg = (
                    f"<b>Peer {NODE_NO}</b>\n"
                    f"Name: <code>{name}</code>\n"
                    f"Peer ID: <code>{peer_id}</code>\n"
                    f"EOA: <code>{eoa}</code>\n"
                    f"Total Reward: {info['reward']}\n"
                    f"Total Wins: {info['score']}\n"
                    f"Status: {status}\n"
                    f'<a href="{explorer_link}">View on Explorer</a>'
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
