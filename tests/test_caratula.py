import re
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

# Minimal stub for PySide6.QtCore.QRegularExpression
class _FakeMatch:
    def __init__(self, m: re.Match | None):
        self._m = m

    def hasMatch(self) -> bool:  # pragma: no cover - simple stub
        return bool(self._m)

    def __bool__(self) -> bool:  # pragma: no cover - simple stub
        return bool(self._m)


class _FakeQRegularExpression:
    def __init__(self, pattern: str):
        self._re = re.compile(pattern)

    def match(self, text: str) -> _FakeMatch:
        return _FakeMatch(self._re.match(text))


qtcore = types.ModuleType("PySide6.QtCore")
qtcore.QRegularExpression = _FakeQRegularExpression
sys.modules.setdefault("PySide6", types.ModuleType("PySide6"))
sys.modules["PySide6.QtCore"] = qtcore

import core
# ── CARÁTULA ──────────────────────────────────────────────────────────
_PAT_CARAT_1 = re.compile(          # 1) bloque completo con o sin paréntesis
    r'(.+?)\s*'
    r'(?:\(\s*(?:Expte\.\s*)?(?:SAC|Expte\.?)\s*(?:N\s*[°º\.]*\s*)?([\d.]+)\s*\)'
    r'|(?:Expte\.\s*)?(?:SAC|Expte\.?)\s*(?:N\s*[°º\.]*\s*)?([\d.]+))',
    re.I,
)

_PAT_CARAT_2 = re.compile(          # 2) autos caratulados “…”
    r'autos?\s+(?:se\s+)?(?:denominad[oa]s?|intitulad[oa]s?|'
    r'caratulad[oa]s?)\s+[«"”]?([^"»\n]+)[»"”]?', re.I)

_PAT_CARAT_3 = re.compile(          # 3) encabezado “EXPEDIENTE SAC: … - …”
    r'EXPEDIENTE\s+(?:SAC|Expte\.?)\s*:?\s*([\d.]+)\s*-\s*(.+?)(?:[-–]|$)', re.I)

def extraer_caratula(txt: str) -> str:
    """
    Devuelve la carátula formal “…” (SAC N° …) o '' si no encuentra nada creíble.
    Se prueban, en orden, tres patrones:
      1. Entre comillas + (SAC/Expte N° …)
      2. Frase “… autos caratulados ‘X’ …”
      3. Encabezado “EXPEDIENTE SAC: 123 – X – …”
    """
    # normalizo blancos para evitar saltos de línea entre tokens
    plano = re.sub(r'\s+', ' ', txt)

    m = _PAT_CARAT_1.search(plano)
    if m:
        bloque, n1, n2 = m.groups()
        nro = n1 or n2
        bloque = bloque.strip()
        mq = re.search(r"[\"“'‘`][^\"”'’`]+[\"”'’`]", bloque)
        if mq:
            inner = mq.group(0)[1:-1]
            quoted = f'“{inner}”'
        # Mantengo siempre lo que antecede a las comillas.
        # El corte por longitud descartaba carátulas largas (p. ej. con
        # varios imputados) y terminaba mostrando sólo el hecho.
        prefix = bloque[:mq.start()].strip()
        bloque = f'{prefix} {quoted}' if prefix else quoted
        if prefix and len(prefix) <= 150:
            bloque = f"{prefix} {quoted}"
        else:
            bloque = quoted
        return f'{bloque.strip()} (SAC N° {nro})'


    m = _PAT_CARAT_2.search(plano)
    if m:
        titulo = m.group(1).strip()
        # intento buscar el número SAC/Expte más próximo
        mnum = re.search(r'(?:SAC|Expte\.?)\s*N°?\s*([\d.]+)', plano)
        nro  = mnum.group(1) if mnum else '…'
        return f'“{titulo}” (SAC N° {nro})'

    # El encabezado suele estar en la primera página; me quedo con la 1ª coincidencia
    encabezados = _PAT_CARAT_3.findall(plano[:5000])
    if encabezados:
        nro, resto = encabezados[0]
        titulo = resto.split(' - ')[0].strip()
        return f'“{titulo}” (SAC N° {nro})'
    return ""
