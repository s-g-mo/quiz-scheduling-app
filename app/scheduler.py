from typing import Dict, List, Tuple, Union

import pulp
import numpy as np
import pandas as pd
from app.models import Matchup


class ScheduleSolver:
    def __init__(self, n_teams: int, n_matches_per_team: int, n_rooms: int, n_time_slots: int):
        self.n_teams = n_teams
        self.n_matches_per_team = n_matches_per_team
        self.n_rooms = n_rooms
        self.n_time_slots = n_time_slots

    def schedule_matches(self, matchups: List[Matchup]) -> Union[pd.DataFrame, List[str]]:
        constraints_relaxed = []
        problem = self.attempt_schedule(matchups)

        if pulp.LpStatus[problem.status] == "Optimal":
            print("Solution found!")
        else:
            for constraint in ["room_diversity", "consecutive_matches"]:
                constraints_relaxed.append(constraint)
                problem = self.attempt_schedule(matchups, relax_constraints=constraints_relaxed)
                if pulp.LpStatus[problem.status] == "Optimal":
                    break
            else:
                print("No feasible solution found even after relaxing constraints.")
                return None, constraints_relaxed

        solution_variables = {v.name: v.varValue for v in problem.variables() if v.varValue == 1}
        formatted_solution = self._format_solution(solution_variables, matchups)
        return formatted_solution, constraints_relaxed

    def attempt_schedule(
        self, matchups: List[Matchup], relax_constraints: List[str] = []
    ) -> Union[pd.DataFrame, None]:
        problem = pulp.LpProblem("Quiz_Scheduling_With_Rooms", pulp.LpMaximize)
        variables = pulp.LpVariable.dicts(
            "MatchupRoomTime",
            (range(len(matchups)), range(1, self.n_rooms + 1), range(1, self.n_time_slots + 1)),
            cat=pulp.LpBinary,
        )
        self.enforce_constraints(problem, variables, matchups, relax_constraints)

        problem.solve()
        return problem

    def check_schedule(self, df_schedule: pd.DataFrame) -> bool:
        print(df_schedule)
        is_solution = True
        team_rooms = {team: [] for team in range(1, self.n_teams + 1)}
        team_time_slots = {team: [] for team in range(1, self.n_teams + 1)}

        for _, row in df_schedule.iterrows():
            room = row["Room"]
            matchup = row["Matchup"]
            time_slot = row["TimeSlot"]
            for team in matchup.teams:
                team_rooms[team].append(room)
                team_time_slots[team].append(time_slot)

        # Check for conflicts
        is_solution = self._check_team_conflicts(df_schedule) and is_solution
        is_solution = self._check_room_visits(team_rooms) and is_solution
        is_solution = self._check_consecutive_matches(team_time_slots) and is_solution
        print(f"Valid Schedule?: {is_solution}")
        print()
        return is_solution

    def enforce_constraints(
        self,
        problem: pulp.LpProblem,
        variables: pulp.LpVariable,
        matchups: List[Tuple[int, int, int]],
        relax_constraints: List[str],
    ):
        problem = self._enforce_each_matchup_occurrence(problem, variables, matchups)
        problem = self._enforce_each_room_to_host_single_matchup_per_time_slot(
            problem, variables, matchups
        )
        problem = self._enforce_no_simultaneous_scheduling_for_each_team(
            problem, variables, matchups
        )
        if "consecutive_matches" not in relax_constraints:
            problem = self._limit_consecutive_matchups(problem, variables, matchups)
        if "room_diversity" not in relax_constraints:
            problem = self._enforce_room_diversity(problem, variables, matchups)

    def _enforce_each_matchup_occurrence(
        self, problem: pulp.LpProblem, variables: pulp.LpVariable, matchups: List[Matchup]
    ):
        for i in range(len(matchups)):
            problem += (
                pulp.lpSum(
                    variables[i][j][k]
                    for j in range(1, self.n_rooms + 1)
                    for k in range(1, self.n_time_slots + 1)
                )
                == 1
            )
        return problem

    def _enforce_each_room_to_host_single_matchup_per_time_slot(
        self, problem: pulp.LpProblem, variables: pulp.LpVariable, matchups: List[Matchup]
    ):
        for j in range(1, self.n_rooms + 1):
            for k in range(1, self.n_time_slots + 1):
                problem += pulp.lpSum(variables[i][j][k] for i in range(len(matchups))) <= 1
        return problem

    def _enforce_no_simultaneous_scheduling_for_each_team(
        self, problem: pulp.LpProblem, variables: pulp.LpVariable, matchups: List[Matchup]
    ):
        for k in range(1, self.n_time_slots + 1):
            for team in range(1, self.n_teams + 1):
                problem += (
                    pulp.lpSum(
                        variables[i][j][k]
                        for i, matchup in enumerate(matchups)
                        for j in range(1, self.n_rooms + 1)
                        if team in matchup.teams
                    )
                    <= 1
                )
        return problem

    def _limit_consecutive_matchups(
        self, problem: pulp.LpProblem, variables: pulp.LpVariable, matchups: List[Matchup]
    ):
        for team in range(1, self.n_teams + 1):
            for k in range(1, self.n_time_slots - 1):
                problem += (
                    pulp.lpSum(
                        variables[i][j][k] + variables[i][j][k + 1] + variables[i][j][k + 2]
                        for i, matchup in enumerate(matchups)
                        if team in matchup.teams
                        for j in range(1, self.n_rooms + 1)
                    )
                    <= 2
                )
        return problem

    def _enforce_room_diversity(
        self, problem: pulp.LpProblem, variables: pulp.LpVariable, matchups: List[Matchup]
    ):
        for team in range(1, self.n_teams + 1):
            problem += (
                pulp.lpSum(
                    variables[i][j][k]
                    for i, matchup in enumerate(matchups)
                    for j in range(1, self.n_rooms + 1)
                    for k in range(1, self.n_time_slots + 1)
                    if team in matchup.teams
                )
                == self.n_matches_per_team
            )

            for j in range(1, self.n_rooms + 1):
                problem += (
                    pulp.lpSum(
                        variables[i][j][k]
                        for i, matchup in enumerate(matchups)
                        for k in range(1, self.n_time_slots + 1)
                        if team in matchup.teams
                    )
                    <= 1
                )
        return problem

    def _format_solution(self, solution: Dict[str, float], matchups: List[Matchup]):
        data = []
        for key, value in solution.items():
            if value == 1.0:
                parts = key.split("_")
                matchup_idx = int(parts[1])
                room = int(parts[2])
                time_slot = int(parts[3])
                matchup = matchups[matchup_idx]
                data.append((time_slot, room, matchup))
        df = pd.DataFrame(data, columns=["TimeSlot", "Room", "Matchup"])
        df.sort_values(["TimeSlot", "Room"], inplace=True)
        df.reset_index(drop=True, inplace=True)
        return df

    def _check_team_conflicts(self, df_schedule: pd.DataFrame) -> bool:
        for time_slot in range(1, self.n_time_slots + 1):
            df_time_slot = df_schedule[df_schedule.TimeSlot == time_slot]
            teams_in_slot = np.array([matchup.teams for matchup in df_time_slot.Matchup])
            n_unique_teams = len(np.unique(teams_in_slot))
            if n_unique_teams != teams_in_slot.size:
                print("A team is scheduled more than once at the same time.")
                return False
        return True

    def _check_room_visits(self, team_rooms: Dict[int, List[int]]) -> bool:
        expected_room_visits = min(self.n_rooms, self.n_matches_per_team)
        for team, rooms in team_rooms.items():
            unique_rooms = np.unique(rooms)
            if len(unique_rooms) != expected_room_visits:
                print(
                    f"Team {team} visited {len(unique_rooms)} rooms (expected {expected_room_visits})"
                )
                return False
        return True

    def _check_consecutive_matches(self, team_time_slots: Dict[int, List[int]]) -> bool:
        for team, time_slots in team_time_slots.items():
            time_slots.sort()
            time_diffs = np.diff(np.array(time_slots))
            if (time_diffs == 1).sum() > 2:  # Check if there are 3 consecutive time slots
                print(f"Team {team} is scheduled for 3 consecutive matches.")
                return False
        return True
