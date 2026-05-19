import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv

from rate_limiter import limiter
from routers.health import router as health_router
from routers.auth_router import router as auth_router
from routers.admin_router import router as admin_router
from routers.partners_router import router as partners_router
from routers.partner_profiles_router import router as partner_profiles_router
from routers.documents_router import router as documents_router
from routers.partner_users_router import router as partner_users_router
from routers.activities_router import router as activities_router
from routers.config_router import router as config_router
from routers.applications_router import router as applications_router
from routers.deal_registrations_router import router as deal_registrations_router
from routers.dashboard_router import router as dashboard_router
from routers.internal_users_router import router as internal_users_router
from routers.internal_partner_users_router import router as internal_partner_users_router
from routers.internal_partners_router import router as internal_partners_router
from routers.program_config_router import router as program_config_router

load_dotenv()

app = FastAPI(
    title="Fracttal PRM API",
    description="Partner Relationship Management System",
    version="0.1.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "*")],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(partners_router)
app.include_router(partner_profiles_router)
app.include_router(documents_router)
app.include_router(partner_users_router)
app.include_router(activities_router)
app.include_router(config_router)
app.include_router(applications_router)
app.include_router(deal_registrations_router)
app.include_router(dashboard_router)
app.include_router(internal_users_router)
app.include_router(internal_partner_users_router)
app.include_router(internal_partners_router)
app.include_router(program_config_router)


@app.get("/")
def root():
    return {"message": "Fracttal PRM API", "version": "0.1.0"}
