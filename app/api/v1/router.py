from fastapi import APIRouter
from app.api.v1.alerts import router as alerts_router
from app.api.v1.auth import router as auth_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.devices import router as devices_router
from app.api.v1.telemetry import router as telemetry_router
from app.api.v1.organizations import router as organizations_router
from app.api.v1.sites import router as sites_router
from app.api.v1.device_types import router as device_types_router
from app.api.v1.alert_rules import router as alert_rules_router
from app.api.v1.anomalies import router as anomalies_router
from app.api.v1.analytics import router as analytics_router

api_v1_router = APIRouter()

api_v1_router.include_router(auth_router)
api_v1_router.include_router(devices_router)
api_v1_router.include_router(telemetry_router)
api_v1_router.include_router(alerts_router)
api_v1_router.include_router(dashboard_router)
api_v1_router.include_router(organizations_router)
api_v1_router.include_router(sites_router)
api_v1_router.include_router(device_types_router)
api_v1_router.include_router(alert_rules_router)
api_v1_router.include_router(anomalies_router)
api_v1_router.include_router(analytics_router)