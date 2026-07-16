#!/usr/bin/env python3
"""InboxGuard — Local AI Email Triage Agent"""

import time
import logging
import signal
import sys
import threading
import argparse
from pathlib import Path

from src.config import Config
from src.database import Database
from src.email_fetcher import EmailFetcher
from src.triage import EmailTriage
from src.notifier import Notifier

def setup_logging(level: str):
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

logger = logging.getLogger("inboxguard")
running = True


def signal_handler(sig, frame):
    global running
    logger.info("Shutdown signal received — stopping InboxGuard…")
    running = False


def main():
    global running

    parser = argparse.ArgumentParser(description="InboxGuard — Local AI Email Triage")
    parser.add_argument("--config", help="Path to config.yaml", default=None)
    parser.add_argument("--once", action="store_true", help="Run one check then exit")
    parser.add_argument("--no-web", action="store_true", help="Disable web UI")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        config = Config(args.config)
    except FileNotFoundError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    setup_logging(config.get("logging.level", "INFO"))

    db = Database(config)
    fetcher = EmailFetcher(config)
    triage = EmailTriage(config)
    notifier = Notifier(config)

    # ── Web UI ─────────────────────────────────────────────────────────────
    if config.get("web_ui.enabled", True) and not args.no_web:
        from web.app import create_app
        app = create_app(config, db)
        host = config.get("web_ui.host", "127.0.0.1")
        port = config.get("web_ui.port", 5000)

        web_thread = threading.Thread(
            target=lambda: app.run(host=host, port=port, debug=False, use_reloader=False),
            daemon=True,
            name="web-ui",
        )
        web_thread.start()
        logger.info(f"Web dashboard → http://{host}:{port}")

    logger.info("InboxGuard started. Monitoring your inbox…")

    # ── Main loop ──────────────────────────────────────────────────────────
    while running:
        try:
            emails = fetcher.fetch_new_emails()
            new_count = 0

            for email in emails:
                if db.is_processed(email["message_id"]):
                    continue

                result = triage.process(email)
                db.save_result(email, result)

                action = result["action"]
                priority = result.get("priority", "normal")

                if action != "ignore":
                    notifier.notify(email, result)

                icon = {"read": "🔴", "summary": "📋", "ignore": "🗑️"}.get(action, "📧")
                prio_tag = f" [{priority.upper()}]" if priority == "high" else ""
                logger.info(f"{icon} {action.upper()}{prio_tag} — {email['subject'][:70]}")
                new_count += 1

            if new_count:
                logger.info(f"Processed {new_count} new email(s).")
            else:
                logger.debug("No new emails.")

        except Exception as e:
            logger.error(f"Error in main loop: {e}", exc_info=True)

        if args.once:
            break

        interval = config.get("email.check_interval", 300)
        logger.debug(f"Sleeping {interval}s until next check…")
        for _ in range(interval):
            if not running:
                break
            time.sleep(1)

    logger.info("InboxGuard stopped cleanly.")


if __name__ == "__main__":
    main()
