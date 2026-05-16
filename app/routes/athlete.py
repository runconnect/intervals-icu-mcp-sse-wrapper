from typing import Any, Dict, List

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from core.client import intervals_get, INTERVALS_ATHLETE_ID

router = APIRouter()


def _round_if_number(value: Any, digits: int = 1) -> Any:
    return round(value, digits) if isinstance(value, (int, float)) else value


def _format_pace_seconds_per_km(value: Any) -> str | None:
    if not isinstance(value, (int, float)) or value <= 0:
        return None
    minutes = int(value // 60)
    seconds = int(value % 60)
    return f"{minutes}:{seconds:02d} /km"


def build_form_analysis(tsb: Any) -> Dict[str, Any]:
    if not isinstance(tsb, (int, float)):
        return {}

    if tsb > 20:
        return {
            "form_status": "very_fresh",
            "form_description": "Très frais, profil favorable pour une course ou une séance clé.",
        }
    if tsb > 5:
        return {
            "form_status": "recovered",
            "form_description": "Récupéré et prêt pour un entraînement soutenu.",
        }
    if tsb > -10:
        return {
            "form_status": "optimal",
            "form_description": "Zone généralement productive pour l'entraînement.",
        }
    if tsb > -30:
        return {
            "form_status": "fatigued",
            "form_description": "Fatigue en accumulation, récupération à surveiller.",
        }
    return {
        "form_status": "very_fatigued",
        "form_description": "Fatigue élevée, priorité à la récupération.",
    }


def build_ramp_rate_analysis(ramp_rate: Any) -> Dict[str, Any]:
    if not isinstance(ramp_rate, (int, float)):
        return {}

    if ramp_rate > 8:
        return {
            "ramp_rate_status": "high_risk",
            "ramp_rate_description": "Progression de charge très rapide.",
            "ramp_rate_warning": "Réduire la charge pour limiter le risque de surmenage.",
        }
    if ramp_rate > 5:
        return {
            "ramp_rate_status": "caution",
            "ramp_rate_description": "Progression de charge rapide.",
            "ramp_rate_warning": "Surveiller la fatigue et la récupération de près.",
        }
    if ramp_rate > 0:
        return {
            "ramp_rate_status": "good",
            "ramp_rate_description": "Progression de fitness soutenable.",
        }
    if ramp_rate > -5:
        return {
            "ramp_rate_status": "declining",
            "ramp_rate_description": "Fitness légèrement en baisse, compatible avec une phase d'allègement.",
        }
    return {
        "ramp_rate_status": "declining_significantly",
        "ramp_rate_description": "Fitness en baisse marquée.",
    }


def build_training_recommendations(tsb: Any, ramp_rate: Any) -> List[str]:
    if not isinstance(tsb, (int, float)) or not isinstance(ramp_rate, (int, float)):
        return []

    recommendations: List[str] = []

    if tsb < -30:
        recommendations.append("Prévoir des jours faciles ou du repos.")
        recommendations.append("Favoriser la récupération et les intensités basses.")
    elif tsb < -10 and ramp_rate > 5:
        recommendations.append("Mieux équilibrer charge élevée et récupération.")
        recommendations.append("Envisager une semaine allégée prochainement.")
    elif tsb > 5:
        if ramp_rate < 0:
            recommendations.append("Fenêtre favorable pour remonter progressivement la charge.")
            recommendations.append("Ajouter du volume ou une séance qualitative si le contexte le permet.")
        else:
            recommendations.append("Bon niveau de fraîcheur pour une séance clé ou une compétition.")
            recommendations.append("Capacité probable à encaisser du travail soutenu.")
    else:
        recommendations.append("Poursuivre l'approche actuelle avec alternance charge/récupération.")
        recommendations.append("Maintenir l'équilibre entre séances dures et jours faciles.")

    return recommendations


def normalize_athlete_profile(athlete: Dict[str, Any]) -> Dict[str, Any]:
    profile: Dict[str, Any] = {
        "id": athlete.get("id") or INTERVALS_ATHLETE_ID,
        "name": athlete.get("name") or athlete.get("fullname") or "Athlete",
    }

    for src, dst in [
        ("email", "email"),
        ("sex", "sex"),
        ("dob", "dob"),
        ("weight", "weight_kg"),
        ("height", "height_cm"),
    ]:
        if athlete.get(src) is not None:
            profile[dst] = athlete.get(src)

    fitness: Dict[str, Any] = {}
    for src, dst in [
        ("ctl", "ctl"),
        ("atl", "atl"),
        ("tsb", "tsb"),
        ("ramp_rate", "ramp_rate"),
    ]:
        if athlete.get(src) is not None:
            fitness[dst] = _round_if_number(athlete.get(src), 1)

    sports: List[Dict[str, Any]] = []
    sport_settings = athlete.get("sport_settings") or athlete.get("sports") or []

    if isinstance(sport_settings, list):
        for sport in sport_settings:
            if not isinstance(sport, dict):
                continue

            sport_data: Dict[str, Any] = {}
            if sport.get("type"):
                sport_data["type"] = sport.get("type")
            if sport.get("ftp") is not None:
                sport_data["ftp"] = sport.get("ftp")
            if sport.get("fthr") is not None:
                sport_data["fthr"] = sport.get("fthr")
            if sport.get("pace_threshold") is not None:
                pace_threshold = sport.get("pace_threshold")
                sport_data["pace_threshold_seconds_per_km"] = pace_threshold
                formatted = _format_pace_seconds_per_km(pace_threshold)
                if formatted:
                    sport_data["pace_threshold_formatted"] = formatted
            if sport.get("swim_threshold") is not None:
                sport_data["swim_threshold"] = sport.get("swim_threshold")

            if sport_data:
                sports.append(sport_data)

    analysis: Dict[str, Any] = {}
    analysis.update(build_form_analysis(athlete.get("tsb")))
    analysis.update(build_ramp_rate_analysis(athlete.get("ramp_rate")))

    result: Dict[str, Any] = {
        "profile": profile,
        "fitness": fitness,
    }

    if sports:
        result["sports"] = sports
    if analysis:
        result["analysis"] = analysis

    result["raw_json"] = athlete
    return result


def normalize_fitness_summary(athlete: Dict[str, Any]) -> Dict[str, Any]:
    fitness_metrics: Dict[str, Any] = {}

    if athlete.get("ctl") is not None:
        fitness_metrics["ctl"] = {
            "value": _round_if_number(athlete.get("ctl"), 1),
            "description": "Chronic Training Load",
            "explanation": "Charge chronique, reflet approximatif du niveau de fitness.",
        }

    if athlete.get("atl") is not None:
        fitness_metrics["atl"] = {
            "value": _round_if_number(athlete.get("atl"), 1),
            "description": "Acute Training Load",
            "explanation": "Charge aiguë, reflet approximatif de la fatigue récente.",
        }

    if athlete.get("tsb") is not None:
        fitness_metrics["tsb"] = {
            "value": _round_if_number(athlete.get("tsb"), 1),
            "description": "Training Stress Balance",
            "explanation": "Équilibre entre fitness et fatigue, souvent utilisé comme indicateur de forme.",
        }

    if athlete.get("ramp_rate") is not None:
        fitness_metrics["ramp_rate"] = {
            "value": _round_if_number(athlete.get("ramp_rate"), 1),
            "description": "Ramp rate",
            "explanation": "Vitesse d'évolution de la charge chronique.",
        }

    analysis: Dict[str, Any] = {}
    analysis.update(build_form_analysis(athlete.get("tsb")))
    analysis.update(build_ramp_rate_analysis(athlete.get("ramp_rate")))

    recommendations = build_training_recommendations(
        athlete.get("tsb"),
        athlete.get("ramp_rate"),
    )
    if recommendations:
        analysis["recommendations"] = recommendations

    return {
        "athlete_name": athlete.get("name") or athlete.get("fullname") or "Athlete",
        "fitness_metrics": fitness_metrics,
        "analysis": analysis,
        "raw_json": athlete,
    }


@router.get(
    "/athlete/profile",
    operation_id="get_athlete_profile",
    tags=["athlete"],
    summary="Get athlete profile",
    description="Retourne le profil athlète, les métriques de fitness actuelles et les réglages par sport.",
)
async def get_athlete_profile():
    athlete = await intervals_get(f"/athlete/{INTERVALS_ATHLETE_ID}")
    if not isinstance(athlete, dict):
        return JSONResponse(
            status_code=502,
            content={"detail": "Réponse athlète invalide depuis Intervals.icu"},
        )
    return JSONResponse(content=normalize_athlete_profile(athlete))


@router.get(
    "/athlete/fitness",
    operation_id="get_fitness_summary",
    tags=["athlete"],
    summary="Get fitness summary",
    description="Retourne un résumé interprété des métriques CTL, ATL, TSB et ramp rate.",
)
async def get_fitness_summary():
    athlete = await intervals_get(f"/athlete/{INTERVALS_ATHLETE_ID}")
    if not isinstance(athlete, dict):
        return JSONResponse(
            status_code=502,
            content={"detail": "Réponse athlète invalide depuis Intervals.icu"},
        )

    if athlete.get("ctl") is None and athlete.get("atl") is None and athlete.get("tsb") is None:
        return JSONResponse(
            status_code=404,
            content={
                "detail": "Aucune donnée de fitness disponible pour cet athlète."
            },
        )

    return JSONResponse(content=normalize_fitness_summary(athlete))