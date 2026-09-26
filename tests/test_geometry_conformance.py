"""Board-geometry conformance for the white_noise plugin.

Falling-rain noise is the one art effect that scales to any rectangle for
free: however many rows and columns a board has, that's how far a drop can
fall and how many columns it can spawn in. ``strict_growth=True`` is used
because the rendered output always fills every row/column of whatever board
is bound -- a taller board must show a taller (not just re-centred) frame.

No network access is involved -- fetch_data only touches ``random`` and the
plugin's own in-memory rain state -- so ``make_plugin`` needs no stubbing.
"""

import json
from pathlib import Path

from src.plugins.geometry_conformance import assert_board_conformance

from plugins.white_noise import WhiteNoisePlugin

MANIFEST = json.loads((Path(__file__).parent.parent / "manifest.json").read_text())


def make_plugin() -> WhiteNoisePlugin:
    """Fresh, ready-to-render plugin. No network access is involved."""
    plugin = WhiteNoisePlugin(MANIFEST)
    plugin.config = {"intensity": "heavy", "drop_color": "white", "max_drops": 500}
    return plugin


def test_renders_on_every_board_shape():
    assert_board_conformance(
        make_plugin,
        manifest=MANIFEST,
        strict_growth=True,
        require_note_array_preview=True,
    )
