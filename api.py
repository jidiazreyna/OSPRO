# api.py
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import Response
import core

app = FastAPI(title="Generador OSPRO")

@app.post("/autocompletar")
async def autocompletar(file: UploadFile = File(...)):
    try:
        datos = core.procesar_sentencia(await file.read(), file.filename)
        return datos
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/oficios")
async def oficios(payload: dict):
    try:
        docx_bytes = core.generar_oficios(payload)
        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": 'attachment; filename="oficios.docx"'
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
