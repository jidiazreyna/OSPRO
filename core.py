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

import docx2txt
import openai
import streamlit as st            # ← para volcar datos en la UI
from pdfminer.high_level import extract_text

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

# ────────────────── RegEx + helpers abreviados ──────────────
_FOOTER = re.compile(
    r"""\s*Expediente\s+SAC\s+\d+\s*-\s*P[áa]g\.\s*\d+\s*/\s*\d+\s*-\s*\n?
        N(?:[°º]|ro\.?|o\.)?\s*Res\.\s*\d+\s*""",
    re.I | re.X,
)
_RES_FIRMA = re.compile(r"Firmad[oa] digital", re.I)

_PAT_CARAT = re.compile(
    r"“([^”]+?)”\s*\(\s*(?:SAC|Expte\.?)\s*N°?\s*([\d.]+)\s*\)", re.I
)
_PAT_TRIB = re.compile(
    r"en\s+(?:esta|este|el|la)\s+([A-ZÁÉÍÓÚÑ][^,;.]+)", re.I
)

_DNI = re.compile(r"\b(?:\d{1,3}\.){2}\d{3}\b|\b\d{7,8}\b")
_FIRMAS = re.compile(
    r"Firmad[oa] digitalmente por:?[\s:]*(?P<nombre>[A-ZÁÉÍÓÚÑ ].+?)\s*,\s*"
    r"(?P<cargo>[A-ZÁÉÍÓÚÑ/ ].+)",
    re.I,
)


def limpiar_pies(txt: str) -> str:
    return re.sub(_FOOTER, " ", txt)


def extraer_resuelvo(txt: str) -> str:
    txt = limpiar_pies(txt)
    idx = max(txt.lower().rfind("resuelve"), txt.lower().rfind("resuelvo"))
    if idx == -1:
        return ""
    frag = txt[idx:]
    m = _RES_FIRMA.search(frag)
    if m:
        frag = frag[: m.start()]
    return re.sub(r"^resuelv[eo]\s*:?\s*", "", frag, flags=re.I).strip()


def extraer_caratula(txt: str) -> str:
    plano = re.sub(r"\s+", " ", txt)
    m = _PAT_CARAT.search(plano)
    if not m:
        return ""
    titulo, nro = m.groups()
    return f"“{titulo.strip()}” (SAC N° {nro})"


def extraer_tribunal(txt: str) -> str:
    plano = re.sub(r"\s+", " ", txt)
    m = _PAT_TRIB.search(plano)
    if not m:
        return ""
    nom = m.group(1).lower().capitalize()
    return nom if nom.startswith(("el ", "la ")) else "la " + nom


def extraer_dni(txt: str) -> str:
    m = _DNI.search(txt)
    return re.sub(r"\D", "", m.group(0)) if m else ""


def extraer_firmantes(txt: str) -> List[Dict[str, str]]:
    return [
        {"nombre": m.group("nombre").title().strip(),
         "cargo":  m.group("cargo").title().strip()}
        for m in _FIRMAS.finditer(txt)
    ]


def capitalizar_frase(txt: str) -> str:
    """Times-style: mayúscula inicial salvo preposiciones menores."""
    minus = {"de", "del", "la", "las", "y", "en", "el", "los"}
    palabras = txt.lower().split()
    for i, w in enumerate(palabras):
        if i == 0 or w not in minus:
            palabras[i] = w.capitalize()
    return " ".join(palabras)


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
    g.setdefault("caratula", extraer_caratula(texto))
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
    st.session_state.carat    = g.get("caratula", "")
    st.session_state.trib     = g.get("tribunal", "")
    st.session_state.snum     = g.get("sent_num", "")
    st.session_state.sfecha   = g.get("sent_fecha", "")
    st.session_state.sres     = g.get("resuelvo", "")
    st.session_state.sfirmaza = g.get("firmantes", [])

    # ----- IMPUTADOS -----
    imps = datos.get("imputados", [])
    st.session_state.n_imputados = max(1, len(imps))

    for i, imp in enumerate(imps):
        key = f"imp{i}"
        bruto = imp.get("datos_personales", imp)
        st.session_state[f"{key}_nom"]   = imp.get("nombre") or bruto.get("nombre", "")
        dni = imp.get("dni") or bruto.get("dni") or extraer_dni(str(bruto))
        st.session_state[f"{key}_dni"]   = dni
        st.session_state[f"{key}_datos"] = capitalizar_frase(str(bruto))

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
