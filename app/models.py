from pydantic import BaseModel, Field
from typing import Dict, List, Tuple


class MatchupsRequest(BaseModel):
    n_teams: int = Field(30, description="Number of teams participating", example=30)
    n_matches_per_team: int = Field(3, description="Number of matches each team plays", example=3)
    n_matchup_solutions: int = Field(
        2, description="Number of matchup solutions to generate", example=2
    )


class Matchup(BaseModel):
    teams: Tuple[int, int, int]


class MatchupsResponse(BaseModel):
    solutions: Dict[str, List[Matchup]]


class ScheduleRequest(BaseModel):
    n_teams: int = Field(30, description="Number of teams participating", example=30)
    n_matches_per_team: int = Field(3, description="Number of matches each team plays", example=3)
    n_rooms: int = Field(5, description="Number of available rooms for matches", example=5)
    n_time_slots: int = Field(6, description="Number of time slots for scheduling", example=6)


class ScheduleItem(BaseModel):
    TimeSlot: int
    Room: int
    Matchup: Matchup


class ScheduleResponse(BaseModel):
    schedule: List[ScheduleItem]
    constraints_relaxed: List[str]
