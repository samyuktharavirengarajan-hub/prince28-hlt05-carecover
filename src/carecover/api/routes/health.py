from fastapi import APIRouter, Response

from carecover.api.deps import DbCheckDep, SettingsDep

router = APIRouter(tags=["health"])


@router.get("/health")
def health(settings: SettingsDep) -> dict[str, str]:
    """Liveness: is the application process alive?"""
    return {
        "status": "ok",
        "app": settings.app_name,
        "env": settings.app_env,
    }


@router.get("/ready")
def ready(db_ok: DbCheckDep, response: Response) -> dict:
    """Readiness: can this instance connect to PostgreSQL?"""
    checks = {"database": db_ok}
    if not db_ok:
        response.status_code = 503

    return {
        "status": "ready" if db_ok else "not_ready",
        "checks": checks,
    }
