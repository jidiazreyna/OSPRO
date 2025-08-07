import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytest.importorskip("streamlit")

import streamlit as st
import core


def test_autocompletar_formats_resuelvo_and_datos(monkeypatch):
    st.session_state.clear()

    def fake_procesar_sentencia(_bytes, _name):
        return {
            "generales": {"resuelvo": ["Punto 1", "Punto 2"]},
            "imputados": [
                {"datos_personales": {"nombre": "Juan Perez", "dni": "12.345"}}
            ],
        }

    monkeypatch.setattr(core, "procesar_sentencia", fake_procesar_sentencia)

    core.autocompletar(b"", "dummy.pdf")

    assert st.session_state.sres == "Punto 1, Punto 2"
    assert st.session_state.imp0_datos == "Juan Perez, D.N.I. 12.345"


def test_autocompletar_flattens_resuelvo_newlines(monkeypatch):
    st.session_state.clear()

    def fake_procesar_sentencia(_bytes, _name):
        return {"generales": {"resuelvo": "Linea 1\nLinea 2"}, "imputados": []}

    monkeypatch.setattr(core, "procesar_sentencia", fake_procesar_sentencia)

    core.autocompletar(b"", "dummy.pdf")

    assert st.session_state.sres == "Linea 1 Linea 2"