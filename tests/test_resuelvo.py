import sys
import types
from pathlib import Path

# Ensure root path is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Stub PySide6 modules required by ospro during import
pyside = types.ModuleType("PySide6")
core = types.ModuleType("PySide6.QtCore")
widgets = types.ModuleType("PySide6.QtWidgets")
gui = types.ModuleType("PySide6.QtGui")

def _cls(name):
    return type(name, (), {"__init__": lambda self, *a, **k: None})

core.Qt = type("Qt", (), {"__getattr__": lambda self, name: 0})()
for name in ["QRect", "QPropertyAnimation", "QEvent", "QUrl", "QMimeData", "QRegularExpression", "QObject", "Signal", "QThread"]:
    setattr(core, name, _cls(name))

for name in [
    "QApplication", "QMainWindow", "QWidget", "QLabel", "QLineEdit", "QComboBox",
    "QSpinBox", "QPushButton", "QGridLayout", "QVBoxLayout", "QTabWidget",
    "QFileDialog", "QMessageBox", "QScrollArea", "QSizePolicy", "QSplitter",
    "QTextBrowser", "QTextEdit", "QFrame", "QHBoxLayout", "QDialog",
    "QDialogButtonBox", "QInputDialog", "QPlainTextEdit", "QProgressDialog",
    "QProgressBar",
]:
    setattr(widgets, name, _cls(name))

for name in ["QIcon", "QTextCursor", "QRegularExpressionValidator", "QTextBlockFormat", "QTextCharFormat", "QTextDocument"]:
    setattr(gui, name, _cls(name))

class _QFont:
    Normal = 0
    def __init__(self, *a, **k):
        pass

gui.QFont = _QFont

sys.modules["PySide6"] = pyside
sys.modules["PySide6.QtCore"] = core
sys.modules["PySide6.QtWidgets"] = widgets
sys.modules["PySide6.QtGui"] = gui
pyside.QtCore = core
pyside.QtWidgets = widgets
pyside.QtGui = gui

# Stub libraries used by ospro but unnecessary for the test
sys.modules.setdefault("openai", types.ModuleType("openai"))

pdfminer = types.ModuleType("pdfminer")
pdf_high = types.ModuleType("pdfminer.high_level")
pdf_high.extract_text = lambda *a, **k: ""
pdfminer.high_level = pdf_high
sys.modules["pdfminer"] = pdfminer
sys.modules["pdfminer.high_level"] = pdf_high

docx2txt = types.ModuleType("docx2txt")
docx2txt.process = lambda *a, **k: ""
sys.modules["docx2txt"] = docx2txt

import ospro


def test_extraer_resuelvo_removes_digital_signature():
    texto = (
        "Texto previo\n"
        "RESUELVO:\n"
        "1) Ordenar algo.\n"
        "2) Otra cosa.\n"
        "\u2022 Texto Firmado digitalmente por: JUEZ\n"
        "Fecha: 2024-01-01\n"
    )
    res = ospro.extraer_resuelvo(texto)
    assert "Firmado digitalmente" not in res
    assert res == "RESUELVO:\n1) Ordenar algo.\n2) Otra cosa."
