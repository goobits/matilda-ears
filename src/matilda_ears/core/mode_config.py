from dataclasses import dataclass
from typing import Any


@dataclass
class ModeConfig:
    debug: bool = False
    format: str = "text"
    sample_rate: int | None = None
    device: str | None = None
    language: str | None = None
    model: str | None = None

    @classmethod
    def from_args(cls, args: Any) -> "ModeConfig":
        return cls(
            debug=bool(getattr(args, "debug", False)),
            format=getattr(args, "format", "text"),
            sample_rate=getattr(args, "sample_rate", None),
            device=getattr(args, "device", None),
            language=getattr(args, "language", None),
            model=getattr(args, "model", None),
        )


@dataclass
class ConversationConfig(ModeConfig):
    pass


@dataclass
class ListenOnceConfig(ModeConfig):
    pass


@dataclass
class FileTranscribeConfig(ModeConfig):
    file: str = ""
    no_formatting: bool = False

    @classmethod
    def from_args(cls, args: Any) -> "FileTranscribeConfig":
        config = super().from_args(args)
        return cls(
            debug=config.debug,
            format=config.format,
            sample_rate=config.sample_rate,
            device=config.device,
            language=config.language,
            model=config.model,
            file=getattr(args, "file", ""),
            no_formatting=bool(getattr(args, "no_formatting", False)),
        )
