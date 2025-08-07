# app.py  – versión resumida
import re
import streamlit as st
import streamlit.components.v1 as components
from core import autocompletar   # ← función principal
from datetime import datetime
from helpers import dialog_link, strip_dialog_links
import json

def copy_to_clipboard(texto: str) -> None:
    """Copia ``texto`` al portapapeles.

    En versiones recientes de Streamlit el helper experimental
    ``st.experimental_copy`` fue removido.  Para mantener la
    funcionalidad se intenta utilizar :mod:`pyperclip` y, en caso de
    no estar disponible, se recurre a la API del navegador.
    """
    try:
        import pyperclip  # type: ignore

        pyperclip.copy(texto)
        st.success("Texto copiado al portapapeles")
        return
    except Exception:  # pragma: no cover - solo en entornos sin pyperclip
        pass

    try:
        ok = components.html(
            f"""
            <script>
            (async () => {{
              let exito = false;
              if (navigator.clipboard && navigator.clipboard.writeText) {{
                try {{
                  await navigator.clipboard.writeText({json.dumps(texto)});
                  exito = true;
                }} catch (err) {{
                  console.error('Error al copiar:', err);
                }}
              }}
              if (!exito) {{
                const textarea = document.createElement('textarea');
                textarea.value = {json.dumps(texto)};
                document.body.appendChild(textarea);
                textarea.select();
                try {{
                  exito = document.execCommand('copy');
                }} catch (err) {{
                  console.error('Error al copiar:', err);
                }}
                document.body.removeChild(textarea);
              }}
              Streamlit.setComponentValue(exito);
            }})();
            </script>
            """,
            height=0,
            key="clipboard",
        )
        if ok:
            st.success("Texto copiado al portapapeles")
        else:
            st.warning("No se pudo copiar automáticamente. Copie el texto manualmente.")
    except Exception:  # pragma: no cover - sin soporte de portapapeles
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
(function () {
  const parent = window.parent;
  const doc    = parent.document;

  // Borrá cualquier handler previo para no acumularlos al rerender
  if (parent.__ospro_edit_handler__) {
    doc.removeEventListener('input', parent.__ospro_edit_handler__, true);
    doc.removeEventListener('blur',  parent.__ospro_edit_handler__, true);
  }

  function handler(e) {
    const el = e.target.closest('.editable');
    if (!el) return;
    Streamlit.setComponentValue({
      key:   el.dataset.key,   // misma key que usan tus text_input
      value: el.innerText      // lo editado
    });
  }

  // ① se dispara en cada tecla
  doc.addEventListener('input', handler, true);
  // ② de yapa, cuando el usuario sale del span
  doc.addEventListener('blur',  handler, true);

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

# En la interfaz principal los elementos editables usan como ``data-key``
# la misma clave empleada en ``st.session_state``.  De esta manera, cuando
# el usuario modifica el texto desde el anchor, el valor correspondiente en
# la barra lateral se actualiza automáticamente.


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
        st.session_state[clave] = valor
        st.rerun()

# ───── proceso diferido de autocompletado ───────────────────────────
if "pending_autocompletar" in st.session_state:
    file_bytes, filename = st.session_state.pop("pending_autocompletar")
    try:
        autocompletar(file_bytes, filename)
    except RuntimeError as exc:
        st.session_state["ac_error"] = str(exc)
    else:
        st.session_state["ac_success"] = True


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
            st.session_state.pending_autocompletar = (up.read(), up.name)
            st.rerun()

    err = st.session_state.pop("ac_error", None)
    if err:
        st.error(err)
    elif st.session_state.pop("ac_success", False):
        st.success(
            "Campos cargados. Revisá y editá donde sea necesario."
        )

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
    loc_a = dialog_link(loc, 'loc')
    fecha_txt = fecha_alineada(loc_a, punto=True)
    st.markdown(f"<p style='text-align:right'>{fecha_txt}</p>", unsafe_allow_html=True)

    car_a = f"<b>{dialog_link(caratula, 'carat')}</b>"
    trib_a = f"<b>{dialog_link(tribunal, 'trib')}</b>"
    imp_a = dialog_link(st.session_state.get('imp0_datos',''), 'imp0_datos')
    sent_n_a = dialog_link(sent_num, 'snum')
    sent_f_a = dialog_link(sent_fecha, 'sfecha')
    res_a = dialog_link(resuelvo, 'sres')
    firm_a = dialog_link(firmantes, 'sfirmaza')
    sent_firmeza_a = dialog_link(sent_firmeza, 'sfirmeza')
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
        texto = re.sub(r"<br\s*/?>", "\n", strip_dialog_links(cuerpo + saludo))
        copy_to_clipboard(texto)

# ---------- plantilla Consulado ----------
with tabs[1]:
    loc_a = dialog_link(loc, 'loc')
    fecha_txt = fecha_alineada(loc_a, punto=True)
    st.markdown(f"<p style='text-align:right'>{fecha_txt}</p>", unsafe_allow_html=True)
    car_a = f"<b>{dialog_link(caratula, 'carat')}</b>"
    trib_a = f"<b>{dialog_link(tribunal, 'trib')}</b>"
    pais_a = dialog_link(consulado, 'consulado')
    imp_a = dialog_link(st.session_state.get('imp0_datos',''), 'imp0_datos')
    sent_n_a = dialog_link(sent_num, 'snum')
    sent_f_a = dialog_link(sent_fecha, 'sfecha')
    res_a = dialog_link(resuelvo, 'sres')
    firm_a = dialog_link(firmantes, 'sfirmaza')
    sent_firmeza_a = dialog_link(sent_firmeza, 'sfirmeza')
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
        texto = re.sub(r"<br\s*/?>", "\n", strip_dialog_links(cuerpo + saludo))
        copy_to_clipboard(texto)

# ---------- plantilla Juez Electoral ----------
with tabs[2]:
    loc_a = dialog_link(loc, 'loc')
    fecha_txt = fecha_alineada(loc_a, punto=True)
    st.markdown(f"<p style='text-align:right'>{fecha_txt}</p>", unsafe_allow_html=True)
    car_a = f"<b>{dialog_link(caratula, 'carat')}</b>"
    trib_a = f"<b>{dialog_link(tribunal, 'trib')}</b>"
    imp_a = dialog_link(st.session_state.get('imp0_datos',''), 'imp0_datos')
    sent_n_a = dialog_link(sent_num, 'snum')
    sent_f_a = dialog_link(sent_fecha, 'sfecha')
    res_a = dialog_link(resuelvo, 'sres')
    firm_a = dialog_link(firmantes, 'sfirmaza')
    sent_firmeza_a = dialog_link(sent_firmeza, 'sfirmeza')
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
        texto = re.sub(r"<br\s*/?>", "\n", strip_dialog_links(cuerpo + saludo))
        copy_to_clipboard(texto)


# -- parche global del antiguo manejo JS ------------------------------
# (reemplazado por la inyección al comienzo del archivo)

