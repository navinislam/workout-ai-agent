from __future__ import annotations

"""
Thin OpenAI client wrapper.

Usage:
- Set OPENAI_API_KEY in env.
- Configure model via OPENAI_CHAT_MODEL (default: gpt-4o-mini) and OPENAI_JSON_MODEL (for strict JSON, optional).
"""

import json
import os
from typing import Optional

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - openai may not be installed in all envs
    OpenAI = None  # type: ignore


class OpenAIClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.chat_model = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
        self.client = OpenAI(api_key=self.api_key) if (OpenAI and self.api_key) else None

    def available(self) -> bool:
        return self.client is not None

    def chat_json(self, system: str, user: str) -> Optional[dict]:
        """
        Call the chat model and attempt to parse JSON from the response.
        Returns parsed dict or None if unavailable/error.
        """
        if not self.client:
            return None
        try:
            resp = self.client.chat.completions.create(
                model=self.chat_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.2,
            )
            content = resp.choices[0].message.content or "{}"
            # Try to extract JSON block
            content_str = content.strip()
            # Handle fenced code blocks
            if content_str.startswith("```"):
                content_str = content_str.strip("`\n")
                # Remove optional json hint
                if content_str.startswith("json\n"):
                    content_str = content_str[5:]
            return json.loads(content_str)
        except Exception:
            return None

