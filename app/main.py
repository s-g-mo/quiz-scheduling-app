import os
import traceback
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.matchups import MatchupSolver
from app.scheduler import ScheduleSolver
from app.models import (
    MatchupsRequest,
    MatchupsResponse,
    Matchup,
    ScheduleRequest,
    ScheduleResponse,
    ScheduleItem,
)

app = FastAPI(
    title="Quiz Schedule Generator API",
    description="API to generate valid quiz schedules based on input parameters",
    version="1.0.0",
    contact={
        "name": "Stephen Mosher",
        "url": "https://github.com/s-g-mo",
        "contact": "email@example.com",
    },
)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
async def read_index():
    return FileResponse(os.path.join("app/static", "index.html"))


@app.post("/generate-matchups/", tags=["Matchups"])
async def generate_matchups(request: MatchupsRequest) -> MatchupsResponse:
    try:
        matchups_solver = MatchupSolver(
            n_teams=request.n_teams, n_matches_per_team=request.n_matches_per_team
        )

        all_possible_matchups = matchups_solver.generate_all_possible_matchups()
        matchup_solutions = matchups_solver.find_matchup_solutions(
            matchups=all_possible_matchups, max_solutions=request.n_matchup_solutions
        )
        if matchup_solutions:
            for matchup_solution in matchup_solutions:
                matchups_solver.check_matchups(matchup_solution)
            solutions = {
                f"solution_set_{i+1}": [Matchup(teams=tuple(matchup)) for matchup in solution]
                for i, solution in enumerate(matchup_solutions)
            }

            return MatchupsResponse(solutions=solutions)
        else:
            return MatchupsResponse(solutions={})
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate-schedule/", tags=["Schedule"])
async def generate_schedule(request: ScheduleRequest) -> ScheduleResponse:
    try:
        schedule_solver = ScheduleSolver(
            n_teams=request.n_teams,
            n_matches_per_team=request.n_matches_per_team,
            n_rooms=request.n_rooms,
            n_time_slots=request.n_time_slots,
        )
        matchups_request = MatchupsRequest(
            n_teams=request.n_teams,
            n_matches_per_team=request.n_matches_per_team,
            n_matchup_solutions=1,
        )
        matchups_response = await generate_matchups(request=matchups_request)

        for proposed_matchups in matchups_response.solutions.values():
            schedule, constraints_relaxed = schedule_solver.schedule_matches(proposed_matchups)
            if schedule is not None:
                schedule_solver.check_schedule(schedule)
                schedule_items = [
                    ScheduleItem(
                        TimeSlot=row["TimeSlot"],
                        Room=row["Room"],
                        Matchup=row["Matchup"],
                    )
                    for _, row in schedule.iterrows()
                ]
                return ScheduleResponse(
                    schedule=schedule_items, constraints_relaxed=constraints_relaxed
                )
        raise HTTPException(status_code=404, detail="No valid schedule found")
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
