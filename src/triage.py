"""
Email Triage Engine
===================
Decision pipeline:
  1. Check hard rules from config.yaml  →  instant decision, no LLM call
  2. Ask local LLM (Ollama)             →  JSON result
  3. Fallback if LLM fails              →  "summary" / normal priority
"""

import json
import logging
import re
from typing import Dict, Optional

from .llm_client import LLMClient

logger = logging.getLogger(__name__)

# ── Prompt ────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are InboxGuard, an email triage assistant.
Read the email below and respond ONLY with a valid JSON object — no markdown, no preamble.

Required format:
{
  "action":   "read" | "summary" | "ignore",
  "priority": "high" | "normal" | "low",
  "summary":  "<one sentence summarising the email>",
  "reason":   "<brief reason for your decision>"
}

Action meanings:
  read    — User must read this personally (requires action, time-sensitive, from a real person)
  summary — Informational only; provide a summary but no action needed
  ignore  — Automated, marketing, spam, or irrelevant; can be safely skipped

Be conservative: when unsure between read and summary, choose read.
Respond with ONLY the JSON object.
"""

# ── Defaults ──────────────────────────────────────────────────────────────

FALLBACK_RESULT: Dict = {
    "action":   "summary",
    "priority": "normal",
    "summary":  "Could not analyse this email (LLM unavailable).",
    "reason":   "LLM fallback",
}


class EmailTriage:
    def __init__(self, config):
        self.config = config
        self.llm    = LLMClient(config)
        self.rules  = config.get("rules") or {}

    # ── Rule engine ───────────────────────────────────────────────────────

    def _match_rule(self, email: Dict, rule: dict, field: str) -> bool:
        value = email.get(field, "").lower()
        for pattern in rule.get(f"{field}_contains", []):
            if pattern.lower() in value:
                return True
        return False

    _ACTION_MAP = {
        "always_read":  ("read",    "high"),
        "summary_only": ("summary", "low"),
        "ignore":       ("ignore",  "low"),
    }

    def _check_rules(self, email: Dict) -> Optional[Dict]:
        for rule_key, (action, priority) in self._ACTION_MAP.items():
            for rule in self.rules.get(rule_key, []):
                for field in ("sender", "subject"):
                    if self._match_rule(email, rule, field):
                        matched = rule.get(f"{field}_contains", [])
                        pattern = next((p for p in matched if p.lower() in email.get(field, "").lower()), "")
                        return {
                            "action":   action,
                            "priority": priority,
                            "summary":  f"{email['subject'][:80]}",
                            "reason":   f"Rule '{rule_key}' matched {field}: '{pattern}'",
                        }
        return None

    # ── LLM parsing ───────────────────────────────────────────────────────

    def _parse_llm(self, raw: str) -> Optional[Dict]:
        # Direct parse
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # Extract JSON object from messy output
        match = re.search(r"\{[^{}]*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        # Last resort: keyword sniff
        lower = raw.lower()
        if any(w in lower for w in ("ignore", "spam", "marketing", "automated", "skip")):
            return {"action": "ignore", "priority": "low",
                    "summary": "Automated/marketing content", "reason": raw[:120]}
        if any(w in lower for w in ("urgent", "action required", "important", "reply")):
            return {"action": "read", "priority": "high",
                    "summary": "Appears important", "reason": raw[:120]}
        return None

    # ── Validation ────────────────────────────────────────────────────────

    @staticmethod
    def _validate(result: Dict) -> Dict:
        valid_actions   = {"read", "summary", "ignore"}
        valid_priority  = {"high", "normal", "low"}
        if result.get("action") not in valid_actions:
            result["action"] = "summary"
        if result.get("priority") not in valid_priority:
            result["priority"] = "normal"
        result.setdefault("summary", "")
        result.setdefault("reason", "")
        return result

    # ── Public API ────────────────────────────────────────────────────────

    def process(self, email: Dict) -> Dict:
        # 1 — Hard rules (fast, no LLM cost)
        rule_result = self._check_rules(email)
        if rule_result:
            logger.debug(f"Rule hit: {rule_result['action']} — {email['subject'][:50]}")
            return self._validate(rule_result)

        # 2 — LLM
        prompt = (
            f"From:    {email.get('sender', '')}\n"
            f"Subject: {email.get('subject', '')}\n"
            f"Date:    {email.get('date', '')}\n\n"
            f"--- Email body (first 1500 chars) ---\n"
            f"{email.get('body', '')[:1500]}"
        )

        raw = self.llm.generate(prompt, system=SYSTEM_PROMPT)

        if raw is None:
            # LLM unavailable — safe fallback
            fallback = dict(FALLBACK_RESULT)
            fallback["summary"] = f"{email.get('subject', '')} — from {email.get('sender', '')}"
            return fallback

        parsed = self._parse_llm(raw)
        if parsed is None:
            logger.warning(f"Could not parse LLM response: {raw[:200]}")
            return dict(FALLBACK_RESULT)

        return self._validate(parsed)
