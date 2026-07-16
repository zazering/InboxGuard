# 🛡️ InboxGuard

**A local AI email triage agent for Linux.** Runs entirely on your machine — no cloud, no subscriptions, no data leaving your PC.

InboxGuard connects to your inbox via IMAP, uses a small local LLM (via [Ollama](https://ollama.com)) to decide what matters, sends desktop notifications, and shows everything in a clean web dashboard.

---

## What it does

For every new email, InboxGuard decides:

| Decision | Meaning |
|----------|---------|
| 🔴 **Read** | You need to read this personally — it requires action |
| 📋 **Summary** | Informational only — here's a one-line summary |
| 🗑️ **Ignore** | Marketing/spam/automated — safely skipped, no notification |

Rules you define in `config.yaml` always override the LLM. The LLM only runs when no rule matches.

---

## Screenshots

Dashboard at `http://localhost:5000`:

```
🛡️ InboxGuard                                    ● Running   Updated 14:32:01

  [ 47 Total ]  [ 12 To Read ]  [ 29 Summary ]  [ 6 Ignored ]

  [All] [🔴 Read] [📋 Summary] [🗑️ Ignored]             [↻ Refresh]

  🔴 READ ▲ HIGH  Meeting tomorrow re: Q3 budget
           From: boss@company.com
           Your manager wants to confirm the meeting agenda for tomorrow at 9am.
           💡 Rule 'always_read' matched sender

  📋 SUMMARY  GitHub: New PR opened on inboxguard
           From: notifications@github.com
           A new pull request has been opened requesting changes to the config...
```

---

## Hardware

Built and tested on **Intel i7 11370H + RTX 3060 6 GB + 16 GB RAM**.

| Component | Minimum | Good |
|-----------|---------|------|
| CPU | Any x86_64 | i5 8th gen+ |
| RAM | 8 GB | 16 GB |
| GPU VRAM | — (CPU fallback) | 4–8 GB |
| Disk | 3 GB free | 5 GB+ |

---

## Quick Start

### 1. Install system dependencies

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv libnotify-bin git curl
```

### 2. Install Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
# Start it (or it auto-starts as a service):
ollama serve &
```

### 3. Clone and set up InboxGuard

```bash
git clone https://github.com/yourusername/inboxguard.git
cd inboxguard
bash setup.sh
```

`setup.sh` will:
- Create `~/.config/inboxguard/config.yaml` from the example
- Set up the Python virtual environment
- Pull the LLM model
- Install the systemd user service

### 4. Configure

```bash
nano ~/.config/inboxguard/config.yaml
```

Fill in at minimum:
```yaml
email:
  imap_server: imap.gmail.com
  username:    you@gmail.com
  password:    xxxx-xxxx-xxxx-xxxx   # Gmail App Password
```

> **Gmail users:** go to Google Account → Security → 2-Step Verification → App Passwords and generate one for "Mail".

### 5. Start it

```bash
# As a background service (recommended):
systemctl --user enable --now inboxguard

# Or run once for testing:
source .venv/bin/activate
python main.py --once
```

### 6. Open the dashboard

```
http://localhost:5000
```

---

## Configuration guide

```yaml
email:
  imap_server: imap.gmail.com
  imap_port:   993
  username:    you@gmail.com
  password:    your-app-password
  check_interval: 300          # Check every 5 minutes
  max_fetch_per_cycle: 25      # Max emails per check

llm:
  model: qwen2.5:3b            # Recommended for 6 GB VRAM
  ollama_url: http://localhost:11434
  timeout: 45

rules:
  always_read:                 # Override: always flag as "read"
    - from_contains:
        - boss@company.com
    - subject_contains:
        - "URGENT"

  summary_only:                # Override: always give just a summary
    - from_contains:
        - noreply@
        - github.com

  ignore:                      # Override: silently discard
    - subject_contains:
        - "50% off"
```

### Model options (by VRAM usage)

| Model | VRAM | Speed | Quality |
|-------|------|-------|---------|
| `gemma2:2b` | ~1.5 GB | ⚡⚡⚡ | Good |
| `qwen2.5:3b` | ~2 GB | ⚡⚡ | **Best** ← recommended |
| `phi3.5:mini` | ~2.5 GB | ⚡⚡ | Great |
| `mistral:7b` | ~5 GB | ⚡ | Excellent |

---

## Useful commands

```bash
# Live logs
journalctl --user -u inboxguard -f

# Restart after config change
systemctl --user restart inboxguard

# Stop
systemctl --user stop inboxguard

# Manual single run (debug)
source .venv/bin/activate
python main.py --once

# Disable background service
systemctl --user disable --now inboxguard
```

---

## Supported email providers

| Provider | IMAP Server | Port |
|----------|-------------|------|
| Gmail | `imap.gmail.com` | 993 |
| Outlook / Hotmail | `outlook.office365.com` | 993 |
| Yahoo | `imap.mail.yahoo.com` | 993 |
| ProtonMail (Bridge) | `127.0.0.1` | 1143 |
| Any IMAP provider | your server | 993 |

---

## Project structure

```
inboxguard/
├── main.py                  # Entry point & main loop
├── requirements.txt
├── config.example.yaml      # Template config (copy to ~/.config/inboxguard/)
├── setup.sh                 # One-command setup
├── src/
│   ├── config.py            # Config loader (YAML + env vars)
│   ├── database.py          # SQLite persistence
│   ├── email_fetcher.py     # IMAP email fetching
│   ├── llm_client.py        # Ollama API client
│   ├── triage.py            # Rule engine + LLM triage logic
│   └── notifier.py          # Desktop notifications (notify-send)
├── web/
│   ├── app.py               # Flask dashboard
│   └── templates/index.html # Dashboard UI
└── systemd/
    └── inboxguard.service   # Systemd user service template
```

---

## Privacy

- All LLM inference runs locally via Ollama
- Email credentials stored only in `~/.config/inboxguard/config.yaml` (never committed — see `.gitignore`)
- Email bodies are processed in memory and only a short snippet is stored in the local SQLite database
- No analytics, no telemetry, no network calls except to your IMAP server and local Ollama

---

## License

MIT — do whatever you want with it.
