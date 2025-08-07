# app.py  – versión revisada 2025-08-07
import re
import uuid
import html
import json
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components
import streamlit.components.v1 as components
import uuid, json, html as _html
from core import autocompletar          # lógica de autocompletado
from helpers import dialog_link, strip_dialog_links


# ────────── util: copiar al portapapeles ────────────────────────────
def copy_to_clipboard(texto: str) -> None:
    """
    Copia `texto al portapapeles.  
    1) Usa pyperclip si está disponible.  
    2) Si falla, inyecta JS que realiza el copiado en el mismo gesto
       de usuario.  Soporta todas las versiones de Streamlit.
    """
    # ——— 1) backend local
    try:
        import pyperclip  # type: ignore
        pyperclip.copy(texto)
        st.success("¡Texto copiado al portapapeles!")
        return
    except Exception:
        pass

    # ——— 2) fallback JS (con soporte a versiones viejas de Streamlit)
    uid = f"cpy_{uuid.uuid4().hex}"
    safe_txt = json.dumps(texto)   # escapa comillas y \n
    js_html = f"""
        <button id="{uid}" style="display:none"></button>
        <script>
          const btn = parent.document.getElementById("{uid}");
          if (btn) {{
            btn.addEventListener("click", async () => {{
              let exito = false;
              try {{
                await navigator.clipboard.writeText({safe_txt});
                exito = true;
              }} catch(e) {{
                console.error(e);
              }}
              Streamlit.setComponentValue(exito);
            }});
            btn.click();
          }}
        </script>
    """

    # Intento 1 (con 'key' → Streamlit ≥ 1.30)
    try:
        ok = components.html(js_html, height=0, key=uid)
    except TypeError:
        # Intento 2 (sin 'key' → Streamlit ≤ 1.29)
        ok = components.html(js_html, height=0)

    # Valor devuelto puede ser None en versiones viejas → chequeo suave
    if ok:
        st.success("¡Texto copiado al portapapeles!")
    else:
        st.info("Se disparó el copiado. Si no resultó, copiá manualmente.")


# ────────── config general de la página ─────────────────────────────
st.set_page_config(page_title="OSPRO – Oficios", layout="wide")


# ────────── helper de compatibilidad para components.html ───────────
def _html_compat(content: str, *, height: int = 0, width: int = 0):
    """
    Llama a components.html() con la firma que soporte tu versión
    de Streamlit (maneja cambios entre 1.29 y 1.33+).
    """
    try:  # ≥ 1.33
        return components.html(
            content,
            height=height,
            width=width,
            key="dlg_handler",
            sandbox="allow-scripts allow-same-origin",
        )
    except TypeError:
        pass

    try:  # 1.30 – 1.32
        return components.html(
            content,
            height=height,
            width=width,
            sandbox="allow-scripts allow-same-origin",
        )
    except TypeError:
        pass

    # ≤ 1.29
    return components.html(content, height=height, width=width)


# ────────── inyección global para spans editables ───────────────────
_js_edit_handler = """
<script>
(function () {
  const parent = window.parent, doc = parent.document;

  // Evitar duplicados al rerender
  if (parent.__ospro_edit_handler__) {
    doc.removeEventListener('input', parent.__ospro_edit_handler__, true);
    doc.removeEventListener('blur',  parent.__ospro_edit_handler__, true);
  }

  function handler(e) {
    const el = e.target.closest('.editable');
    if (!el) return;
    Streamlit.setComponentValue({ key: el.dataset.key, value: el.innerText });
  }

  doc.addEventListener('input', handler, true);
  doc.addEventListener('blur',  handler, true);
  parent.__ospro_edit_handler__ = handler;

  Streamlit.setComponentReady();
  Streamlit.setFrameHeight(0);
})();
</script>
"""
edit_event = _html_compat(_js_edit_handler, height=0, width=0)


# ────────── utilidades varias ───────────────────────────────────────
MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

def fecha_alineada(loc: str, fecha=None, punto=False):
    d = fecha or datetime.now()
    txt = f"{loc}, {d.day} de {MESES_ES[d.month-1]} de {d.year}"
    return txt + ("." if punto else "")


