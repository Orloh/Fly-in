# CLI Output + Zone Color Implementation Plan

## Summary
Implement zone-name coloring by `color=` metadata in CLI output, and update GUI to use the same rose-pine palette mapping. Factor the shared palette into `src/palette.py`.

## Decisions (confirmed)
- **Color mapping**: red→rose, blue→iris, green→pine, cyan→foam, gold→gold, plus synonyms (pink→rose, purple→iris, yellow→gold, teal→pine, white→text, gray→muted).
- **Scope**: zone NAME tokens only — in map header (`format_map`) and turn lines (`format_turn`); uncolored zones keep current defaults.
- **GUI consistency**: update `src/gui/app.py:_zone_color` to use rose-pine mapping instead of `pygame.Color`; remove dead `_parse_color`.
- **Shared module**: `src/palette.py` — pure, no pygame; exports `PALETTE` (with `iris`), `COLOR_NAME_TO_ROLE`, `color_role`.
- **Backward compat**: uncolored zones unchanged; existing CLI tests pass.

## Files to create/modify

### 1. `src/palette.py` (new — shared)
Pure, no pygame. Single source of truth for CLI + GUI.

**Exports:**
- `PALETTE: dict[str, tuple[int, int, int]]` — gold, foam, rose, pine, iris, text, muted, bg.
- `COLOR_NAME_TO_ROLE: dict[str, str]` — color-name → rose-pine role (synonyms included).
- `color_role(color_name: str) -> str | None` — returns mapped role or None for "none"/unknown (caller picks default). Lowercases input.

### 2. `src/cli.py` (modify)
- Import `PALETTE`, `COLOR_NAME_TO_ROLE`, `color_role` from `src.palette`; keep `paint`.
- **`format_map`**: build `name→color_name` from all `ParsedMap` zones; restructure lines to paint **name token** with `color_role(zone_color) or <line_default>` (text for start/end hubs, foam for regular hubs, pine for connection endpoints — each independently). Prefix/coords keep line default; metadata unchanged.
- **`format_turn`**: add `zone_roles: dict[str, str] | None = None`; paint `to_zone` with `zone_roles.get(to_zone, "foam")`.
- **`simulate`**: build `zone_roles = {name: color_role(zone.color) or "foam" ...}` from `graph.zones`; pass to `format_turn`.
- Re-export `PALETTE`, `COLOR_NAME_TO_ROLE`, `color_role` for test compatibility.

### 3. `src/gui/app.py` (modify)
- Import `PALETTE`, `color_role` from `src.palette`.
- **`_zone_color`**: replace `_parse_color(zone.color)` with `PALETTE[color_role(zone.color)]` when mapped, else fall back to `ZONE_COLORS[zone.zone_type]` (unknown/`none` → type color).
- Remove dead `_parse_color`.

### 4. `src/__main__.py` (no change — already wired)
CLI already calls `src.cli.run`; `--no-color` flag exists.

### 5. `tests/test_cli.py` (TDD — update first)
- `color_role`: red→rose, blue→iris, green→pine, cyan→foam, gold→gold, "none"→None, unknown→None.
- `format_map` with `color=red` zone: name token wrapped in rose escape; plain mode unchanged.
- `format_turn` with `zone_roles={"A": "rose"}`: `to_zone` rose; `None`→foam (existing `test_colored_prefix` passes).
- `simulate` with graph whose zones have `color=`: colored names in yielded lines.

### 6. `tests/test_gui_app.py` (update if needed)
- Verify `_zone_color` with mapped colors (e.g., `color=blue`→iris RGB). Update any assertions.

## Output example (CLI, with color enabled)
```
nb_drones: 3
start_hub: base 0 0
end_hub: target 400 300 [color=green]
hub: roof1 200 -100
hub: corridorA 300 150 [color=blue zone=priority]
hub: vault 350 -150 [zone=restricted]
hub: landing 150 250 [color=red]
connection: base-roof1 [max_link_capacity=3]
connection: roof1-corridorA
connection: corridorA-target
connection: base-landing
connection: landing-target
connection: roof1-vault

D1-landing          ← "landing" in red (rose)
D1-target D2-landing   ← "target" in green (pine), "landing" in red
D2-target D3-landing
D3-target
```

## Verification
- `uv run pytest tests` (real signal — `make test` masks failures)
- `make lint` (mypy strict + flake8, 79 cols)
- `make run MAP=maps/example.map` — zone names colored per their metadata
- `make gui MAP=maps/example.map` — zone circles colored per rose-pine mapping