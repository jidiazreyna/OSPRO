# -*- coding: utf-8 -*-
"""
core.py – capa lógica pura de OSPRO
-----------------------------------

La app web expone un único nombre público:

    autocompletar(file_bytes, filename) -> None
        Extrae los datos y rellena st.session_state.

¡Nada más!  El resto son utilidades internas.
"""
from __future__ import annotations

import json
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, List, Dict

import os
import ast

import docx2txt
import openai
import streamlit as st            # ← para volcar datos en la UI
from pdfminer.high_level import extract_text

try:
    from PyQt6.QtCore import QRegularExpression
except Exception:  # pragma: no cover - fallback for PyQt5 or no Qt
    try:
        from PyQt5.QtCore import QRegularExpression  # type: ignore
    except Exception:  # pragma: no cover - simple stub
        class QRegularExpression:  # minimal interface
            def __init__(self, pattern: str):
                self.pattern = pattern

            def match(self, text: str):
                return re.match(self.pattern, text)

# ────────────────────────── Config ──────────────────────────
CONFIG_FILE = "config.json"


def _resource_path(rel: str) -> Path:
    return Path(__file__).resolve().parent / rel


def _cargar_config() -> Dict[str, Any]:
    cfg = _resource_path(CONFIG_FILE)
    if cfg.exists():
        with cfg.open(encoding="utf-8") as fh:
            return json.load(fh)
    return {}


_cfg = _cargar_config()


# ── listas de opciones para la UI web ───────────────────────────────
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

DEPOSITOS = [
    "Depósito General de Efectos Secuestrados",
    "Depósito de la Unidad Judicial de Lucha c/ Narcotráfico",
    "Depósito de Armas (Tribunales II)",
    "Depósito de Automotores 1 (Bouwer)",
    "Depósito de Automotores 2 (Bouwer)",
    "Depositado en Cuenta Judicial en pesos o dólares del Banco de Córdoba",
    "Depósito de Armas y elementos secuestrados (Tribunales II)",
]

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
    "Juzgado de Violencia de Género, modalidad doméstica -causas graves- de 8ª Nom. – Sec.\u202fN°\u202f15",
    "Juzgado de Violencia de Género, modalidad doméstica -causas graves- de 8ª Nom. – Sec.\u202fN°\u202f16",
    "Juzgado de Violencia de Género, modalidad doméstica -causas graves- de 9ª Nom. – Sec.\u202fN°\u202f17",
    "Juzgado de Violencia de Género, modalidad doméstica -causas graves- de 9ª Nom. – Sec.\u202fN°\u202f18",
]

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


# Máximo de imputados soportados por la interfaz
MAX_IMPUTADOS = 20


def _get_openai_client():
    """Return an OpenAI client compatible with v0 and v1 APIs."""
    api_key = os.environ.get("OPENAI_API_KEY", _cfg.get("api_key", ""))
    if not api_key or api_key == "TU_API_KEY":
        raise RuntimeError(
            "Falta la clave de API de OpenAI. Definí OPENAI_API_KEY o actualizá config.json."
        )
    proxy = os.environ.get("PROXY_URL", _cfg.get("proxy", ""))
    try:
        from openai import OpenAI  # type: ignore
        kwargs = {"api_key": api_key}
        if proxy:
            try:
                import httpx  # type: ignore
                kwargs["http_client"] = httpx.Client(proxy=proxy)
            except Exception:
                pass
        return OpenAI(**kwargs)
    except Exception:
        # Old OpenAI < 1.0 style
        openai.api_key = api_key
        if proxy:
            try:
                import requests  # type: ignore
                session = requests.Session()
                session.proxies.update({"http": proxy, "https": proxy})
                openai.requestssession = session  # type: ignore[attr-defined]
            except Exception:
                pass
        return openai
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
    """Elimina de `texto los pies de página estándar de las sentencias."""
    return re.sub(_FOOTER_REGEX, " ", texto)

# alias histórico
limpiar_pies = limpiar_pies_de_pagina

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
# Carátula: debe incluir un número de expediente o SAC.
# Se admite un texto previo con o sin comillas y diferentes variantes de
# "Expte."/"SAC"/"N°" al final.
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

