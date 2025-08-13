import sys
from pathlib import Path
import types

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Stubs mínimos para módulos opcionales que usa core
sys.modules.setdefault("streamlit", types.SimpleNamespace(session_state={}))
sys.modules.setdefault("docx2txt", types.ModuleType("docx2txt"))
sys.modules.setdefault("openai", types.ModuleType("openai"))
pdf_high = types.ModuleType("pdfminer.high_level")
pdf_high.extract_text = lambda *a, **k: ""
sys.modules.setdefault("pdfminer", types.ModuleType("pdfminer"))
sys.modules.setdefault("pdfminer.high_level", pdf_high)

import core

def test_extrae_nombre_antes_de_dni_sin_edad():
    texto = "Imputado: Juan de la Cruz Pérez, DNI 12.345.678, argentino, soltero"
    dp = core.extraer_datos_personales(texto)
    assert dp["nombre"] == "Juan de la Cruz Pérez"
    assert dp["dni"] == "12345678"
