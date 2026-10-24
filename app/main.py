from fastapi import FastAPI

app = FastAPI(title="HackSphere Microgrid Backend")

@app.get("/api/health")
def health():
    return {"status": "ok"}