ALIAS_RE   = re.compile(r'alias\s+[«“"\'’]?([^"»”\n]+)[»”"\'’]?', re.I)
EDAD_RE    = re.compile(r'\b(\d{1,3})\s*años(?:\s*de\s*edad)?', re.I)
NAC_RE = re.compile(r'(?:de\s+)?nacionalidad\s+([a-záéíóúñ]+)', re.I)
ECIVIL_RE  = re.compile(r'de\s+estado\s+civil\s+([a-záéíóúñ\s]+?)(?:[,.;]|\s$)', re.I)
OCUP_RE    = re.compile(r'de\s+ocupaci[oó]n\s+([a-záéíóúñ\s]+?)(?:[,.;]|\s$)', re.I)
INSTR_RE   = re.compile(r'instrucci[oó]n\s+([a-záéíóúñ\s]+?)(?:[,.;]|\s$)', re.I)
DOM_RE = re.compile(r'(?:domiciliad[oa]\s+en|con\s+domicilio\s+en)\s+([^.\n]+)', re.I)
FNAC_RE = re.compile(r'(?:Nacid[oa]\s+el\s+|el\s*d[íi]a\s*)(\d{1,2}/\d{1,2}/\d{2,4})', re.I)
LNAC_RE    = re.compile(r'Nacid[oa]\s+el\s+\d{1,2}/\d{1,2}/\d{2,4},?\s+en\s+([^.,\n]+)', re.I)
PADRES_RE  = re.compile(r'hij[oa]\s+de\s+([^.,\n]+?)(?:\s+y\s+de\s+([^.,\n]+))?(?:[,.;]|\s$)', re.I)
PRIO_RE    = re.compile(r'(?:Prio\.?|Pront\.?|Prontuario)\s*[:\-]?\s*([^\n.;]+)', re.I)
DNI_TXT_RE = re.compile(r'(?:D\.?\s*N\.?\s*I\.?|DNI)\s*:?\s*([\d.]+)', re.I)
NOMBRE_RE  = re.compile(r'([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑ\s.\-]+?),\s*de\s*\d{1,3}\s*años.*?D\.?N\.?I\.?:?\s*[\d.]+', re.I | re.S)
NOMBRE_INICIO_RE = re.compile(
    r'^\s*([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑ.\-]+(?:\s+[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑ.\-]+){1,3})\s*,',
    re.M
)

# ── NUEVO: helpers de segmentación ─────────────────────────
MULTI_PERSONA_PAT = re.compile(r'(D\.?\s*N\.?\s*I\.?|Prontuario)', re.I)

def es_multipersona(s: str) -> bool:
    # ≥2 ocurrencias de DNI o Prontuario → probable texto con varias personas
    return len(MULTI_PERSONA_PAT.findall(s or "")) >= 2

def segmentar_imputados(texto: str) -> list[str]:
    plano = re.sub(r'\s+', ' ', texto)

    # Intento segmentar por "Nombre, ..." que arranca una ficha
    NAME_START = re.compile(
        r'(?<!\w)([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑ.\-]+(?:\s+[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑ.\-]+){1,3})\s*,\s*'
        r'(?:de\s*\d{1,3}\s*años|D\.?\s*N\.?\s*I\.?|nacionalidad)',
        re.I
    )
    hits = list(NAME_START.finditer(plano))

    bloques: list[str] = []
    if hits:
        for i, m in enumerate(hits):
            start = m.start()
            end = hits[i+1].start() if i+1 < len(hits) else len(plano)
            bloques.append(_recortar_bloque_un_persona(plano[start:end]))
        return bloques

    # Fallback: si no pude, uso "…Prontuario." y recorto por DNI duplicado
    candidatos = re.findall(r'.*?Prontuario[^\n.]*\.', plano, flags=re.I | re.S)
    return [_recortar_bloque_un_persona(b) for b in candidatos]


def _recortar_bloque_un_persona(b: str) -> str:
    s = re.sub(r'\s+', ' ', b).strip()
    # 1) Corto en el primer "Prontuario ... .", si existe
    m_prio = re.search(r'Prontuario[^\n.]*\.', s, re.I)
    if m_prio:
        s = s[:m_prio.end()]
    # 2) Si hay 2 DNIs dentro del mismo bloque → me quedo hasta el 1º DNI
    dnis = list(DNI_TXT_RE.finditer(s))
    if len(dnis) >= 2:
        s = s[:dnis[1].start()]
    return s.strip()

