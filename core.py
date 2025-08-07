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

# ── CARÁTULA ──────────────────────────────────────────────────────────
_PAT_CARAT_1 = re.compile(          # 1) bloque completo con comillas
    r'([^“\n]+?“[^”]+?”)\s*\(\s*(?:Expte\.\s*)?(?:SAC|Expte\.?)\s*(?:N°)?\s*([\d.]+)\s*\)',
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
        bloque, nro = m.groups()
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
    """Convierte un dict o texto con llaves en una línea legible."""
    if isinstance(raw, dict):
        dp = raw
    else:
        try:
            dp = ast.literal_eval(str(raw))
            if not isinstance(dp, dict):
                raise ValueError
        except Exception:
            return str(raw)

    partes = []
    if dp.get("nombre"):
        partes.append(dp["nombre"])
    if dp.get("dni"):
        partes.append(f"D.N.I. {dp['dni']}")
    if dp.get("nacionalidad"):
        partes.append(dp["nacionalidad"])
    if dp.get("edad"):
        partes.append(f"{dp['edad']} años")
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

    if dp.get("prontuario") or dp.get("prio") or dp.get("pront"):
        pront = dp.get("prontuario") or dp.get("prio") or dp.get("pront")
        partes.append(f"Pront. {pront}")
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
                    "Devolvé un JSON con la clave 'generales' "
                    "(caratula, tribunal, sent_num, sent_fecha, "
                    "resuelvo, firmantes) y la clave 'imputados' "
                    "(lista).  Cada imputado debe traer "
                    "`datos_personales` con nombre y dni al menos."
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

    # 3) Saneo rápido
    g = datos.setdefault("generales", {})
    g["resuelvo"] = extraer_resuelvo(texto) or g.get("resuelvo", "")
    carat = extraer_caratula(texto)
    if carat:
        g["caratula"] = carat
    else:
        g.setdefault("caratula", "")
    g.setdefault("tribunal", extraer_tribunal(texto))
    g.setdefault("firmantes", extraer_firmantes(texto))

    for imp in datos.get("imputados", []):
        dp = imp.get("datos_personales", {}) or {}
        if isinstance(dp, str):
            dni = extraer_dni(dp)
        else:
            dni = dp.get("dni") or extraer_dni(json.dumps(dp, ensure_ascii=False))
        imp.setdefault("dni", dni)

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
    st.session_state.sres     = _flatten_resuelvo(_as_str(g.get("resuelvo")))
    st.session_state.sfirmaza = _as_str(g.get("firmantes"))

    # ----- IMPUTADOS -----
    imps = datos.get("imputados", [])
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
__all__ = ["autocompletar"]


if __name__ == "__main__":
    print("⚠️  core.py es una biblioteca; no se ejecuta directamente.")
