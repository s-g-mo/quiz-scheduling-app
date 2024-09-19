import itertools
from typing import List, Tuple
import pulp
import numpy as np


class MatchupSolver:
    def __init__(self, n_teams: int, n_matches_per_team: int):
        self.n_teams = n_teams
        self.n_matches_per_team = n_matches_per_team

    def generate_all_possible_matchups(self) -> List[Tuple[int, int, int]]:
        teams = list(range(1, self.n_teams + 1))
        all_triples = list(itertools.combinations(teams, 3))
        possible_matchups = []
        for triple in all_triples:
            for perm in itertools.permutations(triple):
                possible_matchups.append(perm)
        return possible_matchups

    def find_matchup_solutions(
        self, matchups: List[Tuple[int, int, int]], max_solutions: int = 10
    ) -> List[np.ndarray]:
        """
        Generates matchup solutions based on the number of teams, the number of matches played by
        each team, and the matchup constraints.

        Args:
            matchups: A list of tuples representing possible team matchups.
            max_solutions: Maximum number of solutions to return.

        Returns:
            A list of numpy arrays where each array contains a valid set of matchups that satisfy
            the given constraints.
        """

        self._validate_inputs()

        solutions = []
        problem = pulp.LpProblem("Quiz_Scheduling", sense=pulp.LpMaximize)
        variables = pulp.LpVariable.dicts("Matchup", (range(len(matchups))), cat=pulp.LpBinary)

        self.enforce_constraints(problem, variables, matchups)

        while len(solutions) < max_solutions:
            problem.solve()
            if pulp.LpStatus[problem.status] == "Optimal":
                solution = [i for i in range(len(matchups)) if variables[i].varValue == 1]
                selected_matchups = [matchups[i] for i in solution]
                solutions.append(np.array(selected_matchups))
                problem += pulp.lpSum(variables[i] for i in solution) <= len(solution) - 1
            else:
                break

        return solutions

    def check_matchups(self, solution: np.array) -> bool:
        print(solution)
        is_solution = True

        for team in range(1, self.n_teams + 1):
            team_filter = solution == team

            # Check to ensure each team has exactly n_matches_per_team
            if team_filter.sum() != self.n_matches_per_team:
                print(
                    f"Team {team} has {team_filter.sum()} matches, expected"
                    f"{self.n_matches_per_team}."
                )
                is_solution = False

            # Check bench constraints
            base_visits = self.n_matches_per_team // 3
            bench_counts = team_filter.sum(axis=0)

            # Ensure each team visits each bench position at least base_visits times
            if (bench_counts < base_visits).any():
                print(
                    f"Team {team} does not visit each bench position at least",
                    f"{base_visits} times.",
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

            if number_unique_opponents != self.n_matches_per_team * 2:
                print(
                    f"Team {team} has {self.n_matches_per_team * 2} opponents, but found"
                    f"{number_unique_opponents} unique opponents."
                )
                is_solution = False

        print(f"Valid Matchups?: {is_solution}")
        print()
        return is_solution

    def enforce_constraints(
        self,
        problem: pulp.LpProblem,
        variables: pulp.LpVariable,
        matchups: List[Tuple[int, int, int]],
    ) -> None:
        problem = self._enforce_each_team_in_exactly_n_matches_per_team(
            problem, variables, matchups
        )
        problem = self._enforce_unique_opponents_constraint(problem, variables, matchups)
        problem = self._enforce_bench_constraints(problem, variables, matchups)

    def _enforce_each_team_in_exactly_n_matches_per_team(
        self, problem: pulp.LpProblem, variables: pulp.LpVariable, matchups: list
    ) -> pulp.LpProblem:
        for team in range(1, self.n_teams + 1):
            problem += (
                pulp.lpSum(variables[i] for i, M in enumerate(matchups) if team in M)
                == self.n_matches_per_team
            )
        return problem

    def _enforce_bench_constraints(
        self, problem: pulp.LpProblem, variables: pulp.LpVariable, matchups: list
    ) -> pulp.LpProblem:
        for team in range(1, self.n_teams + 1):
            for position in range(3):
                if self.n_matches_per_team < 3:
                    problem += (
                        pulp.lpSum(
                            variables[i] for i, M in enumerate(matchups) if M[position] == team
                        )
                        <= 1
                    )
                elif self.n_matches_per_team % 3 == 0:
                    problem += pulp.lpSum(
                        variables[i] for i, M in enumerate(matchups) if M[position] == team
                    ) == (self.n_matches_per_team // 3)
                else:
                    base_visits = self.n_matches_per_team // 3
                    problem += (
                        pulp.lpSum(
                            variables[i] for i, M in enumerate(matchups) if M[position] == team
                        )
                        >= base_visits
                    )
                    problem += (
                        pulp.lpSum(
                            variables[i] for i, M in enumerate(matchups) if M[position] == team
                        )
                        <= base_visits + 1
                    )
        return problem

    def _enforce_unique_opponents_constraint(
        self, problem: pulp.LpProblem, variables: pulp.LpVariable, matchups: list
    ) -> pulp.LpProblem:
        for team1 in range(1, self.n_teams + 1):
            for team2 in range(team1 + 1, self.n_teams + 1):
                problem += (
                    pulp.lpSum(
                        variables[i] for i, M in enumerate(matchups) if team1 in M and team2 in M
                    )
                    <= 1
                )
        return problem

    def _validate_inputs(self):
        if self.n_matches_per_team % 3 == 0:
            assert self.n_teams > 2 * self.n_matches_per_team, (
                f"It is impossible to generate valid matchups if n_matches_per_team "
                f"is a multiple of 3 and n_teams <= 2 * n_matches_per_team. "
                f"Current values: n_matches_per_team = {self.n_matches_per_team}, "
                f"n_teams = {self.n_teams}"
            )
        else:
            assert (
                self.n_teams % 3 == 0
            ), "If n_matches_per_team is not a multiple of 3, n_teams must be a multiple of 3."
            assert self.n_teams >= 2 * self.n_matches_per_team, (
                f"If n_matches_per_team is not a multiple of 3, n_teams must also be greater than "
                f"or equal to 2 * n_matches_per_team. Current values: n_matches_per_team = "
                f"{self.n_matches_per_team}, n_teams = {self.n_teams}"
            )
