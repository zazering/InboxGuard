#!/usr/bin/env bash
# InboxGuard — setup.sh
# Run once after cloning:  bash setup.sh
set -euo pipefail

CYAN='\033[0;36m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
RED='\033[0;31m';  BOLD='\033[1m';     NC='\033[0m'

banner() {
echo -e "${CYAN}${BOLD}"
cat << 'ART'
  ___      _              ____                     _ 
 |_ _|_ _ | |__  _____ _/ ___|_   _  __ _ _ __ __| |
  | || ' \| '_ \/ _ \ \ \___ \ | | |/ _` | '__/ _` |
  | || || | |_) | (_) > |___) || |_| | (_| | | | (_| |
 |___|_||_|_.__/ \___/_\|____/ \__,_|\__,_|_|  \__,_|
ART
echo -e "  Local AI Email Triage Agent${NC}"
echo ""
}

step() { echo -e "${CYAN}▶  $1${NC}"; }
ok()   { echo -e "${GREEN}✓  $1${NC}"; }
warn() { echo -e "${YELLOW}⚠  $1${NC}"; }
die()  { echo -e "${RED}✗  $1${NC}"; exit 1; }

banner

# ── Pre-flight checks ────────────────────────────────────────────────────────
step "Checking prerequisites…"

command -v python3 >/dev/null 2>&1 || die "python3 not found. Install with: sudo apt install python3"
command -v pip3    >/dev/null 2>&1 || die "pip3 not found.   Install with: sudo apt install python3-pip"
command -v ollama  >/dev/null 2>&1 || die "Ollama not found.\n   Install with: curl -fsSL https://ollama.com/install.sh | sh"
command -v git     >/dev/null 2>&1 || warn "git not found — optional, needed only for GitHub"

PYTHON_VER=$(python3 -c 'import sys; print(sys.version_info[:2] >= (3,9))')
[[ "$PYTHON_VER" == "True" ]] || die "Python 3.9+ required."

ok "Prerequisites OK"

# ── Directories ──────────────────────────────────────────────────────────────
step "Creating directories…"
mkdir -p ~/.config/inboxguard
mkdir -p ~/.local/share/inboxguard
mkdir -p ~/.config/systemd/user
ok "Directories ready"

# ── Config ───────────────────────────────────────────────────────────────────
if [ ! -f ~/.config/inboxguard/config.yaml ]; then
  step "Installing example config…"
  cp config.example.yaml ~/.config/inboxguard/config.yaml
  warn "Config created at ~/.config/inboxguard/config.yaml"
  warn "Edit it with your email credentials BEFORE starting InboxGuard!"
else
  ok "Config already exists at ~/.config/inboxguard/config.yaml"
fi

# ── Python venv ──────────────────────────────────────────────────────────────
step "Setting up Python virtual environment…"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
ok "Python dependencies installed"

# ── Systemd service ──────────────────────────────────────────────────────────
step "Installing systemd user service…"
INSTALL_DIR="$(pwd)"
sed "s|INSTALL_DIR|${INSTALL_DIR}|g" systemd/inboxguard.service \
  > ~/.config/systemd/user/inboxguard.service
systemctl --user daemon-reload
ok "Systemd service installed (~/.config/systemd/user/inboxguard.service)"

# ── Pull LLM model if missing ────────────────────────────────────────────────
MODEL=$(python3 -c "
import yaml, pathlib
cfg = yaml.safe_load(pathlib.Path('~/.config/inboxguard/config.yaml').expanduser().read_text())
print(cfg.get('llm',{}).get('model','qwen2.5:3b'))
" 2>/dev/null || echo "qwen2.5:3b")

if ollama list 2>/dev/null | grep -q "${MODEL%%:*}"; then
  ok "Model '$MODEL' already downloaded"
else
  step "Pulling model '$MODEL' (this may take a few minutes)…"
  ollama pull "$MODEL"
  ok "Model '$MODEL' ready"
fi

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}🎉  Setup complete!${NC}"
echo ""
echo "  Next steps:"
echo -e "  1.  ${YELLOW}nano ~/.config/inboxguard/config.yaml${NC}   ← add email credentials"
echo -e "  2.  ${YELLOW}systemctl --user enable --now inboxguard${NC} ← start background service"
echo -e "  3.  ${YELLOW}xdg-open http://localhost:5000${NC}           ← open dashboard"
echo ""
echo "  Useful commands:"
echo "    journalctl --user -u inboxguard -f      # live logs"
echo "    systemctl --user restart inboxguard     # restart"
echo "    systemctl --user stop inboxguard        # stop"
echo "    source .venv/bin/activate && python main.py --once   # manual test run"
echo ""
