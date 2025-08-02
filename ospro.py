# -*- coding: utf-8 -*-
"""
Generador de documentos judiciales – versión base
Interfaz: datos generales + pestañas de imputados (sin plantillas)
"""
import sys, json, os
from pathlib import Path
from datetime import datetime
import re
from PySide6.QtCore import (
    Qt, QRect, QPropertyAnimation, QEvent, QUrl, QMimeData, QRegularExpression, QObject, Signal, QThread
)
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
    QProgressDialog,
    QProgressBar,
)
from PySide6.QtGui import (
    QIcon,
    QTextCursor,
    QFont,
    QRegularExpressionValidator,
)
from PySide6.QtGui import QTextBlockFormat, QTextCharFormat, QTextDocument
# ── NUEVOS IMPORTS ──────────────────────────────────────────────
import openai                    # cliente oficial
from pdfminer.high_level import extract_text              # PDF → texto
import docx2txt                  # DOCX → texto
import ast
import subprocess
import shutil
import tempfile
from helpers import anchor, anchor_html, strip_anchors, _strip_anchor_styles, strip_color

# util para obtener ruta de recursos (útil con PyInstaller)
def resource_path(relative_path: str) -> str:
    """Devuelve la ruta absoluta a un recurso incluido junto al script."""
    try:
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except AttributeError:
        base_path = Path(__file__).resolve().parent
    return str(Path(base_path) / relative_path)

# ──────────────────── utilidades menores ────────────────────
class NoWheelComboBox(QComboBox):
    """Evita que la rueda del mouse cambie accidentalmente la opción."""
    def wheelEvent(self, event): event.ignore()

class NoWheelSpinBox(QSpinBox):
    def wheelEvent(self, event): event.ignore()


class PlainCopyTextBrowser(QTextBrowser):
    """QTextBrowser that strips anchor styling when copying."""

    def copy(self) -> None:
        super().copy()
        cb = QApplication.clipboard()
        mime = cb.mimeData()
        html = mime.html()
        if html:
            html = _strip_anchor_styles(html)
            html = strip_anchors(html)
            html = strip_color(html)
            new_mime = QMimeData()
            new_mime.setHtml(html)
            new_mime.setText(mime.text())
            cb.setMimeData(new_mime)

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
_rx_bold      = re.compile(r'<span[^>]*font-weight:600[^>]*>(.*?)</span>', re.S)
_rx_italic    = re.compile(r'<span[^>]*font-style:italic[^>]*>(.*?)</span>', re.S)
_rx_bold_it   = re.compile(r'<span[^>]*font-weight:600[^>]*font-style:italic[^>]*>(.*?)</span>', re.S)
_rx_spans     = re.compile(r'<span[^>]*>(.*?)</span>', re.S)
_rx_p_cleanup = re.compile(r'<p style="[^"]*text-align:([^";]+)[^"]*">')
_rx_tag       = re.compile(r'<(/?)(b|strong|i|em|u|p)(?:\s+[^>]*)?>', re.I)
_rx_p_align   = re.compile(r'text-align\s*:\s*(left|right|center|justify)', re.I)

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

    doc = QTextDocument()
    doc.setHtml(html)
    texto = doc.toPlainText()

    texto = texto.replace("\u00A0", " ").replace("\u202F", " ")

    if not mantener_saltos:
        texto = texto.replace("\n", " ")

    return texto.strip()

def _sanitize_html(html_raw: str) -> str:
    """Devuelve SOLO el fragmento de <body>, manteniendo <b>, <i>, <u> y quitando estilos."""
    import html as html_mod
    m = re.search(r'<body[^>]*>(.*?)</body>', html_raw, flags=re.I | re.S)
    if m:
        html_raw = m.group(1)

    html_raw = re.sub(r'</?strong>', lambda m: '<b>' if m.group(0)[1] != '/' else '</b>', html_raw, flags=re.I)
    html_raw = re.sub(r'</?em>',     lambda m: '<i>' if m.group(0)[1] != '/' else '</i>', html_raw, flags=re.I)

    html_raw = re.sub(
        r'<span[^>]*style="[^"]*font-weight\s*:\s*(?:bold|700)[^"]*"[^>]*>(.*?)</span>',
        r'<b>\1</b>',
        html_raw,
        flags=re.I | re.S,
    )

    html_raw = re.sub(r'\s*(style|class|dir|lang)="[^"]*"', '', html_raw, flags=re.I)
    html_raw = re.sub(r'</?span[^>]*>', '', html_raw, flags=re.I)
    html_raw = re.sub(r'(?i)<br\s*/?>', ' ', html_raw)
    html_raw = re.sub(
        r'<p[^>]*-qt-paragraph-type:empty[^>]*>\s*(<br\s*/?>)?\s*</p>',
        ' ',
        html_raw,
        flags=re.I,
    )
    html_raw = re.sub(r'(\r\n|\r|\n|&#10;|&#13;|\u2028|\u2029|&nbsp;)', ' ', html_raw)
    html_raw = re.sub(r'\s+', ' ', html_raw).strip()
    if html_raw.lower().startswith('<p') and html_raw.lower().endswith('</p>'):
        html_raw = re.sub(r'^<p[^>]*>|</p>$', '', html_raw, flags=re.I).strip()
    return html_mod.unescape(html_raw)


def _html_to_rtf_fragment(html: str) -> str:
    """Convierte un HTML muy sencillo (p, b/strong, i/em, u) a la secuencia RTF equivalente."""
    rtf = []
    pos = 0
    for m in _rx_tag.finditer(html):
        text = html[pos:m.start()]
        text = (
            text.replace('\\', r'\\')
            .replace('{', r'\{')
            .replace('}', r'\}')
            .replace('&nbsp;', ' ')
        )
        rtf.append(text)
        pos = m.end()
        closing, tag = m.group(1), m.group(2).lower()
        if tag == 'p':
            if closing:
                rtf.append(r'\par ')
            else:
                style = m.group(0)
                alg = 'justify'
                ma = _rx_p_align.search(style)
                if ma:
                    alg = ma.group(1).lower()
                rtf.append(r'\pard')
                rtf.append({
                    'left': r'\ql ',
                    'right': r'\qr ',
                    'center': r'\qc ',
                    'justify': r'\qj ',
                }[alg])
        elif tag in ('b', 'strong'):
            rtf.append(r'\b0 ' if closing else r'\b ')
        elif tag in ('i', 'em'):
            rtf.append(r'\i0 ' if closing else r'\i ')
        elif tag == 'u':
            rtf.append(r'\ulnone ' if closing else r'\ul ')

    tail = html[pos:]
    tail = (
        tail.replace('\\', r'\\')
        .replace('{', r'\{')
        .replace('}', r'\}')
        .replace('&nbsp;', ' ')
    )
    rtf.append(tail)

    return ''.join(rtf)

def strip_trailing_single_dot(text: str | None) -> str:
    """
    Elimina puntos redundantes sin romper las elipsis.

    • Convierte cada ".." aislado (no precedido ni seguido por otro punto)
      en un único ".", aun cuando los dos puntos estén separados sólo por
      etiquetas de cierre HTML (</a>, </b>…), espacios o saltos de línea.
    • Si aún quedasen dos o más puntos al final, los reduce a:
        – "…"   → se mantiene (puntos suspensivos)
        – "."   → un solo punto
    """
    if not text:
        return ""

    # ── 1)  ".." directos → "."  (como antes)
    text = re.sub(r"(?<!\.)\.\.(?!\.)", ".", text)

    # ── 2)  ".</tag>."   ó   ".</tag></b> ."  → sólo un punto
    #        (punto  + etiquetas de cierre/espacios  + punto)
    text = re.sub(
        r"(?<!\.)"  # el char anterior NO es punto
        r"\."  # un punto
        r"(?:\s*</[^>]+>\s*)+"  # ≥1 etiquetas de cierre con posible white-space
        r"\."  # otro punto
        r"(?!\.)",  # el siguiente char NO es punto
        lambda m: m.group(0)[:-1],  # suprime el último punto
        text,
    )

    # ── 3)  Normalizar la cola ("….." → "…" | ".." → ".")
    tail = re.search(r"\.*$", text).group(0)  # todos los puntos del final
    if tail and tail not in ("...", "…"):
        text = text[: -len(tail)] + "."

    return text

