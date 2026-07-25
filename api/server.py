from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import sqlite3
from uvicorn import run

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.post("/chat")
async def chat(request: Request):
    data = await request.json()
    message = data["message"]
    # Traitement du message ici...
    response = {"response": "Réponse au message", "status": "ok"}
    return JSONResponse(content=response, media_type="application/json")

@app.get("/history")
async def history():
    conn = sqlite3.connect("orion.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM conversations")
    rows = cur.fetchall()
    conn.close()
    historique = [{"message": row[1], "response": row[2]} for row in rows]
    return JSONResponse(content=historique, media_type="application/json")

@app.get("/status")
async def status():
    response = {"status": "running", "version": "0.1"}
    return JSONResponse(content=response, media type="application/json")

if __name__ == "__main__":
    run("api.server:app", host="0.0.0.0", port=8000)
