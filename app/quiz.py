import itertools
from typing import Dict, List, Tuple, Union

import pulp
import numpy as np
import pandas as pd


def find_matchup_solutions(
    n_teams: int,
    n_matches_per_team: int,
    matchups: List[Tuple[int, int, int]],
    max_solutions: int = 10,
) -> List[np.ndarray]:

    if n_matches_per_team % 3 == 0:

        error_msg_1 = (
            f"It is impossible to generate valid matchups if n_matches_per_team "
            f"is a multiple of 3 and n_teams <= 2 * n_matches_per_team. "
            f"Current values: n_matches_per_team = {n_matches_per_team}, "
            f"n_teams = {n_teams}"
        )
        assert n_teams > 2 * n_matches_per_team, error_msg_1

    if n_matches_per_team % 3 != 0:
        error_msg_2a = (
            f"If n_matches_per_team is not a multiple of 3, n_teams must be a "
            f"multiple of 3 to generate valid matchups. Current values: "
            f"n_matches_per_team = {n_matches_per_team}, n_teams = {n_teams}"
        )
        error_msg_2b = (
            f"If n_matches_per_team is not a multiple of 3, n_teams must also be "
            f"greater than or equal to 2 * n_matches_per_team to generate valid "
            f"matchups. Current values: n_matches_per_team = {n_matches_per_team}"
            f", n_teams = {n_teams}"
        )

        # Ensure n_teams is a multiple of 3
        assert n_teams % 3 == 0, error_msg_2a

        # Ensure n_teams is at least 2 times n_matches_per_team
        assert n_teams >= 2 * n_matches_per_team, error_msg_2b

    solutions = []

    # Problem setup
    problem = pulp.LpProblem("Quiz_Scheduling", sense=pulp.LpMaximize)
    variables = pulp.LpVariable.dicts("Matchup", (range(len(matchups))), cat=pulp.LpBinary)

    # Constraints
    prob = enforce_each_team_in_exactly_n_matches_per_team(
        problem=problem,
        variables=variables,
        matchups=matchups,
        n_teams=n_teams,
        n_matches_per_team=n_matches_per_team,
    )
    prob = enforce_unique_opponents_constraint(
        problem=problem, variables=variables, matchups=matchups, n_teams=n_teams
    )
    prob = enforce_bench_constraints(
        problem=problem,
        variables=variables,
        matchups=matchups,
        n_teams=n_teams,
        n_matches_per_team=n_matches_per_team,
    )

    while len(solutions) < max_solutions:

        prob.solve()

        if pulp.LpStatus[prob.status] == "Optimal":
            solution = [i for i in range(len(matchups)) if variables[i].varValue == 1]
            selected_matchups = [matchups[i] for i in solution]
            solutions.append(np.array(selected_matchups))

            problem += pulp.lpSum(variables[i] for i in solution) <= len(solution) - 1
        else:
            break

    return solutions


def check_matchups(solution: np.array, n_teams: int, n_matches_per_team: int) -> bool:

    print(solution)
    is_solution = True

    for team in range(1, n_teams + 1):

        team_filter = solution == team

        # Check to ensure each team has exactly n_matches_per_team
        if team_filter.sum() != n_matches_per_team:
            print(f"Team {team} has {team_filter.sum()} matches, expected" f"{n_matches_per_team}.")
            is_solution = False

        # Check bench constraints
        base_visits = n_matches_per_team // 3
        extra_visits = n_matches_per_team % 3
        bench_counts = team_filter.sum(axis=0)

        # Ensure each team visits each bench position at least base_visits times
        if (bench_counts < base_visits).any():
            print(
                f"Team {team} does not visit each bench position at least", f"{base_visits} times."
            )
            is_solution = False

        # Ensure no team visits any bench position > base_visits + 1 times
        if (bench_counts > base_visits + 1).any():
            print(f"Team {team} visits a bench position more than" f"{base_visits + 1} times.")
            is_solution = False

        # Check for unique opponents
        rows_containing_current_team_matches = np.where(solution == True)[0]
        opponents_faced = solution[rows_containing_current_team_matches]
        number_unique_opponents = len(np.unique(opponents_faced)) - 1

        if number_unique_opponents != n_matches_per_team * 2:
            print(
                f"Team {team} has {n_matches_per_team * 2} opponents, but found"
                f"{number_unique_opponents} unique opponents."
            )
            is_solution = False

    print(f"Valid Matchups?: {is_solution}")
    print()
    return is_solution


