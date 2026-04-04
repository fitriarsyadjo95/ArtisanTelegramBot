from fastapi import FastAPI

app = FastAPI(title="Blackgrid Bot")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "blackgrid-bot"}
