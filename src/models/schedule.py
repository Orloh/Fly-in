"""Schedule domain models produced by the CBS planner."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ScheduledAction(BaseModel):
    """One timed action for a drone (WAIT or MOVE)."""

    kind: str
    turn: int
    from_zone: str
    to_zone: str
    turns_required: int = 1


class Schedule(BaseModel):
    """Optimal-makespan plan: per-drone timed action lists."""

    actions: dict[int, list[ScheduledAction]] = Field(default_factory=dict)
    makespan: int = 0

    def is_conflict_free(self) -> bool:
        """Whether no zone/link exceeds capacity at any turn."""
        raise NotImplementedError("is_conflict_free not yet implemented")

    def occupies_goal_after_arrival(self) -> bool:
        """Whether arrived drones keep occupying finite-capacity goals."""
        raise NotImplementedError(
            "occupies_goal_after_arrival not yet implemented"
        )
