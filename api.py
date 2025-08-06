# api.py
from fastapi import FastAPI, UploadFile, File, HTTPException
import core

app = FastAPI(title="Generador OSPRO")

@app.post("/autocompletar")
async def autocompletar(file: UploadFile = File(...)):
    try:
        datos = core.procesar_sentencia(await file.read(), file.filename)
        return datos
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

