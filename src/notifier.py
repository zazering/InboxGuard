"""Desktop notifications via notify-send (libnotify)."""

import logging
import subprocess
from typing import Dict

logger = logging.getLogger(__name__)

_ICONS = {
    "read":    "mail-unread-symbolic",
    "summary": "mail-read-symbolic",
}
_URGENCY = {
    "high":   "critical",
    "normal": "normal",
    "low":    "low",
}
_EMOJI = {
    "read":    "🔴",
    "summary": "📋",
}


class Notifier:
    def __init__(self, config):
        self.enabled = config.get("notifications.enabled", True)
        self.show_summary = config.get("notifications.summary_in_notification", True)

    def notify(self, email: Dict, result: Dict):
        if not self.enabled:
            return

        action   = result.get("action", "summary")
        priority = result.get("priority", "normal")

        if action == "ignore":
            return  # Never notify for ignored mail

        emoji   = _EMOJI.get(action, "📧")
        urgency = _URGENCY.get(priority, "normal")
        icon    = _ICONS.get(action, "mail-message-new")

        title = f"InboxGuard {emoji} — {action.upper()}"
        if priority == "high":
            title += " [HIGH PRIORITY]"

        sender  = email.get("sender",  "Unknown")[:50]
        subject = email.get("subject", "(no subject)")[:70]
        summary = result.get("summary", "")[:120]

        body_parts = [f"From:  {sender}", f"       {subject}"]
        if self.show_summary and summary:
            body_parts.append(f"\n{summary}")

        body = "\n".join(body_parts)

        try:
            subprocess.run(
                [
                    "notify-send",
                    "--app-name",    "InboxGuard",
                    "--urgency",     urgency,
                    "--icon",        icon,
                    "--expire-time", "9000",
                    title,
                    body,
                ],
                check=False,
                timeout=5,
            )
        except FileNotFoundError:
            logger.warning(
                "notify-send not found — install it with:  "
                "sudo apt install libnotify-bin"
            )
        except Exception as e:
            logger.warning(f"Notification failed: {e}")