# ── limpiar pies de página recurrentes ────────────────────────────────
_FOOTER_REGEX = re.compile(
    r"""
    \s*                                # espacios iniciales
    Expediente\s+SAC\s+\d+\s*-\s*      # Expediente SAC 13393379 -
    P[áa]g\.\s*\d+\s*/\s*\d+\s*-\s*    # Pág. 13 / 15 -
    N(?:[°º]|ro\.?|o\.)?\s*Res\.\s*\d+\s*
    """,
    re.IGNORECASE | re.VERBOSE,
)


def limpiar_pies_de_pagina(texto: str) -> str:
    """Elimina de ``texto`` los pies de página estándar de las sentencias."""
    return re.sub(_FOOTER_REGEX, " ", texto)

# ­­­ ---- bloque RESUELVE / RESUELVO ───────────────────────────────
_RESUELVO_REGEX = re.compile(
    r"""
    resuelv[eo]\s*:?\s*                           # “RESUELVE:” / “RESUELVO:”
    (?P<bloque>                                   # ← bloque que queremos extraer
        (?:
            (?:                                   # ─ un inciso: I) / 1. / II.- …
                \s*(?:[IVXLCDM]+|\d+)             #   núm. romano o arábigo
                \s*(?:\)|\.-|\.|-|-)              #   )  .  -  -  o .-   ← ¡cambio!
                \s+
                .*?                               #   texto del inciso (lazy)
                (?:                               #   líneas del mismo inciso
                    \n(?!\s*(?:[IVXLCDM]+|\d+)\s*(?:\)|\.-|\.|-|-)).*?
                )*
            )
        )+                                        # uno o más incisos
    )
    (?=                                           # -- corte del bloque --
        \s*(?:Protocol[íi]?cese|Notifíquese|
            Hágase\s+saber|Of[íi]ciese)           # fórmulas de cierre
        |\Z                                       # o fin de texto
    )
    """,
    re.IGNORECASE | re.DOTALL | re.VERBOSE,
)

# ── CARÁTULA ──────────────────────────────────────────────────────────
_PAT_CARAT_1 = re.compile(          # 1) entre comillas
    r'“([^”]+?)”\s*\(\s*(?:SAC|Expte\.?)\s*N°?\s*([\d.]+)\s*\)', re.I)

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
        titulo, nro = m.groups()
        return f'“{titulo.strip()}” (SAC N° {nro})'

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

# ── TRIBUNAL ──────────────────────────────────────────────────────────
# Lista de palabras clave válidas al inicio de la descripción
_CLAVES_TRIB = (
    r'Cámara|Juzgado|Tribunal|Sala|Corte'  # extensible
)

# 1) “… en esta Cámara / en el Juzgado …”
_PAT_TRIB_1 = re.compile(
    rf'en\s+(?:esta|este|el|la)\s+({_CLAVES_TRIB}[^,;.]+)', re.I)

# 2) encabezado en versales: “CAMARA EN LO CRIMINAL Y CORRECCIONAL 3ª NOM.”
_PAT_TRIB_2 = re.compile(
    r'(CAMARA\s+EN\s+LO\s+CRIMINAL[^/]+NOM\.)', re.I)

def _formatea_tribunal(raw: str) -> str:
    """Pasa a minúsculas y respeta mayúsculas iniciales."""
    raw = raw.lower()
    return capitalizar_frase(raw)

def extraer_tribunal(txt: str) -> str:
    """Devuelve la mención al órgano: 'la Cámara …' / 'el Juzgado …'."""
    plano = re.sub(r'\s+', ' ', txt)

    m = _PAT_TRIB_1.search(plano)
    if m:
        t = _formatea_tribunal(m.group(1))
        if not re.match(r'^(el|la)\s', t, re.I):
            t = 'la ' + t
        return t.strip(' .')

    m = _PAT_TRIB_2.search(plano[:2000])  # suele estar arriba de todo
    if m:
        nom = m.group(1)
        nom = (nom
               .replace('CAMARA', 'la Cámara')
               .replace('NOM.-', 'Nominación')
               .replace('NOM.',  'Nominación')
               .title())        # Cámara En Lo…
        return nom
    return ""


_FIRMA_FIN_PAT = re.compile(
    r'''
        ^\s*(?:                  # comienzo de línea + posibles firmas o meta‑datos
            Firmad[oa]           # Firmado / Firmada
          | Firma\s+digital      # Firma digital
          | Texto\s+Firmado      # Texto Firmado digitalmente
          | Fdo\.?               # Fdo.:
          | Fecha\s*:\s*\d{4}    # Fecha: 2025‑08‑02
          | Expediente\s+SAC     # Expediente SAC …
        )
    ''', re.I | re.M | re.X)

def extraer_resuelvo(texto: str) -> str:
    """
    Devuelve el ÚLTIMO bloque dispositvo completo (incluidas las fórmulas
    'Protocolícese', 'Notifíquese', 'Ofíciese', etc.).  Algoritmo:

    1.  Quita pies de página repetitivos.
    2.  Busca la última aparición de 'RESUELVE' / 'RESUELVO'.
    3.  Toma desde allí hasta la primera línea que parezca una firma
        o meta‑dato (o hasta el final del documento si no hay nada).
    """
    texto = limpiar_pies_de_pagina(texto)

    # 1) posición de la última palabra RESUELVE / RESUELVO
    idx = max(texto.lower().rfind("resuelve"),
              texto.lower().rfind("resuelvo"))
    if idx == -1:
        return ""

    frag = texto[idx:]                        # desde RESUELVE hasta el final

    # 2) cortar justo antes de firmas / fechas
    m_fin = _FIRMA_FIN_PAT.search(frag)
    if m_fin:
        frag = frag[:m_fin.start()]

    # 3) prolijo
    frag = frag.strip()
    return frag


# ── helper para capturar FIRMANTES ────────────────────────────
# ── helper para capturar FIRMANTES ────────────────────────────
_FIRMAS_REGEX = re.compile(r'''
    # Cabecera opcional: "Firmado digitalmente por:" (con o sin "Texto")
    (?:^|\n)\s*
    (?: (?:Texto\s+)?Firmad[oa]\s+digitalmente\s+por:\s* )?      

    # Nombre (mayúsculas con espacios, puntos o guiones)
    (?P<nombre>[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s.\-]+?)\s*                

    # Separador: coma o salto de línea
    (?: ,\s* | \n\s* )

    # Cargo (toma todo hasta salto de línea o coma)
    (?P<cargo>[A-ZÁÉÍÓÚÑ/][^\n,]+)                              

    # Documento opcional en la misma línea o inmediata
    (?: [,\s]* \n?\s* (?:CUIL|DNI|ID)\s* (?P<doc>[\d.\-]+) )?    

    # Debe haber una línea "Fecha: aaaa.mm.dd" a ≤2 renglones
    (?= (?:[^\n]*\n){0,2}\s*Fecha\s*:\s*\d{4}[./-]\d{2}[./-]\d{2} )
''', re.IGNORECASE | re.MULTILINE | re.UNICODE | re.VERBOSE)

# ── validaciones de campos ─────────────────────────────────────────────
# Carátula: debe incluir comillas y un número de expediente o SAC
CARATULA_REGEX = QRegularExpression(
    r'^["“][^"”]+(?:\(Expte\.\s*N°\s*\d+\))?["”](?:\s*\((?:SAC|Expte\.?\s*)\s*N°\s*\d+\))?$'
)
# Tribunal: al menos una letra minúscula y empezar en mayúscula
TRIBUNAL_REGEX = QRegularExpression(r'^(?=.*[a-záéíóúñ])[A-ZÁÉÍÓÚÑ].*$')

# ── NUEVO BLOQUE ─────────────────────────────────────────────
DNI_REGEX = re.compile(
    r'\b(?:\d{1,3}\.){2}\d{3}\b'   # 12.345.678 con puntos
    r'|\b\d{7,8}\b'                # 12345678 sin puntos
)

