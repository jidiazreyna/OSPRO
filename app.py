# app.py  – versión resumida
import streamlit as st
from core import autocompletar, generar_oficios   # ← mismas funciones
from datetime import datetime
from helpers import anchor, strip_anchors

st.set_page_config(page_title="OSPRO – Oficios", layout="wide")
st.divider()
st.subheader("Descarga")

if st.button("Generar DOCX con todos los oficios"):
    payload = {
        "generales": {
            "caratula":  st.session_state.carat,
            "tribunal":  st.session_state.trib,
            "sent_num":  st.session_state.snum,
            "sent_fecha":st.session_state.sfecha,
            "resuelvo":  st.session_state.sres,
            "firmantes": st.session_state.sfirmaza,
        },
        "imputados": [
            {
                "datos_personales": st.session_state.get(f"imp{i}_datos",""),
                "nombre":           st.session_state.get(f"imp{i}_nom",""),
                "dni":              st.session_state.get(f"imp{i}_dni",""),
            }
            for i in range(st.session_state.n_imputados)
        ],
    }
    docx = generar_oficios(payload)
    st.download_button("Descargar oficios.docx", docx,
                       file_name="oficios.docx",
                       mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

# ───────── helpers comunes ──────────────────────────────────────────
MESES_ES = ["enero","febrero","marzo","abril","mayo","junio",
            "julio","agosto","septiembre","octubre","noviembre","diciembre"]

def fecha_alineada(loc: str, fecha=None, punto=False):
    d = fecha or datetime.now()
    txt = f"{loc}, {d.day} de {MESES_ES[d.month-1]} de {d.year}"
    return txt + ("." if punto else "")

# ───────── estado de sesión ─────────────────────────────────────────
if "n_imputados" not in st.session_state: st.session_state.n_imputados = 1
if "datos_autocompletados" not in st.session_state: st.session_state.datos_autocompletados = {}

# ───────── barra lateral (datos generales) ──────────────────────────
with st.sidebar:
    st.header("Datos generales")
    loc       = st.text_input("Localidad",  value="Córdoba", key="loc")
    caratula  = st.text_input("Carátula",   key="carat")
    tribunal  = st.text_input("Tribunal",   key="trib")
    col1, col2 = st.columns(2)
    with col1:
        sent_num = st.text_input("Sentencia Nº", key="snum")
    with col2:
        sent_fecha = st.text_input("Fecha sentencia", key="sfecha")
    sent_firmeza = st.text_input("Firmeza sentencia", key="sfirmeza")
    resuelvo = st.text_area("Resuelvo", height=80, key="sres")
    firmantes = st.text_input("Firmantes", key="sfirmaza")
    consulado = st.text_input("Consulado", key="consulado")

    # ── número de imputados dinamico ──
    n = st.number_input("Número de imputados", 1, 20, st.session_state.n_imputados,
                        key="n_imp", on_change=lambda: st.experimental_rerun())
    st.session_state.n_imputados = n

    # ── cargar sentencia y autocompletar ──
    up = st.file_uploader("Cargar sentencia (PDF/DOCX)", type=["pdf","docx"])
    if st.button("Autocompletar"):
        if up is None:
            st.warning("Subí un archivo primero.")
        else:
            autocompletar(up.read(), up.name)
            st.success("Campos cargados. Revisá y editá donde sea necesario.")
            st.experimental_rerun()   # refrescamos la UI

# ───────── pestañas de imputados (en la sidebar) ────────────────────
    for i in range(st.session_state.n_imputados):
        imp_key = f"imp{i}"
        with st.expander(f"Imputado {i+1}", expanded=False):
            nombre = st.text_input("Nombre y apellido", key=f"{imp_key}_nom")
            dni    = st.text_input("DNI", key=f"{imp_key}_dni")
            datos  = st.text_area("Datos personales", key=f"{imp_key}_datos", height=80)
            condena= st.text_input("Condena", key=f"{imp_key}_condena")
            # …añadí todos los demás campos que necesites …

# ───────── panel principal con tabs de oficios ──────────────────────
tabs = st.tabs([
    "Migraciones","Consulado","Juez Electoral","Reg. Automotor",
    "Decomiso (Reg. Auto.)","Decomiso c/Traslado","Comisaría Traslado",
    "Decomiso s/Traslado","Automotores Secuestrados","RePAT",
    # …agregá las demás…
])

# ----------  ejemplo: plantilla Migraciones  ----------
with tabs[0]:
    # recomponemos los textos cada vez que alguien cambia algo
    fecha_txt = fecha_alineada(loc, punto=True)
    st.markdown(f"<p style='text-align:right'>{fecha_txt}</p>", unsafe_allow_html=True)

    # bloque cuerpo (acá resumido)
    cuerpo = (
        "<b>Sr/a Director/a de la Dirección Nacional de Migraciones</b><br>"
        f"En los autos caratulados: <b>{anchor(caratula, 'caratula')}</b>, "
        f"que se tramitan por ante <b>{anchor(tribunal, 'tribunal')}</b>, se ha dispuesto…"
    )
    st.markdown(cuerpo, unsafe_allow_html=True)

    # botón copiar (texto plano)
    if st.button("Copiar", key="copy_migr"):
        st.experimental_copy(strip_anchors(cuerpo).replace("<br>", "\n"))

# ---------- plantilla Consulado ----------
with tabs[1]:
    fecha_txt = fecha_alineada(loc, punto=True)
    st.markdown(f"<p style='text-align:right'>{fecha_txt}</p>", unsafe_allow_html=True)
    cuerpo = (
        "<b>Al Sr. Titular del Consulado</b><br>"
        f"<b>de {anchor(consulado, 'consulado')}</b><br>"
        "<b>S/D:</b><br><br>"
        f"En los autos caratulados: <b>{anchor(caratula, 'caratula')}</b>, que se tramitan por ante "
        f"<b>{anchor(tribunal, 'tribunal')}</b>, se ha dispuesto informar respecto de "
        f"{anchor(st.session_state.get('imp0_datos',''), 'imp0_datos')}.<br><br>"
        f"Sentencia Nº {anchor(sent_num, 'snum')} de fecha {anchor(sent_fecha, 'sfecha')} - "
        f"Resuelve: {anchor(resuelvo, 'sres')} - Firmantes: {anchor(firmantes, 'sfirmaza')}.<br><br>"
        f"La sentencia quedó firme el {anchor(sent_firmeza, 'sfirmeza')}.")
    st.markdown(cuerpo, unsafe_allow_html=True)
    if st.button("Copiar", key="copy_cons"):
        st.experimental_copy(strip_anchors(cuerpo).replace("<br>", "\n"))

# ---------- plantilla Juez Electoral ----------
with tabs[2]:
    fecha_txt = fecha_alineada(loc, punto=True)
    st.markdown(f"<p style='text-align:right'>{fecha_txt}</p>", unsafe_allow_html=True)
    cuerpo = (
        "<b>Sr. Juez Electoral</b><br>"
        "<b>S................../..................D</b><br><br>"
        f"En los autos caratulados: <b>{anchor(caratula, 'caratula')}</b>, que se tramitan por ante "
        f"<b>{anchor(tribunal, 'tribunal')}</b>, se informa sobre "
        f"{anchor(st.session_state.get('imp0_datos',''), 'imp0_datos')}.<br><br>"
        f"Sentencia Nº {anchor(sent_num, 'snum')} de fecha {anchor(sent_fecha, 'sfecha')}. "
        f"Resuelve: {anchor(resuelvo, 'sres')}. Fdo.: {anchor(firmantes, 'sfirmaza')}.<br><br>"
        f"La sentencia quedó firme el {anchor(sent_firmeza, 'sfirmeza')}.")
    st.markdown(cuerpo, unsafe_allow_html=True)
    if st.button("Copiar", key="copy_electoral"):
        st.experimental_copy(strip_anchors(cuerpo).replace("<br>", "\n"))
