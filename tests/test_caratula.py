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


def test_extraer_caratula_sin_parentesis():
    texto = (
        '"Agüero, Saúl Maximiliano y otro p.ss.aa robo calificado por escalamiento, etc." '
        'SAC n.° 13551621, radicados por ante este Juzgado...'
    )
    esperado = (
        'Agüero, Saúl Maximiliano y otro p.ss.aa robo calificado por escalamiento, etc. '
        '(SAC N° 13551621)'
    )
    assert core.extraer_caratula(texto) == esperado


def test_extraer_caratula_con_texto_previo():
    texto = (
        'JUZGADO DE CONTROL Y FALTAS Nº 9 Protocolo de Sentencias Nº Resolución: 5 Año: 2025 '
        'Tomo: 1 Folio: 16-23 EXPEDIENTE SAC: 13393379 - DIAZ, ESTEBAN ARIEL - DIAZ, '
        'YANINA ELIZABETH - CAUSA CON IMPUTADOS PROTOCOLO DE SENTENCIAS. NÚMERO: 5 DEL '
        '12/02/2025 En la ciudad de Córdoba, el doce de febrero de dos mil veinticinco, se '
        'dan a conocer los fundamentos de la sentencia dictada en la causa "Díaz, Esteban '
        'Ariel y otra p. ss. aa. amenazas calificadas, etc." (SAC N° 13393379)'
    )
    esperado = (
        'Díaz, Esteban Ariel y otra p. ss. aa. amenazas calificadas, etc. '
        '(SAC N° 13393379)'
    )
    assert core.extraer_caratula(texto) == esperado