# ────────── estado inicial de sesión ────────────────────────────────
if "n_imputados" not in st.session_state:
    st.session_state.n_imputados = 1
if "datos_autocompletados" not in st.session_state:
    st.session_state.datos_autocompletados = {}

# sincronicemos spans editables → barra lateral
if isinstance(edit_event, dict):
    k, v = edit_event.get("key"), edit_event.get("value")
    if isinstance(k, str) and isinstance(v, str):
        st.session_state[k] = v
        st.rerun()


# ────────── procesamiento diferido del autocompletar ────────────────
if "pending_autocompletar" in st.session_state:
    file_bytes, filename = st.session_state.pop("pending_autocompletar")
    try:
        autocompletar(file_bytes, filename)
    except RuntimeError as exc:
        st.session_state["ac_error"] = str(exc)
    else:
        st.session_state["ac_success"] = True

def html_copy_button(label: str, text: str, *, key: str | None = None):
    """
    Renderiza un botón HTML+JS que copia text al portapapeles.
    Corre con todas las versiones de Streamlit (maneja la ausencia de 'key').
    """
    btn_id = key or f"btn_{uuid.uuid4().hex}"
    safe   = json.dumps(text)     # escapa comillas y saltos de línea

    html_snippet = f"""
        <button id="{btn_id}" style="margin:4px;">{_html.escape(label)}</button>
        <script>
          const btn = document.getElementById("{btn_id}");
          if (btn) {{
            btn.addEventListener("click", async () => {{
              try {{
                await navigator.clipboard.writeText({safe});
              }} catch (_) {{
                /* fallback viejo */
                const ta = Object.assign(document.createElement("textarea"), {{
                    value: {safe}, style: "position:fixed;opacity:0"
                }});
                document.body.appendChild(ta);
                ta.select(); document.execCommand("copy"); ta.remove();
              }}
              const old = btn.innerText;
              btn.innerText = "¡Copiado!";
              setTimeout(() => btn.innerText = old, 1500);
            }});
          }}
        </script>
    """

    # ≥ 1.30 acepta 'key'; ≤ 1.29 no.
    try:
        components.html(html_snippet, height=40, key=btn_id)
    except TypeError:
        components.html(html_snippet, height=40)
# ────────── barra lateral: datos generales ──────────────────────────
with st.sidebar:
    st.header("Datos generales")
    loc       = st.text_input("Localidad", value="Córdoba", key="loc")
    caratula  = st.text_input("Carátula", key="carat")
    tribunal  = st.text_input("Tribunal", key="trib")

    col1, col2 = st.columns(2)
    with col1:
        sent_num   = st.text_input("Sentencia Nº", key="snum")
    with col2:
        sent_fecha = st.text_input("Fecha sentencia", key="sfecha")

    sent_firmeza = st.text_input("Firmeza sentencia", key="sfirmeza")
    resuelvo     = st.text_area("Resuelvo", height=80, key="sres")
    firmantes    = st.text_input("Firmantes", key="sfirmaza")
    consulado    = st.text_input("Consulado", key="consulado")

    # Nº de imputados dinámico
    n = st.number_input(
        "Número de imputados", 1, 20, st.session_state.n_imputados,
        key="n_imp", on_change=st.rerun,
    )
    st.session_state.n_imputados = n

    # cargar sentencia y autocompletar
    up = st.file_uploader("Cargar sentencia (PDF/DOCX)", type=["pdf", "docx"])
    if st.button("Autocompletar"):
        if up is None:
            st.warning("Subí un archivo primero.")
        else:
            st.session_state.pending_autocompletar = (up.read(), up.name)
            st.rerun()

    err = st.session_state.pop("ac_error", None)
    if err:
        st.error(err)
    elif st.session_state.pop("ac_success", False):
        st.success("Campos cargados. Revisá y editá donde sea necesario.")

    # pestañas de imputados en sidebar
    for i in range(st.session_state.n_imputados):
        k = f"imp{i}"
        with st.expander(f"Imputado {i+1}", expanded=False):
            st.text_input("Nombre y apellido", key=f"{k}_nom")
            st.text_input("DNI",               key=f"{k}_dni")
            st.text_area ("Datos personales",  key=f"{k}_datos", height=80)
            st.text_input("Condena",           key=f"{k}_condena")
            # …más campos aquí…


