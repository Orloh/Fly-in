"""Headless test configuration for the pygame GUI.

Sets SDL dummy drivers before any pygame module initializes a display,
so GUI tests can run without a video device or audio output.
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")