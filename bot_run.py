import os
import subprocess
import sys
from pathlib import Path

VENV_DIR = Path(".venv")
MAIN_SCRIPT = "main.py"
REQUIREMENTS = ["web3", "requests", "pytz"]

def create_venv():
    print("Creating virtual environment...")
    subprocess.check_call([sys.executable, "-m", "venv", str(VENV_DIR)])

def install_packages():
    pip_path = VENV_DIR / "bin" / "pip"
    if os.name == "nt":
        pip_path = VENV_DIR / "Scripts" / "pip.exe"
    subprocess.check_call([str(pip_path), "install"] + REQUIREMENTS)

def run_main_script():
    python_path = VENV_DIR / "bin" / "python"
    if os.name == "nt":
        python_path = VENV_DIR / "Scripts" / "python.exe"
    subprocess.check_call([str(python_path), MAIN_SCRIPT])

# === Run process ===
if not VENV_DIR.exists():
    create_venv()
    install_packages()

run_main_script()
