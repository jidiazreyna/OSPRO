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

def test_lista_enumerada_incompleta_no_trunca():
    texto = (
        "Imputado 1 – Juan Pérez\n"
        "Imputado 2 – María López\n"
        "\n"
        "Juan Pérez, de 30 años de edad, DNI n.° 12.345.678, domiciliado en calle X. Prio. 123. "
        "María López, de 25 años de edad, DNI n.° 98.765.432, domiciliada en calle Y. Prio. 456. "
        "Lucas Gómez, de 27 años de edad, DNI n.° 11.222.333, domiciliado en calle Z."
    )
    bloques = core.segmentar_imputados(texto)
    assert len(bloques) == 3
    nombres = [core.extraer_datos_personales(b)["nombre"] for b in bloques]
    assert nombres == ["Juan Pérez", "María López", "Lucas Gómez"]
