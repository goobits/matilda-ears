"""Detectors sub-package for specialized entity detection modules."""

from .web_detector import WebEntityDetector
from .code_detector import CodeEntityDetector
from .numeric_detector import NumericalEntityDetector

__all__ = ["CodeEntityDetector", "NumericalEntityDetector", "WebEntityDetector"]
