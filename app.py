# app.py  – versión resumida
import streamlit as st
import streamlit.components.v1 as components
from core import autocompletar   # ← función principal
from datetime import datetime
from helpers import dialog_link, strip_dialog_links
import re


def copy_to_clipboard(texto: str) -> None:
    """Copia ``texto`` al portapapeles.

    En versiones recientes de Streamlit el helper experimental
    ``st.experimental_copy`` fue removido.  Para mantener la
    funcionalidad se intenta utilizar :mod:`pyperclip` y, en caso de
    no estar disponible, se muestra el texto para copiarlo de forma
    manual.
    """
    try:
        import pyperclip  # type: ignore

        pyperclip.copy(texto)
        st.success("Texto copiado al portapapeles")
    except Exception:  # pragma: no cover - solo en entornos sin pyperclip
        st.code(texto)
        st.warning("No se pudo copiar automáticamente. Copie el texto manualmente.")

st.set_page_config(page_title="OSPRO – Oficios", layout="wide")


# --- helper de compatibilidad --------------------------------------
def _html_compat(content: str, *, height: int = 0, width: int = 0):
    """
    Llama a components.html() con los argumentos que soporte la versión
    instalada de Streamlit.  Intenta primero con 'sandbox'; si falla,
    re‑intenta sin él; si además falla con 'key', re‑intenta solo con los
    parámetros básicos.
    """
    # 1º: con 'sandbox' y 'key' (Streamlit ≥ 1.33 aprox.)
    try:
        return components.html(
            content,
            height=height,
            width=width,
            key="dlg_handler",
            sandbox="allow-scripts allow-same-origin",
        )
    except TypeError:
        pass

    # 2º: solo con 'sandbox' (Streamlit 1.30 – 1.32)
    try:
        return components.html(
            content,
            height=height,
            width=width,
            sandbox="allow-scripts allow-same-origin",
        )
    except TypeError:
        pass

    # 3º: firma mínima (Streamlit ≤ 1.29)
    return components.html(content, height=height, width=width)


# -------------------------------------------------------------------
js_code = """
<script>
/* Envía a Streamlit los cambios en elementos editables */
(function () {
  const parent = window.parent;
  const doc = parent.document;

  if (parent.__ospro_edit_handler__)
      doc.removeEventListener('focusout', parent.__ospro_edit_handler__, true);

  function handler(e) {
    const el = e.target.closest('.editable');
    if (!el) return;
    const val = el.innerText;
    Streamlit.setComponentValue({key: el.dataset.key, value: val});
  }

  doc.addEventListener('focusout', handler, true);
  parent.__ospro_edit_handler__ = handler;

  Streamlit.setComponentReady();
  Streamlit.setFrameHeight(0);
})();
</script>
"""

# ⬇️  aquí ya no fallará, sea cual sea tu versión de Streamlit
edit_event = _html_compat(js_code, height=0, width=0)

# ───────── helpers comunes ──────────────────────────────────────────
MESES_ES = [
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
]

# Mapeo de claves de elementos editables → keys del estado de sesión
FIELD_MAP = {
    "edit_caratula": "carat",
    "combo_tribunal": "trib",
    "edit_sent_num": "snum",
    "edit_sent_fecha": "sfecha",
    "edit_sent_firmeza": "sfirmeza",
    "edit_resuelvo": "sres",
    "edit_firmantes": "sfirmaza",
    "edit_consulado": "consulado",
    "edit_localidad": "loc",
}


def fecha_alineada(loc: str, fecha=None, punto=False):
    d = fecha or datetime.now()
    txt = f"{loc}, {d.day} de {MESES_ES[d.month-1]} de {d.year}"
    return txt + ("." if punto else "")

# ───────── estado de sesión ─────────────────────────────────────────
if "n_imputados" not in st.session_state:
    st.session_state.n_imputados = 1
if "datos_autocompletados" not in st.session_state:
    st.session_state.datos_autocompletados = {}

