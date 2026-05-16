import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from routers.health import router as health_router

load_dotenv()

app = FastAPI(
    title="Fracttal PRM API",
    description="Partner Relationship Management System",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "*")],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)


@app.get("/")
def root():
    return {"message": "Fracttal PRM API", "version": "0.1.0"}
