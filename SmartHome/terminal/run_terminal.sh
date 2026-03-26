SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "Script dir: $SCRIPT_DIR"
cd "$SCRIPT_DIR" || exit 1
./venv/bin/python terminal.py
