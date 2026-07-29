from fastapi import FastAPI

from api.routers import tasks

app = FastAPI(title="Crowdwork Platform API")

app.include_router(tasks.router)


@app.get("/health")
def health_check():
    """Quick endpoint to confirm the API is alive."""
    return {"status": "ok"}