# -*- coding: utf-8 -*-
"""
Generador de documentos judiciales – versión base
Interfaz: datos generales + pestañas de imputados (sin plantillas)
"""
import sys, json, os
from pathlib import Path
from datetime import datetime
import re
from PySide6.QtCore import Qt, QRect, QPropertyAnimation, QEvent, QUrl, QMimeData
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QLabel,
    QLineEdit,
    QComboBox,
    QSpinBox,
    QPushButton,
    QGridLayout,
    QVBoxLayout,
    QTabWidget,
    QFileDialog,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTextBrowser,
    QTextEdit,
    QFrame,
    QHBoxLayout,
    QDialog,
    QDialogButtonBox,
    QInputDialog,
    QPlainTextEdit,
)
from PySide6.QtGui import QIcon, QTextCursor, QFont  # QIcon y QFont para más adelante
from PySide6.QtGui import QTextBlockFormat, QTextCharFormat
# ── NUEVOS IMPORTS ──────────────────────────────────────────────
import openai                    # cliente oficial
from pdfminer.high_level import extract_text              # PDF → texto
import docx2txt                  # DOCX → texto
import ast
import subprocess
import shutil
import tempfile
from helpers import anchor, anchor_html

# ──────────────────── utilidades menores ────────────────────
class NoWheelComboBox(QComboBox):
    """Evita que la rueda del mouse cambie accidentalmente la opción."""
    def wheelEvent(self, event): event.ignore()

class NoWheelSpinBox(QSpinBox):
    def wheelEvent(self, event): event.ignore()

CAUSAS_DIR = Path("causas_guardadas")
CAUSAS_DIR.mkdir(exist_ok=True)

# meses en español para las fechas
MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
]

# opciones de Tribunales; el usuario puede editarlas o escribir otras
TRIBUNALES = [
    "la Cámara en lo Criminal y Correccional de Primera Nominación",
    "la Cámara en lo Criminal y Correccional de Segunda Nominación",
    "la Cámara en lo Criminal y Correccional de Tercera Nominación",
    "la Cámara en lo Criminal y Correccional de Cuarta Nominación",
    "la Cámara en lo Criminal y Correccional de Quinta Nominación",
    "la Cámara en lo Criminal y Correccional de Sexta Nominación",
    "la Cámara en lo Criminal y Correccional de Séptima Nominación",
    "la Cámara en lo Criminal y Correccional de Octava Nominación",
    "la Cámara en lo Criminal y Correccional de Novena Nominación",
    "la Cámara en lo Criminal y Correccional de Décima Nominación",
    "la Cámara en lo Criminal y Correccional de Onceava Nominación",
    "la Cámara en lo Criminal y Correccional de Doceava Nominación",
    "el Juzgado de Control en lo Penal Económico",
    "el Juzgado de Control y Faltas N° 2",
    "el Juzgado de Control y Faltas N° 3",
    "el Juzgado de Control y Faltas N° 4",
    "el Juzgado de Control y Faltas N° 5",
    "el Juzgado de Control en Violencia de Género y Familiar N° 1",
    "el Juzgado de Control en Violencia de Género y Familiar N° 2",
    "el Juzgado de Control y Faltas N° 7",
    "el Juzgado de Control y Faltas N° 8",
    "el Juzgado de Control y Faltas N° 9",
    "el Juzgado de Control y Faltas N° 10",
    "el Juzgado de Control y Faltas N° 11",
    "el Juzgado de Control de Lucha contra el Narcotráfico",
]

# opciones de complejos penitenciarios
PENITENCIARIOS = [
    "Complejo Carcelario n.° 1 (Bouwer)",
    "Establecimiento Penitenciario n.° 9 (UCA)",
    "Establecimiento Penitenciario n.° 3 (para mujeres)",
    "Complejo Carcelario n.° 2 (Cruz del Eje)",
    "Establecimiento Penitenciario n.° 4 (Colonia Abierta Monte Cristo)",
    "Establecimiento Penitenciario n.° 5 (Villa María)",
    "Establecimiento Penitenciario n.° 6 (Río Cuarto)",
    "Establecimiento Penitenciario n.° 7 (San Francisco)",
    "Establecimiento Penitenciario n.° 8 (Villa Dolores)",
]

# opciones de depósitos para rodados u objetos decomisados
DEPOSITOS = [
    "Depósito General de Efectos Secuestrados",
    "Depósito de la Unidad Judicial de Lucha c/ Narcotráfico",
    "Depósito de Armas (Tribunales II)",
    "Depósito de Automotores 1 (Bouwer)",
    "Depósito de Automotores 2 (Bouwer)",
    "Depositado en Cuenta Judicial en pesos o dólares del Banco de Córdoba",
    "Depósito de Armas y elementos secuestrados (Tribunales II)",
]

# opciones para el carácter de la entrega de vehículos
CARACTER_ENTREGA = ["definitivo", "de depositario judicial"]

# opciones de Juzgados de Niñez, Adolescencia, Violencia Familiar y de Género
JUZ_NAVFYG = [
    "Juzgado de Niñez, Adolescencia, Violencia Familiar y de Género de 1ª Nom. – Sec.\u202fN°\u202f1",
    "Juzgado de Niñez, Adolescencia, Violencia Familiar y de Género de 1ª Nom. – Sec.\u202fN°\u202f2",
    "Juzgado de Niñez, Adolescencia, Violencia Familiar y de Género de 2ª Nom. – Sec.\u202fN°\u202f3",
    "Juzgado de Niñez, Adolescencia, Violencia Familiar y de Género de 2ª Nom. – Sec.\u202fN°\u202f4",
    "Juzgado de Niñez, Adolescencia, Violencia Familiar y de Género de 3ª Nom. – Sec.\u202fN°\u202f5",
    "Juzgado de Niñez, Adolescencia, Violencia Familiar y de Género de 3ª Nom. – Sec.\u202fN°\u202f6",
    "Juzgado de Niñez, Adolescencia, Violencia Familiar y de Género de 4ª Nom. – Sec.\u202fN°\u202f7",
    "Juzgado de Niñez, Adolescencia, Violencia Familiar y de Género de 4ª Nom. – Sec.\u202fN°\u202f8",
    "Juzgado de Niñez, Adolescencia, Violencia Familiar y de Género de 5ª Nom. – Sec.\u202fN°\u202f9",
    "Juzgado de Niñez, Adolescencia, Violencia Familiar y de Género de 5ª Nom. – Sec.\u202fN°\u202f10",
    "Juzgado de Niñez, Adolescencia, Violencia Familiar y de Género de 6ª Nom. – Sec.\u202fN°\u202f11",
    "Juzgado de Niñez, Adolescencia, Violencia Familiar y de Género de 6ª Nom. – Sec.\u202fN°\u202f12",
    "Juzgado de Niñez, Adolescencia, Violencia Familiar y de Género de 7ª Nom. – Sec.\u202fN°\u202f13",
    "Juzgado de Niñez, Adolescencia, Violencia Familiar y de Género de 7ª Nom. – Sec.\u202fN°\u202f14",
    "Juzgados de Violencia de Género, modalidad doméstica -causas graves- de 8ª Nom. – Sec.\u202fN°\u202f15",
    "Juzgados de Violencia de Género, modalidad doméstica -causas graves- de 8ª Nom. – Sec.\u202fN°\u202f16",
    "Juzgados de Violencia de Género, modalidad doméstica -causas graves- de 9ª Nom. – Sec.\u202fN°\u202f17",
    "Juzgados de Violencia de Género, modalidad doméstica -causas graves- de 9ª Nom. – Sec.\u202fN°\u202f18",
]

# texto acortado para mostrar en el combo: tomamos la última parte
def _abreviar_juzgado(nombre: str) -> str:
    idx = nombre.rfind(" de ")
    return nombre[idx + 4:] if idx != -1 else nombre

def fecha_alineada(loc: str, hoy: datetime = None, punto: bool = False) -> str:
    hoy = hoy or datetime.now()
    txt = f"{loc}, {hoy.day} de {MESES_ES[hoy.month-1]} de {hoy.year}"
    return txt + ("." if punto else "")

# -- conversor HTML a texto plano --
def html_a_plano(html: str, mantener_saltos: bool = True) -> str:
    """Convierte un fragmento HTML en texto simple."""
    if not html:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"</p\s*>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    if not mantener_saltos:
        text = " ".join(text.splitlines())
    return text.strip()

# ── helper para capturar el bloque dispositvo (resuelvo) ─────────────

# ── helper para capturar SIEMPRE el bloque dispositvo (resuelvo) ──────────
# Busca la parte final de la sentencia iniciada con «RESUELVE» o «RESUELVO»
# y finalizada con las fórmulas de cierre habituales.
_RESUELVO_REGEX = re.compile(
    r'''(?isx)
        resuelv[eo]\s*:?                 # palabra clave introductoria
        (                                 # ── INICIO bloque a devolver ──
            (?:                           #   uno o más ítems "I) …"
                \s*[IVXLCDM]+\)\s.*?     #   línea con número romano
                (?:\n(?!\s*[IVXLCDM]+\)).*?)*
            )+                            #   líneas internas que no inician otro número
        )                                 # ── FIN bloque ──
        (?=                               # look‑ahead de cierre
            \s*(?:Protocol[íi]?cese|Notifíquese|Hágase\s+saber|Of[íi]ciese)
        )
    ''',
    re.IGNORECASE | re.DOTALL | re.VERBOSE,
)


def extraer_resuelvo(texto: str) -> str:
    """
    Devuelve el ÚLTIMO bloque dispositvo (resuelvo) de la sentencia.
    Si no hay coincidencias, devuelve cadena vacía.
    """
    matches = list(_RESUELVO_REGEX.finditer(texto))
    return matches[-1].group(1).strip() if matches else ""

