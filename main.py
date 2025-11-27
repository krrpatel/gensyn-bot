import os
import time
import json
import html
import requests
import subprocess
from datetime import datetime, timedelta
import pytz

CONFIG_FILE = "config.json"
VENV_DIR = ".venv"

# Gensyn Testnet Constants
CONTRACT_ADDRESS = "0x7745a8FE4b8D2D2c3BB103F8dCae822746F35Da0"
SUPABASE_ENDPOINT = "https://axkgbsksejmkngaajrbo.supabase.co/functions/v1/query-peer"


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
    print("\n=== Telegram + Tracker Setup ===")
    config = {}
    config["TELEGRAM_API_TOKEN"] = input("Enter Telegram Bot API Token: ").strip()
    config["CHAT_ID"] = input("Enter Telegram Chat ID: ").strip()
    config["DELAY_SECONDS"] = int(input("Enter delay in seconds (e.g., 1800 for 30 mins): ").strip())
    print("\nGet your API key from: https://gensyntracker.vercel.app/api")
    config["API_KEY"] = input("Enter Gensyn Tracker API Key: ").strip()
    config["PEER_ID"] = input("Enter your Peer ID: ").strip()
    config["SCREEN_NAME"] = input("Enter screen session name (for logs), e.g: gensyn: ").strip()
    config["NODE_NO"] = input("Enter Node No , e.g: 1,2,3: ").strip()
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


def fetch_peer_data(api_key: str, peer_id: str, contract_address: str):
    """
    Calls the Supabase edge function:

    curl -X POST 'https://axkgbsksejmkngaajrbo.supabase.co/functions/v1/query-peer' \
      -H 'Content-Type: application/json' \
      -H 'Authorization: Bearer YOUR_API_KEY' \
      -d '{"peerId": "your-peer-id-here", "contractAddress": "0x..."}'
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "peerId": peer_id,
        "contractAddress": contract_address,
    }
    try:
        r = requests.post(SUPABASE_ENDPOINT, headers=headers, json=payload, timeout=20)
        if r.ok:
            return r.json()
        else:
            print(f"⚠️ API error: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"⚠️ API request failed: {e}")
    return None


def format_last_seen(last_seen_str):
    try:
        # Example: "2025-01-15T10:30:00Z"
        if last_seen_str.endswith("Z"):
            last_seen_str = last_seen_str.replace("Z", "+00:00")
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
    except Exception:
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

    while True:
        try:
            data = fetch_peer_data(config["API_KEY"], config["PEER_ID"], CONTRACT_ADDRESS)
            if not data:
                raise Exception("No data returned from tracker API.")

            # Example response:
            # {
            #   "peerId": "example-peer-id",
            #   "eoa": "0x1234...",
            #   "rewards": 1500000,
            #   "wins": 42,
            #   "votes": 128,
            #   "registered": true,
            #   "lastCheckedAt": "2025-01-15T10:30:00Z"
            # }

            peer_id = data.get("peerId", config["PEER_ID"])
            eoa = data.get("eoa", "N/A")
            rewards = data.get("rewards", 0)
            wins = data.get("wins", 0)
            votes = data.get("votes", 0)
            registered = data.get("registered", False)
            last_checked = data.get("lastCheckedAt", "")

            msg = (
                f"<b>Peer {config['NODE_NO']}</b>\n"
                f"Peer ID: <code>{peer_id}</code>\n"
                f"EOA: <code>{eoa}</code>\n"
                f"🎯 Wins: {wins}\n"
                f"💰 Rewards: {rewards}\n"
                f"🗳️ Votes: {votes}\n"
                f"📋 Registered: {'✅ Yes' if registered else '❌ No'}\n"
            )

            if last_checked:
                msg += f"⏰ Last Checked: {format_last_seen(last_checked)}\n"

            logs = get_last_screen_logs(config["SCREEN_NAME"])
            full_message = msg + f"\n<b>Last Logs:</b>\n<code>{html.escape(logs)}</code>"

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
