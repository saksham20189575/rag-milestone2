from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes.chat import router as chat_router

app = FastAPI(
    title="Mutual Fund FAQ Assistant",
    description="Facts-only FAQ assistant for HDFC mutual fund schemes.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(chat_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
