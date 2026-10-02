"""Replaceable model-provider contract for Personal Nexus."""
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass(frozen=True)
class ModelResponse:
    success: bool
    content: str
    model: str
    error: str | None = None

class ModelProvider(ABC):
    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        json_mode: bool = False,
        profile: str = "normal",
    ) -> ModelResponse:
        """Generate model output without owning Nexus memory, tools, or policy."""
        raise NotImplementedError