def check_schedule(
    df_schedule: pd.DataFrame, n_teams: int, n_rooms: int, n_time_slots: int
) -> bool:

    print(df_schedule)
    is_solution = True

    # Keep track of which rooms each team visits and their time slots
    team_rooms = {team: [] for team in range(1, n_teams + 1)}
    team_time_slots = {team: [] for team in range(1, n_teams + 1)}

    for index, row in df_schedule.iterrows():

        room = row["Room"]
        matchup = row["Matchup"]
        time_slot = row["TimeSlot"]

        for team in matchup:
            team_rooms[team].append(room)
            team_time_slots[team].append(time_slot)

    # Check to make sure no team has been scheduled more than once at a time
    for time_slot in range(1, n_time_slots + 1):

        df_time_slot = df_schedule[df_schedule.TimeSlot == time_slot]

        teams_competing_in_current_time_slot = np.array(df_time_slot.Matchup.to_list())
        n_teams_in_time_slot = len(np.unique(teams_competing_in_current_time_slot))

        if n_teams_in_time_slot != teams_competing_in_current_time_slot.size:
            print(f"A team has been scheduled more than once at the same time")
            is_solution = False

    # Check if teams have visited the expected number of rooms
    if n_rooms >= n_matches_per_team:
        expected_room_visits = n_matches_per_team
    else:
        expected_room_visits = n_rooms

    for team, rooms in team_rooms.items():
        unique_rooms = np.unique(rooms)
        if len(unique_rooms) != expected_room_visits:
            print(
                f"Team {team} has visited {len(unique_rooms)} rooms:"
                f"{unique_rooms} (expected {expected_room_visits})"
            )
            is_solution = False

    # Check for more than 2 consecutive matches
    if n_matches_per_team > 3:
        for team, time_slots in team_time_slots.items():
            time_slots.sort()
            time_slot_diffs = np.diff(np.array(time_slots))
            if time_slot_diffs.sum() == 2:
                print(f"Team {team} has been scheduled for 3 consecutive time_slots")
                is_solution = False
    return is_solution


def generate_all_possible_matchups(n_teams: int) -> List[Tuple[int, int, int]]:
    teams = list(range(1, n_teams + 1))
    all_triples = list(itertools.combinations(teams, 3))

    possible_matchups = []
    for triple in all_triples:
        for perm in itertools.permutations(triple):
            possible_matchups.append(perm)

    return possible_matchups


def enforce_each_team_in_exactly_n_matches_per_team(
    problem: pulp.LpProblem,
    variables: pulp.LpVariable,
    matchups: list,
    n_teams: int,
    n_matches_per_team: int,
) -> pulp.LpProblem:

    for team in range(1, n_teams + 1):
        problem += (
            pulp.lpSum(variables[i] for i, M in enumerate(matchups) if team in M)
            == n_matches_per_team
        )

    return problem


