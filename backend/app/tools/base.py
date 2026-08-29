from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any


class RiskLevel(StrEnum):
    SAFE = "SAFE"
    CONFIRM = "CONFIRM"
    DANGEROUS = "DANGEROUS"


class Tool(ABC):
    name: str
    description: str
    input_schema: dict[str, Any]
    risk_level: RiskLevel

    @abstractmethod
    def execute(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    def ollama_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {"name": self.name, "description": self.description, "parameters": self.input_schema},
        }

