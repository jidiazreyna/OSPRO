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

def test_segmenta_dos_imputados_y_extrae_dni():
    texto = (
        "Saúl Maximiliano Agüero, de 20 años de edad, DNI n.° 52.053.434, domiciliado en calle Bilbao n.° 2832. "
        "Prio. Policial AG AG- 1319566 AG- 1381005. "
        "E Imanol Andrés Urán, de 25 años de edad, DNI n.° 42.440.252, domiciliado en calle Manuel Astrada n.° 1488."
    )
    bloques = core.segmentar_imputados(texto)
    assert len(bloques) == 2
    dp1 = core.extraer_datos_personales(bloques[0])
    dp2 = core.extraer_datos_personales(bloques[1])
    assert dp1["nombre"] == "Saúl Maximiliano Agüero"
    assert dp1["dni"] == "52053434"
    assert dp2["nombre"] == "Imanol Andrés Urán"
    assert dp2["dni"] == "42440252"