def extraer_dni(texto: str) -> str:
    """Devuelve sólo los dígitos del primer DNI hallado en `texto`."""
    if not texto:
        return ""
    m = DNI_REGEX.search(texto)
    return normalizar_dni(m.group(0)) if m else ""
# ─────────────────────────────────────────────────────────────


def capitalizar_frase(txt: str) -> str:
    """Devuelve la frase en mayúsculas y minúsculas tipo título."""
    minus = {"de", "del", "la", "las", "y", "en", "el", "los"}
    palabras = txt.lower().split()
    if not palabras:
        return txt
    for i, w in enumerate(palabras):
        if i == 0 or w not in minus:
            palabras[i] = w.capitalize()
    return " ".join(palabras)


def normalizar_caratula(txt: str) -> str:
    """Reemplaza comillas simples por dobles y normaliza espacios."""
    if txt is None:
        return ""
    txt = txt.strip()
    txt = txt.replace("\u201c", '"').replace("\u201d", '"')
    txt = txt.replace("'", '"')
    return txt


def normalizar_dni(txt: str) -> str:
    """Devuelve solo los dígitos del DNI."""
    if txt is None:
        return ""
    return re.sub(r"\D", "", str(txt))



def extraer_firmantes(texto: str) -> list[dict]:
    """
    Devuelve [{'nombre':…, 'cargo':…, 'doc':…}, …] con cada
    firma hallada en el texto de la sentencia.
    """
    firmas = []
    for m in _FIRMAS_REGEX.finditer(texto):
        firmas.append({
            "nombre": capitalizar_frase(m.group("nombre")).strip(),
            "cargo" : capitalizar_frase(m.group("cargo")).strip(),
            "doc"   : (m.group("doc") or "").strip(),
        })
    return firmas

# ----------------------------------------------------------------------
class Worker(QObject):
    """
    Convierte PDF / DOCX a texto, llama a la API de OpenAI, procesa
    el JSON y devuelve el dict final listo para volcar en la GUI.
    Trabaja en un hilo separado para no congelar la interfaz.
    """
    finished = Signal(dict, str)          # (datos, error)

    def __init__(self, ruta: str):
        super().__init__()
        self.ruta = ruta

    def run(self):
        try:
            # -------- 1) Extraer texto --------
            ext = self.ruta.lower()
            if ext.endswith(".pdf"):
                texto = extract_text(self.ruta)
            elif ext.endswith(".docx"):
                texto = docx2txt.process(self.ruta)
            else:
                raise ValueError("Formato no soportado")

            texto = limpiar_pies_de_pagina(texto)

            # -------- 2) OpenAI JSON mode --------
            respuesta = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Devolvé un JSON con: "
                            "generales (caratula, tribunal, sent_num, sent_fecha, resuelvo, firmantes) "
                            "e imputados (lista).  Cada imputado debe traer un objeto "
                            "`datos_personales` **con TODAS ESTAS CLAVES**:\n"
                            "nombre, dni, nacionalidad, fecha_nacimiento, lugar_nacimiento, edad, "
                            "estado_civil, domicilio, instruccion, ocupacion, padres, "
                            "prontuario, seccion_prontuario.\n"
                            "La **caratula** es la denominación de la causa, generalmente entre comillas "
                            "y con “(SAC N° …)”, “(Expte. N° …)”, “(EE N° …)”, “(SAC …)”, “(Expte. …)”, “(EE …)”, etc..  Nunca debe contener la palabra "
                            "Cámara, Juzgado ni Tribunal."
                            " “tribunal” es el órgano que dictó la sentencia, empieza con "
                            "‘la Cámara’, ‘el Juzgado’, etc. "
                            "Si un dato falta, dejá la clave vacía."
                        ),
                    },
                    {"role": "user", "content": texto[:120000]},
                ],
            )
            datos = json.loads(respuesta.choices[0].message.content)

            # -------- 3) Ajustes post-API --------
            # a) resuelvo definitivo (siempre tomar el bloque final real)
            g = datos.get("generales", {})
            g["resuelvo"] = extraer_resuelvo(texto)
            g["resuelvo"] = limpiar_pies_de_pagina(
                re.sub(r"\s*\n\s*", " ", g["resuelvo"])
            ).strip()

            # b) firmantes de respaldo
            firmas = extraer_firmantes(texto)
            if firmas:
                datos.setdefault("generales", {})["firmantes"] = firmas
            # c) verificar / completar carátula y tribunal
            carat_raw = g.get("caratula", "").strip()
            trib_raw  = g.get("tribunal", "").strip()

            # ¿La IA trajo algo plausible?
            carat_ok = CARATULA_REGEX.match(carat_raw)
            trib_ok  = TRIBUNAL_REGEX.match(trib_raw)

            # Heurística de “campos invertidos”
            if not carat_ok and ('cámara' in carat_raw.lower() or 'juzgado' in carat_raw.lower()):
                # probablemente los invirtió
                carat_raw, trib_raw = "", carat_raw    # fuerza re‑extracción abajo

            if not trib_ok and trib_raw.lower().startswith('dr'):
                trib_raw = ""                          # forzamos re‑extracción

            # Relleno / corrección
            if not carat_ok:
                nueva_carat = extraer_caratula(texto)
                if nueva_carat:
                    g['caratula'] = nueva_carat

            if not trib_ok:
                nuevo_trib = extraer_tribunal(texto)
                if nuevo_trib:
                    g['tribunal'] = nuevo_trib
            # listo: emitimos
            self.finished.emit(datos, "")          # sin error

        except Exception as e:
            self.finished.emit({}, str(e))          # devolvemos el error


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
        self.setWindowTitle("OSPRO - Oficios post sentencias")
        self.resize(1100, 610)
        self._wait_dialog = None

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


        # validadores de tribunal y revisión de carátula al terminar de editar
        self.entry_tribunal.setValidator(QRegularExpressionValidator(TRIBUNAL_REGEX))
        self.entry_caratula.editingFinished.connect(self._check_caratula)
        self.entry_caratula.setPlaceholderText('"Imputado…" (SAC N° …)')
        if self.entry_tribunal.isEditable() and self.entry_tribunal.lineEdit():
            self.entry_tribunal.lineEdit().editingFinished.connect(
                lambda: self.entry_tribunal.setCurrentText(
                    capitalizar_frase(self.entry_tribunal.currentText())
                )
            )

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
        self.entry_consulado = add_line('entry_consulado', "Consulado de:")
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
            ("Oficio Registro Automotor", "Oficio Decomiso (Reg. Automotor)"),
            ("Oficio Decomiso Con Traslado", "Oficio Comisaría Traslado"),
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
                    "Oficio Decomiso (Reg. Automotor)",
                    "Oficio Decomiso Con Traslado",  
                    "Oficio Comisaría Traslado",
                    "Oficio Decomiso Sin Traslado",
                    ):

            te = PlainCopyTextBrowser();
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
                'liberacion': QLineEdit(),
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
            w['liberacion'].textChanged.connect(self.update_templates)
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
            pair("Liberación:", w['liberacion'])
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
            'caratula'  : normalizar_caratula(self.entry_caratula.text()),
            'tribunal'  : self.entry_tribunal.currentText(),

            'resuelvo'  : self.entry_resuelvo.text(),
            'firmantes' : self.entry_firmantes.text(),

            'sent_num'  : self.entry_sent_num.text(),
            'sent_fecha': self.entry_sent_date.text(),
            'sent_firmeza': self.entry_sent_firmeza.text(),
            'consulado' : self.entry_consulado.text(),
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
            self.entry_caratula.setText(normalizar_caratula(g.get("caratula", "")))
            self.entry_tribunal.setCurrentText(
                capitalizar_frase(g.get("tribunal", ""))
            )
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
            # Lista de firmantes en forma de dicts
            if value and all(isinstance(x, dict) for x in value):
                partes = []
                for d in value:
                    nombre = d.get("nombre", "").strip()
                    cargo  = d.get("cargo", "").strip()
                    fecha  = d.get("fecha", "").strip()
                    partes.append(", ".join(p for p in (nombre, cargo, fecha) if p))
                return "; ".join(partes)
            # Lista de strings normal
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
        

    def autocompletar_desde_sentencia(self):
        """Abre un archivo, procesa en segundo plano y actualiza la GUI."""
        ruta, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar sentencia (PDF/DOCX)",
            "",
            "Documentos (*.pdf *.docx)",
        )
        if not ruta:
            return

        # ───── feedback visual ──────────────────────────────────
        self.setCursor(Qt.WaitCursor)

        self._wait_dialog = QProgressDialog("Procesando sentencia…", None, 0, 0, self)
        self._wait_dialog.setWindowTitle("Espere")
        self._wait_dialog.setWindowModality(Qt.ApplicationModal)
        self._wait_dialog.setCancelButton(None)
        self._wait_dialog.setMinimumDuration(0)
        self._wait_dialog.setValue(0)

        # ── centramos texto y barra ─────────────────────────────
        label = self._wait_dialog.findChild(QLabel)
        bar   = self._wait_dialog.findChild(QProgressBar)

        if label:
            label.setAlignment(Qt.AlignCenter)

        if bar:
            bar.setTextVisible(False)
            bar.setRange(0, 0)
            bar.setFixedWidth(160)
            bar.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)

            lay = self._wait_dialog.layout()      # puede ser None si aún no existe
            if lay is not None:
                lay.setAlignment(bar, Qt.AlignHCenter)

        # ───── hilo + worker ───────────────────────────────────
        self._thread = QThread(self)
        self._worker = Worker(ruta)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_autocomplete_done)

        self._thread.start()