def extraer_datos_personales(texto: str) -> dict:
    t = re.sub(r'\s+', ' ', texto)  # línea corrida para facilitar regex largas
    dp: dict[str, str | list] = {}

    # Nombre cerca de "de XX años ... DNI"
    m = NOMBRE_RE.search(t)
    if m:
        dp["nombre"] = capitalizar_frase(m.group(1).strip())
    # Nombre: prefiero el que está al INICIO del bloque; si no, el genérico
    m = NOMBRE_INICIO_RE.search(t) or NOMBRE_RE.search(t)
    if m:
        dp["nombre"] = capitalizar_frase(m.group(1).strip())

    # DNI (robusto)
    m = DNI_TXT_RE.search(t) or DNI_REGEX.search(t)
    if m:
        dp["dni"] = normalizar_dni(m.group(1))

    # Alias: sólo lo tomo ANTES del primer DNI (evita “heredar” alias ajenos)
    alias_scope = t[:m.start()] if m else t
    if (m2 := ALIAS_RE.search(alias_scope)):   
        dp["alias"] = m2.group(1).strip()

    # DNI (robusto)
    m = DNI_TXT_RE.search(t) or DNI_REGEX.search(t)
    if m:
        dp["dni"] = normalizar_dni(m.group(1))

    if (m := ALIAS_RE.search(t)):   dp["alias"] = m.group(1).strip()
    if (m := EDAD_RE.search(t)):    dp["edad"]  = m.group(1)
    if (m := NAC_RE.search(t)):     dp["nacionalidad"] = m.group(1).strip()
    if (m := ECIVIL_RE.search(t)):  dp["estado_civil"] = m.group(1).strip()
    if (m := OCUP_RE.search(t)):    dp["ocupacion"]    = m.group(1).strip()
    if (m := INSTR_RE.search(t)):   dp["instruccion"]  = m.group(1).strip()
    if (m := DOM_RE.search(t)):     dp["domicilio"]    = m.group(1).strip()
    if (m := FNAC_RE.search(t)):    dp["fecha_nacimiento"] = m.group(1).strip()
    if (m := LNAC_RE.search(t)):    dp["lugar_nacimiento"] = m.group(1).strip()
    if (m := PADRES_RE.search(t)):
        padres = [m.group(1).strip()]
        if m.group(2): padres.append(m.group(2).strip())
        dp["padres"] = padres
    if (m := PRIO_RE.search(t)):
        dp["prio"] = m.group(1).strip()

    return dp


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
    """Reemplaza comillas simples por dobles, balancea y normaliza espacios."""
    if txt is None:
        return ""
    txt = txt.strip()
    # unifico variantes de comillas en una sola
    txt = txt.replace("\u201c", '"').replace("\u201d", '"')
    txt = txt.replace("'", '"')
    # si hay una sola comilla, cierro antes del número de expediente/SAC
    if txt.count('"') == 1:
        m = re.search(r'\s*(\(\s*(?:Expte\.\s*)?(?:SAC|Expte\.?)\b)', txt, re.I)
        if m:
            txt = txt[:m.start()].rstrip() + '"' + txt[m.start():]
        else:
            txt = txt + '"'
    return txt


def autocompletar_caratula(txt: str) -> str:
    """Intenta extraer y normalizar la carátula desde ``txt``."""
    txt = normalizar_caratula(txt)
    if not txt:
        return ""
    extraida = extraer_caratula(txt)
    return extraida or txt


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

# ── helpers varios ------------------------------------------------------
def _as_str(value):
    """Convierte listas, números o ``None`` en ``str`` plano."""
    if isinstance(value, list):
        if value and all(isinstance(x, dict) for x in value):
            partes = []
            for d in value:
                nombre = d.get("nombre", "").strip()
                cargo = d.get("cargo", "").strip()
                fecha = d.get("fecha", "").strip()
                partes.append(", ".join(p for p in (nombre, cargo, fecha) if p))
            return "; ".join(partes)
        return ", ".join(map(str, value))
    return str(value) if value is not None else ""

def _flatten_resuelvo(text: str) -> str:
    """Reemplaza saltos de línea por espacios simples."""
    # Unifico todos los saltos de línea en espacios y normalizo espacios dobles
    text = re.sub(r"\s*\n\s*", " ", text)
    return re.sub(r"\s{2,}", " ", text).strip()



