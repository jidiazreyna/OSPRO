# -*- coding: utf-8 -*-
"""
core.py – nuevas utilidades de extracción y procesamiento para OSPRO.
"""

from __future__ import annotations

import json
import re

import docx2txt
import openai
from pdfminer.high_level import extract_text

try:
    from PyQt6.QtCore import QRegularExpression, QObject, Signal
except Exception:  # pragma: no cover - fallback for PyQt5 or no Qt
    try:
        from PyQt5.QtCore import QRegularExpression, QObject, Signal  # type: ignore
    except Exception:  # pragma: no cover - simple stubs
        class QRegularExpression:
            def __init__(self, pattern: str):
                self.pattern = pattern

            def match(self, text: str):
                return re.match(self.pattern, text)

        class QObject:
            pass

        class Signal:  # minimal pyqtSignal replacement
            def __init__(self, *a, **k):
                pass

            def emit(self, *a, **k):
                pass

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
    """Elimina de `texto` los pies de página estándar de las sentencias."""
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
                    \n(?!\s*(?:[IVXLCDM]+|\d+)\s*(?:\)|\.-|\.|-|-) ).*?
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
        ^\s*(?:[\-\u2022*·]\s*)?   # posible viñeta o puntuación inicial
        (?:
            (?:Texto\s+)?Firmad[oa]\s+digitalmente(?:\s+por:)?  # "Firmado digitalmente por:"
          | Firmad[oa]                                 # Firmado / Firmada
          | Firma\s+digital                            # Firma digital
          | Texto\s+Firmado                            # Texto Firmado digitalmente
          | Fdo\.?                                     # Fdo.:
          | Fecha\s*:\s*\d{4}                         # Fecha: 2025‑08‑02
          | Expediente\s+SAC                           # Expediente SAC …
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

    # quitar encabezado "RESUELVE:" / "RESUELVO:" si quedó incluido
    frag = re.sub(r"^resuelv[eo]\s*:?\s*", "", frag, flags=re.I)

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
    r'^["“][^"”]+(?:\(Expte\.\s*N°\s*\d+\))?["”](?:\s*\((?:SAC|Expte\.?)\s*N°\s*\d+\))?$'
)
# Tribunal: al menos una letra minúscula y empezar en mayúscula
TRIBUNAL_REGEX = QRegularExpression(r'^(?=.*[a-záéíóúñ])[A-ZÁÉÍÓÚÑ].*$')

# ── NUEVO BLOQUE ─────────────────────────────────────────────
DNI_REGEX = re.compile(
    r'\b(?:\d{1,3}\.){2}\d{3}\b'   # 12.345.678 con puntos
    r'|\b\d{7,8}\b'                # 12345678 sin puntos
)

