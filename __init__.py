"""White Noise plugin for FiestaBoard.

Generates a gentle rain / white noise visual effect, sized to whatever board
it renders on -- a Flagship, a Note, or any note-array panel. Falling-rain
noise is naturally rectangle-agnostic: however many rows and columns the
board has, that is how many rows a drop can fall through and how many
columns it can spawn in. Only a few white tiles appear at a time, drifting
slowly downward like light rain, so the physical board produces a soft,
soothing pitter-patter rather than an overwhelming clatter.
"""

import random
from typing import Any, Dict, List, Tuple

import logging

from src.plugins.base import PluginBase, PluginResult
from src.board_chars import BoardChars
from src.devices import NOTE_COLS, NOTE_ROWS, MAX_NOTES_PER_AXIS

logger = logging.getLogger(__name__)

# Dimensions used only when no board is bound (self.board is None) -- unit
# tests and legacy callers hit this path. The documented contract is to
# treat that as a Flagship. Everything on the actual render path derives
# rows/cols from self.board via _dimensions(); nothing here is a layout
# constant.
DEFAULT_ROWS = 6
DEFAULT_COLS = 22
# Backwards-compatible aliases for the names this module used to export.
ROWS = DEFAULT_ROWS
COLS = DEFAULT_COLS

# Largest board a user can own: an 8x8 note array. validate_config has no
# board bound to it -- one config applies to every board the user owns --
# so it bounds inputs against the biggest possible board. The render path
# (_step) independently clamps to whichever board is actually being drawn,
# so a value that's valid here but too big for a smaller board simply gets
# clamped there rather than rejected here.
MAX_COLS = NOTE_COLS * MAX_NOTES_PER_AXIS  # 120
MAX_ROWS = NOTE_ROWS * MAX_NOTES_PER_AXIS  # 24
MAX_TILES = MAX_ROWS * MAX_COLS  # 2880

# Intensity presets: how many drops appear per frame
INTENSITY_PRESETS = {
    "light": {"drops": 3, "description": "Light drizzle — very few tiles"},
    "medium": {"drops": 6, "description": "Gentle rain — a handful of tiles"},
    "heavy": {"drops": 10, "description": "Steady rain — more tiles"},
    "custom": {"drops": 0, "description": "Custom drop count (use drops_per_frame)"},
}

DEFAULT_INTENSITY = "light"
DEFAULT_DROPS_PER_FRAME = 3
DEFAULT_MAX_DROPS = 30

# Color palette for rain drops
RAINDROP_COLORS = {
    "white": BoardChars.WHITE,
    "blue": BoardChars.BLUE,
    "violet": BoardChars.VIOLET,
}

DEFAULT_DROP_COLOR = "white"


