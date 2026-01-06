from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class WakeWordTrainingRequest:
    phrase: str
    output_path: Path
    samples: int
    epochs: int


@dataclass(frozen=True)
class WakeWordTrainingResult:
    status: str
    model_path: Optional[Path] = None
    error: Optional[str] = None
