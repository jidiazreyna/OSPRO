import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytest.importorskip("streamlit")

import core


def test_extrae_nombre_y_prontuario_cuando_prio_primero():
    texto = (
        "Prontuario 12345. Juan Perez, de 30 años, D.N.I. 12.345.678. "
        "Prontuario 98765. Carlos Gomez, de 25 años, D.N.I. 98.765.432."
    )

    bloques = core.segmentar_imputados(texto)
    assert len(bloques) == 2

    dp1 = core.extraer_datos_personales(bloques[0])
    dp2 = core.extraer_datos_personales(bloques[1])

    assert dp1["nombre"] == "Juan Perez"
    assert dp1.get("prontuario") == "12345"
    assert dp2["nombre"] == "Carlos Gomez"
    assert dp2.get("prontuario") == "98765"

