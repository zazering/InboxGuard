"""Fetches unseen emails from any IMAP mailbox."""

import email
import email.header
import email.message
import imaplib
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class EmailFetcher:
    def __init__(self, config):
        self.server   = config.get("email.imap_server", "imap.gmail.com")
        self.port     = config.get("email.imap_port", 993)
        self.username = config.get("email.username", "")
        self.password = config.get("email.password", "")
        self.folder   = config.get("email.folder", "INBOX")
        self.max_per_cycle = config.get("email.max_fetch_per_cycle", 20)

    # ── Connection ─────────────────────────────────────────────────────────

    def _connect(self) -> imaplib.IMAP4_SSL:
        mail = imaplib.IMAP4_SSL(self.server, self.port)
        mail.login(self.username, self.password)
        return mail

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _decode(raw) -> str:
        if raw is None:
            return ""
        parts = email.header.decode_header(str(raw))
        result = []
        for chunk, enc in parts:
            if isinstance(chunk, bytes):
                result.append(chunk.decode(enc or "utf-8", errors="replace"))
            else:
                result.append(str(chunk))
        return " ".join(result).strip()

    @staticmethod
    def _get_body(msg: email.message.Message, max_chars: int = 3000) -> str:
        """Extract plain-text body; falls back to HTML stripped of tags."""
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                ct = part.get_content_type()
                if ct == "text/plain":
                    try:
                        body = part.get_payload(decode=True).decode(
                            part.get_content_charset() or "utf-8", errors="replace"
                        )
                        break
                    except Exception:
                        pass
        else:
            try:
                body = msg.get_payload(decode=True).decode(
                    msg.get_content_charset() or "utf-8", errors="replace"
                )
            except Exception:
                body = str(msg.get_payload())

        return body[:max_chars]

    # ── Public API ─────────────────────────────────────────────────────────

    def fetch_new_emails(self) -> List[Dict]:
        emails: List[Dict] = []
        try:
            mail = self._connect()
            mail.select(self.folder, readonly=True)

            _, data = mail.search(None, "UNSEEN")
            uids: List[bytes] = data[0].split() if data[0] else []

            # Only process the most recent N unseen mails
            uids = uids[-self.max_per_cycle:]
            logger.debug(f"Found {len(uids)} unseen email(s) to check.")

            for uid in uids:
                try:
                    _, msg_data = mail.fetch(uid, "(RFC822)")
                    raw = msg_data[0][1]
                    msg = email.message_from_bytes(raw)

                    message_id = self._decode(msg.get("Message-ID")) or f"uid-{uid.decode()}"
                    sender  = self._decode(msg.get("From"))
                    subject = self._decode(msg.get("Subject")) or "(no subject)"
                    date    = self._decode(msg.get("Date"))
                    body    = self._get_body(msg)

                    emails.append({
                        "message_id": message_id.strip("<> "),
                        "sender":     sender,
                        "subject":    subject,
                        "date":       date,
                        "body":       body,
                        "snippet":    body[:200],
                    })
                except Exception as e:
                    logger.warning(f"Failed to parse email uid={uid}: {e}")

            mail.logout()

        except imaplib.IMAP4.error as e:
            logger.error(f"IMAP error: {e}")
        except ConnectionError as e:
            logger.error(f"Connection error: {e}")
        except Exception as e:
            logger.error(f"Unexpected fetch error: {e}", exc_info=True)

        return emails