def enforce_bench_constraints(
    problem: pulp.LpProblem,
    variables: pulp.LpVariable,
    matchups: list,
    n_teams: int,
    n_matches_per_team: int,
) -> pulp.LpProblem:

    for team in range(1, n_teams + 1):
        for position in range(3):

            if n_matches_per_team < 3:
                # No bench repeats
                problem += (
                    pulp.lpSum(variables[i] for i, M in enumerate(matchups) if M[position] == team)
                    <= 1
                )

            elif n_matches_per_team % 3 == 0:
                # Each team must visit each bench exactly (n_matches_per_team // 3) times
                problem += pulp.lpSum(
                    variables[i] for i, M in enumerate(matchups) if M[position] == team
                ) == (n_matches_per_team // 3)

            else:
                # Calculate base visits and extra visits
                base_visits = n_matches_per_team // 3
                extra_visits = n_matches_per_team % 3

                # Ensure each team visits each bench at least base_visits times
                problem += (
                    pulp.lpSum(variables[i] for i, M in enumerate(matchups) if M[position] == team)
                    >= base_visits
                )

                # Ensure no team visits any bench more than base_visits + 1 times
                problem += (
                    pulp.lpSum(variables[i] for i, M in enumerate(matchups) if M[position] == team)
                    <= base_visits + 1
                )

    return problem


def enforce_unique_opponents_constraint(
    problem: pulp.LpProblem, variables: pulp.LpVariable, matchups: list, n_teams
) -> pulp.LpProblem:
    # No team faces the same opponent more than once
    for team1 in range(1, n_teams + 1):
        for team2 in range(team1 + 1, n_teams + 1):
            problem += (
                pulp.lpSum(
                    variables[i] for i, M in enumerate(matchups) if team1 in M and team2 in M
                )
                <= 1
            )

    return problem


def enforce_each_matchup_must_occur_once(
    problem: pulp.LpProblem,
    variables: pulp.LpVariable,
    matchups: list,
    n_rooms: int,
    n_time_slots: int,
) -> pulp.LpProblem:
    for i in range(len(matchups)):
        problem += (
            pulp.lpSum(
                variables[i][j][k]
                for j in range(1, n_rooms + 1)
                for k in range(1, n_time_slots + 1)
            )
            == 1
        )
    return problem


def enforce_each_room_to_host_single_matchup_per_time_slot(
    problem: pulp.LpProblem,
    variables: pulp.LpVariable,
    matchups: list,
    n_rooms: int,
    n_time_slots: int,
) -> pulp.LpProblem:
    for j in range(1, n_rooms + 1):
        for k in range(1, n_time_slots + 1):
            problem += pulp.lpSum(variables[i][j][k] for i in range(len(matchups))) <= 1
    return problem


def limit_consecutive_matchups(
    problem: pulp.LpProblem,
    variables: pulp.LpVariable,
    matchups: list,
    n_teams: int,
    n_rooms: int,
    n_time_slots: int,
) -> pulp.LpProblem:
    # No team can have matches in 3 consecutive time slots
    for team in range(1, n_teams + 1):

        # Avoid the last two time slots since we're checking triplets
        for k in range(1, n_time_slots - 1):

            # For every triplet of time slots (k, k+1, k+2), team cannot be scheduled in all three
            problem += (
                pulp.lpSum(
                    variables[i][j][k] + variables[i][j][k + 1] + variables[i][j][k + 2]
                    for i, matchup in enumerate(matchups)
                    if team in matchup
                    for j in range(1, n_rooms + 1)
                )
                <= 2
            )  # At most 2 out of the 3 consecutive time slots
    return problem


def enforce_room_diversity_for_each_teams_matchups(
    problem: pulp.LpProblem,
    variables: pulp.LpVariable,
    matchups: list,
    n_teams: int,
    n_rooms: int,
    n_time_slots: int,
    n_matches_per_team: int,
) -> pulp.LpProblem:

    # Each team must visit different rooms across all time slots
    for team in range(1, n_teams + 1):
        problem += (
            pulp.lpSum(
                variables[i][j][k]
                for i, matchup in enumerate(matchups)
                for j in range(1, n_rooms + 1)
                for k in range(1, n_time_slots + 1)
                if team in matchup
            )
            == n_matches_per_team
        )  # expected number of matches per team

        # Ensure a team isn't scheduled in the same room more than once
        for j in range(1, n_rooms + 1):
            problem += (
                pulp.lpSum(
                    variables[i][j][k]
                    for i, matchup in enumerate(matchups)
                    for k in range(1, n_time_slots + 1)
                    if team in matchup
                )
                <= 1
            )  # Team can appear at most once in room j
    return problem


def enforce_no_simultaneous_scheduling_for_each_team(
    problem: pulp.LpProblem,
    variables: pulp.LpVariable,
    matchups: list,
    n_teams: int,
    n_rooms: int,
    n_time_slots: int,
) -> pulp.LpProblem:

    for k in range(1, n_time_slots + 1):
        for team in range(1, n_teams + 1):
            problem += (
                pulp.lpSum(
                    variables[i][j][k]
                    for i, matchup in enumerate(matchups)
                    for j in range(1, n_rooms + 1)
                    if team in matchup
                )
                <= 1
            )
    return problem


def attempt_schedule(
    matchups: list,
    n_teams: int,
    n_matches_per_team: int,
    n_rooms: int,
    n_time_slots: int,
    relax_constraints: list = [],
) -> Union[pd.DataFrame, None]:

    prob = pulp.LpProblem("Quiz_Scheduling_With_Rooms", pulp.LpMaximize)

    # Define binary variables for matchups in room j at time k
    x = pulp.LpVariable.dicts(
        "MatchupRoomTime",
        (range(len(matchups)), range(1, n_rooms + 1), range(1, n_time_slots + 1)),
        cat=pulp.LpBinary,
    )

    # Constraints
    prob = enforce_each_matchup_must_occur_once(
        problem=prob, variables=x, matchups=matchups, n_rooms=n_rooms, n_time_slots=n_time_slots
    )
    prob = enforce_each_room_to_host_single_matchup_per_time_slot(
        problem=prob, variables=x, matchups=matchups, n_rooms=n_rooms, n_time_slots=n_time_slots
    )
    prob = enforce_no_simultaneous_scheduling_for_each_team(
        problem=prob,
        variables=x,
        matchups=matchups,
        n_teams=n_teams,
        n_rooms=n_rooms,
        n_time_slots=n_time_slots,
    )
    if "consecutive_matches" not in relax_constraints:
        prob = limit_consecutive_matchups(
            problem=prob,
            variables=x,
            matchups=matchups,
            n_teams=n_teams,
            n_rooms=n_rooms,
            n_time_slots=n_time_slots,
        )
    if "room_diversity" not in relax_constraints:
        prob = enforce_room_diversity_for_each_teams_matchups(
            problem=prob,
            variables=x,
            matchups=matchups,
            n_teams=n_teams,
            n_rooms=n_rooms,
            n_time_slots=n_time_slots,
            n_matches_per_team=n_matches_per_team,
        )

    prob.solve()
    return prob


def schedule_matches(
    matchups: list, n_teams: int, n_matches_per_team: int, n_rooms: int, n_time_slots: int
) -> Union[pd.DataFrame, List[str]]:
    """
    Schedule matches into n_rooms and n_time_slots, ensuring constraints are met.
    If not possible, relax constraints and inform the user.

    Parameters:
        matchups (list): The list of valid matchups (triples).
        n_teams (int): The number of teams.
        n_matches_per_team (int): The number of matches per team.
        n_rooms (int): The number of rooms available.
        n_time_slots (int): The total number of time slots available.

    Returns:
        pulp.LpProblem: The PuLP problem after solving.
    """
    # Problem setup

    constraints_relaxed = []

    prob = attempt_schedule(
        matchups=matchups,
        n_teams=n_teams,
        n_matches_per_team=n_matches_per_team,
        n_rooms=n_rooms,
        n_time_slots=n_time_slots,
    )

    if pulp.LpStatus[prob.status] == "Optimal":
        print("Solution found!")
    else:
        constraints_to_relax = ["room_diversity", "consecutive_matches"]
        for constraint in constraints_to_relax:
            constraints_relaxed.append(constraint)
            prob = attempt_schedule(
                matchups=matchups,
                n_teams=n_teams,
                n_matches_per_team=n_matches_per_team,
                n_rooms=n_rooms,
                n_time_slots=n_time_slots,
                relax_constraints=constraints_relaxed,
            )
            if pulp.LpStatus[prob.status] == "Optimal":
                break
        else:
            print("No feasible solution found even after relaxing constraints.")
            return None, constraints_relaxed

    solution_variables = {v.name: v.varValue for v in prob.variables() if v.varValue == 1}
    formatted_solution = format_schedule_output(
        solution=solution_variables, matchups=matchups, n_rooms=n_rooms, n_time_slots=n_time_slots
    )

    return formatted_solution, constraints_relaxed


def format_schedule_output(
    solution: Dict[str, float],
    matchups: List[Tuple[int, int, int]],
    n_rooms: int,
    n_time_slots: int,
):
    """
    Converts the raw schedule solution into a pandas DataFrame with readable columns.

    Parameters:
    - solution: dict of decision variables from the optimization, e.g., { 'MatchupRoomTime_0_4_5': 1.0 }
    - matchups: List of tuples representing team matchups (triples).
    - K_rooms: Number of rooms.
    - n_time_slots: Number of time slots.

    Returns:
    - pandas DataFrame with columns [Matchup, Room, TimeSlot]
    """

    data = []

    for key, value in solution.items():
        if value == 1.0:
            parts = key.split("_")

            matchup_idx = int(parts[1])
            room = int(parts[2])
            time_slot = int(parts[3])

            matchup = matchups[matchup_idx]

            data.append((time_slot, room, matchup))

    # Create a DataFrame
    df = pd.DataFrame(data, columns=["TimeSlot", "Room", "Matchup"])
    df.sort_values(["TimeSlot", "Room"], inplace=True)
    df.reset_index(drop=True, inplace=True)

    return df


################################################################################

n_teams = 7
n_matches_per_team = 3
n_time_slots = 7
n_rooms = 3

all_possible_matchups = generate_all_possible_matchups(n_teams=n_teams)

matchup_solutions = find_matchup_solutions(
    n_teams=n_teams,
    n_matches_per_team=n_matches_per_team,
    matchups=all_possible_matchups,
    max_solutions=1,
)
for i, proposed_matchups in enumerate(matchup_solutions):

    valid_matchups = check_matchups(
        solution=proposed_matchups, n_teams=n_teams, n_matches_per_team=n_matches_per_team
    )
    if valid_matchups:
        try:
            df_schedule, constraints_relaxed = schedule_matches(
                matchups=proposed_matchups,
                n_teams=n_teams,
                n_matches_per_team=n_matches_per_team,
                n_rooms=n_rooms,
                n_time_slots=n_time_slots,
            )
            if df_schedule is not None:
                check_schedule(
                    df_schedule=df_schedule,
                    n_teams=n_teams,
                    n_rooms=n_rooms,
                    n_time_slots=n_time_slots,
                )
                if constraints_relaxed:
                    print(f"Constraints relaxed: {', '.join(constraints_relaxed)}")
                else:
                    print("All constraints satisfied")
                break
        except Exception as e:
            print(f"Scheduling of proposed matchups set {i + 1} is infeasible. " f" Error: {e}")
            continue
