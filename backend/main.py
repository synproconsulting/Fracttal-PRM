import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv

logger = logging.getLogger("fracttal_prm")

from rate_limiter import limiter
from routers.health import router as health_router
from routers.auth_router import router as auth_router
from routers.admin_router import router as admin_router
from routers.partners_router import router as partners_router
from routers.partner_profiles_router import router as partner_profiles_router
from routers.documents_router import router as documents_router, rules_router as document_type_rules_router
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
from routers.reports_router import router as reports_router
from routers.quotes_router import router as quotes_router
from routers.pricing_admin_router import router as pricing_admin_router
from routers.assets_router import router as assets_router
from routers.partner_channel_managers_router import router as partner_channel_managers_router

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

# AD-43 (FPRM-451) — security response-headers baseline. Set centrally on every
# response; never per-router. Hardcoded baseline values (no env var). CORS is
# intentionally NOT touched here (Sprint 25 scope decision).
SECURITY_HEADERS = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    # Baseline CSP for a JSON API that serves no HTML/JS of its own.
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    for header, value in SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
    return response


# S3 (FPRM-453) — generic 500 for UNHANDLED exceptions only. FastAPI's own
# handlers for HTTPException (4xx) and RequestValidationError (422) run first and
# are untouched, so intended detail strings are preserved. The full exception is
# logged server-side; the client only ever sees the generic body.
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(partners_router)
app.include_router(partner_profiles_router)
app.include_router(documents_router)
app.include_router(document_type_rules_router)
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
app.include_router(reports_router)
app.include_router(quotes_router)
app.include_router(pricing_admin_router)
app.include_router(assets_router)
app.include_router(partner_channel_managers_router)


@app.get("/")
def root():
    return {"message": "Fracttal PRM API", "version": "0.1.0"}
