# -*- coding: utf-8 -*-
"""
Generador de documentos judiciales – versión base
Interfaz: datos generales + pestañas de imputados (sin plantillas)
"""
import sys, json, os
from pathlib import Path
from datetime import datetime
from PySide6.QtCore    import Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QLineEdit, QComboBox, QSpinBox,
    QPushButton, QGridLayout, QVBoxLayout, QTabWidget, QFileDialog, QMessageBox,
    QScrollArea, QSizePolicy, QSplitter, QTextEdit     
)
from PySide6.QtGui import QIcon, QTextCursor, QFont   # QIcon y QFont para más adelante
from PySide6.QtWidgets import QHBoxLayout             
from PySide6.QtGui import QTextBlockFormat, QTextCharFormat
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

def fecha_alineada(loc: str, hoy: datetime = None, punto: bool = False) -> str:
    hoy = hoy or datetime.now()
    txt = f"{loc}, {hoy.day} de {MESES_ES[hoy.month-1]} de {hoy.year}"
    return txt + ("." if punto else "")

# ───────────────────────── MainWindow ────────────────────────
class MainWindow(QMainWindow):
    FIELD_WIDTH = 140        # ancho preferido de los campos cortos

    # ── helper para insertar párrafos con alineación ─────────────
    def _insert_paragraph(self, te: QTextEdit, text: str,
                          align: Qt.AlignmentFlag = Qt.AlignJustify,
                          font_family: str = "Times New Roman",
                          point_size: int = 12) -> None:
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

        for linea in text.split("\n"):
            cursor.insertBlock(block)
            cursor.setCharFormat(char)
            cursor.insertText(linea)


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
        self.entry_localidad = add_combo('entry_localidad', "Localidad:", [], editable=True)
        self.entry_caratula  = add_line ('entry_caratula',  "Carátula:")
        self.entry_tribunal  = add_combo('entry_tribunal',  "Tribunal:", [], editable=True)
        self.entry_fecha     = add_line ('entry_fecha',     "Fecha audiencia:")
        self.entry_hora      = add_combo('entry_hora',      "Hora audiencia:",
                                        [f"{h:02d}:{m:02d}" for h in range(24) for m in (0,30)])

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

        # pestañas de oficios
        self.text_edits = {}
        for name in ("Oficio Migraciones",
                    "Oficio Juez Electoral",
                    "Oficio Consulado",
                    "Oficio Registro Automotor",
                    "Oficio TSJ Sec. Penal",
                    "Oficio TSJ Sec. Penal (Depósitos)",  
                    "Oficio Comisaría Traslado",
                    "Oficio TSJ Sec. Penal (Elementos)",
                    "Oficio Automotores Secuestrados",
                    "Oficio Fiscalía Instrucción",
                    "Oficio Policía Documentación",
                    "Oficio Registro Civil",
                    "Oficio Registro Condenados Sexuales", 
                    "Oficio Registro Nacional Reincidencia",
                    "Oficio RePAT", 
                    "Oficio Juzgado Niñez‑Adolescencia",
                    "Oficio Complejo Carcelario" ):

            te = QTextEdit(); te.setReadOnly(True)
            te.setFontFamily("Times New Roman"); te.setFontPointSize(12)
            cont = QWidget(); lay = QVBoxLayout(cont)
            lay.addWidget(te)
            btn = QPushButton("Copiar al portapapeles")
            btn.clicked.connect(lambda _=False, t=te: self.copy_to_clipboard(t))
            lay.addWidget(btn)
            self.tabs_txt.addTab(cont, name)
            self.text_edits[name] = te

        # ─── AHORA que selector_imp existe, construimos imputados ───
        self.imputados_widgets = []         #  ← línea movida aquí
        self.rebuild_imputados()            #  ← llamada movida aquí

        # primer refresco de textos
        self.update_templates()


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
                'tipo'    : NoWheelComboBox(),
                'nombre'  : QLineEdit(),
                'dni'     : QLineEdit(),
                'delitos' : QLineEdit(),
                'defensa' : QLineEdit(),
            }
            w['tipo'].addItems(['efectiva', 'condicional'])

            pair("Tipo de pena:",      w['tipo'])
            pair("Nombre y apellido:", w['nombre'])
            pair("DNI:",               w['dni'])
            pair("Delitos:",           w['delitos'])
            pair("Defensa:",           w['defensa'])

            # 4) restauro datos previos si los hubiera
            if i < len(prev):
                for k, v in prev[i].items():
                    if isinstance(w[k], QLineEdit):
                        w[k].setText(v)
                    else:
                        w[k].setCurrentText(v)

            # 5) agrego pestaña y actualizo listas
            self.tabs_imp.addTab(tab, f"Imputado {i+1}")
            self.selector_imp.addItem(f"Imputado {i+1}")
            self.imputados_widgets.append(w)

        # 6) habilito señales y dejo seleccionado el primero
        self.selector_imp.blockSignals(False)
        self.selector_imp.setCurrentIndex(0)


    # ───────────────────────── persistencia ────────────────────────
    def _generales_dict(self):
        """Devuelve un dict con los datos generales."""
        return {
            'localidad' : self.entry_localidad.currentText(),
            'caratula'  : self.entry_caratula.text(),
            'tribunal'  : self.entry_tribunal.currentText(),
            'fecha'     : self.entry_fecha.text(),
            'hora'      : self.entry_hora.currentText(),
        }

    def _imputados_list(self):
        li = []
        for w in self.imputados_widgets:
            li.append({k: (
                w[k].text() if isinstance(w[k], QLineEdit) else
                w[k].currentText()
            ) for k in w})
        return li

    def guardar_causa(self):
        ruta, _ = QFileDialog.getSaveFileName(self, "Guardar causa", str(CAUSAS_DIR), "JSON (*.json)")
        if not ruta: return
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump({'generales': self._generales_dict(),
                       'imputados': self._imputados_list()}, f, ensure_ascii=False, indent=2)
        QMessageBox.information(self, "OK", "Causa guardada correctamente.")

    def cargar_causa(self):
        ruta, _ = QFileDialog.getOpenFileName(self, "Abrir causa", str(CAUSAS_DIR), "JSON (*.json)")
        if not ruta: return
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                data = json.load(f)
            g = data.get('generales', {})
            self.entry_localidad.setCurrentText(g.get('localidad', ""))
            self.entry_caratula.setText(g.get('caratula', ""))
            self.entry_tribunal.setCurrentText(g.get('tribunal', ""))
            self.entry_fecha.setText(g.get('fecha', ""))
            self.entry_hora.setCurrentText(g.get('hora', ""))

            imps = data.get('imputados', [])
            self.combo_n.setCurrentText(str(max(1, len(imps))))
            for idx, imp in enumerate(imps):
                w = self.imputados_widgets[idx]
                for k,v in imp.items():
                    if isinstance(w[k], QLineEdit): w[k].setText(v)
                    else:                           w[k].setCurrentText(v)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def eliminar_causa(self):
        ruta, _ = QFileDialog.getOpenFileName(self, "Eliminar causa", str(CAUSAS_DIR), "JSON (*.json)")
        if ruta and QMessageBox.question(self, "Confirmar",
                                         f"¿Eliminar {Path(ruta).name}?",
                                         QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            Path(ruta).unlink(missing_ok=True)

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
        loc = self.entry_localidad.currentText() or "Córdoba"
        hoy = datetime.now()
        fecha = fecha_alineada(loc, hoy, punto=True)       # ← solo el texto

        # 1) FECHA a la derecha
        self._insert_paragraph(te, fecha, Qt.AlignRight)

        # 2) CUERPO justificado
        car  = self.entry_caratula.text() or "“…”"
        trib = self.entry_tribunal.currentText() or \
            "la Cámara en lo Criminal y Correccional"

        cuerpo = (
            "Sr/a Director/a\n"
            "de la Dirección Nacional de Migraciones\n"
            "S/D:\n\n"
            f"En los autos caratulados: {car}, que se tramitan "
            f"por ante {trib}, se ha dispuesto librar a Ud. el presente oficio, "
            "a fin de informar lo resuelto por dicho Tribunal respecto de la persona "
            "cuyos datos personales se mencionan a continuación:\n\n"
            "“SENTENCIA N° …, DE FECHA: …/…/…. Se Resuelve: (transcribir toda la parte "
            "resolutoria de la sentencia)..”\n\n"
            "Asimismo, se informa que la sentencia antes señalada quedó firme con fecha …\n"
            "Se adjuntan al presente oficio copia digital de la misma y del cómputo de pena respectivo.\n\n"
            "Sin otro particular, saludo a Ud. atentamente."
        )
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify)


    def _plantilla_juez_electoral(self):
        te = self.text_edits["Oficio Juez Electoral"]
        te.clear()

        # ─ datos básicos ─
        loc  = self.entry_localidad.currentText() or "Córdoba"
        hoy  = datetime.now()
        fecha = fecha_alineada(loc, hoy, punto=True)

        car   = self.entry_caratula.text() or "“…”"
        trib  = self.entry_tribunal.currentText() or "la Cámara en lo Criminal y Correccional"
        sac   = "…"   # si luego agregás un campo “N° SAC”, leélo acá
        nom   = "…"   # idem Nominación
        sec   = "…"   # idem Secretaría

        cuerpo = (
            "SR. JUEZ ELECTORAL:\n"
            "S………………./………………D\n"
            "-Av. Concepción Arenales esq. Wenceslao Paunero, Bº Rogelio Martínez, Córdoba.\n"
            "Tribunales Federales de Córdoba-\n\n"
            f"En los autos caratulados: {car} (Expte. SAC N° {sac}), que se tramitan por ante "
            f"{trib} de {nom} Nominación, Secretaría N° {sec}, de la ciudad de Córdoba, Provincia de Córdoba, "
            "con la intervención de ésta Oficina de Servicios Procesales (OSPRO), se ha dispuesto librar a Ud. "
            "el presente oficio, a fin de informar lo resuelto por dicho Tribunal respecto de la persona cuyos "
            "datos personales se mencionan a continuación: (Nombre, Apellido / D.N.I. / Fecha de Nacimiento / Padre, Madre).\n\n"
            "SENTENCIA N° …, DE FECHA: …/…/…. “Se Resuelve: (Transcribir toda la parte resolutoria de la sentencia)..” "
            "Fdo. Dr/a. ……… -Vocal de Cámara-, Dr/a. ……… -Secretario/a de Cámara-.\n\n"
            "Asimismo, se informa que la sentencia antes señalada quedó firme con fecha …\n"
            "Se adjuntan al presente oficio copia digital de la misma y del cómputo de pena respectivo.\n\n"
            "Sin otro particular, saludo a Ud. atentamente."
        )

        self._insert_paragraph(te, fecha, Qt.AlignRight)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify)

    def _plantilla_consulado(self):
        te = self.text_edits["Oficio Consulado"]
        te.clear()

        # ─ datos básicos ─
        loc  = self.entry_localidad.currentText() or "Córdoba"
        hoy  = datetime.now()
        fecha = fecha_alineada(loc, hoy, punto=True)

        car   = self.entry_caratula.text() or "“…”"
        trib  = self.entry_tribunal.currentText() or "la Cámara en lo Criminal y Correccional"
        sac   = "…"   # campo opcional a futuro
        nom   = "…"   # idem Nominación
        sec   = "…"   # idem Secretaría
        pais  = "…"   # cuando agregues un ComboBox para el país, usalo acá

        cuerpo = (
            "Al Sr. Titular del Consulado de la República de " + pais + " S/D:\n"
            f"En los autos caratulados: {car} (Expte. SAC N° {sac}), que se tramitan por ante "
            f"{trib} de {nom} Nominación, Secretaría N° {sec}, de la ciudad de Córdoba, Provincia de Córdoba, "
            "con la intervención de ésta Oficina de Servicios Procesales (OSPRO), se ha dispuesto librar el presente oficio, "
            "a fin de informar lo resuelto por dicho Tribunal respecto de la persona cuyos datos personales se mencionan a "
            "continuación: (Nombre, Apellido / D.N.I. / Fecha de Nacimiento / Padre, Madre).\n\n"
            "SENTENCIA N° …, DE FECHA: …/…/…. “Se Resuelve: (Transcribir toda la parte resolutoria de la sentencia).” "
            "Fdo. Dr/a. ……… -Vocal de Cámara-, Dr/a. ……… -Secretario/a de Cámara-.\n\n"
            "Asimismo, se informa que la sentencia antes señalada quedó firme con fecha …\n"
            "Se adjuntan al presente oficio copia digital de la misma y del cómputo de pena respectivo.\n\n"
            "Sin otro particular, saludo a Ud. atentamente."
        )

        self._insert_paragraph(te, fecha, Qt.AlignRight)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify)

    def _plantilla_registro_automotor(self):
        te = self.text_edits["Oficio Registro Automotor"]
        te.clear()

        loc  = self.entry_localidad.currentText() or "Córdoba"
        hoy  = datetime.now()
        fecha = fecha_alineada(loc, hoy, punto=True)

        car  = self.entry_caratula.text() or "“…”"
        trib = self.entry_tribunal.currentText() or "la Cámara en lo Criminal y Correccional"
        sac  = "…"   # Nº SAC (añadí el widget cuando lo necesites)
        nom  = "…"   # Nominación
        sec  = "…"   # Secretaría
        regn = "…"   # Nº de Registro del Automotor
        veh  = "marca, modelo, dominio …"   # datos del rodado

        cuerpo = (
            f"AL SR. TITULAR DEL REGISTRO DE LA\n"
            f"PROPIEDAD DEL AUTOMOTOR N° {regn}\n"
            "S/D:\n"
            f"\tEn los autos caratulados: {car} (SAC N° {sac}), que se tramitan por ante "
            f"{trib} de {nom} Nominación, Secretaría N° {sec}, con intervención de esta Oficina de Servicios "
            "Procesales – OSPRO –, se ha dispuesto librar a Ud. el presente, a fin de informarle que mediante "
            "Sentencia N° … de fecha ………, dicho Tribunal resolvió ordenar el DECOMISO del vehículo "
            f"{veh}.\n"
            "Se transcribe a continuación la parte pertinente de la misma:\n"
            "“SE RESUELVE: (copiar la parte resolutiva que ordena el decomiso del automotor)”. "
            "(Fdo. Dr./a. Vocal de Cámara, Dr./a. Secretario/a de Cámara).\n\n"
            "Sin otro particular, saludo a Ud. atte."
        )
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify)

    def _plantilla_tsj_secpenal(self):
        te = self.text_edits["Oficio TSJ Sec. Penal"]
        te.clear()

        loc  = self.entry_localidad.currentText() or "Córdoba"
        hoy  = datetime.now()
        fecha = fecha_alineada(loc, hoy, punto=True)

        car  = self.entry_caratula.text() or "“…”"
        trib = self.entry_tribunal.currentText() or "la Cámara en lo Criminal y Correccional"
        sac  = "…"   # Nº SAC
        nom  = "…"   # Nominación
        sec  = "…"   # Secretaría
        registro = "…de …"  # Nº de Registro y localidad

        cuerpo = (
            "A LA SRA. SECRETARIA PENAL\n"
            "DEL TRIBUNAL SUPERIOR DE JUSTICIA  DRA. MARIA PUEYRREDON DE MONFARRELL\n"
            "S______/_______D:\n"
            f"En los autos caratulados: {car} (SAC N° {sac}), que se tramitan por ante "
            f"{trib} de {nom} Nom., Secretaría {sec}, con conocimiento e intervención de esta Oficina de Servicios "
            "Procesales – OSPRO –, se ha dispuesto librar a Ud. el presente a fin de poner en conocimiento lo "
            "resuelto por la Sentencia N° … del …………, dictada por la Cámara mencionada, en virtud de la cual "
            "se ordenó el DECOMISO de los siguientes objetos:\n\n"
            "Tipos de elementos\tUbicación actual\n"
            "Automotores (RUV)\tDepósito de Automotores 1 (Bouwer)\n"
            "Motovehículos (RUV)\tDepósito de Automotores 2 (Bouwer)\n\n"
            "Pongo en su conocimiento que la mencionada sentencia se encuentra firme, transcribiéndose a "
            "continuación la parte pertinente de la misma:\n"
            "“SE RESUELVE: (copiar la parte resolutiva del decomiso)”. "
            "(Fdo. Dr./a. … Vocal de Cámara, Dr./a. … Secretario/a de Cámara).\n\n"
            f"Asimismo, se informa que en el día de la fecha se comunicó dicha resolución al Registro del Automotor "
            f"donde está radicado el vehículo, Nº {registro}.\n\n"
            "Sin otro particular, saludo a Ud. muy atentamente."
        )
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify)

    def _plantilla_tsj_secpenal_depositos(self):
        te = self.text_edits["Oficio TSJ Sec. Penal (Depósitos)"]
        te.clear()

        loc  = self.entry_localidad.currentText() or "Córdoba"
        hoy  = datetime.now()
        fecha = fecha_alineada(loc, hoy, punto=True)

        car  = self.entry_caratula.text() or "“…”"
        trib = self.entry_tribunal.currentText() or "la Cámara en lo Criminal y Correccional"
        sac  = "…"   # Nº SAC
        nom  = "…"   # Nominación
        sec  = "…"   # Secretaría
        desc = "RUS/RUV: …………………….."                   # editable
        ubic = "Cría. n°/Sub‑Destacamento/Comisaría …"    # editable

        cuerpo = (
            "A LA SRA. SECRETARIA PENAL\n"
            "DEL TRIBUNAL SUPERIOR DE JUSTICIA  DRA. MARIA PUEYRREDON DE MONFARRELL\n"
            "S/D:\n\n"
            f"En los autos caratulados “{car}” (SAC N° {sac}), que se tramitan por ante "
            f"{trib} de {nom} Nominación, Secretaría N° {sec}, con intervención de esta Oficina de Servicios Procesales "
            "- OSPRO -, se ha dispuesto librar a Ud. el presente, a fin de informarle que mediante Sentencia N° … "
            "de ………, dicho Tribunal resolvió ordenar el DECOMISO de los siguientes objetos:\n\n"
            "Descripción del objeto\tUbicación Actual\n"
            f"{desc}\t{ubic}\n\n"
            "Se hace saber a Ud. que el/los elemento/s referido/s se encuentra/n en la Cría. ………… de la Policía de Córdoba "
            "y en el día de la fecha se libró oficio a dicha dependencia policial a los fines de remitir al Depósito General "
            "de Efectos Secuestrados el/los objeto/s decomisado/s.\n\n"
            "Asimismo, informo que la sentencia referida se encuentra firme, transcribiéndose a continuación la parte "
            "pertinente de la misma: “SE RESUELVE: (copiar la parte resolutiva que ordena el decomiso)”. "
            "(Fdo. Dr./a. … Vocal de Cámara, Dr./a. … Secretario/a de Cámara).\n\n"
            "Sin otro particular, saludo a Ud. muy atentamente."
        )
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify)

    def _plantilla_comisaria_traslado(self):
        te = self.text_edits["Oficio Comisaría Traslado"]
        te.clear()

        loc  = self.entry_localidad.currentText() or "Córdoba"
        hoy  = datetime.now()
        fecha = fecha_alineada(loc, hoy, punto=True)

        car  = self.entry_caratula.text() or "“…”"
        trib = self.entry_tribunal.currentText() or "la Cámara en lo Criminal y Correccional"
        sac  = "…"   # Nº SAC
        nom  = "…"   # Nominación
        sec  = "…"   # Secretaría
        comi = "…"   # Nº Comisaría
        objetos = "(descripción de los objetos a trasladar)"

        cuerpo = (
            f"AL SR. TITULAR\n"
            f"DE LA COMISARÍA N° {comi} DE LA POLICÍA DE CÓRDOBA\n"
            "S/D:\n\n"
            f"En los autos caratulados “{car}” (SAC N° {sac}) que se tramitan por ante "
            f"{trib} de {nom} Nominación, Secretaría N° {sec}, con intervención de esta Oficina de Servicios Procesales "
            "- OSPRO -, se ha dispuesto librar a Ud. el presente, a los fines de solicitarle que personal a su cargo "
            "traslade los efectos que a continuación se detallan al Depósito General de Efectos Secuestrados "
            "-sito en calle Abdel Taier n° 270, B° Comercial, de esta ciudad de Córdoba-, para que sean allí recibidos:\n\n"
            f"{objetos}\n\n"
            "Lo solicitado obedece a directivas generales impartidas por la Secretaría Penal del T.S.J, de la cual "
            "depende esta Oficina, para los casos en los que se haya dictado la pena de decomiso y los objetos aún "
            "estén en Comisarías, Subcomisarías y otras dependencias policiales.\n\n"
            "Se transcribe a continuación la parte pertinente de la Sentencia que así lo ordena:\n"
            "Sentencia N° … de fecha ………, “II)… (Copiar la parte de la Sentencia que ordena el decomiso)” "
            "(Fdo. Dr./a. … Vocal de Cámara, Dr./a. … Secretario/a de Cámara), elemento/s que fuera/n secuestrado/s "
            "en las presentes actuaciones y que actualmente se encuentra/n en el Depósito de la Comisaría a su cargo.\n\n"
            "Sin otro particular, saludo a Ud. muy atentamente."
        )
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify)

    def _plantilla_tsj_secpenal_elementos(self):
        te = self.text_edits["Oficio TSJ Sec. Penal (Elementos)"]
        te.clear()

        loc  = self.entry_localidad.currentText() or "Córdoba"
        hoy  = datetime.now()
        fecha = fecha_alineada(loc, hoy, punto=True)

        car  = self.entry_caratula.text() or "“…”"
        trib = self.entry_tribunal.currentText() or "la Cámara en lo Criminal y Correccional"
        sac  = "…"   # Nº SAC
        nom  = "…"   # Nominación
        sec  = "…"   # Secretaría

        cuerpo = (
            "A LA SRA. SECRETARIA PENAL\n"
            "DEL TRIBUNAL SUPERIOR DE JUSTICIA  DRA. MARIA PUEYRREDON DE MONFARRELL\n"
            "S______/_______D:\n\n"
            f"En los autos caratulados: “{car}” (SAC N° {sac}), que se tramitan por ante "
            f"{trib} de {nom} Nom., Secretaría {sec}, con conocimiento e intervención de ésta Oficina de Servicios "
            "Procesales ‑ OSPRO‑, se ha dispuesto librar a Ud. el presente a fin de poner en conocimiento lo resuelto "
            "por la Sentencia N° … del …………, dictada por la Cámara mencionada, en virtud de la cual se ordenó el "
            "DECOMISO de los siguientes objetos:\n\n"
            "TIPOS DE ELEMENTOS\tUBICACIÓN ACTUAL\n"
            "Objetos en general (RUS)\tDepósito General de Efectos Secuestrados\n"
            "Estupefacientes y elementos secuestrados en causas de Narcotráfico (RUE)\tDepósito de la Unidad Judicial de Lucha c/ Narcotráfico\n"
            "Armas, proyectiles, cartuchos, etc. (RUA)\tDepósito de Armas (Tribunales II)\n"
            "Automotores (RUV)\tDepósito de Automotores 1 (Bouwer)\n"
            "Motovehículos (RUV)\tDepósito de Automotores 2 (Bouwer)\n"
            "Dinero (pesos argentinos y/o dólares) (N° de registro)\tDepositado en Cuenta Judicial del Banco de Córdoba\n"
            "Otros billetes de moneda extranjera y/o dólares en mal estado (N° de registro)\tDepósito de Armas y elementos secuestrados (Tribunales II)\n\n"
            "Pongo en su conocimiento que la mencionada resolución se encuentra firme, transcribiéndose a continuación "
            "la parte pertinente de la misma: “SE RESUELVE: (copiar la parte resolutiva del decomiso)”. "
            "(Fdo. Dr./a. … Vocal de Cámara, Dr./a. … Secretario/a de Cámara).\n\n"
            "Sin otro particular, saludo a Ud. muy atentamente."
        )
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify)

    def _plantilla_automotores_secuestrados(self):
        te = self.text_edits["Oficio Automotores Secuestrados"]
        te.clear()

        loc  = self.entry_localidad.currentText() or "Córdoba"
        hoy  = datetime.now()
        fecha = fecha_alineada(loc, hoy, punto=True)

        car  = self.entry_caratula.text() or "“…”"
        trib = self.entry_tribunal.currentText() or "la Cámara en lo Criminal y Correccional"
        sac  = "…"   # Nº SAC
        nom  = "…"   # Nominación
        sec  = "…"   # Secretaría
        marca = "…"  # rellenar a mano
        modelo = "…"
        dominio = "…"
        motor = "…"
        chasis = "…"
        color = "…"
        ruv = "…"    # Nº RUV
        deposito = "…"  # Depósito actual

        cuerpo = (
            "A LA OFICINA DE\n"
            "AUTOMOTORES SECUESTRADOS EN CAUSAS PENALES, TRIBUNAL SUPERIOR DE JUSTICIA.\n"
            "S/D:\n\n"
            f"En los autos caratulados: “{car}” (SAC N° {sac}), que se tramitan por ante "
            f"{trib} de {nom} Nominación, Secretaría N° {sec}, con intervención de ésta Oficina de Servicios Procesales "
            "(OSPRO), se ha resuelto enviar a Ud. el presente a fines de solicitarle que establezca lo necesario para que, "
            "por intermedio de quien corresponda, se coloque a la orden y disposición de la Cámara señalada, el rodado "
            f"MARCA: {marca}, MODELO: {modelo}, DOMINIO: {dominio}, MOTOR N°: {motor}, CHASIS N°: {chasis}, "
            f"DE COLOR: {color}, RUV N° {ruv}, vehículo que se encuentra en el Depósito de {deposito}.\n\n"
            "Se hace saber a Ud. que dicha petición obedece a que el Tribunal mencionado ha dispuesto la entrega del "
            "referido vehículo en carácter de ………… al/la titular registral Sr./Sra. ………………... Para mayor recaudo se "
            "adjunta en documento informático copia de la resolución que dispuso la medida.\n\n"
            "Finalmente, se informa que a dicho rodado, con fecha …/…/…, se le realizó el correspondiente Informe "
            "Técnico de Identificación de Matrículas N° XXXXXX (Interno N° XXXXXXX), concluyendo que la unidad no "
            "presenta adulteración en sus matrículas identificatorias. (Revisar en el informe y, de existir informe de "
            "dominio, remitirlo también; no es indispensable según la Oficina del T.S.J.).\n\n"
            "Saludo a Ud. muy atentamente."
        )
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify)

    def _plantilla_fiscalia_instruccion(self):
        te = self.text_edits["Oficio Fiscalía Instrucción"]
        te.clear()

        loc, hoy = self.entry_localidad.currentText() or "Córdoba", datetime.now()
        fecha = fecha_alineada(loc, hoy, punto=True)
        car   = self.entry_caratula.text() or "“…”"
        trib  = self.entry_tribunal.currentText() or "la Cámara en lo Criminal y Correccional"
        nom, sec, sac = "…", "…", "…"

        cuerpo = (
            "Sr/a Fiscal de Instrucción que por turno corresponda\n"
            "S/D:\n\n"
            f"En los autos caratulados: “{car}” (Expte. SAC N° {sac}), que se tramitan por ante "
            f"{trib} de {nom} Nominación, Secretaría N° {sec}, con intervención de la Oficina de Servicios Procesales "
            "(OSPRO), se ha dispuesto librar a Ud. el presente, por disposición de la Cámara señalada y conforme a la "
            "sentencia dictada en la causa de referencia, remitiendo los antecedentes obrantes en el expediente mencionado "
            "a fin de investigar la posible comisión de un delito perseguible de oficio.\n\n"
            "Se transcribe a continuación la parte pertinente: “Se resuelve: (transcribir la parte respectiva)”. "
            "(Fdo. Dr./a. … ‑Vocal de Cámara‑, Dr./a. … ‑Secretario/a de Cámara‑).\n\n"
            "Sin otro particular, saludo a Ud. atte."
        )
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify)

    def _plantilla_policia_documentacion(self):
        te = self.text_edits["Oficio Policía Documentación"]
        te.clear()

        loc, hoy = self.entry_localidad.currentText() or "Córdoba", datetime.now()
        fecha = fecha_alineada(loc, hoy, punto=True)
        car   = self.entry_caratula.text() or "“…”"
        trib  = self.entry_tribunal.currentText() or "la Cámara en lo Criminal y Correccional"
        nom, sec, sac = "…", "…", "…"

        cuerpo = (
            "Sr. Titular de la División de Documentación Personal – Policía de la Provincia de Córdoba\n"
            "S ______/_______D:\n\n"
            f"En los autos caratulados “{car}”, Expte. SAC Nº {sac}, que se tramitan ante "
            f"{trib} de {nom} Nom., Sec. {sec}, con intervención de esta Oficina de Servicios Procesales (OSPRO), "
            "se ha resuelto enviar el presente oficio a fin de informar lo resuelto por dicho Tribunal respecto de la persona "
            "cuyos datos se detallan a continuación:\n\n"
            "IMPUTADO: ………………………………..\n"
            "DNI: …………………………………………       OCUPACIÓN: ………………………………\n"
            "PADRES: ……………………………………\n"
            "DOMICILIO:………………………………...\n"
            "ALIAS:……………………………………….  FECHA NAC.: …/…/……  NACIONALIDAD: ……………………. \n"
            "N° PRONTUARIO PCIAL: ……………...\n\n"
            "SENTENCIA N° …, DE FECHA …/…/.. “Se resuelve: (transcribir parte resolutoria). PROTOCOLÍCESE. NOTIFÍQUESE.” "
            "(Fdo. Dr./a. … ‑Vocal de Cámara‑, Dr./a. … ‑Secretaria de Cámara‑).\n\n"
            "Se transcribe a continuación el cómputo de pena respectivo / la resolución que fija la fecha de cumplimiento "
            "de los arts. 27 y 27 bis del C.P.\n"
            "Fecha de firmeza de la Sentencia: ………\n\n"
            "Saluda a Ud. atentamente."
        )
        te.setPlainText(cuerpo)

    def _plantilla_registro_civil(self):
        te = self.text_edits["Oficio Registro Civil"]
        te.clear()

        loc, hoy = self.entry_localidad.currentText() or "Córdoba", datetime.now()
        fecha = fecha_alineada(loc, hoy, punto=True)
        car   = self.entry_caratula.text() or "“…”"
        trib  = self.entry_tribunal.currentText() or "la Cámara en lo Criminal y Correccional"
        nom, sec, sac = "…", "…", "…"

        cuerpo = (
            "Sr/a Director/a del Registro Civil y Capacidad de las Personas\n"
            "S/D:\n\n"
            f"En los autos caratulados: “{car}” (Expte. SAC N° {sac}), que se tramitan por ante "
            f"{trib} de {nom} Nominación, Secretaría N° {sec}, de la ciudad de Córdoba, Provincia de Córdoba, con "
            "intervención de ésta Oficina de Servicios Procesales (OSPRO), se ha dispuesto librar a Ud. el presente oficio, "
            "a fin de informar lo resuelto por dicho Tribunal respecto de la persona cuyos datos se mencionan a continuación: "
            "(Nombre, Apellido / D.N.I. / Fecha de Nacimiento / Padre, Madre).\n\n"
            "SENTENCIA N° …, DE FECHA …/…/…. “Se Resuelve: (transcribir parte resolutoria).” "
            "Fdo. Dr./a. … ‑Vocal de Cámara‑, Dr./a. … ‑Secretario/a de Cámara‑.\n\n"
            "Asimismo, se informa que la sentencia antes señalada quedó firme con fecha …\n"
            "Se adjuntan al presente oficio copia digital de la misma y del cómputo de pena respectivo.\n\n"
            "Sin otro particular, saludo a Ud. atentamente."
        )
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify)

    def _plantilla_registro_condenados_sexuales(self):
        te = self.text_edits["Oficio Registro Condenados Sexuales"]
        te.clear()

        loc, hoy = self.entry_localidad.currentText() or "Córdoba", datetime.now()
        fecha = fecha_alineada(loc, hoy, punto=True)
        car   = self.entry_caratula.text() or "“…”"
        trib  = self.entry_tribunal.currentText() or "la CÁMARA EN LO CRIMINAL Y CORRECCIONAL"
        nom, sec, sac = "…", "…", "…"

        cuerpo = (
            "Al Sr. Titular del Registro Provincial de Personas Condenadas por Delitos contra la Integridad Sexual\n"
            "S./D.\n\n"
            f"En los autos caratulados: “{car}”, SAC Nº {sac}, que se tramitan por ante "
            f"{trib} de {nom} Nom., Sec. {sec}, con intervención de ésta Oficina de Servicios Procesales (OSPRO), "
            "se ha resuelto librar el presente a fin de registrar en dicha dependencia lo resuelto por Sentencia N° …, "
            "de fecha …/…/… dictada por el mencionado Tribunal.\n\n"
            "I. DATOS PERSONALES\n"
            "……………………….., D.N.I. Nº ……………, nacionalidad …………, nacido el …/…/……, en …………, "
            "de … años, estado civil …………, domiciliado en ……………, Bº …….., ciudad de …………, con instrucción "
            "…………., profesión ……………, hijo de …………… y de …………… ., Prio. ………………, Sección ….\n"
            "Lugares frecuentados: –  Otros datos de contacto: –\n"
            "Señas particulares: Altura …, Cabello …, etc.\n\n"
            "II. IDENTIFICACIÓN DACTILAR (adjuntar ficha).\n"
            "III. DATOS DE CONDENA Y LIBERACIÓN (adjuntar copia de la sentencia).\n"
            "   • Condena impuesta: … años … meses de prisión.\n"
            "   • Fecha firmeza: …/…/20…\n"
            "   • Fecha de extinción: … de … de …\n"
            "   • Servicio Penitenciario: Bower, Complejo …, Legajo …\n"
            "   • Delito: …\n"
            "IV. HISTORIAL DE DELITOS Y CONDENAS ANTERIORES: …\n"
            "V. TRATAMIENTOS MÉDICOS Y PSICOLÓGICOS: …\n"
            "VI. OTROS DATOS DE INTERÉS:\n"
            "   La Cámara … resolvió mediante Sentencia N° … de fecha …/…/.. …RESUELVE: 1) Declarar a ………………\n"
            "   Fdo. Dr/a. … (Vocal), Dr/a. … (Secretario). Por decreto … se fijó fecha definitiva de cumplimiento "
            "el … de … de …\n\n"
            "Se adjuntan copias digitales de ficha RNR, sentencia firme y cómputo.\n\n"
            "Saludo a Ud. atentamente."
        )
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify)

    def _plantilla_registro_nacional_reincidencia(self):
        te = self.text_edits["Oficio Registro Nacional Reincidencia"]
        te.clear()

        loc, hoy = self.entry_localidad.currentText() or "Córdoba", datetime.now()
        fecha = fecha_alineada(loc, hoy, punto=True)
        car   = self.entry_caratula.text() or "“…”"
        trib  = self.entry_tribunal.currentText() or "la Cámara en lo Criminal y Correccional"
        nom, sec, sac = "…", "…", "…"

        cuerpo = (
            "Al Sr. Director del Registro Nacional de Reincidencia\n"
            "S/D:\n\n"
            "De acuerdo a lo dispuesto por el art. 2º de la Ley 22.177, remito a Ud. testimonio de la parte dispositiva "
            "de la resolución dictada en los autos caratulados: "
            f"“{car}” (Expte. SAC Nº {sac}), que se tramitan por ante "
            f"{trib} de {nom} Nom., Sec. {sec}, de la ciudad de Córdoba, Provincia de Córdoba, con intervención de ésta "
            "Oficina de Servicios Procesales (OSPRO), respecto de:\n\n"
            "IMPUTADO: ……………………    DNI: ……………………\n"
            "OCUPACIÓN: ………………….\n"
            "PADRES: …………………….\n"
            "DOMICILIO: ………………….\n"
            "ALIAS: …………………….\n"
            "FECHA NACIMIENTO: ………  NACIONALIDAD: ………\n"
            "Nº PRONTUARIO PCIAL: ………\n\n"
            "SENTENCIA N° …, DE FECHA …/…: “I. Declarar a ……… – (transcribir parte resolutoria). "
            "PROTOCOLÍCESE. NOTIFÍQUESE.” (Fdo. Dr/a. … –Vocal de Cámara–, Dr/a. … –Sec. de Cámara–).\n\n"
            "Se transcribe a continuación el cómputo de pena respectivo / la resolución que fija la fecha de cumplimiento "
            "de los arts. 27 y 27 bis del C.P.\n"
            "Fecha de firmeza de la sentencia: ………\n\n"
            "Saluda a Ud. atentamente."
        )
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify)

    def _plantilla_repat(self):
        te = self.text_edits["Oficio RePAT"]
        te.clear()

        loc, hoy = self.entry_localidad.currentText() or "Córdoba", datetime.now()
        fecha = fecha_alineada(loc, hoy, punto=True)
        car   = self.entry_caratula.text() or "“…”"
        trib  = self.entry_tribunal.currentText() or "la Cámara en lo Criminal y Correccional"
        nom, sec, sac = "…", "…", "…"

        cuerpo = (
            "SR. DIRECTOR DEL REGISTRO PROVINCIAL DE ANTECEDENTES DE TRÁNSITO (RePAT)\n"
            "S/D:\n\n"
            f"En los autos caratulados: “{car}” (Expte. SAC. Nº {sac}), que se tramitan por ante "
            f"{trib} de {nom} Nom., Sec. N° {sec}, de esta ciudad de Córdoba, con intervención de esta Oficina de "
            "Servicios Procesales (OSPRO), se ha dispuesto librar a Ud. el presente a fin de comunicar lo resuelto por "
            "dicho Tribunal respecto de la persona cuyos datos se detallan a continuación: (Nombre, D.N.I., Fecha de "
            "Nacimiento, Padre, Madre).\n\n"
            "SENTENCIA N° …, DE FECHA …/…/…: “Se resuelve: I. Declarar a ……… (transcribir parte resolutoria).” "
            "(Fdo. Dr/a. … ‑Vocal de Cámara‑, Dr/a. … ‑Secretario/a de Cámara‑).\n\n"
            "Asimismo, se informa que la sentencia condenatoria quedó firme con fecha …\n"
            "Se adjuntan copias digitales de la sentencia y del cómputo de pena respectivos.\n\n"
            "Saludo a Ud. atentamente."
        )
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify)

    def _plantilla_juzgado_ninez(self):
        te = self.text_edits["Oficio Juzgado Niñez‑Adolescencia"]
        te.clear()

        loc, hoy = self.entry_localidad.currentText() or "Córdoba", datetime.now()
        fecha = fecha_alineada(loc, hoy, punto=True)
        car   = self.entry_caratula.text() or "“…”"
        trib  = self.entry_tribunal.currentText() or "la Cámara en lo Criminal y Correccional"
        nom, sec, sac = "…", "…", "…"

        cuerpo = (
            "Juzgado de Niñez, Adolescencia, Violencia Familiar y de Género de "
            "….. Nom. – Sec. N° …..\n"
            "S/D:\n\n"
            f"En los autos caratulados: “{car}” (Expte. SAC N° {sac}), que se tramitan por ante "
            f"{trib} de {nom} Nominación, Secretaría N.º {sec}, con intervención de esta Oficina de Servicios Procesales "
            "(OSPRO), se ha dispuesto librar a Ud. el presente a fin de comunicar lo resuelto por el Tribunal respecto de "
            "(Apellido y Nombre – D.N.I.):\n\n"
            "SENTENCIA N° …, de fecha …/…/…: “Se Resuelve: ……… (transcribir todos los puntos).” "
            "(Fdo. Dr/a. … ‑Vocal de Cámara‑, Dr/a. … ‑Secretario/a de Cámara‑).\n\n"
            "Se adjuntan copias digitales de la sentencia y, de existir, del cómputo de pena.\n"
            "Expediente de V.F. relacionado: n° ………….\n\n"
            "Sin otro particular, saludo a Ud. atentamente."
        )
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify)

    def _plantilla_complejo_carcelario(self):
        te = self.text_edits["Oficio Complejo Carcelario"]
        te.clear()

        loc, hoy = self.entry_localidad.currentText() or "Córdoba", datetime.now()
        fecha = fecha_alineada(loc, hoy)
        car   = self.entry_caratula.text() or "“…”"
        trib  = self.entry_tribunal.currentText() or "la Cámara en lo Criminal y Correccional"
        nom, sec, sac = "…", "…", "…"
        complejo = "…"  # Nº Complejo
        localidad = "…" # Localidad

        cuerpo = (
            f"AL SEÑOR DIRECTOR DEL COMPLEJO CARCELARIO N° {complejo}\n"
            f"LOCALIDAD DE {localidad}\n"
            "S/D:\n\n"
            f"En los autos caratulados: “{car}” (SAC N° {sac}), que se tramitan por ante "
            f"{trib} de {nom} Nominación, Sec. {sec}, con intervención de esta Oficina de Servicios Procesales (OSPRO), "
            "me dirijo a Ud. a fin de informar lo resuelto respecto de (Nombre y Apellido – D.N.I.) mediante Sentencia "
            "N° …, de fecha …/…/…: “IV) Oficiar al lugar donde se encuentra actualmente detenido …, para que, en caso "
            "de evaluarse su necesidad, brinde tratamiento … por su adicción a …”. (Fdo. Dr/a. … ‑Vocal de Cámara‑, "
            "Dr/a. … ‑Secretaria/o de Cámara‑).\n\n"
            "Sin otro particular, lo saludo atentamente."
        )
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify)

    def copy_to_clipboard(self, te: QTextEdit):
        QApplication.clipboard().setText(te.toPlainText())

    def update_for_imp(self, idx: int):       # idx es el índice seleccionado
        pass

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
    win = MainWindow(); win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
