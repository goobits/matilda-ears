from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WakeWordTrainingRequest:
    phrase: str
    output_path: Path
    samples: int
    epochs: int


@dataclass(frozen=True)
class WakeWordTrainingResult:
    status: str
    model_path: Path | None = None
    error: str | None = None