# ───────────────────────── MainWindow ────────────────────────
class MainWindow(QMainWindow):
    FIELD_WIDTH = 140        # ancho preferido de los campos cortos

    # ── helper para insertar párrafos con alineación ─────────────
    def _insert_paragraph(self, te: QTextEdit, text: str,
                          align: Qt.AlignmentFlag = Qt.AlignJustify,
                          font_family: str = "Times New Roman",
                          point_size: int = 12,
                          weight: int = QFont.Normal,
                          rich: bool = False) -> None:
        """
        Agrega uno o varios párrafos a `te` con la alineación indicada
        (Left, Right, Center o Justify).  Cada salto de línea en `text`
        genera un bloque nuevo.
        """
        cursor = te.textCursor()
        block  = QTextBlockFormat()
        block.setAlignment(align)

        char   = QTextCharFormat()
        char.setFontFamily(font_family)
        char.setFontPointSize(point_size)
        char.setFontWeight(weight)

        for linea in text.split("\n"):
            cursor.insertBlock(block)
            cursor.setCharFormat(char)
            if rich:
                cursor.insertHtml(linea)
            else:
                cursor.insertText(linea)

    def _insert_with_header(self, te: QTextEdit, text: str) -> None:
        """Inserta todo el texto justificado, sin convertir \n\n en encabezado."""
        self._insert_paragraph(te, text, Qt.AlignJustify)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Generador base")
        self.resize(1100, 610)

        # ───────── splitter horizontal ─────────
        splitter = QSplitter(Qt.Horizontal, self)
        self.setCentralWidget(splitter)

        # =========== PANEL IZQUIERDO (formulario con scroll) ===========
        left_scroll = QScrollArea(); left_scroll.setWidgetResizable(True)
        left_inner  = QWidget();     left_scroll.setWidget(left_inner)
        splitter.addWidget(left_scroll)
        splitter.setStretchFactor(0, 0)

        self.form = QGridLayout(left_inner)
        self.form.setAlignment(Qt.AlignTop)
        self.form.setColumnStretch(0, 0)
        self.form.setColumnStretch(1, 1)
        left_inner.setMinimumWidth(280)

        # —— helpers ——
        self._row = 0
        def label(t): self.form.addWidget(QLabel(t), self._row, 0)
        def add_line(attr, txt):
            label(txt)
            w = QLineEdit(); w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            w.textChanged.connect(self.update_templates)
            self.form.addWidget(w, self._row, 1); self._row += 1
            setattr(self, attr, w); return w
        def add_combo(attr, txt, items=(), editable=False):
            label(txt)
            w = NoWheelComboBox(); w.addItems(items); w.setEditable(editable)
            w.currentIndexChanged.connect(self.update_templates)
            w.editTextChanged.connect(self.update_templates)
            self.form.addWidget(w, self._row, 1); self._row += 1
            setattr(self, attr, w); return w

        # ─── datos generales ───
        self.entry_localidad = add_line('entry_localidad', "Localidad:")
        self.entry_caratula  = add_line ('entry_caratula',  "Carátula:")
        self.entry_tribunal  = add_combo('entry_tribunal',  "Tribunal:", TRIBUNALES, editable=True)
        self.entry_consulado = add_line('entry_consulado', "Consulado de:")

        # ─── sentencia (número y fecha) ───
        label("Sentencia:")
        hbox = QHBoxLayout()
        self.entry_sent_num = QLineEdit();  self.entry_sent_num.setPlaceholderText("N°")
        self.entry_sent_date = QLineEdit(); self.entry_sent_date.setPlaceholderText("Fecha")
        for w in (self.entry_sent_num, self.entry_sent_date):
            w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            w.textChanged.connect(self.update_templates)
        hbox.addWidget(self.entry_sent_num)
        hbox.addWidget(self.entry_sent_date)
        self.form.addLayout(hbox, self._row, 1); self._row += 1

        # Firmeza de la sentencia (fecha)
        self.entry_sent_firmeza = add_line('entry_sent_firmeza',
                                            "Firmeza de la sentencia:")
        self.entry_sent_firmeza.setPlaceholderText("Fecha")

        self.entry_resuelvo = add_line('entry_resuelvo', "Resuelvo:")
        self.entry_firmantes = add_line('entry_firmantes', "Firmantes de la sentencia:")

        self.entry_rodado = add_line('entry_rodado', "Decomisado/secuestrado:")
        label("Reg. automotor / Comisaría:")
        h_reg_com = QHBoxLayout()
        self.entry_regn = QLineEdit(); self.entry_regn.setPlaceholderText("Reg. N°")
        self.entry_comisaria = QLineEdit(); self.entry_comisaria.setPlaceholderText("Comisaría N°")
        for w in (self.entry_regn, self.entry_comisaria):
            w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            w.textChanged.connect(self.update_templates)
        h_reg_com.addWidget(self.entry_regn)
        h_reg_com.addWidget(self.entry_comisaria)
        self.form.addLayout(h_reg_com, self._row, 1); self._row += 1
        self.entry_deposito = add_combo('entry_deposito', "Depósito:", DEPOSITOS, editable=True)
        self.entry_dep_def = add_combo('entry_dep_def', "Carácter de la entrega:", CARACTER_ENTREGA, editable=True)
        self.entry_titular_veh = add_line('entry_titular_veh', "Titular del vehículo:")

        label("Inf. Téc. Iden. Matrícula:")
        h_itim = QHBoxLayout()
        self.entry_itim_num = QLineEdit();  self.entry_itim_num.setPlaceholderText("N°")
        self.entry_itim_fecha = QLineEdit(); self.entry_itim_fecha.setPlaceholderText("Fecha")
        for w in (self.entry_itim_num, self.entry_itim_fecha):
            w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            w.textChanged.connect(self.update_templates)
        h_itim.addWidget(self.entry_itim_num)
        h_itim.addWidget(self.entry_itim_fecha)
        self.form.addLayout(h_itim, self._row, 1); self._row += 1

        # ─── cómputo de pena / resolución art. 27 ───
        #   ← se mueve a la pestaña de cada imputado

        # ─── número de imputados ───
        label("Número de imputados:")
        self.combo_n = NoWheelComboBox(); self.combo_n.addItems([str(i) for i in range(1,21)])
        self.form.addWidget(self.combo_n, self._row, 1); self._row += 1
        self.combo_n.currentIndexChanged.connect(self.rebuild_imputados)

        # pestañas de imputados (se llenarán más tarde)
        self.tabs_imp = QTabWidget()
        self.form.addWidget(self.tabs_imp, self._row, 0, 1, 2); self._row += 1

        # botones archivo
        for txt, slot in (("Guardar causa",  self.guardar_causa),
                        ("Abrir causa",    self.cargar_causa),
                        ("Eliminar causa", self.eliminar_causa)):
            btn = QPushButton(txt); btn.clicked.connect(slot)
            self.form.addWidget(btn, self._row, 0, 1, 2); self._row += 1
        btn_auto = QPushButton("Cargar sentencia y autocompletar")
        btn_auto.clicked.connect(self.autocompletar_desde_sentencia)
        self.form.addWidget(btn_auto, self._row, 0, 1, 2)
        self._row += 1
        # =========== PANEL DERECHO (selector + pestañas texto) ===========
        right_panel  = QWidget()
        right_layout = QVBoxLayout(right_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(1, 1)
        # luego de splitter.addWidget(right_panel)
        splitter.setSizes([350, 1000])   # [ancho_izq, ancho_der] en píxeles


        self.selector_imp = NoWheelComboBox()
        self.selector_imp.currentIndexChanged.connect(self.update_for_imp)
        right_layout.addWidget(self.selector_imp)

        self.tabs_txt = QTabWidget()
        right_layout.addWidget(self.tabs_txt, 1)
        # indicador visual que une pestañas relacionadas (animado)
        self.related_indicator = QFrame(self.tabs_txt.tabBar())
        self.related_indicator.setObjectName("related_indicator")
        self.related_indicator.setStyleSheet(
            "#related_indicator{background:palette(highlight);height:2px;border-radius:1px;}"
        )
        self.related_indicator.hide()
        # Pares de pestañas cuyo vínculo se destaca con una animación
        # cuando el usuario cambia u observa las tabs.
        self.related_pairs = [
            ("Oficio Registro Automotor", "Oficio TSJ Sec. Penal"),
            ("Oficio TSJ Sec. Penal (Depósitos)", "Oficio Comisaría Traslado"),
        ]
        self.tabs_txt.currentChanged.connect(self.update_related_indicator)
        bar = self.tabs_txt.tabBar()
        bar.installEventFilter(self)

        # pestañas de oficios
        self.text_edits = {}
        self.tab_indices = {}
        for name in ("Oficio Migraciones",
                    "Oficio Consulado",
                    "Oficio Juez Electoral",
                    "Oficio Policía Documentación",
                    "Oficio Registro Civil",
                    "Oficio Registro Condenados Sexuales",                     
                    "Oficio Registro Nacional Reincidencia",
                    "Oficio Complejo Carcelario",
                    "Oficio Juzgado Niñez‑Adolescencia",
                    "Oficio RePAT",                    
                    "Oficio Fiscalía Instrucción",
                    "Oficio Automotores Secuestrados",
                    "Oficio Registro Automotor",
                    "Oficio TSJ Sec. Penal",
                    "Oficio TSJ Sec. Penal (Depósitos)",  
                    "Oficio Comisaría Traslado",
                    "Oficio TSJ Sec. Penal (Elementos)",
                    ):

            te = QTextBrowser();
            te.setReadOnly(True)
            te.setOpenLinks(False)
            te.setOpenExternalLinks(False)
            te.anchorClicked.connect(self._on_anchor_clicked)
            font = QFont("Times New Roman", 12)
            te.setFont(font)
            te.document().setDefaultFont(font)
            cont = QWidget(); lay = QVBoxLayout(cont)
            lay.addWidget(te)
            btn = QPushButton("Copiar")
            btn.clicked.connect(lambda _=False, t=te: self.copy_to_clipboard(t))
            lay.addWidget(btn)
            self.tabs_txt.addTab(cont, name)
            idx = self.tabs_txt.indexOf(cont)
            self.tab_indices[name] = idx
            self.text_edits[name] = te

        self.tab_widgets = {n: self.tabs_txt.widget(i) for n, i in self.tab_indices.items()}

        # ─── AHORA que selector_imp existe, construimos imputados ───
        self.imputados_widgets = []         #  ← línea movida aquí
        self.rebuild_imputados()            #  ← llamada movida aquí

        # primer refresco de textos
        self.update_templates()

    def update_related_indicator(self, idx: int) -> None:
        """Muestra un conector animado entre pestañas relacionadas."""
        name = self.tabs_txt.tabText(idx)
        paired = None
        for a, b in self.related_pairs:
            if name == a:
                paired = b
                break
            if name == b:
                paired = a
                break
        if paired is None:
            self.related_indicator.hide()
            return

        tabbar = self.tabs_txt.tabBar()
        idx2 = self.tab_indices.get(paired)
        if idx2 is None:
            self.related_indicator.hide()
            return

        r1 = tabbar.tabRect(idx)
        r2 = tabbar.tabRect(idx2)
        y = r1.bottom() - 1
        start = QRect(r1.center().x(), y, 1, 2)
        end_x = min(r1.center().x(), r2.center().x())
        end_w = abs(r2.center().x() - r1.center().x())
        end = QRect(end_x, y, end_w, 2)
        self.related_indicator.setGeometry(start)
        self.related_indicator.show()
        anim = QPropertyAnimation(self.related_indicator, b"geometry", self)
        anim.setDuration(300)
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.start(QPropertyAnimation.DeleteWhenStopped)

    def eventFilter(self, obj, event):
        bar = self.tabs_txt.tabBar()
        if obj is bar and event.type() in (QEvent.Enter, QEvent.MouseMove):
            idx = bar.tabAt(event.position().toPoint())
            if idx != -1:
                self.update_related_indicator(idx)
        return super().eventFilter(obj, event)

    def rebuild_imputados(self):
        """Reconstruye las pestañas según la cantidad elegida, sin perder datos."""
        # 1) guardo lo ya escrito
        prev = [
            {k: (w[k].text() if isinstance(w[k], QLineEdit)
                else w[k].currentText() if isinstance(w[k], QComboBox)
                else "")
            for k in w}
            for w in self.imputados_widgets
        ]

        # 2) limpio contenedores
        self.tabs_imp.clear()
        self.imputados_widgets = []

        # 3) preparo el selector (sin disparar señales mientras lo relleno)
        self.selector_imp.blockSignals(True)
        self.selector_imp.clear()

        n = int(self.combo_n.currentText())
        for i in range(n):
            tab = QWidget()
            grid = QGridLayout(tab)
            row  = 0

            def pair(lbl, widget):
                nonlocal row
                grid.addWidget(QLabel(lbl), row, 0)
                grid.addWidget(widget,      row, 1)
                row += 1

            # —— widgets del imputado ——
            w = {
                'nombre'  : QLineEdit(),
                'dni'     : QLineEdit(),
                'datos_personales': QTextEdit(),
                'computo' : QLineEdit(),
                'computo_tipo': NoWheelComboBox(),
                'condena': QLineEdit(),
                'servicio_penitenciario': NoWheelComboBox(),
                'legajo': QLineEdit(),
                'delitos': QLineEdit(),
                'antecedentes': QLineEdit(),
                'tratamientos': QLineEdit(),
                'juz_navfyg': NoWheelComboBox(),
                'ee_relacionado': QLineEdit(),
            }
            w['computo_tipo'].addItems(["Efec.", "Cond."])
            w['servicio_penitenciario'].addItems(PENITENCIARIOS)
            for item in JUZ_NAVFYG:
                w['juz_navfyg'].addItem(_abreviar_juzgado(item), item)
            w['juz_navfyg'].setEditable(True)
            w['dni'].textChanged.connect(self.update_templates)
            w['computo'].textChanged.connect(self.update_templates)
            w['computo_tipo'].currentIndexChanged.connect(self.update_templates)
            w['condena'].textChanged.connect(self.update_templates)
            w['servicio_penitenciario'].currentIndexChanged.connect(self.update_templates)
            w['legajo'].textChanged.connect(self.update_templates)
            w['delitos'].textChanged.connect(self.update_templates)
            w['antecedentes'].textChanged.connect(self.update_templates)
            w['tratamientos'].textChanged.connect(self.update_templates)
            w['juz_navfyg'].currentIndexChanged.connect(self.update_templates)
            w['juz_navfyg'].editTextChanged.connect(self.update_templates)
            w['ee_relacionado'].textChanged.connect(self.update_templates)

            pair("Nombre y apellido:", w['nombre'])
            pair("DNI:",               w['dni'])
            pair("Datos personales:", w['datos_personales'])

            pair("Condena:", w['condena'])
            pair("Servicio Penitenciario:", w['servicio_penitenciario'])
            pair("Legajo:", w['legajo'])
            pair("Delitos:", w['delitos'])
            pair("Antecedentes:", w['antecedentes'])
            pair("Tratamientos:", w['tratamientos'])

            grid.addWidget(QLabel("Juz. NAVFyG:"), row, 0)
            hbox_j = QHBoxLayout()
            hbox_j.addWidget(w['juz_navfyg'])
            hbox_j.addWidget(w['ee_relacionado'])
            w['ee_relacionado'].setPlaceholderText("EE relacionado")
            grid.addLayout(hbox_j, row, 1)
            row += 1

            grid.addWidget(QLabel("Cómputo:"), row, 0)
            hbox_c = QHBoxLayout()
            hbox_c.addWidget(w['computo'])
            hbox_c.addWidget(w['computo_tipo'])
            grid.addLayout(hbox_c, row, 1)
            row += 1

            # 4) restauro datos previos si los hubiera
            if i < len(prev):
                for k, v in prev[i].items():
                    widget = w[k]
                    if isinstance(widget, QLineEdit):
                        widget.setText(v)
                    elif isinstance(widget, QTextEdit):
                        widget.setPlainText(v)
                    elif isinstance(widget, QComboBox):
                        idx = widget.findData(v)
                        if idx != -1:
                            widget.setCurrentIndex(idx)
                        else:
                            widget.setCurrentText(v)


            # 5) agrego pestaña y actualizo listas
            self.tabs_imp.addTab(tab, f"Imputado {i+1}")
            self.selector_imp.addItem(f"Imputado {i+1}")
            self.imputados_widgets.append(w)
            w['datos_personales'].textChanged.connect(self.update_templates)
            w['nombre'].textChanged.connect(self.update_templates)
            w['nombre'].textChanged.connect(self._refresh_imp_names_in_selector)
        # 6) habilito señales y dejo seleccionado el primero
        self.selector_imp.blockSignals(False)
        self.selector_imp.setCurrentIndex(0)
        self._refresh_imp_names_in_selector()
        self.update_templates()


    def _refresh_imp_names_in_selector(self):
        """Muestra el nombre si está cargado (“Imputado 1 – Pérez”)."""
        for i, w in enumerate(self.imputados_widgets):
            nom = w['nombre'].text().strip()
            txt = f"Imputado {i+1}" + (f" – {nom}" if nom else "")
            self.selector_imp.setItemText(i, txt)


    # —————————————————— persistencia ——————————————————
    def _generales_dict(self):
        """Devuelve un dict con los datos generales."""
        return {
            'localidad' : self.entry_localidad.text(),
            'caratula'  : self.entry_caratula.text(),
            'tribunal'  : self.entry_tribunal.currentText(),
            'consulado' : self.entry_consulado.text(),

            'resuelvo'  : self.entry_resuelvo.text(),
            'firmantes' : self.entry_firmantes.text(),

            'sent_num'  : self.entry_sent_num.text(),
            'sent_fecha': self.entry_sent_date.text(),
            'sent_firmeza': self.entry_sent_firmeza.text(),

            'rodado': self.entry_rodado.text(),
            'regn': self.entry_regn.text(),
            'deposito': self.entry_deposito.currentText(),
            'comisaria': self.entry_comisaria.text(),
            'dep_def': self.entry_dep_def.currentText(),
            'titular_veh': self.entry_titular_veh.text(),
            'itim_num': self.entry_itim_num.text(),
            'itim_fecha': self.entry_itim_fecha.text(),
        }

    def _imputados_list(self):
        """Devuelve una lista de dicts con TODOS los campos de cada imputado."""
        li = []
        for w in self.imputados_widgets:
            datos = {}
            for k, widget in w.items():
                if isinstance(widget, QLineEdit):
                    datos[k] = widget.text()
                elif isinstance(widget, QTextEdit):
                    datos[k] = widget.toPlainText()
                elif isinstance(widget, QComboBox):
                    data = widget.currentData()
                    datos[k] = data if data is not None else widget.currentText()
                else:
                    datos[k] = ""
            li.append(datos)
        return li

    def guardar_causa(self):
        ruta, _ = QFileDialog.getSaveFileName(self, "Guardar causa", str(CAUSAS_DIR), "JSON (*.json)")
        if not ruta: return
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump({'generales': self._generales_dict(),
                       'imputados': self._imputados_list()}, f, ensure_ascii=False, indent=2)
        QMessageBox.information(self, "OK", "Causa guardada correctamente.")

    def cargar_causa(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Abrir causa", str(CAUSAS_DIR), "JSON (*.json)"
        )
        if not ruta:
            return
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                data = json.load(f)

            # --------- generales ---------
            g = data.get("generales", {})
            self.entry_localidad.setText(g.get("localidad", ""))
            self.entry_caratula.setText(g.get("caratula", ""))
            self.entry_tribunal.setCurrentText(g.get("tribunal", ""))
            self.entry_resuelvo.setText(g.get("resuelvo", ""))
            self.entry_firmantes.setText(g.get("firmantes", ""))
            self.entry_sent_num.setText(g.get("sent_num", ""))
            self.entry_sent_date.setText(g.get("sent_fecha", ""))
            self.entry_sent_firmeza.setText(g.get("sent_firmeza", ""))
            self.entry_consulado.setText(g.get("consulado", ""))
            self.entry_rodado.setText(g.get("rodado", ""))
            self.entry_regn.setText(g.get("regn", ""))
            self.entry_deposito.setCurrentText(g.get("deposito", ""))
            self.entry_comisaria.setText(g.get("comisaria", ""))
            self.entry_dep_def.setCurrentText(g.get("dep_def", ""))
            self.entry_titular_veh.setText(g.get("titular_veh", ""))
            self.entry_itim_num.setText(g.get("itim_num", ""))
            self.entry_itim_fecha.setText(g.get("itim_fecha", ""))

            # --------- imputados ---------
            imps = data.get("imputados", [])
            self.combo_n.setCurrentText(str(max(1, len(imps))))
            # rebuild_imputados() será llamado por la señal currentIndexChanged,
            # así que los widgets ya existen cuando entremos al for.
            for idx, imp in enumerate(imps):
                w = self.imputados_widgets[idx]
                for k, v in imp.items():
                    widget = w[k]
                    if isinstance(widget, QLineEdit):
                        widget.setText(v)
                    elif isinstance(widget, QTextEdit):
                        widget.setPlainText(v)
                    elif isinstance(widget, QComboBox):
                        idx = widget.findData(v)
                        if idx != -1:
                            widget.setCurrentIndex(idx)
                        else:
                            widget.setCurrentText(v)
            self._refresh_imp_names_in_selector()
            self.update_templates()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def eliminar_causa(self):
        ruta, _ = QFileDialog.getOpenFileName(self, "Eliminar causa", str(CAUSAS_DIR), "JSON (*.json)")
        if ruta and QMessageBox.question(self, "Confirmar",
                                         f"¿Eliminar {Path(ruta).name}?",
                                         QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            Path(ruta).unlink(missing_ok=True)

    # ───────── helper: asegura string ──────────
    @staticmethod
    def _as_str(value):
        """Convierte listas, números o None en str plano."""
        if isinstance(value, list):
            return ", ".join(map(str, value))
        return str(value) if value is not None else ""

    def _format_datos_personales(self, raw):
        """
        Convierte un dict o string con llaves en una línea humana.
        Ej. {'nombre':'Juan', 'dni':'12.3'} -> 'Juan, D.N.I. 12.3'
        """
        if isinstance(raw, dict):
            dp = raw
        else:
            # Si viene como texto "{'nombre': …}", intento parsearlo.
            try:
                dp = ast.literal_eval(raw)
                if not isinstance(dp, dict):
                    raise ValueError
            except Exception:
                return str(raw)         # lo dejo como esté
        partes = []
        if dp.get("nombre"): partes.append(dp["nombre"])
        if dp.get("dni"):    partes.append(f"D.N.I. {dp['dni']}")
        if dp.get("nacionalidad"): partes.append(dp["nacionalidad"])
        if dp.get("edad"):   partes.append(f"{dp['edad']} años")
        if dp.get("estado_civil"): partes.append(dp["estado_civil"])
        if dp.get("instruccion"):  partes.append(dp["instruccion"])
        if dp.get("ocupacion"):    partes.append(dp["ocupacion"])
        if dp.get("fecha_nacimiento"):
            partes.append(f"Nacido el {dp['fecha_nacimiento']}")
        if dp.get("lugar_nacimiento"):
            partes.append(f"en {dp['lugar_nacimiento']}")
        if dp.get("domicilio"):    partes.append(f"Domicilio: {dp['domicilio']}")

        if dp.get("padres"):
            padres_val = dp["padres"]
            if isinstance(padres_val, str):
                padres = padres_val                      # ya viene listo
            elif isinstance(padres_val, list):
                # lista de strings o de dicts
                nombres = []
                for item in padres_val:
                    if isinstance(item, dict):
                        nombres.append(item.get("nombre", str(item)))
                    else:
                        nombres.append(str(item))
                padres = ", ".join(nombres)
            else:
                padres = str(padres_val)
            partes.append(f"Hijo de {padres}")

        if dp.get("prontuario") or dp.get("prio") or dp.get("pront"):
            pront = dp.get("prontuario") or dp.get("prio") or dp.get("pront")
            partes.append(f"Pront. {pront}")          # ← NUEVA LÍNEA
        return ", ".join(partes)

    def _imp_datos(self, idx=None):
        if idx is None:
            idx = self.selector_imp.currentIndex()
        if idx < 0 or idx >= len(self.imputados_widgets):
            return "Datos personales"

        raw = self.imputados_widgets[idx]['datos_personales'].toPlainText().strip()
        if not raw:
            return "Datos personales"

        return self._format_datos_personales(raw)

    def _imp_datos_anchor(self, idx=None):
        if idx is None:
            idx = self.selector_imp.currentIndex()
        texto = self._imp_datos(idx)
        return anchor(texto, f"edit_imp_datos_{idx}", "Datos personales")

    def _imp_computo(self, idx=None):
        if idx is None:
            idx = self.selector_imp.currentIndex()
        if idx < 0 or idx >= len(self.imputados_widgets):
            return "", "Efec."
        w = self.imputados_widgets[idx]
        texto = w['computo'].text()
        tipo  = w['computo_tipo'].currentText()
        return texto, tipo

    def _imp_field(self, key, idx=None):
        """Devuelve el contenido textual de un campo del imputado."""
        if idx is None:
            idx = self.selector_imp.currentIndex()
        if idx < 0 or idx >= len(self.imputados_widgets):
            return ""
        widget = self.imputados_widgets[idx][key]
        if isinstance(widget, QLineEdit):
            return widget.text()
        if isinstance(widget, QTextEdit):
            return widget.toPlainText()
        if isinstance(widget, QComboBox):
            data = widget.currentData()
            return data if data is not None else widget.currentText()
        return ""

    def _imp_field_anchor(self, key, idx=None, placeholder: str = None):
        if idx is None:
            idx = self.selector_imp.currentIndex()
        texto = self._imp_field(key, idx)
        if placeholder is None:
            placeholder = key
        return anchor(texto, f"edit_imp_{key}_{idx}", placeholder)

    def _field_anchor(self, widget, clave: str, placeholder: str = None):
        if isinstance(widget, QLineEdit):
            texto = widget.text()
        elif isinstance(widget, QComboBox):
            texto = widget.currentText()
        elif isinstance(widget, QTextEdit):
            texto = widget.toPlainText()
        else:
            texto = str(widget)
        return anchor(texto, clave, placeholder)

    def _res_decomiso(self) -> str:
        """Extrae del resuelvo solo los puntos relacionados al decomiso."""
        res_html = self.entry_resuelvo.property("html")
        if res_html:
            plano = html_a_plano(res_html, mantener_saltos=False)
        else:
            plano = self.entry_resuelvo.text()
        plano = " ".join(plano.splitlines())
        pattern = r"\b([IVXLCDM]+|\d+)[\.\)]\s+([\s\S]*?)(?=\b(?:[IVXLCDM]+|\d+)[\.\)]\s+|$)"
        partes = []
        for m in re.finditer(pattern, plano, re.DOTALL | re.IGNORECASE):
            num, txt = m.group(1), m.group(2).strip()
            if re.search(r"decomis", txt, re.IGNORECASE):
                partes.append(f"{num}. {txt}")
        return " ".join(partes) if partes else (self.entry_resuelvo.text() or "…")


    # ───────────────── Autocompletar ───────────────────────────
    def autocompletar_desde_sentencia(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar sentencia (PDF/DOCX/DOC)",
            "",
            "Documentos (*.pdf *.docx)",
        )
        if not ruta:
            return

        try:
            # 1) Extraer texto
            ext = ruta.lower()
            if ext.endswith(".pdf"):
                texto = extract_text(ruta)
            elif ext.endswith(".docx"):
                texto = docx2txt.process(ruta)

            # 2) Llamar a la API en JSON mode
            respuesta = openai.ChatCompletion.create(
                model="gpt-4o-mini",          # arranquemos barato
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {
                    "role": "system",
                    "content": (
                        "Extraé de la sentencia los siguientes campos y devolvé un JSON con: "
                        "generales (caratula, tribunal, sent_num, sent_fecha, resuelvo o parte resolutiva, firmantes) "
                        "e imputados (lista de datos_personales ‑incluí nombre, DNI, prontuario y el resto‑). "
                        "Si no hay datos, dejá el campo vacío. "
                        "El texto del resuelvo SIEMPRE esta AL FINAL de la sentencia, precedido por “RESUELVE:” o “RESUELVO:”, "
                        "considerá como parte resolutiva todo el bloque que comienza en la primera enumeración después de esas palabras, "
                        "y termina con las fórmulas de estilo “Protocolícese / Hágase saber / Notifíquese (entre otras)”. "
                        "No resumas ni sintetices, devolvé el texto tal cual."
                    ),
                    },
                    {"role": "user", "content": texto[:120000]},  # límite 128 k tokens
                ],
            )

            datos = json.loads(respuesta.choices[0].message.content)

            # --------------- asegurar que 'resuelvo' tenga contenido ---------------
# --------------- asegurar que 'resuelvo' tenga buen contenido ---------------
            g = datos.get("generales", {})
            # siempre priorizamos el bloque final de la sentencia
            g["resuelvo"] = extraer_resuelvo(texto)

            # normalizar saltos de línea (opcional pero recomendable)
            g["resuelvo"] = re.sub(r"\s*\n\s*", " ", g["resuelvo"]).strip()
# -----------------------------------------------------------------------------

            # ------------------ 1) Generales ------------------
            g = datos.get("generales", {})
            self.entry_caratula.setText(self._as_str(g.get("caratula")))
            self.entry_tribunal.setCurrentText(self._as_str(g.get("tribunal")))
            self.entry_sent_num.setText(self._as_str(g.get("sent_num")))
            self.entry_sent_date.setText(self._as_str(g.get("sent_fecha")))
            self.entry_resuelvo.setText(self._as_str(g.get("resuelvo")))
            self.entry_firmantes.setText(self._as_str(g.get("firmantes")))

            # ------------------ 2) Imputados ------------------
            imps = datos.get("imputados", [])
            self.combo_n.setCurrentText(str(max(1, len(imps))))  # ajusta N
            self.rebuild_imputados()                             # fuerza recreación

            for idx, imp in enumerate(imps):
                # ── tomamos el bloque de datos personales ──
                bruto = imp.get("datos_personales", imp)

                # ①  Si el JSON vino con “prontuario” (o “pront/prio”) SUELTO,
                #    lo metemos adentro del mismo dict para que el formateador lo vea.
                if isinstance(bruto, dict):
                    for key in ("prontuario", "pront", "prio"):
                        if key in imp and key not in bruto and imp[key]:
                            bruto["prontuario"] = imp[key]
                            break

                # ②  Ahora sí convertimos todo a la línea legible
                self.imputados_widgets[idx]["datos_personales"].setPlainText(
                    self._format_datos_personales(bruto)
                )
            self._refresh_imp_names_in_selector()
            # 4) Refrescar plantillas
            self.update_templates()

            QMessageBox.information(self, "Listo", "Campos cargados exitosamente.")

        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    # ─────────────────── plantillas de oficios ────────────────────
    def update_templates(self):
        """Regenera todas las plantillas de la pestaña derecha."""
        self._plantilla_migraciones()
        self._plantilla_juez_electoral()
        self._plantilla_consulado() 
        self._plantilla_registro_automotor()  
        self._plantilla_tsj_secpenal() 
        self._plantilla_tsj_secpenal_depositos()  
        self._plantilla_comisaria_traslado() 
        self._plantilla_tsj_secpenal_elementos()  
        self._plantilla_automotores_secuestrados()
        self._plantilla_fiscalia_instruccion()
        self._plantilla_policia_documentacion()
        self._plantilla_registro_civil() 
        self._plantilla_registro_condenados_sexuales()
        self._plantilla_registro_nacional_reincidencia() 
        self._plantilla_repat()  
        self._plantilla_juzgado_ninez()      
        self._plantilla_complejo_carcelario()

    def _plantilla_migraciones(self):
        te = self.text_edits["Oficio Migraciones"]
        te.clear()

        # ─ datos básicos ─
        loc_txt = self.entry_localidad.text() or "Córdoba"
        hoy = datetime.now()
        fecha = fecha_alineada(loc_txt, hoy, punto=True)
        sent_n = self.entry_sent_num.text() or "…"
        sent_f = self.entry_sent_date.text() or "…/…/…"
        res = self.entry_resuelvo.text() or "…"
        firm = self.entry_firmantes.text() or "…"
        sent_firmeza = self.entry_sent_firmeza.text() or "…/…/…"
        loc = self._field_anchor(self.entry_localidad, "edit_localidad", "Córdoba")
        sent_n_a = self._field_anchor(self.entry_sent_num, "edit_sent_num", "…")
        sent_f_a = self._field_anchor(self.entry_sent_date, "edit_sent_fecha", "…/…/…")
        res_a = self._field_anchor(self.entry_resuelvo, "edit_resuelvo", "resuelvo")
        firm_a = self._field_anchor(self.entry_firmantes, "edit_firmantes", "firmantes")
        sent_firmeza_a = self._field_anchor(self.entry_sent_firmeza, "edit_sent_firmeza", "…/…/…")
        # 1) FECHA a la derecha
        self._insert_paragraph(te, fecha, Qt.AlignRight)

        # 2) CUERPO justificado
        car  = self.entry_caratula.text() or "“…”"
        trib = self.entry_tribunal.currentText() or "la Cámara en lo Criminal y Correccional"
        car_a = self._field_anchor(self.entry_caratula, "edit_caratula", "carátula")
        trib_a = self._field_anchor(self.entry_tribunal, "combo_tribunal", "tribunal")

        cuerpo = (
            "<b>Sr/a Director/a</b>\n"
            "<b>de la Dirección Nacional de Migraciones</b>\n"
            "<b>S/D:</b>\n\n"
            f"En los autos caratulados: {car_a}, que se tramitan "
            f"por ante {trib_a}, se ha dispuesto librar a Ud. el presente oficio, "
            "a fin de informar lo resuelto por dicho Tribunal respecto de la persona "
            "cuyos datos personales se mencionan a continuación:\n\n"
            f"{self._imp_datos_anchor()}\n\n"
            f"“SENTENCIA N° {sent_n_a}, DE FECHA: {sent_f_a}. Se Resuelve: {res_a}”\n\n"
            f"Asimismo, se informa que la sentencia antes señalada quedó firme con fecha {sent_firmeza_a}\n"
            "Se adjuntan al presente oficio copia digital de la misma y del cómputo de pena respectivo.\n\n"
            "Sin otro particular, saludo a Ud. atentamente."
        )
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify, rich=True)


    def _plantilla_juez_electoral(self):
        te = self.text_edits["Oficio Juez Electoral"]
        te.clear()

        # ─ datos básicos ─
        loc_txt = self.entry_localidad.text() or "Córdoba"
        hoy  = datetime.now()
        fecha = fecha_alineada(loc_txt, hoy, punto=True)
        sent_n = self.entry_sent_num.text() or "…"
        sent_f = self.entry_sent_date.text() or "…/…/…"
        res = self.entry_resuelvo.text() or "…"
        firm = self.entry_firmantes.text() or "…"
        car   = self.entry_caratula.text() or "“…”"
        trib  = self.entry_tribunal.currentText() or "la Cámara en lo Criminal y Correccional"
        nom   = "…"   # idem Nominación
        sent_firmeza = self.entry_sent_firmeza.text() or "…/…/…"
        car_a = self._field_anchor(self.entry_caratula, "edit_caratula", "carátula")
        trib_a = self._field_anchor(self.entry_tribunal, "combo_tribunal", "tribunal")
        sent_n_a = self._field_anchor(self.entry_sent_num, "edit_sent_num", "…")
        sent_f_a = self._field_anchor(self.entry_sent_date, "edit_sent_fecha", "…/…/…")
        res_a = self._field_anchor(self.entry_resuelvo, "edit_resuelvo", "resuelvo")
        firm_a = self._field_anchor(self.entry_firmantes, "edit_firmantes", "firmantes")
        sent_firmeza_a = self._field_anchor(self.entry_sent_firmeza, "edit_sent_firmeza", "…/…/…")
        cuerpo = (
            "<b>SR. JUEZ ELECTORAL:</b>\n"
            "<b>S………………./………………D</b>\n"
            "<b>-Av. Concepción Arenales esq. Wenceslao Paunero, Bº Rogelio Martínez, Córdoba.</b>\n"
            "<b>Tribunales Federales de Córdoba-</b>\n\n"
            f"En los autos caratulados: {car_a}, que se tramitan por ante "
            f"{trib_a} de {nom} , de la ciudad de Córdoba, Provincia de Córdoba, "
            "con la intervención de ésta Oficina de Servicios Procesales (OSPRO), se ha dispuesto librar a Ud. "
            "el presente oficio, a fin de informar lo resuelto por dicho Tribunal respecto de la persona cuyos "
            "datos personales se mencionan a continuación:\n\n"
            f"{self._imp_datos_anchor()}\n\n"
            f"SENTENCIA N° {sent_n_a}, DE FECHA: {sent_f_a}. “Se Resuelve: {res_a}” "
            f"Fdo.: {firm_a}\n\n"
            f"Asimismo, se informa que la sentencia antes señalada quedó firme con fecha {sent_firmeza_a}\n"
            "Se adjuntan al presente oficio copia digital de la misma y del cómputo de pena respectivo.\n\n"
            "Sin otro particular, saludo a Ud. atentamente."
        )
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify, rich=True)

    def _plantilla_consulado(self):
        te = self.text_edits["Oficio Consulado"]
        te.clear()

        # ─ datos básicos ─
        loc_txt  = self.entry_localidad.text() or "Córdoba"
        hoy  = datetime.now()
        fecha = fecha_alineada(loc_txt, hoy, punto=True)
        sent_n = self.entry_sent_num.text() or "…"
        sent_f = self.entry_sent_date.text() or "…/…/…"
        res = self.entry_resuelvo.text() or "…"
        firm = self.entry_firmantes.text() or "…"
        car   = self.entry_caratula.text() or "“…”"
        trib  = self.entry_tribunal.currentText() or "la Cámara en lo Criminal y Correccional"
        pais  = self.entry_consulado.text() or "…"
        sent_firmeza = self.entry_sent_firmeza.text() or "…/…/…"
        car_a = self._field_anchor(self.entry_caratula, "edit_caratula", "carátula")
        trib_a = self._field_anchor(self.entry_tribunal, "combo_tribunal", "tribunal")
        pais_a = self._field_anchor(self.entry_consulado, "edit_consulado", "país")
        sent_n_a = self._field_anchor(self.entry_sent_num, "edit_sent_num", "…")
        sent_f_a = self._field_anchor(self.entry_sent_date, "edit_sent_fecha", "…/…/…")
        res_a = self._field_anchor(self.entry_resuelvo, "edit_resuelvo", "resuelvo")
        firm_a = self._field_anchor(self.entry_firmantes, "edit_firmantes", "firmantes")
        sent_firmeza_a = self._field_anchor(self.entry_sent_firmeza, "edit_sent_firmeza", "…/…/…")

        cuerpo = (
            "<b>Al Sr. Titular del Consulado </b>\n"
            "<b>de " + pais_a + " </b>\n"
            "<b>S/D:</b>\n\n"
            f"En los autos caratulados: {car_a}, que se tramitan por ante "
            f"{trib_a}, de la ciudad de Córdoba, Provincia de Córdoba, "
            "con la intervención de ésta Oficina de Servicios Procesales (OSPRO), se ha dispuesto librar el presente oficio, "
            "a fin de informar lo resuelto por dicho Tribunal respecto de la persona cuyos datos personales se mencionan a "
            "continuación:\n\n"
            f"{self._imp_datos_anchor()}\n\n"
            f"SENTENCIA N° {sent_n_a}, DE FECHA: {sent_f_a}. “Se Resuelve: {res_a}” "
            f"Fdo.: {firm_a}\n\n"
            f"Asimismo, se informa que la sentencia antes señalada quedó firme con fecha {sent_firmeza_a}\n"
            "Se adjuntan al presente oficio copia digital de la misma y del cómputo de pena respectivo.\n\n"
            "Sin otro particular, saludo a Ud. atentamente."
        )

        self._insert_paragraph(te, fecha, Qt.AlignRight)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify, rich=True)

    def _plantilla_registro_automotor(self):
        te = self.text_edits["Oficio Registro Automotor"]
        te.clear()

        loc  = self.entry_localidad.text() or "Córdoba"
        hoy  = datetime.now()
        fecha = fecha_alineada(loc, hoy, punto=True)
        sent_n = self.entry_sent_num.text() or "…"
        sent_f = self.entry_sent_date.text() or "…/…/…"
        res = self._res_decomiso()
        firm = self.entry_firmantes.text() or "…"
        car  = self.entry_caratula.text() or "“…”"
        trib = self.entry_tribunal.currentText() or "la Cámara en lo Criminal y Correccional"
        regn = self.entry_regn.text() or "…"
        rodado = self.entry_rodado.text() or "…"

        car_a = self._field_anchor(self.entry_caratula, "edit_caratula", "carátula")
        trib_a = self._field_anchor(self.entry_tribunal, "combo_tribunal", "tribunal")
        sent_n_a = self._field_anchor(self.entry_sent_num, "edit_sent_num", "…")
        sent_f_a = self._field_anchor(self.entry_sent_date, "edit_sent_fecha", "…/…/…")
        res_a = self._field_anchor(self.entry_resuelvo, "edit_resuelvo", "resuelvo")
        firm_a = self._field_anchor(self.entry_firmantes, "edit_firmantes", "firmantes")
        regn_a = self._field_anchor(self.entry_regn, "edit_regn", "…")
        rodado_a = self._field_anchor(self.entry_rodado, "edit_rodado", "objeto secuestrado/decomisado")

        cuerpo = (
            f"<b>AL SR. TITULAR DEL REGISTRO DE LA</b>\n"
            f"<b>PROPIEDAD DEL AUTOMOTOR N° {regn_a}</b>\n"
            "<b>S/D:</b>\n\n"
            f"\tEn los autos caratulados: {car_a}, que se tramitan por ante "
            f"{trib_a}, con intervención de esta Oficina de Servicios "
            "Procesales – OSPRO –, se ha dispuesto librar a Ud. el presente, a fin de informarle que mediante "
            f"Sentencia N° {sent_n_a} de fecha {sent_f_a}, dicho Tribunal resolvió ordenar el DECOMISO del "
            f"{rodado_a}.\n\n"
            "Se transcribe a continuación la parte pertinente de la misma:\n"
            f"“SE RESUELVE: {res_a}”. "
            f"(Fdo.: {firm_a}).\n\n"
            "Sin otro particular, saludo a Ud. atte."
        )
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify, rich=True)

    def _plantilla_tsj_secpenal(self):
        te = self.text_edits["Oficio TSJ Sec. Penal"]
        te.clear()

        loc  = self.entry_localidad.text() or "Córdoba"
        hoy  = datetime.now()
        fecha = fecha_alineada(loc, hoy, punto=True)
        sent_n = self.entry_sent_num.text() or "…"
        sent_f = self.entry_sent_date.text() or "…/…/…"
        res = self._res_decomiso()
        firm = self.entry_firmantes.text() or "…"
        car  = self.entry_caratula.text() or "“…”"
        trib = self.entry_tribunal.currentText() or "la Cámara en lo Criminal y Correccional"
        regn = self.entry_regn.text() or "…de …"
        rodado = self.entry_rodado.text() or "…"
        deposito = self.entry_deposito.currentText() or "…"

        car_a = self._field_anchor(self.entry_caratula, "edit_caratula", "carátula")
        trib_a = self._field_anchor(self.entry_tribunal, "combo_tribunal", "tribunal")
        sent_n_a = self._field_anchor(self.entry_sent_num, "edit_sent_num", "…")
        sent_f_a = self._field_anchor(self.entry_sent_date, "edit_sent_fecha", "…/…/…")
        res_a = self._field_anchor(self.entry_resuelvo, "edit_resuelvo", "resuelvo")
        firm_a = self._field_anchor(self.entry_firmantes, "edit_firmantes", "firmantes")
        rodado_a = self._field_anchor(self.entry_rodado, "edit_rodado", "objeto secuestrado/decomisado")
        deposito_a = self._field_anchor(self.entry_deposito, "combo_deposito", "depósito")

        car_a = self._field_anchor(self.entry_caratula, "edit_caratula", "carátula")
        trib_a = self._field_anchor(self.entry_tribunal, "combo_tribunal", "tribunal")
        sent_n_a = self._field_anchor(self.entry_sent_num, "edit_sent_num", "…")
        sent_f_a = self._field_anchor(self.entry_sent_date, "edit_sent_fecha", "…/…/…")
        res_a = self._field_anchor(self.entry_resuelvo, "edit_resuelvo", "resuelvo")
        firm_a = self._field_anchor(self.entry_firmantes, "edit_firmantes", "firmantes")
        regn_a = self._field_anchor(self.entry_regn, "edit_regn", "…")
        rodado_a = self._field_anchor(self.entry_rodado, "edit_rodado", "objeto secuestrado/decomisado")
        deposito_a = self._field_anchor(self.entry_deposito, "combo_deposito", "depósito")
        cuerpo = (
            "<b>A LA SRA. SECRETARIA PENAL</b>\n"
            "<b>DEL TRIBUNAL SUPERIOR DE JUSTICIA</b>\n"
            "<b>DRA. MARIA PUEYRREDON DE MONFARRELL</b>\n"
            "<b>S______/_______D:</b>\n\n"
            f"En los autos caratulados: {car_a}, que se tramitan por ante "
            f"{trib_a}, con conocimiento e intervención de esta Oficina de Servicios "
            "Procesales – OSPRO –, se ha dispuesto librar a Ud. el presente a fin de poner en conocimiento lo "
            f"resuelto por la Sentencia N° {sent_n_a} del {sent_f_a}, dictada por el tribunal mencionado, en virtud de la cual "
            "se ordenó el DECOMISO de los siguientes objetos:\n\n"
            f"<table border='1' cellspacing='0' cellpadding='2'>"
            f"<tr><th>Tipos de elementos</th><th>Ubicación actual</th></tr>"
            f"<tr><td>{rodado_a}</td><td>{deposito_a}</td></tr></table>\n\n"
            "Pongo en su conocimiento que la mencionada sentencia se encuentra firme, transcribiéndose a "
            "continuación la parte pertinente de la misma:\n"
            f"“SE RESUELVE: {res_a}”. "
            f"(Fdo.: {firm_a}).\n\n"
            f"Asimismo, se informa que en el día de la fecha se comunicó dicha resolución al Registro del Automotor "
            f"donde está radicado el vehículo, Nº {regn_a}.\n\n"
            "Sin otro particular, saludo a Ud. muy atentamente."
        )
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify, rich=True)

    def _plantilla_tsj_secpenal_depositos(self):
        te = self.text_edits["Oficio TSJ Sec. Penal (Depósitos)"]
        te.clear()

        loc  = self.entry_localidad.text() or "Córdoba"
        hoy  = datetime.now()
        fecha = fecha_alineada(loc, hoy, punto=True)
        sent_n = self.entry_sent_num.text() or "…"
        sent_f = self.entry_sent_date.text() or "…/…/…"
        res = self._res_decomiso()
        firm = self.entry_firmantes.text() or "…"
        car  = self.entry_caratula.text() or "“…”"
        trib = self.entry_tribunal.currentText() or "la Cámara en lo Criminal y Correccional"
        rodado = self.entry_rodado.text() or "…"
        deposito = self.entry_deposito.currentText() or "…"

        car_a = self._field_anchor(self.entry_caratula, "edit_caratula", "carátula")
        trib_a = self._field_anchor(self.entry_tribunal, "combo_tribunal", "tribunal")
        sent_n_a = self._field_anchor(self.entry_sent_num, "edit_sent_num", "…")
        sent_f_a = self._field_anchor(self.entry_sent_date, "edit_sent_fecha", "…/…/…")
        res_a = self._field_anchor(self.entry_resuelvo, "edit_resuelvo", "resuelvo")
        firm_a = self._field_anchor(self.entry_firmantes, "edit_firmantes", "firmantes")
        rodado_a = self._field_anchor(self.entry_rodado, "edit_rodado", "objeto secuestrado/decomisado")
        deposito_a = self._field_anchor(self.entry_deposito, "combo_deposito", "depósito")
        comisaria_a = self._field_anchor(self.entry_comisaria, "edit_comisaria", "comisaría")

        cuerpo = (
            "<b>A LA SRA. SECRETARIA PENAL</b>\n"
            "<b>DEL TRIBUNAL SUPERIOR DE JUSTICIA</b>\n"
            "<b>DRA. MARIA PUEYRREDON DE MONFARRELL</b>\n"
            "<b>S/D:</b>\n\n"
            f"En los autos caratulados: {car_a}, que se tramitan por ante "
            f"{trib_a}, con intervención de esta Oficina de Servicios Procesales "
            f"- OSPRO -, se ha dispuesto librar a Ud. el presente, a fin de informarle que mediante Sentencia N° {sent_n_a} "
            f"de {sent_f_a}, dicho Tribunal resolvió ordenar el DECOMISO de los siguientes objetos:\n\n"
            f"<table border='1' cellspacing='0' cellpadding='2'>"
            f"<tr><th>Descripción del objeto</th><th>Ubicación Actual</th></tr>"
            f"<tr><td>{rodado_a}</td><td>{deposito_a}</td></tr></table>\n\n"
            f"Se hace saber a Ud. que el/los elemento/s referido/s se encuentra/n en la Cría. {comisaria_a} de la Policía de Córdoba "
            "y en el día de la fecha se libró oficio a dicha dependencia policial a los fines de remitir al Depósito General "
            "de Efectos Secuestrados el/los objeto/s decomisado/s.\n\n"
            "Asimismo, informo que la sentencia referida se encuentra firme, transcribiéndose a continuación la parte "
            f"pertinente de la misma: “SE RESUELVE: {res_a}”. "
            f"(Fdo.: {firm_a}).\n\n"
            "Sin otro particular, saludo a Ud. muy atentamente."
        )
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify, rich=True)

    def _plantilla_comisaria_traslado(self):
        te = self.text_edits["Oficio Comisaría Traslado"]
        te.clear()

        loc  = self.entry_localidad.text() or "Córdoba"
        hoy  = datetime.now()
        fecha = fecha_alineada(loc, hoy, punto=True)
        sent_n = self.entry_sent_num.text() or "…"
        sent_f = self.entry_sent_date.text() or "…/…/…"
        res = self._res_decomiso()
        firm = self.entry_firmantes.text() or "…"
        car  = self.entry_caratula.text() or "“…”"
        trib = self.entry_tribunal.currentText() or "la Cámara en lo Criminal y Correccional"
        comisaria = self.entry_comisaria.text() or "…"
        rodado = self.entry_rodado.text() or "…"

        car_a = self._field_anchor(self.entry_caratula, "edit_caratula", "carátula")
        trib_a = self._field_anchor(self.entry_tribunal, "combo_tribunal", "tribunal")
        sent_n_a = self._field_anchor(self.entry_sent_num, "edit_sent_num", "…")
        sent_f_a = self._field_anchor(self.entry_sent_date, "edit_sent_fecha", "…/…/…")
        res_a = self._field_anchor(self.entry_resuelvo, "edit_resuelvo", "resuelvo")
        firm_a = self._field_anchor(self.entry_firmantes, "edit_firmantes", "firmantes")
        rodado_a = self._field_anchor(self.entry_rodado, "edit_rodado", "objeto secuestrado/decomisado")
        comisaria_a = self._field_anchor(self.entry_comisaria, "edit_comisaria", "…")

        cuerpo = (
            f"<b>AL SR. TITULAR</b>\n"
            f"<b>DE LA COMISARÍA N° {comisaria_a} </b>\n"
            "<b>DE LA POLICÍA DE CÓRDOBA</b>\n"
            "<b>S/D:</b>\n\n"
            f"En los autos caratulados: {car_a}, que se tramitan por ante "
            f"{trib_a}, con intervención de esta Oficina de Servicios Procesales "
            "- OSPRO -, se ha dispuesto librar a Ud. el presente, a los fines de solicitarle que personal a su cargo "
            "traslade los efectos que a continuación se detallan al Depósito General de Efectos Secuestrados "
            "-sito en calle Abdel Taier n° 270, B° Comercial, de esta ciudad de Córdoba-, para que sean allí recibidos:\n\n"
            f"{rodado_a}\n\n"
            "Lo solicitado obedece a directivas generales impartidas por la Secretaría Penal del T.S.J, de la cual "
            "depende esta Oficina, para los casos en los que se haya dictado la pena de decomiso y los objetos aún "
            "estén en Comisarías, Subcomisarías y otras dependencias policiales.\n\n"
            "Se transcribe a continuación la parte pertinente de la Sentencia que así lo ordena:\n"
            f"Sentencia N° {sent_n_a} de fecha {sent_f_a}, “{res_a}” "
            f"(Fdo.: {firm_a}), elemento/s que fuera/n secuestrado/s "
            "en las presentes actuaciones y que actualmente se encuentra/n en el Depósito de la Comisaría a su cargo.\n\n"
            "Sin otro particular, saludo a Ud. muy atentamente."
        )
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify, rich=True)

    def _plantilla_tsj_secpenal_elementos(self):
        te = self.text_edits["Oficio TSJ Sec. Penal (Elementos)"]
        te.clear()

        loc  = self.entry_localidad.text() or "Córdoba"
        hoy  = datetime.now()
        fecha = fecha_alineada(loc, hoy, punto=True)
        sent_n = self.entry_sent_num.text() or "…"
        sent_f = self.entry_sent_date.text() or "…/…/…"
        res = self._res_decomiso()
        firm = self.entry_firmantes.text() or "…"
        car  = self.entry_caratula.text() or "“…”"
        trib = self.entry_tribunal.currentText() or "la Cámara en lo Criminal y Correccional"
        rodado = self.entry_rodado.text() or "…"
        deposito = self.entry_deposito.currentText() or "…"

        car_a = self._field_anchor(self.entry_caratula, "edit_caratula", "carátula")
        trib_a = self._field_anchor(self.entry_tribunal, "combo_tribunal", "tribunal")
        sent_n_a = self._field_anchor(self.entry_sent_num, "edit_sent_num", "…")
        sent_f_a = self._field_anchor(self.entry_sent_date, "edit_sent_fecha", "…/…/…")
        res_a = self._field_anchor(self.entry_resuelvo, "edit_resuelvo", "resuelvo")
        firm_a = self._field_anchor(self.entry_firmantes, "edit_firmantes", "firmantes")
        rodado_a = self._field_anchor(self.entry_rodado, "edit_rodado", "objeto secuestrado/decomisado")
        deposito_a = self._field_anchor(self.entry_deposito, "combo_deposito", "depósito")

        cuerpo = (
            "<b>A LA SRA. SECRETARIA PENAL</b>\n"
            "<b>DEL TRIBUNAL SUPERIOR DE JUSTICIA</b>\n"
            "<b>DRA. MARIA PUEYRREDON DE MONFARRELL</b>\n"
            "<b>S______/_______D:</b>\n\n"
            f"En los autos caratulados: {car_a}, que se tramitan por ante "
            f"{trib_a}, con conocimiento e intervención de ésta Oficina de Servicios "
            "Procesales ‑ OSPRO‑, se ha dispuesto librar a Ud. el presente a fin de poner en conocimiento lo resuelto "
            f"por la Sentencia N° {sent_n_a} del {sent_f_a}, dictada por la Cámara mencionada, en virtud de la cual se ordenó el "
            "DECOMISO de los siguientes objetos:\n\n"
            f"<table border='1' cellspacing='0' cellpadding='2'>"
            f"<tr><th>TIPOS DE ELEMENTOS</th><th>UBICACIÓN ACTUAL</th></tr>"
            f"<tr><td>{rodado_a}</td><td>{deposito_a}</td></tr></table>\n\n"
            "Pongo en su conocimiento que la mencionada resolución se encuentra firme, transcribiéndose a continuación "
            f"la parte pertinente de la misma: “SE RESUELVE: {res_a}”. "
            f"(Fdo.: {firm_a}).\n\n"
            "Sin otro particular, saludo a Ud. muy atentamente."
        )
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify, rich=True)

    def _plantilla_automotores_secuestrados(self):
        te = self.text_edits["Oficio Automotores Secuestrados"]
        te.clear()

        loc  = self.entry_localidad.text() or "Córdoba"
        hoy  = datetime.now()
        fecha = fecha_alineada(loc, hoy, punto=True)
        car  = self.entry_caratula.text() or "“…”"
        trib = self.entry_tribunal.currentText() or "la Cámara en lo Criminal y Correccional"
        rodado = self.entry_rodado.text() or "…"
        deposito = self.entry_deposito.currentText() or "…"
        numero_itim = self.entry_itim_num.text() or "…"
        fecha_itim = self.entry_itim_fecha.text() or "…"
        titular_veh = self.entry_titular_veh.text() or "…"
        dep_def = self.entry_dep_def.currentText() or "…"

        car_a = self._field_anchor(self.entry_caratula, "edit_caratula", "carátula")
        trib_a = self._field_anchor(self.entry_tribunal, "combo_tribunal", "tribunal")
        rodado_a = self._field_anchor(self.entry_rodado, "edit_rodado", "objeto secuestrado/decomisado")
        deposito_a = self._field_anchor(self.entry_deposito, "combo_deposito", "depósito")
        numero_itim_a = self._field_anchor(self.entry_itim_num, "edit_itim_num", "…")
        fecha_itim_a = self._field_anchor(self.entry_itim_fecha, "edit_itim_fecha", "…")
        titular_veh_a = self._field_anchor(self.entry_titular_veh, "edit_titular_veh", "…")
        dep_def_a = self._field_anchor(self.entry_dep_def, "combo_dep_def", "carácter")

        cuerpo = (
            "<b>A LA OFICINA DE</b>\n"
            "<b>AUTOMOTORES SECUESTRADOS EN </b>\n"
            "<b>CAUSAS PENALES, TRIBUNAL SUPERIOR DE JUSTICIA.</b>\n"
            "<b>S/D:</b>\n\n"
            f"En los autos caratulados: {car_a}, que se tramitan por ante "
            f"{trib_a}, con intervención de ésta Oficina de Servicios Procesales "
            "(OSPRO), se ha resuelto enviar a Ud. el presente a fines de solicitarle que establezca lo necesario para que, "
            "por intermedio de quien corresponda, se coloque a la orden y disposición del Tribunal señalado, el rodado "
            f"{rodado_a}, vehículo que se encuentra en el {deposito_a}.\n\n"
            "Se hace saber a Ud. que dicha petición obedece a que el Tribunal mencionado ha dispuesto la entrega del "
            f"referido vehículo en carácter {dep_def_a} a su titular registral {titular_veh_a}. Para mayor recaudo se "
            "adjunta en documento informático copia de la resolución que dispuso la medida.\n\n"
            "Finalmente, se informa que a dicho rodado, se le realizó el correspondiente Informe "
            f"Técnico de Identificación de Matrículas N° {numero_itim_a} de fecha {fecha_itim_a}, concluyendo que la unidad no "
            "presenta adulteración en sus matrículas identificatorias. (Revisar en el informe y, de existir informe de "
            "dominio, remitirlo también; no es indispensable según la Oficina del T.S.J.).\n\n"
            "Saludo a Ud. muy atentamente."
        )
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify, rich=True)

    def _plantilla_fiscalia_instruccion(self):
        te = self.text_edits["Oficio Fiscalía Instrucción"]
        te.clear()

        loc, hoy = self.entry_localidad.text() or "Córdoba", datetime.now()
        fecha = fecha_alineada(loc, hoy, punto=True)
        car   = self.entry_caratula.text() or "“…”"
        trib  = self.entry_tribunal.currentText() or "la Cámara en lo Criminal y Correccional"
        sent_n = self.entry_sent_num.text() or "…"
        sent_f = self.entry_sent_date.text() or "…/…/…"
        res_html = self.entry_resuelvo.property("html")
        if res_html:
            plano = html_a_plano(res_html, mantener_saltos=False)
        else:
            plano = self.entry_resuelvo.text()
        plano = " ".join(plano.splitlines())
        pattern = r"\b([IVXLCDM]+|\d+)[\.\)]\s+([\s\S]*?)(?=\b(?:[IVXLCDM]+|\d+)[\.\)]\s+|$)"
        partes = []
        for m in re.finditer(pattern, plano, re.DOTALL | re.IGNORECASE):
            num, txt = m.group(1), m.group(2).strip()
            if re.search(r"investig|esclarec|antecedente|instruc", txt, re.IGNORECASE):
                partes.append(f"{num}. {txt}")
        res = " ".join(partes) if partes else (self.entry_resuelvo.text() or "…")
        firm = self.entry_firmantes.text() or "…"

        car_a = self._field_anchor(self.entry_caratula, "edit_caratula", "carátula")
        trib_a = self._field_anchor(self.entry_tribunal, "combo_tribunal", "tribunal")
        sent_n_a = self._field_anchor(self.entry_sent_num, "edit_sent_num", "…")
        sent_f_a = self._field_anchor(self.entry_sent_date, "edit_sent_fecha", "…/…/…")
        res_a = self._field_anchor(self.entry_resuelvo, "edit_resuelvo", "resuelvo")
        firm_a = self._field_anchor(self.entry_firmantes, "edit_firmantes", "firmantes")
        cuerpo = (
            "<b>Sr/a Fiscal de </b>\n"
            "<b>Instrucción que por turno corresponda</b>\n"
            "<b>S/D:</b>\n\n"
            f"En los autos caratulados: {car_a}, que se tramitan por ante "
            f"{trib_a}, con intervención de la Oficina de Servicios Procesales "
            "(OSPRO), se ha dispuesto librar a Ud. el presente, por disposición de la Cámara señalada y conforme a la "
            "sentencia dictada en la causa de referencia, remitiendo los antecedentes obrantes en el expediente mencionado "
            "a fin de investigar la posible comisión de un delito perseguible de oficio.\n\n"
            f"Se transcribe a continuación la parte pertinente: “Se resuelve: {res_a}”. "
            f"(Fdo.: {firm_a}).\n\n"
            "Sin otro particular, saludo a Ud. atte."
        )
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify, rich=True)

    def _plantilla_policia_documentacion(self):
        te = self.text_edits["Oficio Policía Documentación"]
        te.clear()
        sent_n = self.entry_sent_num.text() or "…"
        sent_f = self.entry_sent_date.text() or "…/…/…"
        res = self.entry_resuelvo.text() or "…"
        firm = self.entry_firmantes.text() or "…"
        loc, hoy = self.entry_localidad.text() or "Córdoba", datetime.now()
        fecha = fecha_alineada(loc, hoy, punto=True)
        car   = self.entry_caratula.text() or "“…”"
        trib  = self.entry_tribunal.currentText() or "la Cámara en lo Criminal y Correccional"
        sent_firmeza = self.entry_sent_firmeza.text() or "…/…/…"

        car_a = self._field_anchor(self.entry_caratula, "edit_caratula", "carátula")
        trib_a = self._field_anchor(self.entry_tribunal, "combo_tribunal", "tribunal")
        sent_n_a = self._field_anchor(self.entry_sent_num, "edit_sent_num", "…")
        sent_f_a = self._field_anchor(self.entry_sent_date, "edit_sent_fecha", "…/…/…")
        res_a = self._field_anchor(self.entry_resuelvo, "edit_resuelvo", "resuelvo")
        firm_a = self._field_anchor(self.entry_firmantes, "edit_firmantes", "firmantes")
        sent_firmeza_a = self._field_anchor(self.entry_sent_firmeza, "edit_sent_firmeza", "…/…/…")
        sent_n_a = self._field_anchor(self.entry_sent_num, "edit_sent_num", "…")
        sent_f_a = self._field_anchor(self.entry_sent_date, "edit_sent_fecha", "…/…/…")
        res_a = self._field_anchor(self.entry_resuelvo, "edit_resuelvo", "resuelvo")
        firm_a = self._field_anchor(self.entry_firmantes, "edit_firmantes", "firmantes")
        sent_firmeza_a = self._field_anchor(self.entry_sent_firmeza, "edit_sent_firmeza", "…/…/…")

        car_a = self._field_anchor(self.entry_caratula, "edit_caratula", "carátula")
        trib_a = self._field_anchor(self.entry_tribunal, "combo_tribunal", "tribunal")
        sent_n_a = self._field_anchor(self.entry_sent_num, "edit_sent_num", "…")
        sent_f_a = self._field_anchor(self.entry_sent_date, "edit_sent_fecha", "…/…/…")
        res_a = self._field_anchor(self.entry_resuelvo, "edit_resuelvo", "resuelvo")
        firm_a = self._field_anchor(self.entry_firmantes, "edit_firmantes", "firmantes")
        sent_firmeza_a = self._field_anchor(self.entry_sent_firmeza, "edit_sent_firmeza", "…/…/…")
        computo, tipo = self._imp_computo()
        computo = computo or "…"
        if tipo.startswith("Efec"):
            comp_label = "el cómputo de pena respectivo"
        else:
            comp_label = "la resolución que fija la fecha de cumplimiento de los arts. 27 y 27 bis del C.P."
        car_a = self._field_anchor(self.entry_caratula, "edit_caratula", "carátula")
        trib_a = self._field_anchor(self.entry_tribunal, "combo_tribunal", "tribunal")
        sent_n_a = self._field_anchor(self.entry_sent_num, "edit_sent_num", "…")
        sent_f_a = self._field_anchor(self.entry_sent_date, "edit_sent_fecha", "…/…/…")
        res_a = self._field_anchor(self.entry_resuelvo, "edit_resuelvo", "resuelvo")
        firm_a = self._field_anchor(self.entry_firmantes, "edit_firmantes", "firmantes")
        sent_firmeza_a = self._field_anchor(self.entry_sent_firmeza, "edit_sent_firmeza", "…/…/…")
        computo_a = anchor(computo, "edit_computo", "…") if computo else anchor("", "edit_computo", "…")

        cuerpo = (
            "<b>Sr. Titular de la División de Documentación Personal </b>\n"
            "<b>Policía de la Provincia de Córdoba</b>\n"
            "<b>S ______/_______D:</b>\n\n"
            f"En los autos caratulados: {car_a}, que se tramitan ante "
            f"{trib_a}, con intervención de esta Oficina de Servicios Procesales (OSPRO), "
            "se ha resuelto enviar el presente oficio a fin de informar lo resuelto por dicho Tribunal respecto de la persona "
            "cuyos datos se detallan a continuación:\n\n"
            f"{self._imp_datos_anchor()}\n\n"
            f"SENTENCIA N° {sent_n_a}, DE FECHA {sent_f_a} “Se resuelve: {res_a}. PROTOCOLÍCESE. NOTIFÍQUESE.” "
            f"(Fdo.: {firm_a}).\n\n"
            f"Se transcribe a continuación {comp_label}: {computo_a}\n"
            f"Fecha de firmeza de la Sentencia: {sent_firmeza_a}\n\n"
            "Saluda a Ud. atentamente."
        )
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify, rich=True)

    def _plantilla_registro_civil(self):
        te = self.text_edits["Oficio Registro Civil"]
        te.clear()
        sent_n = self.entry_sent_num.text() or "…"
        sent_f = self.entry_sent_date.text() or "…/…/…"
        res = self.entry_resuelvo.text() or "…"
        firm = self.entry_firmantes.text() or "…"
        loc, hoy = self.entry_localidad.text() or "Córdoba", datetime.now()
        fecha = fecha_alineada(loc, hoy, punto=True)
        car   = self.entry_caratula.text() or "“…”"
        trib  = self.entry_tribunal.currentText() or "la Cámara en lo Criminal y Correccional"
        sent_firmeza = self.entry_sent_firmeza.text() or "…/…/…"

        car_a = self._field_anchor(self.entry_caratula, "edit_caratula", "carátula")
        trib_a = self._field_anchor(self.entry_tribunal, "combo_tribunal", "tribunal")
        sent_n_a = self._field_anchor(self.entry_sent_num, "edit_sent_num", "…")
        sent_f_a = self._field_anchor(self.entry_sent_date, "edit_sent_fecha", "…/…/…")
        res_a = self._field_anchor(self.entry_resuelvo, "edit_resuelvo", "resuelvo")
        firm_a = self._field_anchor(self.entry_firmantes, "edit_firmantes", "firmantes")
        sent_firmeza_a = self._field_anchor(self.entry_sent_firmeza, "edit_sent_firmeza", "…/…/…")

        cuerpo = (
            "<b>Sr/a Director/a del </b>\n"
            "<b>Registro Civil y Capacidad de las Personas</b>\n"
            "<b>S/D:</b>\n\n"
            f"En los autos caratulados: {car_a}, que se tramitan por ante "
            f"{trib_a}, de la ciudad de Córdoba, Provincia de Córdoba, con "
            "intervención de ésta Oficina de Servicios Procesales (OSPRO), se ha dispuesto librar a Ud. el presente oficio, "
            "a fin de informar lo resuelto por dicho Tribunal respecto de la persona cuyos datos se mencionan a continuación:\n\n"
            f"{self._imp_datos_anchor()}\n\n"
            f"SENTENCIA N° {sent_n_a}, DE FECHA {sent_f_a}: “Se Resuelve: {res_a}” "
            f"Fdo.: {firm_a}\n\n"
            f"Asimismo, se informa que la sentencia antes señalada quedó firme con fecha {sent_firmeza_a}\n"
            "Se adjuntan al presente oficio copia digital de la misma y del cómputo de pena respectivo.\n\n"
            "Sin otro particular, saludo a Ud. atentamente."
        )
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify, rich=True)

    def _plantilla_registro_condenados_sexuales(self):
        te = self.text_edits["Oficio Registro Condenados Sexuales"]
        te.clear()
        sent_n = self.entry_sent_num.text() or "…"
        sent_f = self.entry_sent_date.text() or "…/…/…"
        res = self.entry_resuelvo.text() or "…"
        firm = self.entry_firmantes.text() or "…"
        loc, hoy = self.entry_localidad.text() or "Córdoba", datetime.now()
        fecha = fecha_alineada(loc, hoy, punto=True)
        car   = self.entry_caratula.text() or "“…”"
        trib  = self.entry_tribunal.currentText() or "la CÁMARA EN LO CRIMINAL Y CORRECCIONAL"
        sent_firmeza = self.entry_sent_firmeza.text() or "…/…/…"
        computo, _ = self._imp_computo()
        extincion = computo or "…"
        condena = self._imp_field('condena') or "…"
        servicio = self._imp_field('servicio_penitenciario') or "…"
        legajo = self._imp_field('legajo') or "…"
        delitos = self._imp_field('delitos') or "…"
        antecedentes = self._imp_field('antecedentes') or "…"
        tratamientos = self._imp_field('tratamientos') or "…"

        car_a = self._field_anchor(self.entry_caratula, "edit_caratula", "carátula")
        trib_a = self._field_anchor(self.entry_tribunal, "combo_tribunal", "tribunal")
        sent_n_a = self._field_anchor(self.entry_sent_num, "edit_sent_num", "…")
        sent_f_a = self._field_anchor(self.entry_sent_date, "edit_sent_fecha", "…/…/…")
        res_a = self._field_anchor(self.entry_resuelvo, "edit_resuelvo", "resuelvo")
        firm_a = self._field_anchor(self.entry_firmantes, "edit_firmantes", "firmantes")
        sent_firmeza_a = self._field_anchor(self.entry_sent_firmeza, "edit_sent_firmeza", "…/…/…")
        extincion_a = anchor(extincion, "edit_computo", "…") if extincion else anchor("", "edit_computo", "…")
        condena_a = anchor(condena, "edit_condena", "…") if condena else anchor("", "edit_condena", "…")
        servicio_a = anchor(servicio, "combo_servicio_penitenciario", "…")
        legajo_a = anchor(legajo, "edit_legajo", "…")
        delitos_a = anchor(delitos, "edit_delitos", "…")
        antecedentes_a = anchor(antecedentes, "edit_antecedentes", "…")
        tratamientos_a = anchor(tratamientos, "edit_tratamientos", "…")
        cuerpo = (
            "<b>Al Sr. Titular del </b>\n"
            "<b>Registro Provincial de Personas Condenadas </b>\n"
            "<b>por Delitos contra la Integridad Sexual</b>\n"
            "<b>S./D.</b>\n\n"
            f"En los autos caratulados: {car_a}, que se tramitan por ante "
            f"{trib_a}, con intervención de ésta Oficina de Servicios Procesales (OSPRO), "
            f"se ha resuelto librar el presente a fin de registrar en dicha dependencia lo resuelto por Sentencia N° {sent_n_a}, "
            f"de fecha {sent_f_a} dictada por el mencionado Tribunal.\n\n"
            "I. DATOS PERSONALES\n"
            f"{self._imp_datos_anchor()}\n"
            "II. IDENTIFICACIÓN DACTILAR (adjuntar ficha).\n"
            "III. DATOS DE CONDENA Y LIBERACIÓN (adjuntar copia de la sentencia).\n"
            f"   • Condena impuesta: {condena_a}\n"
            f"   • Fecha firmeza: {sent_firmeza_a}\n"
            f"   • Fecha de extinción: {extincion_a}\n"
            f"   • Servicio Penitenciario: {servicio_a}\n"
            f"     Legajo: {legajo_a}\n"
            f"   • Delito: {delitos_a}\n"
            f"IV. HISTORIAL DE DELITOS Y CONDENAS ANTERIORES:\n"
            f"   {antecedentes_a}\n"
            f"V. TRATAMIENTOS MÉDICOS Y PSICOLÓGICOS:\n"
            f"   {tratamientos_a}\n"
            "VI. OTROS DATOS DE INTERÉS:\n\n"
            f"   Se le hace saber que {trib_a} resolvió mediante Sentencia N° {sent_n_a} de fecha {sent_f_a} lo siguiente “{res_a}.”.\n"
            f"   Fdo.: {firm_a}.\n\n"
            "Se adjuntan copias digitales de ficha RNR, sentencia firme y cómputo.\n\n"
            "Saludo a Ud. atentamente."
        )
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify, rich=True)

    def _plantilla_registro_nacional_reincidencia(self):
        te = self.text_edits["Oficio Registro Nacional Reincidencia"]
        te.clear()
        sent_n = self.entry_sent_num.text() or "…"
        sent_f = self.entry_sent_date.text() or "…/…/…"
        res = self.entry_resuelvo.text() or "…"
        firm = self.entry_firmantes.text() or "…"
        loc, hoy = self.entry_localidad.text() or "Córdoba", datetime.now()
        fecha = fecha_alineada(loc, hoy, punto=True)
        car   = self.entry_caratula.text() or "“…”"
        trib  = self.entry_tribunal.currentText() or "la Cámara en lo Criminal y Correccional"
        sent_firmeza = self.entry_sent_firmeza.text() or "…/…/…"

        car_a = self._field_anchor(self.entry_caratula, "edit_caratula", "carátula")
        trib_a = self._field_anchor(self.entry_tribunal, "combo_tribunal", "tribunal")
        sent_n_a = self._field_anchor(self.entry_sent_num, "edit_sent_num", "…")
        sent_f_a = self._field_anchor(self.entry_sent_date, "edit_sent_fecha", "…/…/…")
        res_a = self._field_anchor(self.entry_resuelvo, "edit_resuelvo", "resuelvo")
        firm_a = self._field_anchor(self.entry_firmantes, "edit_firmantes", "firmantes")
        sent_firmeza_a = self._field_anchor(self.entry_sent_firmeza, "edit_sent_firmeza", "…/…/…")

        cuerpo = (
            "<b>Al Sr. Director del </b>\n"
            "<b>Registro Nacional de Reincidencia</b>\n"
            "<b>S/D:</b>\n\n"
            "De acuerdo a lo dispuesto por el art. 2º de la Ley 22.177, remito a Ud. testimonio de la parte dispositiva "
            "de la resolución dictada en los autos caratulados: "
            f"{car_a}, que se tramitan por ante "
            f"{trib_a}, de la ciudad de Córdoba, Provincia de Córdoba, con intervención de ésta "
            "Oficina de Servicios Procesales (OSPRO), respecto de:\n\n"
            f"{self._imp_datos_anchor()}\n\n"
            f"SENTENCIA N° {sent_n_a}, DE FECHA {sent_f_a}: “{res_a} PROTOCOLÍCESE. NOTIFÍQUESE.” (Fdo.: {firm_a}).\n\n"
            "Se transcribe a continuación el cómputo de pena respectivo / la resolución que fija la fecha de cumplimiento "
            "de los arts. 27 y 27 bis del C.P.\n"
            f"Fecha de firmeza de la sentencia: {sent_firmeza_a}\n\n"
            "Saluda a Ud. atentamente."
        )
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify, rich=True)

    def _plantilla_repat(self):
        te = self.text_edits["Oficio RePAT"]
        te.clear()
        sent_n = self.entry_sent_num.text() or "…"
        sent_f = self.entry_sent_date.text() or "…/…/…"
        sent_firmeza = self.entry_sent_firmeza.text() or "…/…/…"
        res = self.entry_resuelvo.text() or "…"
        loc, hoy = self.entry_localidad.text() or "Córdoba", datetime.now()
        fecha = fecha_alineada(loc, hoy, punto=True)
        car   = self.entry_caratula.text() or "“…”"
        trib  = self.entry_tribunal.currentText() or "la Cámara en lo Criminal y Correccional"
        firm = self.entry_firmantes.text() or "…"

        car_a = self._field_anchor(self.entry_caratula, "edit_caratula", "carátula")
        trib_a = self._field_anchor(self.entry_tribunal, "combo_tribunal", "tribunal")
        sent_n_a = self._field_anchor(self.entry_sent_num, "edit_sent_num", "…")
        sent_f_a = self._field_anchor(self.entry_sent_date, "edit_sent_fecha", "…/…/…")
        res_a = self._field_anchor(self.entry_resuelvo, "edit_resuelvo", "resuelvo")
        firm_a = self._field_anchor(self.entry_firmantes, "edit_firmantes", "firmantes")
        sent_firmeza_a = self._field_anchor(self.entry_sent_firmeza, "edit_sent_firmeza", "…/…/…")
        cuerpo = (
            "<b>SR. DIRECTOR DEL REGISTRO PROVINCIAL </b>\n"
            "<b>DE ANTECEDENTES DE TRÁNSITO (RePAT)</b>\n"
            "<b>S/D:</b>\n\n"
            f"En los autos caratulados: {car_a}, que se tramitan por ante "
            f"{trib_a}, de esta ciudad de Córdoba, con intervención de esta Oficina de "
            "Servicios Procesales (OSPRO), se ha dispuesto librar a Ud. el presente a fin de comunicar lo resuelto por "
            "dicho Tribunal respecto de la persona cuyos datos se detallan a continuación:\n\n"
            f"{self._imp_datos_anchor()}\n\n"
            f"SENTENCIA N° {sent_n_a}, DE FECHA {sent_f_a}: “Se resuelve: {res_a}” "
            f"(Fdo.: {firm_a}).\n\n"
            f"Asimismo, se informa que la sentencia condenatoria quedó firme con fecha {sent_firmeza_a}\n"
            "Se adjuntan copias digitales de la sentencia y del cómputo de pena respectivos.\n\n"
            "Saludo a Ud. atentamente."
        )
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify, rich=True)

    def _plantilla_juzgado_ninez(self):
        te = self.text_edits["Oficio Juzgado Niñez‑Adolescencia"]
        te.clear()

        loc, hoy = self.entry_localidad.text() or "Córdoba", datetime.now()
        fecha = fecha_alineada(loc, hoy, punto=True)
        car   = self.entry_caratula.text() or "“…”"
        trib  = self.entry_tribunal.currentText() or "la Cámara en lo Criminal y Correccional"
        sent_n = self.entry_sent_num.text() or "…"
        sent_f = self.entry_sent_date.text() or "…/…/…"
        res = self.entry_resuelvo.text() or "…"
        firm = self.entry_firmantes.text() or "…"
        juz = self._imp_field('juz_navfyg') or (
            "Juzgado de Niñez, Adolescencia, Violencia Familiar y de Género de "
            "….. Nom. – Sec. N° ….."
        )
        if juz.startswith("Juzgado de Niñez,"):
            juz = (juz.replace(", Violencia", ",\nViolencia")
                      .replace("Género de ", "Género de \n"))
        ee_rel = self._imp_field('ee_relacionado') or "…………."

        car_a = self._field_anchor(self.entry_caratula, "edit_caratula", "carátula")
        trib_a = self._field_anchor(self.entry_tribunal, "combo_tribunal", "tribunal")
        sent_n_a = self._field_anchor(self.entry_sent_num, "edit_sent_num", "…")
        sent_f_a = self._field_anchor(self.entry_sent_date, "edit_sent_fecha", "…/…/…")
        res_a = self._field_anchor(self.entry_resuelvo, "edit_resuelvo", "resuelvo")
        firm_a = self._field_anchor(self.entry_firmantes, "edit_firmantes", "firmantes")
        juz_a = anchor(juz, "combo_juz_navfyg", "juzgado")
        ee_rel_a = anchor(ee_rel, "edit_ee_relacionado", "…")
        cuerpo = (
            f"<b>{juz_a}</b>\n"
            "<b>S/D:</b>\n\n"
            f"En los autos caratulados: {car_a}, que se tramitan por ante "
            f"{trib_a}, con intervención de esta Oficina de Servicios Procesales "
            "(OSPRO), se ha dispuesto librar a Ud. el presente a fin de comunicar lo resuelto por el Tribunal respecto de "
            f"{self._imp_datos_anchor()}\n\n"
            f"SENTENCIA N° {sent_n_a}, de fecha {sent_f_a}: “Se Resuelve: {res_a}” "
            f"(Fdo.: {firm_a}).\n\n"
            "Se adjuntan copias digitales de la sentencia y, de existir, del cómputo de pena.\n"
            f"Expediente de V.F. relacionado: n° {ee_rel_a}\n\n"
            "Sin otro particular, saludo a Ud. atentamente."
        )
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify, rich=True)

    def _plantilla_complejo_carcelario(self):
        te = self.text_edits["Oficio Complejo Carcelario"]
        te.clear()
        firm = self.entry_firmantes.text() or "…"
        loc, hoy = self.entry_localidad.text() or "Córdoba", datetime.now()
        fecha = fecha_alineada(loc, hoy)
        sent_n = self.entry_sent_num.text() or "…"
        sent_f = self.entry_sent_date.text() or "…/…/…"
        car   = self.entry_caratula.text() or "“…”"
        trib  = self.entry_tribunal.currentText() or "la Cámara en lo Criminal y Correccional"
        res = self.entry_resuelvo.text() or "\u2026"
        establecimiento = self._imp_field('servicio_penitenciario').upper()
        if not establecimiento:
            establecimiento = "\u2026"
        nombre = self._imp_field('nombre') or "\u2026"
        dni = self._imp_field('dni') or "\u2026"

        car_a = self._field_anchor(self.entry_caratula, "edit_caratula", "carátula")
        trib_a = self._field_anchor(self.entry_tribunal, "combo_tribunal", "tribunal")
        sent_n_a = self._field_anchor(self.entry_sent_num, "edit_sent_num", "…")
        sent_f_a = self._field_anchor(self.entry_sent_date, "edit_sent_fecha", "…/…/…")
        res_a = self._field_anchor(self.entry_resuelvo, "edit_resuelvo", "resuelvo")
        firm_a = self._field_anchor(self.entry_firmantes, "edit_firmantes", "firmantes")
        establecimiento_a = anchor(establecimiento, "combo_servicio_penitenciario", "…")
        nombre_a = anchor(nombre, "edit_nombre", "…")
        dni_a = anchor(dni, "edit_dni", "…")

        cuerpo = (
            f"<b>AL SEÑOR DIRECTOR DEL {establecimiento_a}</b>\n"
            "<b>S/D:</b>\n\n"
            f"En los autos caratulados: {car_a}, que se tramitan por ante "
            f"{trib_a}, con intervención de esta Oficina de Servicios Procesales (OSPRO), "
            f"me dirijo a Ud. a fin de informar lo resuelto respecto de {nombre_a} – D.N.I. {dni_a} mediante Sentencia "
            f"N\u202f{sent_n_a}, de fecha {sent_f_a}: \u201c{res_a}\u201d "
            f"(Fdo.: {firm_a}).\n\n"
            "Sin otro particular, lo saludo atentamente."
        )
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify, rich=True)

    def copy_to_clipboard(self, te: QTextEdit):
        mime = QMimeData()
        mime.setHtml(te.toHtml())
        mime.setText(te.toPlainText())
        QApplication.clipboard().setMimeData(mime)

    # ------- edición desde las anclas ---------------------------------
    def _editar_lineedit(self, widget: QLineEdit, titulo: str):
        texto, ok = QInputDialog.getText(self, titulo, titulo, text=widget.text())
        if ok:
            widget.setText(texto.strip())
            self.update_templates()

    def _editar_plaintext(self, widget: QPlainTextEdit, titulo: str):
        texto, ok = QInputDialog.getMultiLineText(
            self, titulo, titulo, widget.toPlainText()
        )
        if ok:
            widget.setPlainText(texto.strip())
            self.update_templates()

    def _editar_combo(self, widget: QComboBox, titulo: str):
        items = [widget.itemText(i) for i in range(widget.count())]
        idx = widget.currentIndex()
        texto, ok = QInputDialog.getItem(
            self,
            titulo,
            titulo,
            items,
            idx,
            editable=widget.isEditable(),
        )
        if ok:
            widget.setCurrentText(texto.strip())
            self.update_templates()

    def _abrir_dialogo_rico(self, titulo: str, html_inicial: str, on_accept):
        dlg = QDialog(self)
        dlg.setWindowTitle(titulo)
        lay = QVBoxLayout(dlg)
        edit = QTextEdit()
        font = QFont("Times New Roman", 12)
        edit.setFont(font)
        edit.document().setDefaultFont(font)
        edit.setHtml(html_inicial)
        lay.addWidget(edit)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        lay.addWidget(btns)

        def aceptar():
            on_accept(edit.toHtml())
            dlg.accept()

        btns.accepted.connect(aceptar)
        btns.rejected.connect(dlg.reject)
        dlg.exec()

    def _on_anchor_clicked(self, url: QUrl) -> None:
        clave = url.toString()

        if clave == "edit_localidad":
            self._editar_lineedit(self.entry_localidad, "Localidad")
            return
        if clave == "edit_caratula":
            self._editar_lineedit(self.entry_caratula, "Carátula")
            return
        if clave == "combo_tribunal":
            self._editar_combo(self.entry_tribunal, "Tribunal")
            return
        if clave == "edit_consulado":
            self._editar_lineedit(self.entry_consulado, "Consulado")
            return
        if clave == "edit_sent_num":
            self._editar_lineedit(self.entry_sent_num, "Sentencia N°")
            return
        if clave == "edit_sent_fecha":
            self._editar_lineedit(self.entry_sent_date, "Fecha de sentencia")
            return
        if clave == "edit_sent_firmeza":
            self._editar_lineedit(self.entry_sent_firmeza, "Firmeza de la sentencia")
            return
        if clave == "edit_resuelvo":
            self._editar_lineedit(self.entry_resuelvo, "Resuelvo")
            return
        if clave == "edit_firmantes":
            self._editar_lineedit(self.entry_firmantes, "Firmantes")
            return
        if clave == "edit_rodado":
            self._editar_lineedit(self.entry_rodado, "Decomisado/secuestrado")
            return
        if clave == "edit_regn":
            self._editar_lineedit(self.entry_regn, "Reg. N°")
            return
        if clave == "combo_deposito":
            self._editar_combo(self.entry_deposito, "Depósito")
            return
        if clave == "edit_comisaria":
            self._editar_lineedit(self.entry_comisaria, "Comisaría")
            return
        if clave == "combo_dep_def":
            self._editar_combo(self.entry_dep_def, "Carácter de la entrega")
            return
        if clave == "edit_titular_veh":
            self._editar_lineedit(self.entry_titular_veh, "Titular del vehículo")
            return
        if clave == "edit_itim_num":
            self._editar_lineedit(self.entry_itim_num, "ITIM Nº")
            return
        if clave == "edit_itim_fecha":
            self._editar_lineedit(self.entry_itim_fecha, "Fecha ITIM")
            return

        # ---- campos del imputado seleccionado ----
        idx_sel = self.selector_imp.currentIndex()
        if clave == "edit_nombre" and idx_sel >= 0:
            self._editar_lineedit(self.imputados_widgets[idx_sel]['nombre'], "Nombre y apellido")
            return
        if clave == "edit_dni" and idx_sel >= 0:
            self._editar_lineedit(self.imputados_widgets[idx_sel]['dni'], "DNI")
            return
        if clave == "edit_legajo" and idx_sel >= 0:
            self._editar_lineedit(self.imputados_widgets[idx_sel]['legajo'], "Legajo")
            return
        if clave == "edit_condena" and idx_sel >= 0:
            self._editar_lineedit(self.imputados_widgets[idx_sel]['condena'], "Condena")
            return
        if clave == "edit_delitos" and idx_sel >= 0:
            self._editar_lineedit(self.imputados_widgets[idx_sel]['delitos'], "Delitos")
            return
        if clave == "edit_antecedentes" and idx_sel >= 0:
            self._editar_lineedit(self.imputados_widgets[idx_sel]['antecedentes'], "Antecedentes")
            return
        if clave == "edit_tratamientos" and idx_sel >= 0:
            self._editar_lineedit(self.imputados_widgets[idx_sel]['tratamientos'], "Tratamientos")
            return
        if clave == "edit_computo" and idx_sel >= 0:
            self._editar_lineedit(self.imputados_widgets[idx_sel]['computo'], "Cómputo")
            return
        if clave == "combo_servicio_penitenciario" and idx_sel >= 0:
            self._editar_combo(self.imputados_widgets[idx_sel]['servicio_penitenciario'], "Servicio Penitenciario")
            return
        if clave == "combo_juz_navfyg" and idx_sel >= 0:
            self._editar_combo(self.imputados_widgets[idx_sel]['juz_navfyg'], "Juzgado NAVFyG")
            return
        if clave == "edit_ee_relacionado" and idx_sel >= 0:
            self._editar_lineedit(self.imputados_widgets[idx_sel]['ee_relacionado'], "EE relacionado")
            return

        if clave.startswith("edit_imp_datos_"):
            idx = int(clave.split("_")[-1])
            self._editar_plaintext(
                self.imputados_widgets[idx]["datos_personales"],
                f"Datos personales #{idx+1}",
            )
            return


    def update_for_imp(self, idx: int):
        self.update_templates()


    # ───────────────────── interceptar cierre ──────────────────────
    def closeEvent(self, ev):
        ans = QMessageBox.question(self, "Salir", "¿Cerrar la aplicación?",
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ans == QMessageBox.Yes:
            ev.accept()
        else:
            ev.ignore()

# ──────────────────────────── main ───────────────────────────────
def main():
    app = QApplication(sys.argv)

    # ahora SÍ podés usar QMessageBox
    if not os.getenv("OPENAI_API_KEY"):
        QMessageBox.critical(
            None, "Error", "Falta la variable OPENAI_API_KEY"
        )
        sys.exit(1)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
