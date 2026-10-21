"""Bounded prompt-context compilation without deleting persisted conversations.

Token estimates are deliberately conservative heuristics; the provider remains the
authority on its actual tokenizer and context window.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping


class SlidingContextManager:
    """Compile recent conversation turns under a configurable approximate budget."""

    def __init__(
        self,
        max_token_ceiling: int = 8192,
        reserved_system_tokens: int = 2048,
        max_turns: int = 20,
    ) -> None:
        if not isinstance(max_token_ceiling, int) or max_token_ceiling < 256:
            raise ValueError("max_token_ceiling must be an integer >= 256")
        if not isinstance(reserved_system_tokens, int) or not 0 <= reserved_system_tokens < max_token_ceiling:
            raise ValueError("reserved_system_tokens must be smaller than the token ceiling")
        if not isinstance(max_turns, int) or max_turns < 1:
            raise ValueError("max_turns must be a positive integer")
        self.max_tokens = max_token_ceiling
        self.reserved = reserved_system_tokens
        self.max_turns = max_turns
        self.allowed_history_tokens = max_token_ceiling - reserved_system_tokens

    @staticmethod
    def estimate_tokens(text: str) -> int:
        # Character-based estimates are less misleading than word counts for code,
        # URLs, and punctuation-heavy text. Four characters/token is only a heuristic.
        return max(1, (len(text) + 3) // 4) if text else 0

    @staticmethod
    def _normalize(item: Mapping) -> str:
        user = str(item.get("user", ""))
        assistant = str(item.get("assistant", ""))
        return f"User: {user}\nNexus: {assistant}"

    def compile_history(self, history: Iterable[Mapping]) -> str:
        turns = [item for item in history if isinstance(item, Mapping)][-self.max_turns:]
        if not turns:
            return "No persisted conversation context is loaded."

        selected: list[str] = []
        used_tokens = 0
        budget = self.allowed_history_tokens
        for item in reversed(turns):
            rendered = self._normalize(item)
            cost = self.estimate_tokens(rendered)
            if used_tokens + cost <= budget:
                selected.append(rendered)
                used_tokens += cost
                continue
            # Keep the newest turn even if it alone exceeds the budget. Preserve
            # its tail, which is generally the most recent part of the exchange.
            if not selected and budget > 0:
                max_chars = budget * 4
                selected.append(rendered[-max_chars:])
            break

        selected.reverse()
        return "\n\n".join(selected) if selected else "No persisted conversation context is loaded."
