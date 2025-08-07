import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Stub external dependencies not required for this test
sys.modules.setdefault("openai", types.ModuleType("openai"))
sys.modules.setdefault("docx2txt", types.ModuleType("docx2txt"))
pdfminer = types.ModuleType("pdfminer")
pdf_high = types.ModuleType("pdfminer.high_level")
pdf_high.extract_text = lambda *a, **k: ""
pdfminer.high_level = pdf_high
sys.modules["pdfminer"] = pdfminer
sys.modules["pdfminer.high_level"] = pdf_high
sys.modules.setdefault("streamlit", types.ModuleType("streamlit"))

import core


def test_extraer_caratula_expte_sac():
    texto = 'Leiva David p. s. a. de “robo en grado de tentativa” (Expte. Sac 13250038)'
    esperado = 'Leiva David p. s. a. de “robo en grado de tentativa” (SAC N° 13250038)'
    assert core.extraer_caratula(texto) == esperado