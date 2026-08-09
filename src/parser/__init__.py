"""Map-file parser and domain-model converter.

Parsing happens in two stages:
1. ``parser`` — reads the text file line-by-line into a ``ParsedMap``.
2. ``converter`` — validates and converts ``ParsedMap`` into ``Graph``
   and fleet of ``Drone`` objects for simulation.
"""
