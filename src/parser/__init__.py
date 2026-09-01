"""Map-file parser and domain-model converter.

Parsing happens in two stages:
1. ``parser`` — reads the text file line-by-line into a ``ParsedMap``.
2. ``converter`` — validates and converts ``ParsedMap`` into ``Graph``
   and fleet of ``Drone`` objects for simulation.
"""

from src.parser.parser import parse_map
from src.parser.converter import build_graph
from src.parser.errors import ParseError

__all__ = ["parse_map", "build_graph", "ParseError"]