def _format_datos_personales(raw):
    # Si ya viene como dict, seguimos como estaba
    if isinstance(raw, dict):
        dp = raw
    else:
        # 1) Si parece multipersona, me quedo con el primer bloque y lo parseo
        s = str(raw or "")
        if es_multipersona(s):
            bloques = segmentar_imputados(s)
            if bloques:
                dp = extraer_datos_personales(bloques[0])
            else:
                dp = extraer_datos_personales(s)
        else:
            # 2) Intento parsear el string como ficha de UNA persona
            dp = extraer_datos_personales(s)

        # Si no pude armar un dict creíble, devuelvo el string original
        if not isinstance(dp, dict):
            return s
        
    partes = []
    if dp.get("nombre"): partes.append(dp["nombre"])
    if dp.get("edad"):   partes.append(f"{dp['edad']} años")
    if dp.get("dni"):    partes.append(f"D.N.I. {dp['dni']}")
    if dp.get("alias"):  partes.append(f'alias “{dp["alias"]}”')
    if dp.get("nacionalidad"): partes.append(dp["nacionalidad"])
    if dp.get("estado_civil"): partes.append(dp["estado_civil"])
    if dp.get("ocupacion"):    partes.append(dp["ocupacion"])
    if dp.get("instruccion"):  partes.append(dp["instruccion"])
    if dp.get("domicilio"):    partes.append(f"Domicilio: {dp['domicilio']}")
    if dp.get("fecha_nacimiento"):
        partes.append(f"Nacido el {dp['fecha_nacimiento']}")
    if dp.get("lugar_nacimiento"):
        partes.append(f"en {dp['lugar_nacimiento']}")

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

    if dp.get("prontuario") or dp.get("prio") or dp.get("pront"):
        pront = dp.get("prontuario") or dp.get("prio") or dp.get("pront")
        partes.append(f"Prio. {pront}")

    return ", ".join(partes)


# ────────────────── Motor principal ─────────────────────────
def _bytes_a_tmp(data: bytes, suf: str) -> Path:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suf)
    tmp.write(data)
    tmp.flush()
    return Path(tmp.name)


def procesar_sentencia(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """Extrae texto del archivo, llama a GPT y devuelve el dict final."""
    # 1) Texto
    name = filename.lower()
    if name.endswith(".pdf"):
        tmp = _bytes_a_tmp(file_bytes, ".pdf")
        texto = extract_text(tmp)
        tmp.unlink(missing_ok=True)
    elif name.endswith(".docx"):
        tmp = _bytes_a_tmp(file_bytes, ".docx")
        texto = docx2txt.process(tmp)
        tmp.unlink(missing_ok=True)
    else:
        raise ValueError("Formato no soportado (PDF o DOCX)")

    texto = limpiar_pies(texto)
# Heurística local para datos personales (complementa a GPT)
    dp_auto = extraer_datos_personales(texto)

    # 2) GPT-4o mini en modo JSON
    client = _get_openai_client()
    kwargs = dict(
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
                    "y con “(SAC N° …)”, “(Expte. N° …)”, “(EE N° …)”, “(SAC …)”, "
                    "“(Expte. …)”, “(EE …)”, etc..  Nunca debe contener la palabra "
                    "Cámara, Juzgado ni Tribunal. "
                    "“tribunal” es el órgano que dictó la sentencia, empieza con "
                    "‘la Cámara’, ‘el Juzgado’, etc. "
                    "Si un dato falta, dejá la clave vacía."
                ),
            },
            {"role": "user", "content": texto[:120_000]},
        ],
    )
    if hasattr(client, "chat"):
        rsp = client.chat.completions.create(**kwargs)  # type: ignore
    else:
        rsp = client.ChatCompletion.create(**kwargs)  # type: ignore
    datos = json.loads(rsp.choices[0].message.content)

    imps = datos.get("imputados") or []


    def _dp_from_block(b: str) -> dict:
        d = extraer_datos_personales(b)
        return {
            "datos_personales": d,
            "dni": d.get("dni", ""),
            "nombre": d.get("nombre", ""),
        }

    # ✅ Siempre preferimos nuestra segmentación local: es más confiable
    bloques = segmentar_imputados(texto)
    if bloques:
        datos["imputados"] = [_dp_from_block(b) for b in bloques]
    else:
        # Sólo si no pudimos segmentar, usamos lo que vino del modelo
        imps = datos.get("imputados") or []
        if not imps:
            dp_auto = extraer_datos_personales(texto)
            if dp_auto:
                datos["imputados"] = [{"datos_personales": dp_auto, "dni": dp_auto.get("dni","")}]

    # Si no hay imputados, o el primero trae un string largo (mal), rehago desde el texto
    if not imps or any(isinstance(imp.get("datos_personales"), str) and es_multipersona(imp["datos_personales"]) for imp in imps):
        bloques = segmentar_imputados(texto)
        if bloques:
            datos["imputados"] = [_dp_from_block(b) for b in bloques]

    # 3) Ajustes post-API
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

    firmas = extraer_firmantes(texto)
    if firmas:
        datos.setdefault("generales", {})["firmantes"] = firmas

    carat_raw = g.get("caratula", "").strip()
    trib_raw = g.get("tribunal", "").strip()

    carat_ok = CARATULA_REGEX.match(carat_raw)
    trib_ok = TRIBUNAL_REGEX.match(trib_raw)

    if not carat_ok and (
        "cámara" in carat_raw.lower() or "juzgado" in carat_raw.lower()
    ):
        carat_raw, trib_raw = "", carat_raw

    if not trib_ok and trib_raw.lower().startswith("dr"):
        trib_raw = ""

    if not carat_ok:
        nueva_carat = extraer_caratula(texto)
        if nueva_carat:
            g["caratula"] = nueva_carat

    if not trib_ok:
        nuevo_trib = extraer_tribunal(texto)
        if nuevo_trib:
            g["tribunal"] = nuevo_trib

    datos["generales"] = g


    for imp in datos.get("imputados", []):
        dp = imp.get("datos_personales", {}) or {}
        if isinstance(dp, str):
            dni = extraer_dni(dp)
        else:
            dni = dp.get("dni") or extraer_dni(json.dumps(dp, ensure_ascii=False))
        imp.setdefault("dni", dni)



    # Completar/imputar datos personales
    imps = datos.setdefault("imputados", [])
    if not imps and dp_auto:
        imps.append({"datos_personales": dp_auto, "dni": dp_auto.get("dni", "")})
    elif imps and dp_auto:
        bruto = imps[0].get("datos_personales") or {}
        if isinstance(bruto, dict):
            for k, v in dp_auto.items():
                bruto.setdefault(k, v)
            imps[0]["datos_personales"] = bruto
            imps[0].setdefault("dni", bruto.get("dni", ""))

    return datos


