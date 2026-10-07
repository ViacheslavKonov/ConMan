from fastapi import FastAPI

from app.config import get_settings
from app.routers import admin_data, applications, auth, checkin, core, finance, planning, public, reports, seating, system, users

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="2.0.0-step7",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.include_router(system.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(core.router, prefix="/api")
app.include_router(applications.router, prefix="/api")
app.include_router(finance.router, prefix="/api")
app.include_router(public.router, prefix="/api")
app.include_router(seating.router, prefix="/api")
app.include_router(planning.router, prefix="/api")
app.include_router(checkin.router, prefix="/api")
app.include_router(admin_data.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
