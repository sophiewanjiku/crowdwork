from fastapi import FastAPI

from api.routers import tasks, auth, assignments, wallet

app = FastAPI(title="Crowdwork Platform API")

app.include_router(tasks.router)
app.include_router(auth.router)
app.include_router(assignments.router)
app.include_router(wallet.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}