# ────────────────── Alias público para la web ───────────────
def autocompletar(file_bytes: bytes, filename: str) -> None:
    """
    Procesa la sentencia y vuelca todos los campos
    en `st.session_state`.  La UI se actualizará sola.
    """
    datos = procesar_sentencia(file_bytes, filename)
    st.session_state.datos_autocompletados = datos

    # ----- GENERALES -----
    g = datos.get("generales", {})
    st.session_state.carat    = normalizar_caratula(_as_str(g.get("caratula")))
    st.session_state.trib     = _as_str(g.get("tribunal"))
    st.session_state.snum     = _as_str(g.get("sent_num"))
    st.session_state.sfecha   = _as_str(g.get("sent_fecha"))
    st.session_state.sres       = _flatten_resuelvo(_as_str(g.get("resuelvo")))
    st.session_state.sfirmeza   = _as_str(g.get("sent_firmeza") or "")  
    st.session_state.sfirmantes = _as_str(g.get("firmantes"))


    # ----- IMPUTADOS -----
    # limitamos al máximo soportado por la UI
    imps = datos.get("imputados", [])[:MAX_IMPUTADOS]
    st.session_state.n_imputados = max(1, len(imps))

    for i, imp in enumerate(imps):
        key = f"imp{i}"
        bruto = imp.get("datos_personales") or imp
        st.session_state[f"{key}_datos"] = _format_datos_personales(bruto)
        nom = _as_str(imp.get("nombre") or (bruto.get("nombre") if isinstance(bruto, dict) else ""))
        dni = _as_str(imp.get("dni") or (bruto.get("dni") if isinstance(bruto, dict) else ""))
        if not dni:
            dni = extraer_dni(str(bruto))
        st.session_state[f"{key}_nom"] = nom
        st.session_state[f"{key}_dni"] = dni

    # inicializo huecos si la UI tenía más imputados
    for j in range(len(imps), st.session_state.n_imputados):
        key = f"imp{j}"
        st.session_state.setdefault(f"{key}_nom", "")
        st.session_state.setdefault(f"{key}_dni", "")
        st.session_state.setdefault(f"{key}_datos", "")


# ────────────────── API pública ─────────────────────────────
__all__ = [
    "autocompletar",
    "autocompletar_caratula",
    "PENITENCIARIOS",
    "DEPOSITOS",
    "JUZ_NAVFYG",
    "TRIBUNALES",
    "MAX_IMPUTADOS",
]


if __name__ == "__main__":
    print("⚠️  core.py es una biblioteca; no se ejecuta directamente.")