if isinstance(edit_event, dict):
    clave = edit_event.get("key")
    valor = edit_event.get("value")
    if isinstance(clave, str) and isinstance(valor, str):
        if clave.startswith("edit_imp") and clave.endswith("_datos"):
            idx = int(re.search(r"edit_imp(\d+)_datos", clave).group(1))
            st.session_state[f"imp{idx}_datos"] = valor
        else:
            estado = FIELD_MAP.get(clave)
            if estado:
                st.session_state[estado] = valor
        st.rerun()


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
    n = st.number_input(
        "Número de imputados",
        1,
        20,
        st.session_state.n_imputados,
        key="n_imp",
        on_change=lambda: st.rerun(),
    )
    st.session_state.n_imputados = n

    # ── cargar sentencia y autocompletar ──
    up = st.file_uploader("Cargar sentencia (PDF/DOCX)", type=["pdf","docx"])
    if st.button("Autocompletar"):
        if up is None:
            st.warning("Subí un archivo primero.")
        else:
            try:
                autocompletar(up.read(), up.name)
            except RuntimeError as exc:
                st.error(str(exc))
            else:
                st.success(
                    "Campos cargados. Revisá y editá donde sea necesario."
                )
                st.rerun()   # refrescamos la UI

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
    loc_a = dialog_link(loc, 'edit_localidad')
    fecha_txt = fecha_alineada(loc_a, punto=True)
    st.markdown(f"<p style='text-align:right'>{fecha_txt}</p>", unsafe_allow_html=True)

    car_a = f"<b>{dialog_link(caratula, 'edit_caratula')}</b>"
    trib_a = f"<b>{dialog_link(tribunal, 'combo_tribunal')}</b>"
    imp_a = dialog_link(st.session_state.get('imp0_datos',''), 'edit_imp0_datos')
    sent_n_a = dialog_link(sent_num, 'edit_sent_num')
    sent_f_a = dialog_link(sent_fecha, 'edit_sent_fecha')
    res_a = dialog_link(resuelvo, 'edit_resuelvo')
    firm_a = dialog_link(firmantes, 'edit_firmantes')
    sent_firmeza_a = dialog_link(sent_firmeza, 'edit_sent_firmeza')
    cuerpo = (
        "<b>Sr/a Director/a</b><br>"
        "<b>de la Dirección Nacional de Migraciones</b><br>"
        "<b>S/D:</b><br><br>"
        f"En los autos caratulados: {car_a}, que se tramitan "
        f"por ante {trib_a}, de la ciudad de Córdoba, Provincia de Córdoba, con la intervención de esta <b>Oficina de Servicios Procesales (OSPRO)</b>, se ha dispuesto librar a Ud. el presente oficio, "
        "a fin de informar lo resuelto por dicho Tribunal respecto de la persona "
        "cuyos datos personales se mencionan a continuación:<br><br>"
        f"{imp_a}.<br><br>"
        f"SENTENCIA N° {sent_n_a}, DE FECHA: {sent_f_a}. “Se Resuelve: {res_a}”. Fdo.: {firm_a}.<br><br>"
        f"Asimismo, se informa que la sentencia antes señalada quedó firme con fecha {sent_firmeza_a}.<br><br>"
        "Se adjuntan al presente oficio copia digital de la misma y del cómputo de pena respectivo.<br><br>"
    )
    saludo = "Sin otro particular, saludo a Ud. atentamente."
    st.markdown(cuerpo, unsafe_allow_html=True)
    st.markdown(f"<p style='text-align:center'>{saludo}</p>", unsafe_allow_html=True)

    if st.button("Copiar", key="copy_migr"):
        texto = strip_dialog_links(cuerpo + saludo).replace("<br>", "\n")
        copy_to_clipboard(texto)

