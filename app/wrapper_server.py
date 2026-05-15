import os
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi_mcp import FastApiMCP

INTERVALS_API_KEY = os.getenv("INTERVALS_API_KEY")
INTERVALS_ATHLETE_ID = os.getenv("INTERVALS_ATHLETE_ID")
INTERVALS_BASE_URL = "https://intervals.icu/api/v1"

if not INTERVALS_API_KEY or not INTERVALS_ATHLETE_ID:
    raise RuntimeError("INTERVALS_API_KEY et INTERVALS_ATHLETE_ID sont requis")

app = FastAPI(
    title="Intervals.icu MCP HTTP Wrapper",
    version="1.1.0",
    description="Wrapper FastAPI + MCP Streamable HTTP pour Intervals.icu avec outils analytiques",
)


async def intervals_get(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    url = f"{INTERVALS_BASE_URL}{path}"
    cleaned_params = {k: v for k, v in (params or {}).items() if v is not None}
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                url,
                params=cleaned_params,
                auth=("API_KEY", INTERVALS_API_KEY),
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        detail = e.response.text if e.response is not None else str(e)
        raise HTTPException(
            status_code=e.response.status_code if e.response is not None else 502,
            detail=f"Erreur Intervals.icu: {detail}",
        )
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Erreur réseau Intervals.icu: {str(e)}")


async def fetch_activities_range(oldest: Optional[str], newest: Optional[str]) -> List[Dict[str, Any]]:
    data = await intervals_get(
        f"/athlete/{INTERVALS_ATHLETE_ID}/activities",
        params={"oldest": oldest, "newest": newest},
    )
    return data if isinstance(data, list) else []


def parse_date_value(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    raw = value[:10]
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def get_activity_date(activity: Dict[str, Any]) -> Optional[date]:
    for key in ["start_date_local", "start_date", "date", "activity_date"]:
        parsed = parse_date_value(activity.get(key))
        if parsed:
            return parsed
    return None


def is_run_activity(activity: Dict[str, Any]) -> bool:
    candidates = [
        activity.get("type"),
        activity.get("sport"),
        activity.get("activity_type"),
        activity.get("category"),
    ]
    normalized = {str(v).strip().lower() for v in candidates if v is not None}
    return any(v in {"run", "running", "trail run", "trail_running"} for v in normalized)


def get_distance_meters(activity: Dict[str, Any]) -> float:
    for key in ["distance", "distance_meters"]:
        value = activity.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    if isinstance(activity.get("distanceKm"), (int, float)):
        return float(activity["distanceKm"]) * 1000.0
    return 0.0


@app.get("/health", operation_id="health_check", tags=["system"], summary="Health check")
async def health():
    return {
        "status": "ok",
        "service": "intervals-icu-mcp-http-wrapper",
        "mcp_endpoint": "/mcp",
        "athlete_id": INTERVALS_ATHLETE_ID,
        "version": "1.1.0",
    }


@app.get("/", operation_id="root_info", tags=["system"], summary="Root information")
async def root():
    return {
        "name": "Intervals.icu MCP HTTP Wrapper",
        "status": "running",
        "health": "/health",
        "mcp": "/mcp",
        "debug_endpoints": [
            "/activities",
            "/wellness",
            "/events",
            "/activity-streams",
            "/best-efforts",
            "/running-volume-by-week",
        ],
    }


@app.get(
    "/activities",
    operation_id="get_activities",
    tags=["intervals"],
    summary="Get activities",
    description="Retourne les activités Intervals.icu sur une plage de dates ISO optional oldest/newest.",
)
async def get_activities(oldest: Optional[str] = None, newest: Optional[str] = None):
    data = await fetch_activities_range(oldest, newest)
    return JSONResponse(content=data)


@app.get(
    "/wellness",
    operation_id="get_wellness",
    tags=["intervals"],
    summary="Get wellness entries",
    description="Retourne les entrées wellness Intervals.icu sur une plage de dates ISO optional oldest/newest.",
)
async def get_wellness(oldest: Optional[str] = None, newest: Optional[str] = None):
    data = await intervals_get(
        f"/athlete/{INTERVALS_ATHLETE_ID}/wellness",
        params={"oldest": oldest, "newest": newest},
    )
    return JSONResponse(content=data)


@app.get(
    "/events",
    operation_id="get_events",
    tags=["intervals"],
    summary="Get calendar events",
    description="Retourne les événements calendrier Intervals.icu sur une plage de dates ISO optional oldest/newest.",
)
async def get_events(oldest: Optional[str] = None, newest: Optional[str] = None):
    data = await intervals_get(
        f"/athlete/{INTERVALS_ATHLETE_ID}/events",
        params={"oldest": oldest, "newest": newest},
    )
    return JSONResponse(content=data)


@app.get(
    "/activity-streams",
    operation_id="get_activity_streams",
    tags=["analysis"],
    summary="Get activity streams",
    description="Retourne les streams d'une activité (watts, heartrate, cadence, distance, time, altitude, etc.).",
)
async def get_activity_streams(
    activity_id: str = Query(..., description="Identifiant de l'activité Intervals.icu"),
    streams: Optional[str] = Query(None, description="Liste de streams séparés par des virgules, ex: watts,heartrate,cadence"),
):
    params: Dict[str, Any] = {}
    if streams:
        params["streams"] = streams
    data = await intervals_get(f"/activity/{activity_id}/streams", params=params)
    available_streams = [k for k, v in data.items() if isinstance(v, list)] if isinstance(data, dict) else []
    stream_lengths = {k: len(v) for k, v in data.items() if isinstance(v, list)} if isinstance(data, dict) else {}
    result = {
        "activity_id": activity_id,
        "available_streams": available_streams,
        "stream_lengths": stream_lengths,
        "streams": data,
    }
    return JSONResponse(content=result)


@app.get(
    "/best-efforts",
    operation_id="get_best_efforts",
    tags=["analysis"],
    summary="Get best efforts",
    description="Retourne les meilleures performances d'une activité (best efforts) si disponibles via l'API Intervals.icu.",
)
async def get_best_efforts(
    activity_id: str = Query(..., description="Identifiant de l'activité Intervals.icu"),
):
    data = await intervals_get(f"/activity/{activity_id}/best-efforts")
    efforts = data if isinstance(data, list) else []
    normalized: List[Dict[str, Any]] = []
    for effort in efforts:
        item: Dict[str, Any] = {
            "name": effort.get("name"),
            "elapsed_time_seconds": effort.get("elapsed_time"),
            "moving_time_seconds": effort.get("moving_time"),
            "distance_meters": effort.get("distance"),
        }
        performance: Dict[str, Any] = {}
        for src, dst in [
            ("average_watts", "average_watts"),
            ("normalized_power", "normalized_power"),
            ("average_heartrate", "average_heartrate"),
            ("average_cadence", "average_cadence"),
            ("average_speed", "average_speed_meters_per_sec"),
        ]:
            if effort.get(src) is not None:
                performance[dst] = effort.get(src)
        if performance:
            item["performance"] = performance
        if effort.get("start_index") is not None:
            item["start_index"] = effort.get("start_index")
        if effort.get("end_index") is not None:
            item["end_index"] = effort.get("end_index")
        normalized.append(item)
    return JSONResponse(content={"activity_id": activity_id, "count": len(normalized), "best_efforts": normalized})


@app.get(
    "/running-volume-by-week",
    operation_id="get_running_volume_by_week",
    tags=["analysis"],
    summary="Get weekly running volume",
    description="Retourne le volume hebdomadaire de course sur route ou trail par semaine ISO, en kilomètres.",
)
async def get_running_volume_by_week(
    oldest: str = Query(..., description="Date ISO de début incluse, ex: 2026-01-01"),
    newest: str = Query(..., description="Date ISO de fin incluse, ex: 2026-01-31"),
):
    start = parse_date_value(oldest)
    end = parse_date_value(newest)
    if not start or not end:
        raise HTTPException(status_code=400, detail="oldest et newest doivent être des dates ISO valides YYYY-MM-DD")
    if start > end:
        raise HTTPException(status_code=400, detail="oldest doit être antérieure ou égale à newest")

    activities = await fetch_activities_range(oldest, newest)
    weekly = defaultdict(lambda: {"distance_meters": 0.0, "activity_count": 0, "activities": []})
    total_run_activities = 0

    for activity in activities:
        activity_date = get_activity_date(activity)
        if not activity_date or not (start <= activity_date <= end):
            continue
        if not is_run_activity(activity):
            continue
        total_run_activities += 1
        week_start = activity_date - timedelta(days=activity_date.weekday())
        dist_m = get_distance_meters(activity)
        bucket = weekly[week_start.isoformat()]
        bucket["distance_meters"] += dist_m
        bucket["activity_count"] += 1
        bucket["activities"].append(
            {
                "id": activity.get("id"),
                "date": activity_date.isoformat(),
                "name": activity.get("name"),
                "type": activity.get("type") or activity.get("sport") or activity.get("activity_type"),
                "distance_km": round(dist_m / 1000.0, 2),
            }
        )

    weeks = []
    for week_start in sorted(weekly.keys()):
        week_end = date.fromisoformat(week_start) + timedelta(days=6)
        weeks.append(
            {
                "week_start": week_start,
                "week_end": week_end.isoformat(),
                "activity_count": weekly[week_start]["activity_count"],
                "distance_km": round(weekly[week_start]["distance_meters"] / 1000.0, 2),
                "activities": weekly[week_start]["activities"],
            }
        )

    return JSONResponse(
        content={
            "sport": "Run",
            "oldest": oldest,
            "newest": newest,
            "weeks": weeks,
            "summary": {
                "week_count": len(weeks),
                "run_activity_count": total_run_activities,
                "total_distance_km": round(sum(w["distance_km"] for w in weeks), 2),
            },
        }
    )


mcp = FastApiMCP(
    app,
    name="Intervals.icu Tools",
    description="Expose des outils Intervals.icu bruts et analytiques via MCP HTTP transport.",
    include_operations=[
        "get_activities",
        "get_wellness",
        "get_events",
        "get_activity_streams",
        "get_best_efforts",
        "get_running_volume_by_week",
    ],
)

mcp.mount_http(mount_path="/mcp")