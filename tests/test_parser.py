"""Tests for the map-file text parser (Phase 1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.parser.errors import ParseError
from src.parser.parser import (
    _parse_connection_line,
    _parse_hub_line,
    _parse_metadata,
    _parse_nb_drones,
    parse_map,
)


class TestParseMetadata:
    """Unit tests for bracket-metadata extraction."""

    def test_no_brackets_returns_empty_dict(self) -> None:
        result = _parse_metadata("hub: A 0 0", 1)
        assert result == {}

    def test_empty_brackets_returns_empty_dict(self) -> None:
        result = _parse_metadata("hub: A 0 0 []", 1)
        assert result == {}

    def test_single_key_value_pair(self) -> None:
        result = _parse_metadata("[zone=normal]", 1)
        assert result == {"zone": "normal"}

    def test_multiple_key_value_pairs(self) -> None:
        result = _parse_metadata("[zone=normal max_drones=3]", 1)
        assert result == {"zone": "normal", "max_drones": "3"}

    def test_missing_closing_bracket_raises_error(self) -> None:
        with pytest.raises(ParseError) as exc:
            _parse_metadata("hub: A 0 0 [zone=normal", 3)
        assert exc.value.line_number == 3

    def test_missing_opening_bracket_raises_error(self) -> None:
        with pytest.raises(ParseError) as exc:
            _parse_metadata("hub: A 0 0 zone=normal]", 3)
        assert exc.value.line_number == 3

    def test_token_without_equals_raises_error(self) -> None:
        with pytest.raises(ParseError) as exc:
            _parse_metadata("[zone=normal badtoken]", 3)
        assert exc.value.line_number == 3

    def test_empty_key_raises_error(self) -> None:
        with pytest.raises(ParseError) as exc:
            _parse_metadata("[=normal]", 3)
        assert exc.value.line_number == 3

    def test_empty_value_raises_error(self) -> None:
        with pytest.raises(ParseError) as exc:
            _parse_metadata("[zone=]", 3)
        assert exc.value.line_number == 3

    def test_multiple_equals_raises_error(self) -> None:
        with pytest.raises(ParseError) as exc:
            _parse_metadata("[a=b=c]", 3)
        assert exc.value.line_number == 3

    def test_double_bracket_group_raises_error(self) -> None:
        with pytest.raises(ParseError) as exc:
            _parse_metadata("[a=1][b=2]", 3)
        assert exc.value.line_number == 3

    def test_trailing_content_after_brackets_raises_error(self) -> None:
        with pytest.raises(ParseError) as exc:
            _parse_metadata("[zone=normal] junk", 3)
        assert exc.value.line_number == 3


class TestParseNbDrones:
    """Unit tests for the drone-count first-line parser."""

    def test_valid_count(self) -> None:
        result = _parse_nb_drones("nb_drones: 3", 1)
        assert result == 3

    def test_missing_space_after_colon_raises_error(self) -> None:
        with pytest.raises(ParseError) as exc:
            _parse_nb_drones("nb_drones:5", 1)
        assert exc.value.line_number == 1

    def test_non_integer_raises_error(self) -> None:
        with pytest.raises(ParseError) as exc:
            _parse_nb_drones("nb_drones: abc", 1)
        assert exc.value.line_number == 1

    def test_zero_raises_error(self) -> None:
        with pytest.raises(ParseError) as exc:
            _parse_nb_drones("nb_drones: 0", 1)
        assert exc.value.line_number == 1

    def test_negative_raises_error(self) -> None:
        with pytest.raises(ParseError) as exc:
            _parse_nb_drones("nb_drones: -5", 1)
        assert exc.value.line_number == 1

    def test_wrong_prefix_raises_error(self) -> None:
        with pytest.raises(ParseError) as exc:
            _parse_nb_drones("start_hub: A 0 0", 1)
        assert exc.value.line_number == 1

    def test_missing_colon_raises_error(self) -> None:
        with pytest.raises(ParseError) as exc:
            _parse_nb_drones("nb_drones", 1)
        assert exc.value.line_number == 1


class TestParseHubLine:
    """Unit tests for the hub-line parser."""

    def test_valid_hub(self) -> None:
        result = _parse_hub_line("hub: A 0 0", 1)
        assert result.name == "A"
        assert result.x == 0
        assert result.y == 0
        assert result.metadata == {}

    def test_valid_hub_with_metadata(self) -> None:
        result = _parse_hub_line("hub: A 0 0 [zone=priority]", 1)
        assert result.name == "A"
        assert result.metadata == {"zone": "priority"}

    def test_missing_coordinate_raises_error(self) -> None:
        with pytest.raises(ParseError) as exc:
            _parse_hub_line("hub: A 0", 1)
        assert exc.value.line_number == 1

    def test_extra_token_raises_error(self) -> None:
        with pytest.raises(ParseError) as exc:
            _parse_hub_line("hub: A 0 0 extra", 1)
        assert exc.value.line_number == 1

    def test_non_integer_coordinate_raises_error(self) -> None:
        with pytest.raises(ParseError) as exc:
            _parse_hub_line("hub: A x 0", 1)
        assert exc.value.line_number == 1

    def test_malformed_metadata_raises_error(self) -> None:
        with pytest.raises(ParseError) as exc:
            _parse_hub_line("hub: A 0 0 [zone", 1)
        assert exc.value.line_number == 1


class TestParseConnectionLine:
    """Unit tests for the connection-line parser."""

    def test_valid_connection(self) -> None:
        result = _parse_connection_line("connection: A-B", 1)
        assert result.zone_a == "A"
        assert result.zone_b == "B"
        assert result.metadata == {}

    def test_valid_connection_with_metadata(self) -> None:
        result = _parse_connection_line(
            "connection: A-B [max_link_capacity=3]", 1
        )
        assert result.zone_a == "A"
        assert result.zone_b == "B"
        assert result.metadata == {"max_link_capacity": "3"}

    def test_no_dash_raises_error(self) -> None:
        with pytest.raises(ParseError) as exc:
            _parse_connection_line("connection: AB", 1)
        assert exc.value.line_number == 1

    def test_three_parts_raises_error(self) -> None:
        with pytest.raises(ParseError) as exc:
            _parse_connection_line("connection: A-B-C", 1)
        assert exc.value.line_number == 1

    def test_empty_endpoint_raises_error(self) -> None:
        with pytest.raises(ParseError) as exc:
            _parse_connection_line("connection: A-", 1)
        assert exc.value.line_number == 1


class TestParseMapHappyPaths:
    """Integration tests for complete valid map files."""

    def test_minimal_map(self, tmp_path: Path) -> None:
        content = (
            "nb_drones: 3\n"
            "start_hub: start 0 0\n"
            "end_hub: end 5 5\n"
        )
        path = tmp_path / "minimal.map"
        path.write_text(content)
        result = parse_map(str(path))
        assert result.nb_drones == 3
        assert result.start_hub.name == "start"
        assert result.start_hub.x == 0
        assert result.start_hub.y == 0
        assert result.end_hub.name == "end"
        assert result.end_hub.x == 5
        assert result.end_hub.y == 5
        assert result.zones == []
        assert result.connections == []

    def test_full_map_with_metadata(self, tmp_path: Path) -> None:
        content = (
            "nb_drones: 5\n"
            "start_hub: base 0 0 [color=green]\n"
            "hub: roof1 1 2 [zone=normal max_drones=2]\n"
            "hub: corridorA 3 4 [zone=priority color=blue]\n"
            "end_hub: target 10 10\n"
            "connection: base-roof1 [max_link_capacity=3]\n"
            "connection: roof1-corridorA\n"
            "connection: corridorA-target\n"
        )
        path = tmp_path / "full.map"
        path.write_text(content)
        result = parse_map(str(path))
        assert result.nb_drones == 5
        assert result.start_hub.name == "base"
        assert result.start_hub.metadata == {"color": "green"}
        assert len(result.zones) == 2
        assert result.zones[0].name == "roof1"
        assert result.zones[1].name == "corridorA"
        assert result.zones[1].metadata == {
            "zone": "priority", "color": "blue"
        }
        assert result.end_hub.name == "target"
        assert len(result.connections) == 3
        assert result.connections[0].zone_a == "base"
        assert result.connections[0].zone_b == "roof1"
        assert result.connections[0].metadata == {
            "max_link_capacity": "3"
        }

    def test_connections_before_zones(self, tmp_path: Path) -> None:
        content = (
            "nb_drones: 2\n"
            "start_hub: A 0 0\n"
            "connection: B-C\n"
            "connection: A-B\n"
            "hub: B 1 1\n"
            "end_hub: C 2 2\n"
        )
        path = tmp_path / "forward.map"
        path.write_text(content)
        result = parse_map(str(path))
        assert len(result.connections) == 2
        assert result.connections[0].zone_a == "B"
        assert result.connections[0].zone_b == "C"
        assert result.connections[1].zone_a == "A"
        assert result.connections[1].zone_b == "B"
        assert len(result.zones) == 1
        assert result.zones[0].name == "B"

    def test_comments_and_blank_lines(self, tmp_path: Path) -> None:
        content = (
            "# This is a comment\n"
            "nb_drones: 2\n"
            "\n"
            "start_hub: A 0 0 # inline comment\n"
            "# another comment\n"
            "end_hub: B 1 1\n"
            "\n"
        )
        path = tmp_path / "comments.map"
        path.write_text(content)
        result = parse_map(str(path))
        assert result.nb_drones == 2
        assert result.start_hub.name == "A"
        assert result.end_hub.name == "B"

    def test_leading_whitespace_lines(self, tmp_path: Path) -> None:
        content = (
            "  nb_drones: 2\n"
            "  start_hub: A 0 0\n"
            "   end_hub: B 1 1\n"
        )
        path = tmp_path / "indented.map"
        path.write_text(content)
        result = parse_map(str(path))
        assert result.nb_drones == 2
        assert result.start_hub.name == "A"
        assert result.end_hub.name == "B"


class TestParseMapErrors:
    """Error-handling tests for malformed map files."""

    def test_empty_file_raises_error(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.map"
        path.write_text("")
        with pytest.raises(ParseError) as exc:
            parse_map(str(path))
        assert exc.value.line_number == 1

    def test_comment_only_file_raises_error(self, tmp_path: Path) -> None:
        path = tmp_path / "comments_only.map"
        path.write_text("# nothing but comments\n# really\n")
        with pytest.raises(ParseError) as exc:
            parse_map(str(path))
        assert exc.value.line_number == 1

    def test_missing_drone_count_raises_error(
        self, tmp_path: Path
    ) -> None:
        content = "start_hub: A 0 0\nend_hub: B 1 1\n"
        path = tmp_path / "nodrones.map"
        path.write_text(content)
        with pytest.raises(ParseError) as exc:
            parse_map(str(path))
        assert exc.value.line_number == 1

    def test_non_integer_drone_count_raises_error(
        self, tmp_path: Path
    ) -> None:
        content = "nb_drones: abc\nstart_hub: A 0 0\nend_hub: B 1 1\n"
        path = tmp_path / "badcount.map"
        path.write_text(content)
        with pytest.raises(ParseError) as exc:
            parse_map(str(path))
        assert exc.value.line_number == 1

    def test_zero_drone_count_raises_error(self, tmp_path: Path) -> None:
        content = "nb_drones: 0\nstart_hub: A 0 0\nend_hub: B 1 1\n"
        path = tmp_path / "zerocount.map"
        path.write_text(content)
        with pytest.raises(ParseError) as exc:
            parse_map(str(path))
        assert exc.value.line_number == 1

    def test_float_drone_count_raises_error(self, tmp_path: Path) -> None:
        content = "nb_drones: 1.5\nstart_hub: A 0 0\nend_hub: B 1 1\n"
        path = tmp_path / "floatcount.map"
        path.write_text(content)
        with pytest.raises(ParseError) as exc:
            parse_map(str(path))
        assert exc.value.line_number == 1

    def test_negative_drone_count_raises_error(
        self, tmp_path: Path
    ) -> None:
        content = "nb_drones: -5\nstart_hub: A 0 0\nend_hub: B 1 1\n"
        path = tmp_path / "negcount.map"
        path.write_text(content)
        with pytest.raises(ParseError) as exc:
            parse_map(str(path))
        assert exc.value.line_number == 1

    def test_missing_start_hub_raises_error(
        self, tmp_path: Path
    ) -> None:
        content = "nb_drones: 1\nend_hub: B 1 1\n"
        path = tmp_path / "nostart.map"
        path.write_text(content)
        with pytest.raises(ParseError) as exc:
            parse_map(str(path))
        assert exc.value.line_number == 2

    def test_missing_end_hub_raises_error(
        self, tmp_path: Path
    ) -> None:
        content = "nb_drones: 1\nstart_hub: A 0 0\n"
        path = tmp_path / "noend.map"
        path.write_text(content)
        with pytest.raises(ParseError) as exc:
            parse_map(str(path))
        assert exc.value.line_number == 2

    def test_duplicate_start_hub_raises_error(
        self, tmp_path: Path
    ) -> None:
        content = (
            "nb_drones: 1\n"
            "start_hub: A 0 0\n"
            "start_hub: B 1 1\n"
            "end_hub: C 2 2\n"
        )
        path = tmp_path / "dupstart.map"
        path.write_text(content)
        with pytest.raises(ParseError) as exc:
            parse_map(str(path))
        assert exc.value.line_number == 3

    def test_duplicate_end_hub_raises_error(
        self, tmp_path: Path
    ) -> None:
        content = (
            "nb_drones: 1\n"
            "start_hub: A 0 0\n"
            "end_hub: B 1 1\n"
            "end_hub: C 2 2\n"
        )
        path = tmp_path / "dupend.map"
        path.write_text(content)
        with pytest.raises(ParseError) as exc:
            parse_map(str(path))
        assert exc.value.line_number == 4

    def test_non_integer_coordinates_raises_error(
        self, tmp_path: Path
    ) -> None:
        content = (
            "nb_drones: 1\n"
            "start_hub: A 0 0\n"
            "hub: B x 0\n"
            "end_hub: C 1 1\n"
        )
        path = tmp_path / "badcoords.map"
        path.write_text(content)
        with pytest.raises(ParseError) as exc:
            parse_map(str(path))
        assert exc.value.line_number == 3

    def test_hub_missing_coordinate_raises_error(
        self, tmp_path: Path
    ) -> None:
        content = (
            "nb_drones: 1\n"
            "start_hub: A 0 0\n"
            "hub: B 1\n"
            "end_hub: C 2 2\n"
        )
        path = tmp_path / "shortcoord.map"
        path.write_text(content)
        with pytest.raises(ParseError) as exc:
            parse_map(str(path))
        assert exc.value.line_number == 3

    def test_end_hub_missing_coordinate_raises_error(
        self, tmp_path: Path
    ) -> None:
        content = (
            "nb_drones: 1\n"
            "start_hub: A 0 0\n"
            "end_hub: B\n"
        )
        path = tmp_path / "shortend.map"
        path.write_text(content)
        with pytest.raises(ParseError) as exc:
            parse_map(str(path))
        assert exc.value.line_number == 3

    def test_hub_extra_token_raises_error(self, tmp_path: Path) -> None:
        content = (
            "nb_drones: 1\n"
            "start_hub: A 0 0\n"
            "hub: B 1 1 extra\n"
            "end_hub: C 2 2\n"
        )
        path = tmp_path / "extracoord.map"
        path.write_text(content)
        with pytest.raises(ParseError) as exc:
            parse_map(str(path))
        assert exc.value.line_number == 3

    def test_start_hub_extra_token_raises_error(
        self, tmp_path: Path
    ) -> None:
        content = (
            "nb_drones: 1\n"
            "start_hub: A 0 0 extra\n"
            "end_hub: B 1 1\n"
        )
        path = tmp_path / "extrastart.map"
        path.write_text(content)
        with pytest.raises(ParseError) as exc:
            parse_map(str(path))
        assert exc.value.line_number == 2

    def test_unknown_prefix_raises_error(
        self, tmp_path: Path
    ) -> None:
        content = (
            "nb_drones: 1\n"
            "start_hub: A 0 0\n"
            "foobar: B 1 1\n"
            "end_hub: C 2 2\n"
        )
        path = tmp_path / "badprefix.map"
        path.write_text(content)
        with pytest.raises(ParseError) as exc:
            parse_map(str(path))
        assert exc.value.line_number == 3

    def test_metadata_malformed_on_hub_line_raises_error(
        self, tmp_path: Path
    ) -> None:
        content = (
            "nb_drones: 1\n"
            "start_hub: A 0 0\n"
            "hub: B 1 1 [zone\n"
            "end_hub: C 2 2\n"
        )
        path = tmp_path / "badmeta.map"
        path.write_text(content)
        with pytest.raises(ParseError) as exc:
            parse_map(str(path))
        assert exc.value.line_number == 3

    def test_trailing_junk_after_metadata_raises_error(
        self, tmp_path: Path
    ) -> None:
        content = (
            "nb_drones: 1\n"
            "start_hub: A 0 0\n"
            "hub: B 1 1 [color=red] junk\n"
            "end_hub: C 2 2\n"
        )
        path = tmp_path / "trailing.map"
        path.write_text(content)
        with pytest.raises(ParseError) as exc:
            parse_map(str(path))
        assert exc.value.line_number == 3

    def test_connection_with_three_parts_raises_error(
        self, tmp_path: Path
    ) -> None:
        content = (
            "nb_drones: 1\n"
            "start_hub: A 0 0\n"
            "end_hub: B 1 1\n"
            "connection: A-B-C\n"
        )
        path = tmp_path / "tripleconn.map"
        path.write_text(content)
        with pytest.raises(ParseError) as exc:
            parse_map(str(path))
        assert exc.value.line_number == 4

    def test_connection_with_empty_name_raises_error(
        self, tmp_path: Path
    ) -> None:
        content = (
            "nb_drones: 1\n"
            "start_hub: A 0 0\n"
            "end_hub: B 1 1\n"
            "connection: A-\n"
        )
        path = tmp_path / "emptyconn.map"
        path.write_text(content)
        with pytest.raises(ParseError) as exc:
            parse_map(str(path))
        assert exc.value.line_number == 4

    def test_connection_without_dash_raises_error(
        self, tmp_path: Path
    ) -> None:
        content = (
            "nb_drones: 1\n"
            "start_hub: A 0 0\n"
            "end_hub: B 1 1\n"
            "connection: AB\n"
        )
        path = tmp_path / "nodash.map"
        path.write_text(content)
        with pytest.raises(ParseError) as exc:
            parse_map(str(path))
        assert exc.value.line_number == 4

    def test_malformed_drone_line_raises_error(
        self, tmp_path: Path
    ) -> None:
        content = (
            "nb_drones\n"
            "start_hub: A 0 0\n"
            "end_hub: B 1 1\n"
        )
        path = tmp_path / "baddrone.map"
        path.write_text(content)
        with pytest.raises(ParseError) as exc:
            parse_map(str(path))
        assert exc.value.line_number == 1
