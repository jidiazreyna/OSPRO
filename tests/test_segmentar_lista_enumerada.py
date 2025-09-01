import sys
from pathlib import Path
import types

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Stubs for optional dependencies used by core.py
sys.modules.setdefault("docx2txt", types.ModuleType("docx2txt"))
sys.modules.setdefault("openai", types.ModuleType("openai"))
st = types.ModuleType("streamlit")
st.session_state = {}
sys.modules.setdefault("streamlit", st)
pdfminer = types.ModuleType("pdfminer")
high = types.ModuleType("pdfminer.high_level")
high.extract_text = lambda *a, **k: ""
pdfminer.high_level = high
sys.modules.setdefault("pdfminer", pdfminer)
sys.modules.setdefault("pdfminer.high_level", high)

import core


def test_segmentar_lista_enumerada():
    texto = (
        "Imputado 1 – Juan Pérez\n"
        "Imputada 2 - María López\n"
        "Imputado 3 – Carlos Díaz"
    )
    bloques = core.segmentar_imputados(texto)
    assert bloques == ["Juan Pérez", "María López", "Carlos Díaz"]
    dps = [core.extraer_datos_personales(b) for b in bloques]
    assert [dp.get("nombre") for dp in dps] == ["Juan Pérez", "María López", "Carlos Díaz"]
