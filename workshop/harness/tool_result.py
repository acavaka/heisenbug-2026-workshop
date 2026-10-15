"""Runtime-owned tool result metadata, never supplied by the diagnosing model."""

from dataclasses import dataclass, field


@dataclass
class ToolResult:
    text: str
    is_error: bool = False
    metadata: dict = field(default_factory=dict)

    def __str__(self) -> str:
        return self.text
