import sys
from pathlib import Path
import json
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytest.importorskip("streamlit")

import core


def test_procesar_sentencia_sanitizes_caratula(monkeypatch):
    texto = (
        "JUZGADO DE CONTROL Y FALTAS Nº 8 Protocolo de Sentencias Nº Resolución: 1 Año: 2025 "
        "Tomo: 1 Folio: 1-8 EXPEDIENTE SAC: 13250038 - LEIVA DAVID P.S.A DE ROBO EN GRADO DE TENTATIVA - "
        "CAUSA CON IMPUTADOS PROTOCOLO DE SENTENCIAS. NÚMERO: 1 DEL 05/02/2025 Córdoba, cinco de febrero de "
        "dos mil veinticinco. VISTOS: los autos caratulados Leiva David p. s. a. de \"robo en grado de tentativa\" "
        "(SAC N° 13250038)"
    )

    expected = core.extraer_caratula(texto)

    # Avoid filesystem operations and external services
    monkeypatch.setattr(core, "_bytes_a_tmp", lambda data, suf: type("Tmp", (), {"unlink": lambda self, **kw: None})())
    monkeypatch.setattr(core.docx2txt, "process", lambda path: texto)
    monkeypatch.setattr(core, "limpiar_pies", lambda txt: txt)

    class DummyRsp:
        choices = [type("Choice", (), {"message": type("Msg", (), {"content": json.dumps({
            "generales": {"caratula": texto},
            "imputados": []
        })})})]

    class DummyCompletions:
        @staticmethod
        def create(**kwargs):
            return DummyRsp()

    class DummyChat:
        completions = DummyCompletions()

    class DummyClient:
        chat = DummyChat()

    monkeypatch.setattr(core, "_get_openai_client", lambda: DummyClient())

    datos = core.procesar_sentencia(b"", "dummy.docx")

    assert datos["generales"]["caratula"] == expected