class WhiteNoisePlugin(PluginBase):
    """White noise / rain ambiance plugin.

    Creates a gentle, slowly-cascading rain effect on the board.  Each call
    to ``fetch_data`` produces a new frame where a small number of "raindrop"
    tiles appear at random positions.  The effect is designed to be subtle —
    only a few tiles change between refreshes — so the physical board makes
    a quiet, soothing pitter-patter sound.
    """

    def __init__(self, manifest: Dict[str, Any]):
        """Initialize the white noise plugin."""
        super().__init__(manifest)
        # Rain state, simulated independently per board geometry. A single
        # shared list would let one board's frame leak into another's: a
        # drop spawned at column 20 for a wide array is a valid position
        # there but out of bounds for a 15-wide Note, so if both geometries
        # advanced the same list, whichever rendered next would silently
        # discard it. Keyed by (rows, cols) -- see self._drops below.
        self._drops_by_geometry: Dict[Tuple[int, int], List[List[int]]] = {}

    @property
    def plugin_id(self) -> str:
        return "white_noise"

    @property
    def _drops(self) -> List[List[int]]:
        """Rain state for whichever board is currently bound (or the default).

        A property rather than a plain attribute so the simulation always
        reads/writes the entry for ``self._dimensions()`` in
        ``self._drops_by_geometry``, without every call site having to
        thread the geometry key through by hand.
        """
        return self._drops_by_geometry.setdefault(self._dimensions(), [])

    @_drops.setter
    def _drops(self, value: List[List[int]]) -> None:
        self._drops_by_geometry[self._dimensions()] = value

    def _dimensions(self) -> Tuple[int, int]:
        """Return ``(rows, cols)`` for the board currently being rendered.

        ``self.board`` is ``None`` outside a board-scoped render (unit
        tests, legacy callers) -- default to a Flagship's 6x22 in that
        case, per the documented contract.
        """
        board = self.board
        if board is None:
            return DEFAULT_ROWS, DEFAULT_COLS
        return board.rows, board.cols

    def validate_config(self, config: Dict[str, Any]) -> List[str]:
        """Validate white noise configuration."""
        errors = []

        intensity = config.get("intensity", DEFAULT_INTENSITY)
        if intensity not in INTENSITY_PRESETS:
            errors.append(
                f"Invalid intensity '{intensity}'. "
                f"Must be one of: {', '.join(INTENSITY_PRESETS.keys())}"
            )

        drop_color = config.get("drop_color", DEFAULT_DROP_COLOR)
        if drop_color not in RAINDROP_COLORS:
            errors.append(
                f"Invalid drop_color '{drop_color}'. "
                f"Must be one of: {', '.join(RAINDROP_COLORS.keys())}"
            )

        # Validate custom drop count. Bounded against the widest board that
        # exists (an 8-wide note array), not any one board's width -- this
        # config is shared across every board the user owns.
        if intensity == "custom":
            drops_per_frame = config.get("drops_per_frame", DEFAULT_DROPS_PER_FRAME)
            if not isinstance(drops_per_frame, int) or drops_per_frame < 1:
                errors.append("drops_per_frame must be a positive integer")
            elif drops_per_frame > MAX_COLS:
                errors.append(f"drops_per_frame cannot exceed {MAX_COLS} (widest supported board)")

        # Validate max drops against the largest board that exists (an 8x8
        # note array), not any one board's tile count.
        max_drops = config.get("max_drops", DEFAULT_MAX_DROPS)
        if not isinstance(max_drops, int) or max_drops < 1:
            errors.append("max_drops must be a positive integer")
        elif max_drops > MAX_TILES:
            errors.append(f"max_drops cannot exceed {MAX_TILES} (largest supported board's tiles)")

        return errors

    # --------------------------------------------------------------------- #
    # Data fetch (the main entry-point)
    # --------------------------------------------------------------------- #

    def fetch_data(self) -> PluginResult:
        """Generate the next rain frame, sized to the board being rendered."""
        try:
            intensity = self.config.get("intensity", DEFAULT_INTENSITY)
            drop_color_name = self.config.get("drop_color", DEFAULT_DROP_COLOR)
            drop_color = RAINDROP_COLORS.get(drop_color_name, BoardChars.WHITE)

            # Determine number of drops to spawn
            if intensity == "custom":
                num_drops = self.config.get("drops_per_frame", DEFAULT_DROPS_PER_FRAME)
            else:
                num_drops = INTENSITY_PRESETS.get(
                    intensity, INTENSITY_PRESETS[DEFAULT_INTENSITY]
                )["drops"]

            # Get max drops limit
            max_drops = self.config.get("max_drops", DEFAULT_MAX_DROPS)

            # Advance the simulation one step
            board = self._step(num_drops, drop_color, max_drops)

            # Convert to the string representation used by the display engine
            board_string = self._board_to_string(board)

            data = {
                "white_noise": board_string,
                "white_noise_array": board,
                "intensity": intensity,
                "drop_color": drop_color_name,
                "active_drops": len(self._drops),
                "drops_per_frame": num_drops,
                "max_drops": max_drops,
            }

            return PluginResult(
                available=True,
                data=data,
                formatted_lines=board_string.split("\n"),
            )

        except Exception as e:
            logger.exception("Error generating white noise frame")
            return PluginResult(available=False, error=str(e))

    # --------------------------------------------------------------------- #
    # Simulation helpers
    # --------------------------------------------------------------------- #

    def _step(self, num_new_drops: int, color: int, max_drops: int) -> List[List[int]]:
        """Advance the rain simulation by one tick, for the bound board.

        1. Move every existing drop down by one row.
        2. Remove drops that have fallen off the bottom.
        3. Spawn ``num_new_drops`` new drops at the top row.
        4. Render the board.

        Args:
            num_new_drops: How many new drops to create at the top.
            color: Board character code for the raindrop tile.
            max_drops: Maximum number of drops allowed on board simultaneously.

        Returns:
            board.rows x board.cols array of character codes (6x22 if no
            board is bound).
        """
        rows, cols = self._dimensions()

        # 1. Advance existing drops downward
        self._drops = [[r + 1, c] for r, c in self._drops if r + 1 < rows]

        # 2. Enforce max drops limit
        if len(self._drops) > max_drops:
            self._drops = self._drops[:max_drops]

        # 3. Spawn new drops along the top row at random columns
        occupied_cols = {c for r, c in self._drops if r == 0}
        available_cols = [c for c in range(cols) if c not in occupied_cols]
        if available_cols and len(self._drops) < max_drops:
            # Don't spawn more than would exceed max_drops
            spawn_count = min(num_new_drops, len(available_cols), max_drops - len(self._drops))
            new_cols = random.sample(available_cols, spawn_count)
            for c in new_cols:
                self._drops.append([0, c])

        # 4. Render board
        board = self._render(color)
        return board

    def _render(self, color: int) -> List[List[int]]:
        """Render the current drop positions onto a blank board.

        Args:
            color: Board character code for the raindrop tile.

        Returns:
            board.rows x board.cols array of character codes (6x22 if no
            board is bound).
        """
        rows, cols = self._dimensions()
        board = [[BoardChars.BLACK] * cols for _ in range(rows)]
        for r, c in self._drops:
            if 0 <= r < rows and 0 <= c < cols:
                board[r][c] = color
        return board

    def _board_to_string(self, board: List[List[int]]) -> str:
        """Convert board array to the color-marker string format.

        Args:
            board: rows x cols array of character codes.

        Returns:
            Newline-separated string using ``{color}`` markers.
        """
        color_map = {
            BoardChars.RED: "{red}",
            BoardChars.ORANGE: "{orange}",
            BoardChars.YELLOW: "{yellow}",
            BoardChars.GREEN: "{green}",
            BoardChars.BLUE: "{blue}",
            BoardChars.VIOLET: "{violet}",
            BoardChars.WHITE: "{white}",
            BoardChars.BLACK: "{black}",
        }

        lines = []
        for row in board:
            line = ""
            for code in row:
                if code in color_map:
                    line += color_map[code]
                else:
                    line += " "
            lines.append(line)
        return "\n".join(lines)

    def cleanup(self) -> None:
        """Reset rain state (for every board geometry) when disabled."""
        self._drops_by_geometry = {}


# Export the plugin class
Plugin = WhiteNoisePlugin