# ────────── panel principal: tabs de oficios ────────────────────────
tabs = st.tabs([
    "Migraciones", "Consulado", "Juez Electoral", "Reg. Automotor",
    "Decomiso (Reg. Auto.)", "Decomiso c/Traslado", "Comisaría Traslado",
    "Decomiso s/Traslado", "Automotores Secuestrados", "RePAT",
])

# ——— TAB 0: Migraciones ————————————————————————————————
with tabs[0]:
    loc_a   = dialog_link(loc, 'loc')
    fecha   = fecha_alineada(loc_a, punto=True)
    st.markdown(f"<p style='text-align:right'>{fecha}</p>", unsafe_allow_html=True)

    car_a   = f"<b>{dialog_link(caratula, 'carat')}</b>"
    trib_a  = f"<b>{dialog_link(tribunal, 'trib')}</b>"
    imp_a   = dialog_link(st.session_state.get('imp0_datos', ''), 'imp0_datos')
    sent_n  = dialog_link(sent_num, 'snum')
    sent_f  = dialog_link(sent_fecha, 'sfecha')
    res_a   = dialog_link(resuelvo, 'sres')
    firm_a  = dialog_link(firmantes, 'sfirmaza')
    firmeza = dialog_link(sent_firmeza, 'sfirmeza')

    cuerpo = (
        "<b>Sr/a Director/a</b><br>"
        "<b>de la Dirección Nacional de Migraciones</b><br>"
        "<b>S/D:</b><br><br>"
        f"En los autos caratulados: {car_a}, que se tramitan "
        f"por ante {trib_a}, de la ciudad de Córdoba, Provincia de Córdoba, "
        "con la intervención de esta <b>Oficina de Servicios Procesales (OSPRO)</b>, "
        "se ha dispuesto librar a Ud. el presente oficio, a fin de informar lo resuelto "
        "por dicho Tribunal respecto de la persona cuyos datos personales se mencionan "
        "a continuación:<br><br>"
        f"{imp_a}.<br><br>"
        f"SENTENCIA N° {sent_n}, DE FECHA: {sent_f}. “Se Resuelve: {res_a}”. "
        f"Fdo.: {firm_a}.<br><br>"
        f"Asimismo, se informa que la sentencia antes señalada quedó firme con "
        f"fecha {firmeza}.<br><br>"
        "Se adjuntan al presente oficio copia digital de la misma y del cómputo "
        "de pena respectivo.<br><br>"
    )
    saludo = "Sin otro particular, saludo a Ud. atentamente."
    st.markdown(cuerpo, unsafe_allow_html=True)
    st.markdown(f"<p style='text-align:center'>{saludo}</p>", unsafe_allow_html=True)

    texto = re.sub(r"<br\s*/?>", "\n", strip_dialog_links(cuerpo + saludo))
    html_copy_button("Copiar", texto, key="copy_migr")