def extraer_dni(texto: str) -> str:
    """Devuelve sólo los dígitos del primer DNI hallado en texto."""
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
                            "datos_personales **con TODAS ESTAS CLAVES**:\n"
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
            g["resuelvo"] = re.sub(
                r"(?i)\s*(?:texto\s+)?firmad[oa]\s+digitalmente.*",
                "",
                g["resuelvo"],
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

# ---- Reexportes para compatibilidad con la API previa -----------------
#
# En la aplicación original estas funciones y constantes vivían en el módulo
# ``ospro``.  Sin embargo, en entornos de pruebas o instalaciones mínimas ese
# módulo puede no estar disponible (o faltarle alguna función), lo que hacía
# que la importación fallase y la librería no pudiera utilizarse siquiera con
# ``monkeypatch``.  Para evitar el ``ImportError`` realizamos una importación
# perezosa: si ``ospro`` o alguno de sus atributos no existen se proveen
# versiones de relleno que lanzan ``NotImplementedError`` cuando se utilizan.
try:  # pragma: no cover - se ejecuta sólo cuando el módulo está instalado
    import ospro as _ospro  # type: ignore
except Exception:  # pragma: no cover - ausencia total del módulo
    _ospro = None  # type: ignore


def _missing(*_args, **_kwargs):  # pragma: no cover - función simple
    """Marcador de posición para funcionalidades ausentes."""
    raise NotImplementedError("La funcionalidad solicitada no está disponible")


procesar_sentencia = getattr(_ospro, "procesar_sentencia", _missing)

if _ospro and hasattr(_ospro, "autocompletar"):
    autocompletar = _ospro.autocompletar  # type: ignore
else:
    def autocompletar(file_bytes: bytes, filename: str) -> dict:
        """Procesa una sentencia y vuelca resultados en ``st.session_state``."""

        try:  # importación perezosa para entornos sin Streamlit
            import streamlit as st  # type: ignore
        except Exception as exc:  # pragma: no cover - fallback defensivo
            raise RuntimeError("Streamlit es requerido para autocompletar") from exc

        datos = procesar_sentencia(file_bytes, filename)
        gen = datos.get("generales", {}) if isinstance(datos, dict) else {}

        res = gen.get("resuelvo", "")
        if isinstance(res, list):
            res_txt = ", ".join(str(r).strip() for r in res)
        else:
            res_txt = str(res).replace("\n", " ")
        st.session_state["sres"] = res_txt

        firmas = gen.get("firmantes")
        if firmas is not None:
            if isinstance(firmas, list):
                if firmas and isinstance(firmas[0], dict):
                    partes = []
                    for f in firmas:
                        nombre = f.get("nombre")
                        cargo = f.get("cargo")
                        partes.append(
                            ", ".join(p for p in [nombre, cargo] if p)
                        )
                    firmas_txt = "; ".join(partes)
                else:
                    firmas_txt = ", ".join(str(f) for f in firmas)
            else:
                firmas_txt = str(firmas)
            st.session_state["sfirmaza"] = firmas_txt

        def _format_dp(raw: object) -> str:
            import ast

            if isinstance(raw, str):
                try:
                    raw_obj = ast.literal_eval(raw)
                    if isinstance(raw_obj, dict):
                        dp = raw_obj
                    else:
                        return str(raw)
                except Exception:
                    return str(raw)
            elif isinstance(raw, dict):
                dp = raw
            else:
                return str(raw)

            partes: list[str] = []
            if dp.get("nombre"):
                partes.append(dp["nombre"])
            if dp.get("dni"):
                partes.append(f"D.N.I. {dp['dni']}")
            if dp.get("nacionalidad"):
                partes.append(dp["nacionalidad"])
            if dp.get("edad"):
                partes.append(f"{dp['edad']} años")
            if dp.get("estado_civil"):
                partes.append(dp["estado_civil"])
            if dp.get("instruccion"):
                partes.append(dp["instruccion"])
            if dp.get("ocupacion"):
                partes.append(dp["ocupacion"])
            if dp.get("fecha_nacimiento"):
                partes.append(f"Nacido el {dp['fecha_nacimiento']}")
            if dp.get("lugar_nacimiento"):
                partes.append(f"en {dp['lugar_nacimiento']}")
            if dp.get("domicilio"):
                partes.append(f"Domicilio: {dp['domicilio']}")
            if dp.get("padres"):
                padres_val = dp["padres"]
                if isinstance(padres_val, str):
                    padres = padres_val
                elif isinstance(padres_val, list):
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
            pront = dp.get("prontuario") or dp.get("prio") or dp.get("pront")
            if pront:
                partes.append(f"Pront. {pront}")
            return ", ".join(partes)

        imputados = datos.get("imputados", []) if isinstance(datos, dict) else []
        for idx, imp in enumerate(imputados):
            bruto = imp.get("datos_personales", imp)
            st.session_state[f"imp{idx}_datos"] = _format_dp(bruto)

        st.session_state.setdefault("datos_autocompletados", {})
        st.session_state["datos_autocompletados"].update(datos)

        return datos

autocompletar_caratula = getattr(_ospro, "autocompletar_caratula", _missing)


if _ospro and hasattr(_ospro, "segmentar_imputados"):
    segmentar_imputados = _ospro.segmentar_imputados  # type: ignore
else:
    def segmentar_imputados(texto: str) -> list[str]:
        """Divide el texto en bloques de imputados.

        Separa por apariciones de ``"Prontuario"`` o por un punto seguido de
        ``y``/``e`` + nombre propio.  Ignora segmentos que comiencen con
        referencias a víctimas (``Sra."`, ``Sr."`, etc.).
        """

        texto = texto.replace("\n", " ")
        partes = re.split(
            r"(?=Prontuario\s+\d+\.)|\.\s+(?=(?:[yYeE])\s+[A-ZÁÉÍÓÚÑ])",
            texto,
        )
        bloques: list[str] = []
        for parte in partes:
            seg = re.sub(r"^(?:[yYeE]\s+)", "", parte)
            seg = re.sub(r"^(?:del\s+)?imputado\s+", "", seg, flags=re.IGNORECASE)
            seg = seg.strip(" .")
            if not seg:
                continue
            if re.match(r"^(Sra|Sr|Señor|Señora)\b", seg):
                continue
            bloques.append(seg)
        return bloques


if _ospro and hasattr(_ospro, "extraer_datos_personales"):
    extraer_datos_personales = _ospro.extraer_datos_personales  # type: ignore
else:
    def extraer_datos_personales(texto: str) -> dict[str, str]:
        """Extrae nombre, DNI y otros datos de un bloque de imputado."""

        datos: dict[str, str] = {}
        t = texto.strip()

        # Prontuario / prio
        m = re.search(r"Prontuario\s+(\d+)", t, flags=re.IGNORECASE)
        if m:
            datos["prontuario"] = m.group(1)
        t = re.sub(r"^Prontuario\s+\d+\.\s*", "", t, flags=re.IGNORECASE)
        m = re.search(r"Prio\.\s*([^\.]+)", t, flags=re.IGNORECASE)
        if m:
            datos["prio"] = m.group(1).strip(" ;.")

        # DNI
        m = re.search(
            r"D\.?N\.?I\.?[:\s]*(?:n.?°)?\s*([0-9\.]+)",
            t,
            flags=re.IGNORECASE,
        )
        if m:
            datos["dni"] = re.sub(r"\D", "", m.group(1))

        # Fecha de nacimiento
        m = re.search(r"Nacido\s+el\s+(\d{2}/\d{2}/\d{4})", t, flags=re.IGNORECASE)
        if m:
            datos["fecha_nacimiento"] = m.group(1)

        # Alias
        m = re.search(
            r"alias\s+[\"“]?([A-Za-zÁÉÍÓÚÑüÜñ\s]+)[\"”]?(?:,|\.)",
            t,
            flags=re.IGNORECASE,
        )
        if m:
            datos["alias"] = m.group(1).strip()

        # Nombre (primera frase antes de la primera coma)
        t = re.sub(r"^(?:Imputado:)?\s*", "", t, flags=re.IGNORECASE)
        t = re.sub(r"^(?:[yYeE]\s+)", "", t)
        t = re.sub(r"^(?:del\s+)?imputado\s+", "", t, flags=re.IGNORECASE)
        m = re.match(r"([^,]+)", t)
        if m:
            datos["nombre"] = m.group(1).strip()

        return datos

PENITENCIARIOS = getattr(_ospro, "PENITENCIARIOS", [])
DEPOSITOS = getattr(_ospro, "DEPOSITOS", [])
JUZ_NAVFYG = getattr(_ospro, "JUZ_NAVFYG", [])
TRIBUNALES = getattr(_ospro, "TRIBUNALES", [])
MAX_IMPUTADOS = getattr(_ospro, "MAX_IMPUTADOS", 10)

__all__ = [
    "limpiar_pies_de_pagina",
    "extraer_caratula",
    "extraer_tribunal",
    "extraer_resuelvo",
    "extraer_dni",
    "extraer_firmantes",
    "capitalizar_frase",
    "normalizar_caratula",
    "normalizar_dni",
    "Worker",
    "procesar_sentencia",
    "segmentar_imputados",
    "extraer_datos_personales",
    "autocompletar",
    "autocompletar_caratula",
    "PENITENCIARIOS",
    "DEPOSITOS",
    "JUZ_NAVFYG",
    "TRIBUNALES",
    "MAX_IMPUTADOS",
]