# ----------------------------------------------------------------------
    def _on_autocomplete_done(self, datos: dict, err: str):
        """Señal del Worker: vuelca los datos o muestra el error."""
        # limpiar hilo / cursor
        self._thread.quit()
        self._thread.wait()
        self.unsetCursor()
        if self._wait_dialog:
            self._wait_dialog.close()
            self._wait_dialog = None

        if err:
            QMessageBox.critical(self, "Error", err)
            return

        # ------- GENERALES -------
        g = datos.get("generales", {})
        self.entry_caratula.setText(
            normalizar_caratula(self._as_str(g.get("caratula")))
        )
        self.entry_tribunal.setCurrentText(
            capitalizar_frase(self._as_str(g.get("tribunal")))
        )
        self.entry_sent_num.setText(self._as_str(g.get("sent_num")))
        self.entry_sent_date.setText(self._as_str(g.get("sent_fecha")))
        self.entry_resuelvo.setText(self._as_str(g.get("resuelvo")))
        self.entry_firmantes.setText(self._as_str(g.get("firmantes")))

        # ------- IMPUTADOS -------
        imps = datos.get("imputados", [])
        self.combo_n.setCurrentText(str(max(1, len(imps))))
        self.rebuild_imputados()

        for idx, imp in enumerate(imps):
            w     = self.imputados_widgets[idx]
            bruto = imp.get("datos_personales", imp)

            # línea formateada
            w["datos_personales"].setPlainText(
                self._format_datos_personales(bruto)
            )

            # nombre / DNI
            nom = self._as_str(imp.get("nombre") or bruto.get("nombre"))
            dni = self._as_str(imp.get("dni")    or bruto.get("dni"))
            if not dni:
                dni = extraer_dni(str(bruto))
            w["nombre"].setText(nom)
            w["dni"].setText(normalizar_dni(dni))

        self._refresh_imp_names_in_selector()
        self.update_templates()
        QMessageBox.information(self, "Listo", "Campos cargados exitosamente.")


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
        car_a = f"<b>{car_a}</b>"
        trib_a = self._field_anchor(self.entry_tribunal, "combo_tribunal", "tribunal")
        trib_a = f"<b>{trib_a}</b>"

        cuerpo = (
            "<b>Sr/a Director/a</b>\n"
            "<b>de la Dirección Nacional de Migraciones</b>\n"
            "<b>S/D:</b>\n\n"
            f"En los autos caratulados: {car_a}, que se tramitan "
            f"por ante {trib_a}, de la ciudad de Córdoba, Provincia de Córdoba, con la intervención de esta <b>Oficina de Servicios Procesales (OSPRO)</b>, se ha dispuesto librar a Ud. el presente oficio, "
            "a fin de informar lo resuelto por dicho Tribunal respecto de la persona "
            "cuyos datos personales se mencionan a continuación:\n\n"
            f"{self._imp_datos_anchor()}.\n\n"
            f"SENTENCIA N° {sent_n_a}, DE FECHA: {sent_f_a}. “Se Resuelve: {res_a}”. Fdo.: {firm_a}.\n\n"
            f"Asimismo, se informa que la sentencia antes señalada quedó firme con fecha {sent_firmeza_a}.\n\n"
            "Se adjuntan al presente oficio copia digital de la misma y del cómputo de pena respectivo.\n\n"
       )
        saludo = "Sin otro particular, saludo a Ud. atentamente."
        cuerpo = strip_trailing_single_dot(cuerpo)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify, rich=True)
        self._insert_paragraph(te, saludo, Qt.AlignCenter)


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
        car_a = f"<b>{car_a}</b>"
        trib_a = self._field_anchor(self.entry_tribunal, "combo_tribunal", "tribunal")
        trib_a = f"<b>{trib_a}</b>"
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
            f"{trib_a}, de la ciudad de Córdoba, Provincia de Córdoba, "
            "con la intervención de esta <b>Oficina de Servicios Procesales (OSPRO)</b>, se ha dispuesto librar a Ud. "
            "el presente oficio, a fin de informar lo resuelto por dicho Tribunal respecto de la persona cuyos "
            "datos personales se mencionan a continuación:\n\n"
            f"{self._imp_datos_anchor()}.\n\n"
            f"SENTENCIA N° {sent_n_a}, DE FECHA: {sent_f_a}. “Se Resuelve: {res_a}”. "
            f"Fdo.: {firm_a}.\n\n"
            f"Asimismo, se informa que la sentencia antes señalada quedó firme con fecha {sent_firmeza_a}.\n\n"
            "Se adjuntan al presente oficio copia digital de la misma y del cómputo de pena respectivo.\n\n"
        )
        saludo = "Sin otro particular, saludo a Ud. atentamente."
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        cuerpo = strip_trailing_single_dot(cuerpo)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify, rich=True)
        self._insert_paragraph(te, saludo, Qt.AlignCenter)

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
        car_a = f"<b>{car_a}</b>"
        trib_a = self._field_anchor(self.entry_tribunal, "combo_tribunal", "tribunal")
        trib_a = f"<b>{trib_a}</b>"
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
            "con la intervención de esta <b>Oficina de Servicios Procesales (OSPRO)</b>, se ha dispuesto librar el presente oficio, "
            "a fin de informar lo resuelto por dicho Tribunal respecto de la persona cuyos datos personales se mencionan a "
            "continuación:\n\n"
            f"{self._imp_datos_anchor()}.\n\n"
            f"SENTENCIA N° {sent_n_a}, DE FECHA: {sent_f_a}. “Se Resuelve: {res_a}.”. "
            f"Fdo.: {firm_a}.\n\n"
            f"Asimismo, se informa que la sentencia antes señalada quedó firme con fecha {sent_firmeza_a}.\n\n"
            "Se adjuntan al presente oficio copia digital de la misma y del cómputo de pena respectivo.\n\n"
        )
        saludo = "Sin otro particular, saludo a Ud. atentamente."

        self._insert_paragraph(te, fecha, Qt.AlignRight)
        cuerpo = strip_trailing_single_dot(cuerpo)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify, rich=True)
        self._insert_paragraph(te, saludo, Qt.AlignCenter)

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
        car_a = f"<b>{car_a}</b>"
        trib_a = self._field_anchor(self.entry_tribunal, "combo_tribunal", "tribunal")
        trib_a = f"<b>{trib_a}</b>"
        sent_n_a = self._field_anchor(self.entry_sent_num, "edit_sent_num", "…")
        sent_f_a = self._field_anchor(self.entry_sent_date, "edit_sent_fecha", "…/…/…")
        res_a = anchor(res, "edit_resuelvo", "resuelvo")
        firm_a = self._field_anchor(self.entry_firmantes, "edit_firmantes", "firmantes")
        regn_a = self._field_anchor(self.entry_regn, "edit_regn", "…")
        rodado_a = self._field_anchor(self.entry_rodado, "edit_rodado", "objeto secuestrado/decomisado")

        cuerpo = (
            f"<b>AL SR. TITULAR DEL REGISTRO DE LA</b>\n"
            f"<b>PROPIEDAD DEL AUTOMOTOR N° {regn_a}</b>\n"
            "<b>S/D:</b>\n\n"
            f"\tEn los autos caratulados: {car_a}, que se tramitan por ante "
            f"{trib_a}, con intervención de esta<b> Oficina de Servicios </b>"
            "<b>Procesales – OSPRO –</b>, se ha dispuesto librar a Ud. el presente, a fin de informarle que mediante "
            f"Sentencia N° {sent_n_a} de fecha {sent_f_a}, dicho Tribunal resolvió ordenar el <b>DECOMISO</b> del "
            f"{rodado_a}.\n\n"
            "Se transcribe a continuación la parte pertinente de la misma:\n"
            f"“SE RESUELVE: {res_a}”. "
            f"(Fdo.: {firm_a}).\n\n"
        )
        saludo = "Sin otro particular, saludo a Ud. atte."
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        cuerpo = strip_trailing_single_dot(cuerpo)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify, rich=True)
        self._insert_paragraph(te, saludo, Qt.AlignCenter)

    def _plantilla_tsj_secpenal(self):
        te = self.text_edits["Oficio Decomiso (Reg. Automotor)"]
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
        car_a = f"<b>{car_a}</b>"
        trib_a = self._field_anchor(self.entry_tribunal, "combo_tribunal", "tribunal")
        trib_a = f"<b>{trib_a}</b>"
        sent_n_a = self._field_anchor(self.entry_sent_num, "edit_sent_num", "…")
        sent_f_a = self._field_anchor(self.entry_sent_date, "edit_sent_fecha", "…/…/…")
        res_a = anchor(res, "edit_resuelvo", "resuelvo")
        firm_a = self._field_anchor(self.entry_firmantes, "edit_firmantes", "firmantes")
        rodado_a = self._field_anchor(self.entry_rodado, "edit_rodado", "objeto secuestrado/decomisado")
        deposito_a = self._field_anchor(self.entry_deposito, "combo_deposito", "depósito")

        car_a = self._field_anchor(self.entry_caratula, "edit_caratula", "carátula")
        car_a = f"<b>{car_a}</b>"
        trib_a = self._field_anchor(self.entry_tribunal, "combo_tribunal", "tribunal")
        trib_a = f"<b>{trib_a}</b>"
        sent_n_a = self._field_anchor(self.entry_sent_num, "edit_sent_num", "…")
        sent_f_a = self._field_anchor(self.entry_sent_date, "edit_sent_fecha", "…/…/…")
        res_a = anchor(res, "edit_resuelvo", "resuelvo")
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
            f"{trib_a}, con conocimiento e intervención de esta <b>Oficina de Servicios</b> "
            "<b>Procesales – OSPRO –</b>, se ha dispuesto librar a Ud. el presente a fin de poner en conocimiento lo "
            f"resuelto por la Sentencia N° {sent_n_a} del {sent_f_a}, dictada por el tribunal mencionado, en virtud de la cual "
            "se ordenó el <b>DECOMISO</b> de los siguientes objetos:\n\n"
            f"<table border='1' cellspacing='0' cellpadding='2'>"
            f"<tr><th>Tipos de elementos</th><th>Ubicación actual</th></tr>"
            f"<tr><td>{rodado_a}</td><td>{deposito_a}</td></tr></table>\n\n"
            "Pongo en su conocimiento que la mencionada sentencia se encuentra firme, transcribiéndose a "
            "continuación la parte pertinente de la misma:\n"
            f"“SE RESUELVE: {res_a}”. "
            f"(Fdo.: {firm_a}).\n\n"
            f"Asimismo, se informa que en el día de la fecha se comunicó dicha resolución al Registro del Automotor "
            f"donde está radicado el vehículo, Nº {regn_a}.\n\n"
        )
        saludo = "Sin otro particular, saludo a Ud. muy atentamente."
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        cuerpo = strip_trailing_single_dot(cuerpo)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify, rich=True)
        self._insert_paragraph(te, saludo, Qt.AlignCenter)

    def _plantilla_tsj_secpenal_depositos(self):
        te = self.text_edits["Oficio Decomiso Con Traslado"]
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
        car_a = f"<b>{car_a}</b>"
        trib_a = self._field_anchor(self.entry_tribunal, "combo_tribunal", "tribunal")
        trib_a = f"<b>{trib_a}</b>"
        sent_n_a = self._field_anchor(self.entry_sent_num, "edit_sent_num", "…")
        sent_f_a = self._field_anchor(self.entry_sent_date, "edit_sent_fecha", "…/…/…")
        res_a = anchor(res, "edit_resuelvo", "resuelvo")
        firm_a = self._field_anchor(self.entry_firmantes, "edit_firmantes", "firmantes")
        rodado_a = self._field_anchor(self.entry_rodado, "edit_rodado", "objeto secuestrado/decomisado")
        deposito_a = self._field_anchor(self.entry_deposito, "combo_deposito", "depósito")
        comisaria_a = self._field_anchor(self.entry_comisaria, "edit_comisaria", "…")

        cuerpo = (
            "<b>A LA SRA. SECRETARIA PENAL</b>\n"
            "<b>DEL TRIBUNAL SUPERIOR DE JUSTICIA</b>\n"
            "<b>DRA. MARIA PUEYRREDON DE MONFARRELL</b>\n"
            "<b>S/D:</b>\n\n"
            f"En los autos caratulados: {car_a}, que se tramitan por ante "
            f"{trib_a}, con intervención de esta <b>Oficina de Servicios Procesales</b> "
            f"<b>- OSPRO -</b>, se ha dispuesto librar a Ud. el presente, a fin de informarle que mediante Sentencia N° {sent_n_a} "
            f"de {sent_f_a}, dicho Tribunal resolvió ordenar el <b>DECOMISO</b> de los siguientes objetos:\n\n"
            f"<table border='1' cellspacing='0' cellpadding='2'>"
            f"<tr><th>Descripción del objeto</th><th>Ubicación Actual</th></tr>"
            f"<tr><td>{rodado_a}</td><td>Comisaría {comisaria_a}</td></tr></table>\n\n"
            f"Se hace saber a Ud. que el/los elemento/s referido/s se encuentra/n en la Cría. {comisaria_a} de la Policía de Córdoba "
            "y en el día de la fecha se libró oficio a dicha dependencia policial a los fines de remitir al Depósito General "
            "de Efectos Secuestrados el/los objeto/s decomisado/s.\n\n"
            "Asimismo, informo que la sentencia referida se encuentra firme, transcribiéndose a continuación la parte "
            f"pertinente de la misma: “SE RESUELVE: {res_a}”. "
            f"(Fdo.: {firm_a}).\n\n"
        )
        saludo = "Sin otro particular, saludo a Ud. muy atentamente."
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        cuerpo = strip_trailing_single_dot(cuerpo)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify, rich=True)
        self._insert_paragraph(te, saludo, Qt.AlignCenter)

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
        car_a = f"<b>{car_a}</b>"
        trib_a = self._field_anchor(self.entry_tribunal, "combo_tribunal", "tribunal")
        trib_a = f"<b>{trib_a}</b>"
        sent_n_a = self._field_anchor(self.entry_sent_num, "edit_sent_num", "…")
        sent_f_a = self._field_anchor(self.entry_sent_date, "edit_sent_fecha", "…/…/…")
        res_a = anchor(res, "edit_resuelvo", "resuelvo")
        firm_a = self._field_anchor(self.entry_firmantes, "edit_firmantes", "firmantes")
        rodado_a = self._field_anchor(self.entry_rodado, "edit_rodado", "objeto secuestrado/decomisado")
        comisaria_a = self._field_anchor(self.entry_comisaria, "edit_comisaria", "…")

        cuerpo = (
            f"<b>AL SR. TITULAR</b>\n"
            f"<b>DE LA COMISARÍA N° {comisaria_a} </b>\n"
            "<b>DE LA POLICÍA DE CÓRDOBA</b>\n"
            "<b>S/D:</b>\n\n"
            f"En los autos caratulados: {car_a}, que se tramitan por ante "
            f"{trib_a}, con intervención de esta <b>Oficina de Servicios Procesales</b> "
            "<b>- OSPRO -</b>, se ha dispuesto librar a Ud. el presente, a los fines de solicitarle que personal a su cargo "
            "Traslade los efectos que a continuación se detallan al Depósito General de Efectos Secuestrados "
            "-sito en calle Abdel Taier n° 270, B° Comercial, de esta ciudad de Córdoba-, para que sean allí recibidos:\n\n"
            f"{rodado_a}\n\n"
            "Lo solicitado obedece a directivas generales impartidas por la Secretaría Penal del T.S.J, de la cual "
            "depende esta Oficina, para los casos en los que se haya dictado la pena de decomiso y los objetos aún "
            "estén en las Comisarías, Subcomisarías y otras dependencias policiales.\n\n"
            "Se transcribe a continuación la parte pertinente de la Sentencia que así lo ordena:\n"
            f"Sentencia N° {sent_n_a} de fecha {sent_f_a}, “{res_a}”. "
            f"(Fdo.: {firm_a}), elemento/s que fuera/n secuestrado/s "
            "en las presentes actuaciones y que actualmente se encuentra/n en el Depósito de la Comisaría a su cargo.\n\n"
        )
        saludo = "Sin otro particular, saludo a Ud. muy atentamente."
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        cuerpo = strip_trailing_single_dot(cuerpo)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify, rich=True)
        self._insert_paragraph(te, saludo, Qt.AlignCenter)

    def _plantilla_tsj_secpenal_elementos(self):
        te = self.text_edits["Oficio Decomiso Sin Traslado"]
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
        car_a = f"<b>{car_a}</b>"
        trib_a = self._field_anchor(self.entry_tribunal, "combo_tribunal", "tribunal")
        trib_a = f"<b>{trib_a}</b>"
        sent_n_a = self._field_anchor(self.entry_sent_num, "edit_sent_num", "…")
        sent_f_a = self._field_anchor(self.entry_sent_date, "edit_sent_fecha", "…/…/…")
        res_a = anchor(res, "edit_resuelvo", "resuelvo")
        firm_a = self._field_anchor(self.entry_firmantes, "edit_firmantes", "firmantes")
        rodado_a = self._field_anchor(self.entry_rodado, "edit_rodado", "objeto secuestrado/decomisado")
        deposito_a = self._field_anchor(self.entry_deposito, "combo_deposito", "depósito")

        cuerpo = (
            "<b>A LA SRA. SECRETARIA PENAL</b>\n"
            "<b>DEL TRIBUNAL SUPERIOR DE JUSTICIA</b>\n"
            "<b>DRA. MARIA PUEYRREDON DE MONFARRELL</b>\n"
            "<b>S______/_______D:</b>\n\n"
            f"En los autos caratulados: {car_a}, que se tramitan por ante "
            f"{trib_a}, con conocimiento e intervención de esta <b>Oficina de Servicios</b> "
            "<b>Procesales ‑ OSPRO‑</b>, se ha dispuesto librar a Ud. el presente a fin de poner en conocimiento lo resuelto "
            f"por la Sentencia N° {sent_n_a} del {sent_f_a}, dictada por la Cámara mencionada, en virtud de la cual se ordenó el "
            "<b>DECOMISO</b> de los siguientes objetos:\n\n"
            f"<table border='1' cellspacing='0' cellpadding='2'>"
            f"<tr><th>TIPOS DE ELEMENTOS</th><th>UBICACIÓN ACTUAL</th></tr>"
            f"<tr><td>{rodado_a}</td><td>{deposito_a}</td></tr></table>\n\n"
            "Pongo en su conocimiento que la mencionada resolución se encuentra firme, transcribiéndose a continuación "
            f"la parte pertinente de la misma: “SE RESUELVE: {res_a}”. "
            f"(Fdo.: {firm_a}).\n\n"
        )
        saludo = "Sin otro particular, saludo a Ud. muy atentamente."
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        cuerpo = strip_trailing_single_dot(cuerpo)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify, rich=True)
        self._insert_paragraph(te, saludo, Qt.AlignCenter)

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
        car_a = f"<b>{car_a}</b>"
        trib_a = self._field_anchor(self.entry_tribunal, "combo_tribunal", "tribunal")
        trib_a = f"<b>{trib_a}</b>"
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
            f"{trib_a}, con intervención de esta <b>Oficina de Servicios Procesales (OSPRO)</b>, se ha resuelto enviar a Ud. el presente a fines de solicitarle que establezca lo necesario para que, "
            "por intermedio de quien corresponda, se coloque a la orden y disposición del Tribunal señalado, el rodado "
            f"{rodado_a}, vehículo que se encuentra en el {deposito_a}.\n\n"
            "Se hace saber a Ud. que dicha petición obedece a que el Tribunal mencionado ha dispuesto la entrega del "
            f"referido vehículo en carácter {dep_def_a} a su titular registral {titular_veh_a}. Para mayor recaudo se "
            "adjunta al presente, en documento informático, copia de la resolución que dispuso la medida.\n\n"
            "Finalmente, se informa que a dicho rodado, se le realizó el correspondiente Informe "
            f"Técnico de Identificación de Matrículas N° {numero_itim_a} de fecha {fecha_itim_a}, concluyendo el mismo que la unidad no "
            "presenta adulteración en sus matrículas identificatorias.\n\n"
        )
        saludo = "Saludo a Ud. muy atentamente."
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        cuerpo = strip_trailing_single_dot(cuerpo)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify, rich=True)
        self._insert_paragraph(te, saludo, Qt.AlignCenter)

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
        res_a = anchor(res, "edit_resuelvo", "resuelvo")
        firm = self.entry_firmantes.text() or "…"

        car_a = self._field_anchor(self.entry_caratula, "edit_caratula", "carátula")
        car_a = f"<b>{car_a}</b>"
        trib_a = self._field_anchor(self.entry_tribunal, "combo_tribunal", "tribunal")
        trib_a = f"<b>{trib_a}</b>"
        sent_n_a = self._field_anchor(self.entry_sent_num, "edit_sent_num", "…")
        sent_f_a = self._field_anchor(self.entry_sent_date, "edit_sent_fecha", "…/…/…")
        firm_a = self._field_anchor(self.entry_firmantes, "edit_firmantes", "firmantes")
        cuerpo = (
            "<b>Sr/a Fiscal de </b>\n"
            "<b>Instrucción que por turno corresponda</b>\n"
            "<b>S/D:</b>\n\n"
            f"En los autos caratulados: {car_a}, que se tramitan por ante "
            f"{trib_a}, con intervención de la <b>Oficina de Servicios Procesales (OSPRO)</b>, se ha dispuesto librar a Ud. el presente, por disposición de la Cámara señalada y conforme a lo resuelto en la "
            "sentencia dictada en la causa de referencia, los antecedentes obrantes en el expediente mencionado, "
            "a los fines de investigar la posible comisión de un delito perseguible de oficio.\n\n"
            f"Se transcribe a continuación la parte pertinente de la misma: “Se resuelve: {res_a}”. "
            f"(Fdo.: {firm_a}).\n\n"
        )
        saludo = "Sin otro particular, saludo a Ud. atte."
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        cuerpo = strip_trailing_single_dot(cuerpo)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify, rich=True)
        self._insert_paragraph(te, saludo, Qt.AlignCenter)

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
        car_a = f"<b>{car_a}</b>"
        trib_a = self._field_anchor(self.entry_tribunal, "combo_tribunal", "tribunal")
        trib_a = f"<b>{trib_a}</b>"
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
        car_a = f"<b>{car_a}</b>"
        trib_a = self._field_anchor(self.entry_tribunal, "combo_tribunal", "tribunal")
        trib_a = f"<b>{trib_a}</b>"
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
        car_a = f"<b>{car_a}</b>"
        trib_a = self._field_anchor(self.entry_tribunal, "combo_tribunal", "tribunal")
        trib_a = f"<b>{trib_a}</b>"
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
            f"{trib_a}, con intervención de esta <b>Oficina de Servicios Procesales (OSPRO)</b>, "
            "se ha resuelto enviar el presente oficio a fin de informar lo resuelto por dicho Tribunal respecto de la persona "
            "cuyos datos se mencionan a continuación, a saber:\n\n"
            f"{self._imp_datos_anchor()}.\n\n"
            f"SENTENCIA N° {sent_n_a}, DE FECHA {sent_f_a} “Se resuelve: {res_a}”. "
            f"(Fdo.: {firm_a}).\n\n"
            f"Se transcribe a continuación {comp_label}: {computo_a}.\n"
            f"Fecha de firmeza de la Sentencia: {sent_firmeza_a}.\n\n"
        )
        saludo = "Saluda a Ud. atentamente."
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        cuerpo = strip_trailing_single_dot(cuerpo)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify, rich=True)
        self._insert_paragraph(te, saludo, Qt.AlignCenter)

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
        car_a = f"<b>{car_a}</b>"
        trib_a = self._field_anchor(self.entry_tribunal, "combo_tribunal", "tribunal")
        trib_a = f"<b>{trib_a}</b>"
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
            "intervención de esta <b>Oficina de Servicios Procesales (OSPRO)</b>, se ha dispuesto librar a Ud. el presente oficio, "
            "a fin de informar lo resuelto por dicho Tribunal respecto de la persona cuyos datos se mencionan a continuación:\n\n"
            f"{self._imp_datos_anchor()}.\n\n"
            f"SENTENCIA N° {sent_n_a}, DE FECHA {sent_f_a}: “Se Resuelve: {res_a}”. "
            f"Fdo.: {firm_a}.\n\n"
            f"Asimismo, se informa que la sentencia antes señalada quedó firme con fecha {sent_firmeza_a}.\n\n"
            "Se adjuntan al presente oficio copia digital de la misma y del cómputo de pena respectivo.\n\n"
        )
        saludo = "Sin otro particular, saludo a Ud. atentamente."
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        cuerpo = strip_trailing_single_dot(cuerpo)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify, rich=True)
        self._insert_paragraph(te, saludo, Qt.AlignCenter)

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
        liberacion = self._imp_field('liberacion') or "…"
        antecedentes = self._imp_field('antecedentes') or "…"
        tratamientos = self._imp_field('tratamientos') or "…"

        car_a = self._field_anchor(self.entry_caratula, "edit_caratula", "carátula")
        car_a = f"<b>{car_a}</b>"
        trib_a = self._field_anchor(self.entry_tribunal, "combo_tribunal", "tribunal")
        trib_a = f"<b>{trib_a}</b>"
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
        liberacion_a = anchor(liberacion, "edit_liberacion", "…")
        antecedentes_a = anchor(antecedentes, "edit_antecedentes", "…")
        tratamientos_a = anchor(tratamientos, "edit_tratamientos", "…")
        cuerpo = (
            "<b>Al Sr. Titular del </b>\n"
            "<b>Registro Provincial de Personas Condenadas </b>\n"
            "<b>por Delitos contra la Integridad Sexual</b>\n"
            "<b>S./D.</b>\n\n"
            f"En los autos caratulados: {car_a}, que se tramitan por ante "
            f"{trib_a}, con intervención de esta <b>Oficina de Servicios Procesales (OSPRO)</b>, "
            f"se ha resuelto librar el presente a fin de registrar en dicha dependencia lo resuelto por Sentencia N° {sent_n_a}, "
            f"de fecha {sent_f_a} dictada por el mencionado Tribunal.\n\n"
            "<b>I. DATOS PERSONALES</b>\n"
            f"{self._imp_datos_anchor()}.\n\n"
            "<b>II. IDENTIFICACIÓN DACTILAR</b> (Adjuntar Ficha Dactiloscópica).\n\n"
            "<b>III. DATOS DE CONDENA Y LIBERACIÓN</b> (adjuntar copia de la sentencia).\n"
            f"   • Condena impuesta: {condena_a}\n"
            f"   • Fecha en que la sentencia quedó firme: {sent_firmeza_a}, Legajo: {legajo_a}.\n"
            f"   • Fecha de extinción de la pena: {extincion_a}\n"
            f"   • Servicio Correccional o Penitenciario: {servicio_a}\n"
            f"   • Delito (con el tipo de delito y la fecha): {delitos_a}\n"
            f"   • Liberación (fecha y motivo): {liberacion_a}\n\n"
            f"<b>IV. HISTORIAL DE DELITOS Y CONDENAS ANTERIORES.</b>\n"
            "(consignar monto y fecha de la pena, tipo de delito y descripción, correccional o penitenciario y fecha de liberación)\n"
            f"   {antecedentes_a}\n\n"
            f"<b>V. TRATAMIENTOS MÉDICOS Y PSICOLÓGICOS.</b>\n"
            "(adjuntar copia de documentación respaldatoria y consignar fecha aproximada, descripción y tipo de tratamiento, hospital o institución e indicar duración de internación)"
            f"   {tratamientos_a}\n\n"
            "<b>VI. OTROS DATOS DE INTERÉS.</b>\n\n"
            f"   Se le hace saber que {trib_a} resolvió mediante Sentencia N° {sent_n_a} de fecha {sent_f_a} lo siguiente “{res_a}.”.\n"
            f"   Fdo.: {firm_a}.\n\n"
            "Se adjuntan copias digitales de ficha RNR, sentencia firme y cómputo.\n\n"
        )
        saludo = "Saludo a Ud. atentamente."
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        cuerpo = strip_trailing_single_dot(cuerpo)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify, rich=True)
        self._insert_paragraph(te, saludo, Qt.AlignCenter)

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
        car_a = f"<b>{car_a}</b>"
        trib_a = self._field_anchor(self.entry_tribunal, "combo_tribunal", "tribunal")
        trib_a = f"<b>{trib_a}</b>"
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
        computo_a = anchor(computo, "edit_computo", "…") if computo else anchor("", "edit_computo", "…")

        cuerpo = (
            "<b>Al Sr. Director del </b>\n"
            "<b>Registro Nacional de Reincidencia</b>\n"
            "<b>S/D:</b>\n\n"
            "De acuerdo a lo dispuesto por el art. 2º de la Ley 22.177, remito a Ud. testimonio de la parte dispositiva "
            "de la resolución dictada en los autos caratulados: "
            f"{car_a}, que se tramitan por ante "
            f"{trib_a}, de la ciudad de Córdoba, Provincia de Córdoba, con intervención de esta <b>Oficina de Servicios Procesales (OSPRO)</b>, en contra de:\n\n"
            f"{self._imp_datos_anchor()}.\n\n"
            f"SENTENCIA N° {sent_n_a}, DE FECHA {sent_f_a}: “{res_a}.” (Fdo.: {firm_a}).\n\n"
            f"Se transcribe a continuación {comp_label}: {computo_a}.\n"
            f"Fecha de firmeza de la sentencia: {sent_firmeza_a}.\n\n"
        )
        saludo = "Saluda a Ud. atentamente."
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        cuerpo = strip_trailing_single_dot(cuerpo)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify, rich=True)
        self._insert_paragraph(te, saludo, Qt.AlignCenter)

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
        car_a = f"<b>{car_a}</b>"
        trib_a = self._field_anchor(self.entry_tribunal, "combo_tribunal", "tribunal")
        trib_a = f"<b>{trib_a}</b>"
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
            f"{trib_a}, de esta ciudad de Córdoba, provincia de Córdoba, con intervención de esta <b>Oficina de</b> "
            "<b>Servicios Procesales - OSPRO -</b>, se ha dispuesto librar a Ud. el presente a fin de comunicar lo resuelto por "
            "dicho Tribunal, respecto de la persona cuyos datos se detallan a continuación:\n\n"
            f"{self._imp_datos_anchor()}.\n\n"
            f"SENTENCIA N° {sent_n_a}, DE FECHA {sent_f_a}: “Se resuelve: {res_a}”. "
            f"(Fdo.: {firm_a}).\n\n"
            f"Asimismo, se informa que la sentencia condenatoria antes referida quedó firme con fecha {sent_firmeza_a}.\n"
            "Se adjuntan al presente oficio copia digital Sentencia y de cómputo de pena respectivos.\n\n"
        )
        saludo = "Saludo a Ud. atentamente."
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        cuerpo = strip_trailing_single_dot(cuerpo)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify, rich=True)
        self._insert_paragraph(te, saludo, Qt.AlignCenter)

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
        nombre = self._imp_field('nombre') or "\u2026"
        dni = self._imp_field('dni') or "\u2026"

        car_a = self._field_anchor(self.entry_caratula, "edit_caratula", "carátula")
        car_a = f"<b>{car_a}</b>"
        trib_a = self._field_anchor(self.entry_tribunal, "combo_tribunal", "tribunal")
        trib_a = f"<b>{trib_a}</b>"
        sent_n_a = self._field_anchor(self.entry_sent_num, "edit_sent_num", "…")
        sent_f_a = self._field_anchor(self.entry_sent_date, "edit_sent_fecha", "…/…/…")
        res_a = self._field_anchor(self.entry_resuelvo, "edit_resuelvo", "resuelvo")
        firm_a = self._field_anchor(self.entry_firmantes, "edit_firmantes", "firmantes")
        juz_a = anchor(juz, "combo_juz_navfyg", "juzgado")
        ee_rel_a = anchor(ee_rel, "edit_ee_relacionado", "…")
        nombre_a = anchor(nombre, "edit_nombre", "…")
        dni_a = anchor(dni, "edit_dni", "…")

        
        cuerpo = (
            f"<b>{juz_a}</b>\n"
            "<b>S/D:</b>\n\n"
            f"En los autos caratulados: {car_a}, que se tramitan por ante "
            f"{trib_a}, con conocimiento e intervención de esta <b>Oficina de Servicios Procesales (OSPRO)</b>, se ha dispuesto librar a Ud. el presente, a fin de comunicarle lo resuelto por el mencionado Tribunal con relación a "
            f"{nombre_a}, DNI {dni_a}, mediante "
            f"Sentencia N° {sent_n_a}, de fecha {sent_f_a}: “Se Resuelve: {res_a}” "
            f"(Fdo.: {firm_a}).\n\n"
            "Se adjuntan al presente oficio copia digital de la sentencia y del cómputo de pena respectivo.\n\n"
            f"Expediente de V.F. relacionado al presente n° {ee_rel_a}\n\n"
        )
        saludo = "Sin otro particular, saludo a Ud. atentamente."
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        cuerpo = strip_trailing_single_dot(cuerpo)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify, rich=True)
        self._insert_paragraph(te, saludo, Qt.AlignCenter)

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
        car_a = f"<b>{car_a}</b>"
        trib_a = self._field_anchor(self.entry_tribunal, "combo_tribunal", "tribunal")
        trib_a = f"<b>{trib_a}</b>"
        sent_n_a = self._field_anchor(self.entry_sent_num, "edit_sent_num", "…")
        sent_f_a = self._field_anchor(self.entry_sent_date, "edit_sent_fecha", "…/…/…")
        res_a = self._field_anchor(self.entry_resuelvo, "edit_resuelvo", "resuelvo")
        firm_a = self._field_anchor(self.entry_firmantes, "edit_firmantes", "firmantes")
        establecimiento_a = anchor(establecimiento, "combo_servicio_penitenciario", "…")
        nombre_a = anchor(nombre, "edit_nombre", "…")
        dni_a = anchor(dni, "edit_dni", "…")

        cuerpo = (
            "<b>AL SEÑOR DIRECTOR </b>\n"
            f"<b>DEL {establecimiento_a}</b>\n"
            "<b>S/D:</b>\n\n"
            f"En los autos caratulados: {car_a}, que se tramitan por ante "
            f"{trib_a}, con intervención de esta <b>Oficina de Servicios Procesales (OSPRO)</b>, "
            f"me dirijo a Ud. a los fines de informar lo resuelto con relación a {nombre_a}, DNI {dni_a}, mediante Sentencia "
            f"N° {sent_n_a}, de fecha {sent_f_a}: \u201c{res_a}\u201d. "
            f"(Fdo.: {firm_a}).\n\n"
        )
        saludo = "Sin otro particular, lo saludo atentamente."
        self._insert_paragraph(te, fecha, Qt.AlignRight)
        cuerpo = strip_trailing_single_dot(cuerpo)
        self._insert_paragraph(te, cuerpo, Qt.AlignJustify, rich=True)
        self._insert_paragraph(te, saludo, Qt.AlignCenter)

    def copy_to_clipboard(self, te: QTextEdit):
        from PySide6.QtCore import QMimeData
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QClipboard

        plain_text = te.toPlainText().strip()

        basic_html = te.toHtml()
        basic_html = _strip_anchor_styles(basic_html)
        basic_html = strip_anchors(basic_html)
        basic_html = strip_color(basic_html)
        basic_html = re.sub(r"font-size\s*:[^;\"']+;?", '', basic_html, flags=re.I)
        basic_html = re.sub(r'text-align\s*:\s*left\s*;?', '', basic_html, flags=re.I)
        basic_html = re.sub(r'align="left"\s*', '', basic_html, flags=re.I)

        def _ensure_justify(m):
            tag = m.group(0)
            if re.search(r'(text-align\s*:\s*(center|right))|(align="(center|right)")', tag, flags=re.I):
                return tag
            if 'style="' in tag:
                return re.sub(r'style="([^"]*)"', lambda s: f'style="{s.group(1)}text-align:justify;"', tag)
            return tag[:-1] + ' style="text-align:justify;">'

        basic_html = re.sub(r'<p[^>]*>', _ensure_justify, basic_html)
        basic_html = re.sub(r'style="\s*"', '', basic_html)

        html_full = (
            "<!DOCTYPE html><html><head><meta charset='UTF-8'>"
            "<style>"
            "body{font-family:'Times New Roman',serif;"
            "font-size:12pt;line-height:1.0;margin:0;}"
            "</style></head><body><!--StartFragment-->" + basic_html + "<!--EndFragment--></body></html>"
        )

        rtf_paragraphs = []
        for para_html in re.findall(r'<p[^>]*>.*?</p>', basic_html, flags=re.S | re.I):
            rtf_paragraphs.append(_html_to_rtf_fragment(para_html))

        rtf_content = (
            r"{\rtf1\ansi\deff0" r"{\fonttbl{\f0 Times New Roman;}}" r"\fs24 " + ''.join(rtf_paragraphs) + "}"
        )

        mime = QMimeData()
        mime.setText(plain_text)
        mime.setData("text/rtf", rtf_content.encode("utf-8"))
        mime.setHtml(html_full)
        QApplication.clipboard().setMimeData(mime, QClipboard.Clipboard)

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

    def _check_caratula(self) -> None:
        """Valida el formato de la carátula al finalizar la edición."""
        txt = normalizar_caratula(self.entry_caratula.text())
        self.entry_caratula.setText(txt)
        if txt and not CARATULA_REGEX.match(txt):
            QMessageBox.warning(
                self,
                "Carátula inválida",
                "La carátula debe ir entre comillas y contener el número de expediente o SAC.",
            )

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
        if clave == "edit_consulado":
            self._editar_lineedit(self.entry_consulado, "Consulado")
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
    app.setWindowIcon(QIcon(resource_path("icono4.ico")))

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
