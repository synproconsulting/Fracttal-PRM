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


@app.get("/")
def root():
    return {"message": "Fracttal PRM API", "version": "0.1.0"}
