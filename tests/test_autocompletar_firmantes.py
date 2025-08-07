import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytest.importorskip("streamlit")

import streamlit as st
import core


def test_autocompletar_converts_firmantes_to_string(monkeypatch):
    st.session_state.clear()

    def fake_procesar_sentencia(_bytes, _name):
        return {
            "generales": {"firmantes": ["Juez", "Secretario"]},
            "imputados": [],
        }

    monkeypatch.setattr(core, "procesar_sentencia", fake_procesar_sentencia)

    core.autocompletar(b"", "dummy.pdf")

    assert st.session_state.sfirmaza == "Juez, Secretario"


def test_autocompletar_handles_dict_firmantes(monkeypatch):
    st.session_state.clear()

    def fake_procesar_sentencia(_bytes, _name):
        return {
            "generales": {
                "firmantes": [
                    {"nombre": "Ana Perez", "cargo": "Jueza"},
                    {"nombre": "Luis Gomez", "cargo": "Secretario"},
                ]
            },
            "imputados": [],
        }

    monkeypatch.setattr(core, "procesar_sentencia", fake_procesar_sentencia)

    core.autocompletar(b"", "dummy.pdf")

    assert st.session_state.sfirmaza == "Ana Perez, Jueza; Luis Gomez, Secretario"
