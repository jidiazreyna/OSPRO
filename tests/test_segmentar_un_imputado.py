import sys
from pathlib import Path
import types

# Ensure repository root on path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Stubs for optional dependencies used by core.py
sys.modules['docx2txt'] = types.ModuleType('docx2txt')
sys.modules['docx2txt'].process = lambda *a, **k: ''
sys.modules['openai'] = types.ModuleType('openai')
st = types.ModuleType('streamlit')
st.session_state = {}
sys.modules['streamlit'] = st
pdfminer = types.ModuleType('pdfminer')
high = types.ModuleType('pdfminer.high_level')
high.extract_text = lambda *a, **k: ''
pdfminer.high_level = high
sys.modules['pdfminer'] = pdfminer
sys.modules['pdfminer.high_level'] = high

import core

def test_segmenta_un_imputado_y_extrae_datos():
    texto = (
        "y del imputado  Mario David Dante Leiva, de 34 años de edad, DNI: 35.474.051, alias "
        "“asque”, de nacionalidad argentina, de estado civil soltero, de ocupación albañil, instrucción "
        "primario completo, domiciliado en Manzana 6 lote 5, de barrio Nuestro Hogar I, de ésta ciudad Córdoba. "
        "Nacido el 07/12/1990, en la ciudad de Córdoba Capital, hijo de Dante Mario Leiva (v) y de Nora del Carmen Guzmán (v). "
        "Prio. AG 1097617 y 1097639;"
    )
    bloques = core.segmentar_imputados(texto)
    assert len(bloques) == 1
    dp = core.extraer_datos_personales(bloques[0])
    assert dp["nombre"] == "Mario David Dante Leiva"
    assert dp["dni"] == "35474051"
    assert dp.get("alias") == "asque"
    assert dp.get("prio") == "AG 1097617 y 1097639"
    assert dp.get("fecha_nacimiento") == "07/12/1990"