# ——— TAB 1: Consulado ————————————————————————————————
with tabs[1]:
    loc_a   = dialog_link(loc, 'loc')
    fecha   = fecha_alineada(loc_a, punto=True)
    st.markdown(f"<p style='text-align:right'>{fecha}</p>", unsafe_allow_html=True)

    car_a   = f"<b>{dialog_link(caratula, 'carat')}</b>"
    trib_a  = f"<b>{dialog_link(tribunal, 'trib')}</b>"
    pais_a  = dialog_link(consulado, 'consulado')
    imp_a   = dialog_link(st.session_state.get('imp0_datos',''), 'imp0_datos')
    sent_n  = dialog_link(sent_num, 'snum')
    sent_f  = dialog_link(sent_fecha, 'sfecha')
    res_a   = dialog_link(resuelvo, 'sres')
    firm_a  = dialog_link(firmantes, 'sfirmaza')
    firmeza = dialog_link(sent_firmeza, 'sfirmeza')

    cuerpo = (
        "<b>Al Sr. Titular del Consulado </b><br>"
        f"<b>de {pais_a} </b><br>"
        "<b>S/D:</b><br><br>"
        f"En los autos caratulados: {car_a}, que se tramitan por ante {trib_a}, "
        "de la ciudad de Córdoba, Provincia de Córdoba, con la intervención de "
        "esta <b>Oficina de Servicios Procesales (OSPRO)</b>, se ha dispuesto "
        "librar el presente oficio, a fin de informar lo resuelto por dicho "
        "Tribunal respecto de la persona cuyos datos personales se mencionan "
        "a continuación:<br><br>"
        f"{imp_a}.<br><br>"
        f"SENTENCIA N° {sent_n}, DE FECHA: {sent_f}. “Se Resuelve: {res_a}.” "
        f"Fdo.: {firm_a}.<br><br>"
        f"Asimismo, se informa que la sentencia antes señalada quedó firme con "
        f"fecha {firmeza}.<br><br>"
        "Se adjuntan al presente oficio copia digital de la misma y del cómputo "
        "de pena respectivo.<br><br>"
    )
    saludo = "Sin otro particular, saludo a Ud. atentamente."
    st.markdown(cuerpo, unsafe_allow_html=True)
    st.markdown(f"<p style='text-align:center'>{saludo}</p>", unsafe_allow_html=True)

    texto = re.sub(r"<br\s*/?>", "\n", strip_dialog_links(cuerpo + saludo))
    html_copy_button("Copiar", texto, key="copy_cons")

# ——— TAB 2: Juez Electoral ——————————————————————————————
with tabs[2]:
    loc_a   = dialog_link(loc, 'loc')
    fecha   = fecha_alineada(loc_a, punto=True)
    st.markdown(f"<p style='text-align:right'>{fecha}</p>", unsafe_allow_html=True)

    car_a   = f"<b>{dialog_link(caratula, 'carat')}</b>"
    trib_a  = f"<b>{dialog_link(tribunal, 'trib')}</b>"
    imp_a   = dialog_link(st.session_state.get('imp0_datos',''), 'imp0_datos')
    sent_n  = dialog_link(sent_num, 'snum')
    sent_f  = dialog_link(sent_fecha, 'sfecha')
    res_a   = dialog_link(resuelvo, 'sres')
    firm_a  = dialog_link(firmantes, 'sfirmaza')
    firmeza = dialog_link(sent_firmeza, 'sfirmeza')

    cuerpo = (
        "<b>SR. JUEZ ELECTORAL:</b><br>"
        "<b>S………………./………………D</b><br>"
        "<b>-Av. Concepción Arenales esq. Wenceslao Paunero, Bº Rogelio Martínez, Córdoba.</b><br>"
        "<b>Tribunales Federales de Córdoba-</b><br><br>"
        f"En los autos caratulados: {car_a}, que se tramitan por ante {trib_a}, "
        "de la ciudad de Córdoba, Provincia de Córdoba, con la intervención "
        "de esta <b>Oficina de Servicios Procesales (OSPRO)</b>, se ha dispuesto librar "
        "a Ud. el presente oficio, a fin de informar lo resuelto por dicho Tribunal "
        "respecto de la persona cuyos datos personales se mencionan a continuación:"
        "<br><br>"
        f"{imp_a}.<br><br>"
        f"SENTENCIA N° {sent_n}, DE FECHA: {sent_f}. “Se Resuelve: {res_a}”. "
        f"Fdo.: {firm_a}.<br><br>"
        f"Asimismo, se informa que la sentencia antes señalada quedó firme con "
        f"fecha {firmeza}.<br><br>"
        "Se adjuntan al presente oficio copia digital de la misma y del cómputo "
        "de pena respectivo.<br><br>"
    )
    saludo = "Sin otro particular, saludo a Ud. atentamente."
    st.markdown(cuerpo, unsafe_allow_html=True)
    st.markdown(f"<p style='text-align:center'>{saludo}</p>", unsafe_allow_html=True)

    texto = re.sub(r"<br\s*/?>", "\n", strip_dialog_links(cuerpo + saludo))
    html_copy_button("Copiar", texto, key="copy_electoral")