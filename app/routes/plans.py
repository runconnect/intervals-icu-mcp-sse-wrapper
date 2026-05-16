from collections import defaultdict
from datetime import timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from core.client import intervals_get, INTERVALS_ATHLETE_ID
from core.utils import parse_date_value

router = APIRouter()


def resolve_plan_folder_id(items: List[Dict[str, Any]], plan_name: str) -> Optional[int]:
    for item in items:
        if item.get("type") == "PLAN" and item.get("name") == plan_name:
            plan_id = item.get("id")
            if isinstance(plan_id, int):
                return plan_id
    return None


@router.get(
    "/plan-workouts/filtered",
    operation_id="get_plan_workouts_filtered",
    tags=["plans"],
    summary="Filtre les workouts d'un plan",
)
async def get_plan_workouts_filtered(
    plan_name: str = Query(..., description="Nom logique du plan, ex: Plan_Semi"),
    plan_start: str = Query(..., description="Date de début du plan (YYYY-MM-DD)"),
    include_types: Optional[str] = Query(
        None,
        description="Liste de types à inclure, séparés par des virgules, ex: Run,Swim,VirtualRide",
    ),
    exclude_types: Optional[str] = Query(
        None,
        description="Liste de types à exclure, séparés par des virgules, ex: NOTE",
    ),
    folder_id: Optional[int] = Query(
        None,
        description="ID du dossier/plan Intervals.icu. Si absent, déduit dynamiquement de plan_name",
    ),
    max_day: Optional[int] = Query(
        None,
        description="Jour max relatif au plan (optionnel, ex: 96)",
    ),
    return_workouts: bool = Query(
        True,
        description="Si false, ne renvoie que les compteurs/summary",
    ),
):
    folders: List[Dict[str, Any]] = await intervals_get(
        f"/athlete/{INTERVALS_ATHLETE_ID}/folders",
        params=None,
    )

    folder = folder_id if folder_id is not None else resolve_plan_folder_id(folders, plan_name)
    if folder is None:
        raise HTTPException(
            status_code=404,
            detail=f"Plan '{plan_name}' introuvable dans les {len(folders)} éléments.",
        )

    raw_items: List[Dict[str, Any]] = await intervals_get(
        f"/athlete/{INTERVALS_ATHLETE_ID}/workouts",
        params={"folder_id": folder},
    )

    plan_start_date = parse_date_value(plan_start)
    if not plan_start_date:
        raise HTTPException(status_code=400, detail="plan_start doit être au format YYYY-MM-DD")

    include_set = {t.strip() for t in include_types.split(",")} if include_types else None
    exclude_set = {t.strip() for t in exclude_types.split(",")} if exclude_types else set()

    normalized: List[Dict[str, Any]] = []
    min_day = None
    max_day_seen = None

    for w in raw_items:
        w_folder = w.get("folder_id") or w.get("folderid")
        if w_folder != folder:
            continue

        day = w.get("day")
        if day is None:
            continue

        if max_day is not None and isinstance(day, int) and day > max_day:
            continue

        w_type = (w.get("type") or "").strip()
        if include_set is not None and w_type not in include_set:
            continue
        if w_type in exclude_set:
            continue

        date_str = (plan_start_date + timedelta(days=day)).isoformat()
        external_id = f"{INTERVALS_ATHLETE_ID}-{folder}-{date_str}-{w_type}"

        item = {
            "athlete_id": INTERVALS_ATHLETE_ID,
            "folderid": folder,
            "day": day,
            "date": date_str,
            "type": w_type,
            "name": w.get("name") or "",
            "description": w.get("description") or "",
            "external_id": external_id,
            "raw_json": w,
            "mirror_seen": True,
        }

        normalized.append(item)

        min_day = day if min_day is None else min(min_day, day)
        max_day_seen = day if max_day_seen is None else max(max_day_seen, day)

    count_by_type: Dict[str, int] = defaultdict(int)
    for item in normalized:
        count_by_type[item["type"] or ""] += 1

    response: Dict[str, Any] = {
        "plan_name": plan_name,
        "folder_id": folder,
        "plan_start": plan_start_date.isoformat(),
        "count": len(normalized),
        "summary": {
            "count_by_type": dict(sorted(count_by_type.items())),
            "min_day": min_day,
            "max_day": max_day_seen,
        },
    }

    if return_workouts:
        response["workouts"] = normalized

    return JSONResponse(content=response)