# ---------- plantilla Consulado ----------
with tabs[1]:
    loc_a = dialog_link(loc, 'edit_localidad')
    fecha_txt = fecha_alineada(loc_a, punto=True)
    st.markdown(f"<p style='text-align:right'>{fecha_txt}</p>", unsafe_allow_html=True)
    car_a = f"<b>{dialog_link(caratula, 'edit_caratula')}</b>"
    trib_a = f"<b>{dialog_link(tribunal, 'combo_tribunal')}</b>"
    pais_a = dialog_link(consulado, 'edit_consulado')
    imp_a = dialog_link(st.session_state.get('imp0_datos',''), 'edit_imp0_datos')
    sent_n_a = dialog_link(sent_num, 'edit_sent_num')
    sent_f_a = dialog_link(sent_fecha, 'edit_sent_fecha')
    res_a = dialog_link(resuelvo, 'edit_resuelvo')
    firm_a = dialog_link(firmantes, 'edit_firmantes')
    sent_firmeza_a = dialog_link(sent_firmeza, 'edit_sent_firmeza')
    cuerpo = (
        "<b>Al Sr. Titular del Consulado </b><br>"
        f"<b>de {pais_a} </b><br>"
        "<b>S/D:</b><br><br>"
        f"En los autos caratulados: {car_a}, que se tramitan por ante {trib_a}, de la ciudad de Córdoba, Provincia de Córdoba, "
        "con la intervención de esta <b>Oficina de Servicios Procesales (OSPRO)</b>, se ha dispuesto librar el presente oficio, "
        "a fin de informar lo resuelto por dicho Tribunal respecto de la persona cuyos datos personales se mencionan a continuación:<br><br>"
        f"{imp_a}.<br><br>"
        f"SENTENCIA N° {sent_n_a}, DE FECHA: {sent_f_a}. “Se Resuelve: {res_a}.”. Fdo.: {firm_a}.<br><br>"
        f"Asimismo, se informa que la sentencia antes señalada quedó firme con fecha {sent_firmeza_a}.<br><br>"
        "Se adjuntan al presente oficio copia digital de la misma y del cómputo de pena respectivo.<br><br>"
    )
    saludo = "Sin otro particular, saludo a Ud. atentamente."
    st.markdown(cuerpo, unsafe_allow_html=True)
    st.markdown(f"<p style='text-align:center'>{saludo}</p>", unsafe_allow_html=True)
    if st.button("Copiar", key="copy_cons"):
        texto = strip_dialog_links(cuerpo + saludo).replace("<br>", "\n")
        copy_to_clipboard(texto)

# ---------- plantilla Juez Electoral ----------
with tabs[2]:
    loc_a = dialog_link(loc, 'edit_localidad')
    fecha_txt = fecha_alineada(loc_a, punto=True)
    st.markdown(f"<p style='text-align:right'>{fecha_txt}</p>", unsafe_allow_html=True)
    car_a = f"<b>{dialog_link(caratula, 'edit_caratula')}</b>"
    trib_a = f"<b>{dialog_link(tribunal, 'combo_tribunal')}</b>"
    imp_a = dialog_link(st.session_state.get('imp0_datos',''), 'edit_imp0_datos')
    sent_n_a = dialog_link(sent_num, 'edit_sent_num')
    sent_f_a = dialog_link(sent_fecha, 'edit_sent_fecha')
    res_a = dialog_link(resuelvo, 'edit_resuelvo')
    firm_a = dialog_link(firmantes, 'edit_firmantes')
    sent_firmeza_a = dialog_link(sent_firmeza, 'edit_sent_firmeza')
    cuerpo = (
        "<b>SR. JUEZ ELECTORAL:</b><br>"
        "<b>S………………./………………D</b><br>"
        "<b>-Av. Concepción Arenales esq. Wenceslao Paunero, Bº Rogelio Martínez, Córdoba.</b><br>"
        "<b>Tribunales Federales de Córdoba-</b><br><br>"
        f"En los autos caratulados: {car_a}, que se tramitan por ante {trib_a}, de la ciudad de Córdoba, Provincia de Córdoba, "
        "con la intervención de esta <b>Oficina de Servicios Procesales (OSPRO)</b>, se ha dispuesto librar a Ud. el presente oficio, "
        "a fin de informar lo resuelto por dicho Tribunal respecto de la persona cuyos datos personales se mencionan a continuación:<br><br>"
        f"{imp_a}.<br><br>"
        f"SENTENCIA N° {sent_n_a}, DE FECHA: {sent_f_a}. “Se Resuelve: {res_a}”. Fdo.: {firm_a}.<br><br>"
        f"Asimismo, se informa que la sentencia antes señalada quedó firme con fecha {sent_firmeza_a}.<br><br>"
        "Se adjuntan al presente oficio copia digital de la misma y del cómputo de pena respectivo.<br><br>"
    )
    saludo = "Sin otro particular, saludo a Ud. atentamente."
    st.markdown(cuerpo, unsafe_allow_html=True)
    st.markdown(f"<p style='text-align:center'>{saludo}</p>", unsafe_allow_html=True)
    if st.button("Copiar", key="copy_electoral"):
        texto = strip_dialog_links(cuerpo + saludo).replace("<br>", "\n")
        copy_to_clipboard(texto)


# -- parche global del antiguo manejo JS ------------------------------
# (reemplazado por la inyección al comienzo del archivo)

