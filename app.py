# app.py
import re
import uuid
import html
import json
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components
from core import autocompletar, autocompletar_caratula  # lógica de autocompletado
from helpers import dialog_link, strip_dialog_links, create_clipboard_html

# ────────── util: copiar al portapapeles ────────────────────────────
def copy_to_clipboard(texto: str) -> None:
    """
    Copia texto al portapapeles.  
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

# Inyectar CSS global para los spans editables
st.markdown("""
<style>
span.editable {
    color: #0068c9 !important;
    text-decoration: none !important;
    cursor: pointer !important;
}
</style>
""", unsafe_allow_html=True)

LINE_STYLE = "margin:0;line-height:150%;mso-line-height-alt:150%;"
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
  if (parent.__ospro_handlers__) {
    const {span, sidebar, keydown, beforeinput, cleanup} = parent.__ospro_handlers__;
    doc.removeEventListener('input', span, true);
    doc.removeEventListener('blur',  span, true);
    doc.removeEventListener('input', sidebar, true);
    if (keydown)     doc.removeEventListener('keydown', keydown, true);
    if (beforeinput) doc.removeEventListener('beforeinput', beforeinput, true);
  }

  function placeCaretAfter(node) {
    try {
      const r = doc.createRange();
      r.setStartAfter(node); r.collapse(true);
      const sel = doc.getSelection(); sel.removeAllRanges(); sel.addRange(r);
    } catch(_) {}
  }

  function isRemovableGap(n){
    if (!n) return false;
    if (n.nodeType === 3) return !n.nodeValue || /^\\s+$/.test(n.nodeValue); // texto vacío
    if (n.nodeName === 'BR') return true;
    if (n.nodeType === 1) {
      if (n.matches('div,p')) {
        const html = n.innerHTML.replace(/<br\\s*\\/?>/gi,'').trim();
        return html === '';
      }
    }
    return false;
  }

  function cleanupAfter(el){
    // Borra saltos/espacios vacíos inmediatamente DESPUÉS del anchor
    let n = el.nextSibling;
    while (isRemovableGap(n)) {
      const toRemove = n; n = n.nextSibling;
      toRemove.parentNode && toRemove.parentNode.removeChild(toRemove);
    }
  }

  function keydownHandler(e) {
    const el = e.target && e.target.closest && e.target.closest('.editable');
    if (!el) return;
    const single = el.dataset.singleline === '1';

    // Bloquear Enter dentro del anchor: no insertamos nada
    if (single && e.key === 'Enter') {
      e.preventDefault();
      const key = el.dataset.key, value = el.innerText;
      const campo = doc.getElementById(key);
      if (campo) { campo.dataset.origin='span'; if (campo.value !== value) campo.value = value; campo.dataset.origin=''; }
      try { Streamlit.setComponentValue({ key, value, origin: 'span' }); } catch(_){}
      el.blur();
      cleanupAfter(el);
      placeCaretAfter(el);
    }
  }

  function beforeInputHandler(e){
    const el = e.target && e.target.closest && e.target.closest('.editable');
    if (!el) return;
    const single = el.dataset.singleline === '1';
    // En navegadores modernos esto captura "insertParagraph"/"insertLineBreak"
    if (single && (e.inputType === 'insertParagraph' || e.inputType === 'insertLineBreak')) {
      e.preventDefault();
      el.blur();
      cleanupAfter(el);
      placeCaretAfter(el);
    }
  }

  function spanHandler(e) {
    const el = e.target && e.target.closest && e.target.closest('.editable');
    if (!el || el.dataset.origin === 'sidebar') return;
    const key = el.dataset.key, value = el.innerText;
    const campo = doc.getElementById(key);
    if (campo) { campo.dataset.origin='span'; if (campo.value !== value) campo.value=value; campo.dataset.origin=''; }
    try { Streamlit.setComponentValue({ key, value, origin: 'span' }); } catch (_){}
  }

  function sidebarHandler(e) {
    const el = e.target && e.target.closest && e.target.closest('input, textarea');
    if (!el) return;
    const key = el.id; if (!key || el.dataset.origin === 'span') return;
    const value = el.value;
    const spans = doc.querySelectorAll(`.editable[data-key="${key}"]`);
    spans.forEach(sp => { if (sp.innerText !== value) { sp.dataset.origin='sidebar'; sp.innerText=value; sp.dataset.origin=''; } });
  }

  // Limpieza inicial por si ya quedaron saltos fantasma de antes
  doc.querySelectorAll('.editable').forEach(cleanupAfter);

  doc.addEventListener('beforeinput', beforeInputHandler, true);
  doc.addEventListener('keydown',     keydownHandler,     true);
  doc.addEventListener('input',       spanHandler,        true);
  doc.addEventListener('blur',        spanHandler,        true);
  doc.addEventListener('input',       sidebarHandler,     true);

  parent.__ospro_handlers__ = {
    span: spanHandler, sidebar: sidebarHandler,
    keydown: keydownHandler, beforeinput: beforeInputHandler,
    cleanup: cleanupAfter
  };

  Streamlit.setComponentReady();
  Streamlit.setFrameHeight(0);
})();
</script>
"""


edit_event = _html_compat(_js_edit_handler, height=0, width=0)  # 👈 iny. bidireccional


# ────────── utilidades varias ───────────────────────────────────────
MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

def fecha_alineada(loc: str, fecha=None, punto=False):
    d = fecha or datetime.now()
    txt = f"{loc}, {d.day} de {MESES_ES[d.month-1]} de {d.year}"
    return txt + ("." if punto else "")

# ────────── callback: normaliza la carátula después de editar ───────
def _normalizar_caratula():
    raw  = st.session_state.carat
    auto = autocompletar_caratula(raw)
    if auto != raw:
        st.session_state.carat = auto
        st.experimental_rerun()      # fuerza un ciclo nuevo y seguro
# ────────── estado inicial de sesión ────────────────────────────────
if "n_imputados" not in st.session_state:
    st.session_state.n_imputados = 1
if "datos_autocompletados" not in st.session_state:
    st.session_state.datos_autocompletados = {}
st.session_state.setdefault("carat", "")
# sincronicemos spans editables → barra lateral
if isinstance(edit_event, dict):
    k, v = edit_event.get("key"), edit_event.get("value")
    if isinstance(k, str) and isinstance(v, str):
        st.session_state[k] = v
        # No hacer rerun aquí, los cambios se reflejarán automáticamente


# ────────── procesamiento diferido del autocompletar ────────────────
if "pending_autocompletar" in st.session_state:
    file_bytes, filename = st.session_state.pop("pending_autocompletar")
    try:
        autocompletar(file_bytes, filename)
    except RuntimeError as exc:
        st.session_state["ac_error"] = str(exc)
    else:
        st.session_state["ac_success"] = True

def html_copy_button(label: str, html_fragment: str, *, key: str | None = None):
    btn_id    = key or f"btn_{uuid.uuid4().hex}"
    raw_html  = html_fragment                         # ⇦ sin cabeceras
    packaged  = create_clipboard_html(html_fragment)  # ⇦ por si hiciera falta
    js = f"""
      <button id="{btn_id}" style="margin:4px;">{html.escape(label)}</button>
      <script>
        const btn = document.getElementById("{btn_id}");
        if (btn) {{
          btn.addEventListener("click", async () => {{
            try {{
              /* API moderna */
              const blob = new Blob([{json.dumps(raw_html)}], {{type:"text/html"}});
              await navigator.clipboard.write([new ClipboardItem({{"text/html": blob}})]);
            }} catch (_) {{
              /* Fallback execCommand: copiar nodo con HTML real */
              const div = Object.assign(document.createElement("div"), {{
                innerHTML: {json.dumps(raw_html)}, style:"position:fixed;left:-9999px"
              }});
              document.body.appendChild(div);
              const range = document.createRange();
              range.selectNodeContents(div);
              const sel = window.getSelection();
              sel.removeAllRanges(); sel.addRange(range);
              document.execCommand("copy");
              sel.removeAllRanges(); div.remove();
            }}
            const old = btn.innerText;
            btn.innerText = "¡Copiado!";
            setTimeout(() => btn.innerText = old, 1400);
          }});
        }}
      </script>
    """
    try:
        components.html(js, height=40, key=btn_id)  # Streamlit ≥ 1.30
    except TypeError:
        components.html(js, height=40)              # Streamlit ≤ 1.29

# ────────── barra lateral: datos generales ──────────────────────────
with st.sidebar:
    st.header("Datos generales")
    loc       = st.text_input("Localidad", value="Córdoba", key="loc")
    st.text_input(
        "Carátula",
        key="carat",
        on_change=_normalizar_caratula,   # ← NUEVO
    )
    caratula = st.session_state.carat     # ← reemplaza a tu caratula_raw

    tribunal  = st.text_input("Tribunal", key="trib")

    col1, col2 = st.columns(2)
    with col1:
        sent_num   = st.text_input("Sentencia Nº", key="snum")
    with col2:
        sent_fecha = st.text_input("Fecha sentencia", key="sfecha")

    sent_firmeza = st.text_input("Firmeza sentencia", key="sfirmeza")
    resuelvo     = st.text_area("Resuelvo", height=80, key="sres")
    firmantes    = st.text_input("Firmantes", key="sfirmantes")  # Corregido key
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
            st.text_area("Cómputo de pena", key=f"{k}_computo", height=80)
            st.selectbox("Tipo de cómputo", ["Efec.", "Cond."], key=f"{k}_computo_tipo")
            st.text_input("Servicio Correccional o Penitenciario", key=f"{k}_servicio_penitenciario")
            st.text_input("Legajo", key=f"{k}_legajo")
            st.text_input("Delito (con el tipo de delito y la fecha)", key=f"{k}_delitos")
            st.text_input("Liberación (fecha y motivo)", key=f"{k}_liberacion")
            st.text_area("Historial de delitos y condenas anteriores", key=f"{k}_antecedentes", height=80)
            st.text_area("Tratamientos médicos y psicológicos", key=f"{k}_tratamientos", height=80)


# ────────── panel principal: tabs de oficios ────────────────────────
tabs = st.tabs([
    "Migraciones", "Consulado", "Juez Electoral", "Policía Documentación",
    "Registro Civil", "Reg. Condenados Sexuales", "RNR", "Reg. Automotor",
    "Decomiso (Reg. Auto.)", "Decomiso c/Traslado", "Comisaría Traslado",
    "Decomiso s/Traslado", "Automotores Secuestrados", "RePAT",
])

# ───── TAB 0 : Migraciones ─────────────────────────────────────────
with tabs[0]:
    loc_a  = dialog_link(loc, 'loc')
    fecha  = fecha_alineada(loc_a, punto=True)

    # fecha (derecha)
    fecha_html = f"<p align='right' style='{LINE_STYLE}'>{fecha}</p>"
    st.markdown(fecha_html, unsafe_allow_html=True)

    # variables con links
    car_a = dialog_link(caratula, "carat", bold=True)
    trib_a = dialog_link(tribunal, "trib", bold=True)
    imp_a = dialog_link(st.session_state.get('imp0_datos', ''), 'imp0_datos')
    sent_n = dialog_link(sent_num, 'snum')
    sent_f = dialog_link(sent_fecha, 'sfecha')
    res_a = dialog_link(resuelvo, 'sres')
    firm_a = dialog_link(firmantes, 'sfirmantes')  # Key corregido
    firmeza = dialog_link(sent_firmeza, 'sfirmeza')  # Key corregido

    # cuerpo (justificado)
    cuerpo_html = "".join([
        f"<p align='justify' style='{LINE_STYLE}'><b>Sr/a Director/a</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>de la Dirección Nacional de Migraciones</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>S/D:</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'>En los autos caratulados: {car_a}, que se tramitan por ante {trib_a}, de la ciudad de Córdoba, Provincia de Córdoba, con la intervención de esta <b>Oficina de Servicios Procesales (OSPRO)</b>, se ha dispuesto librar a Ud. el presente oficio, a fin de informar lo resuelto por dicho Tribunal respecto de la persona cuyos datos personales se mencionan a continuación:</p>",
        f"<p align='justify' style='{LINE_STYLE}'>{imp_a}.</p>",
        f"<p align='justify' style='{LINE_STYLE}'>SENTENCIA N° {sent_n}, DE FECHA: {sent_f}. “Se Resuelve: {res_a}”. Fdo.: {firm_a}.</p>",
        f"<p align='justify' style='{LINE_STYLE}'>Asimismo, se informa que la sentencia antes señalada quedó firme con fecha {firmeza}.</p>",
        f"<p align='justify' style='{LINE_STYLE}'>Se adjuntan al presente oficio copia digital de la misma y del cómputo de pena respectivo.</p>",
    ])
    st.markdown(cuerpo_html, unsafe_allow_html=True)

    # saludo (centrado)
    saludo_html = f"<p align='center' style='{LINE_STYLE}'>Sin otro particular, saludo a Ud. atentamente.</p>"
    st.markdown(saludo_html, unsafe_allow_html=True)

    # botón copiar
    html_copy_button("Copiar", fecha_html + cuerpo_html + saludo_html, key="copy_migr")

# ───── TAB 1 : Consulado ───────────────────────────────────────────
with tabs[1]:
    loc_a  = dialog_link(loc, 'loc')
    fecha  = fecha_alineada(loc_a, punto=True)

    fecha_html = f"<p align='right' style='{LINE_STYLE}'>{fecha}</p>"
    st.markdown(fecha_html, unsafe_allow_html=True)

    car_a  = f"<b>{dialog_link(caratula,'carat')}</b>"
    trib_a = f"<b>{dialog_link(tribunal,'trib')}</b>"
    pais_a = dialog_link(consulado,'consulado')
    imp_a  = dialog_link(st.session_state.get('imp0_datos',''),'imp0_datos')
    sent_n = dialog_link(sent_num,'snum')
    sent_f = dialog_link(sent_fecha,'sfecha')
    res_a  = dialog_link(resuelvo,'sres')
    firm_a = dialog_link(firmantes,'sfirmantes')  # Key corregido
    firmeza= dialog_link(sent_firmeza,'sfirmeza')  # Key corregido

    cuerpo_html = "".join([
        f"<p align='justify' style='{LINE_STYLE}'><b>Al Sr. Titular del Consulado</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>de {pais_a}</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>S/D:</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'>En los autos caratulados: {car_a}, que se tramitan por ante {trib_a}, de la ciudad de Córdoba, Provincia de Córdoba, con la intervención de esta <b>Oficina de Servicios Procesales (OSPRO)</b>, se ha dispuesto librar el presente oficio, a fin de informar lo resuelto por dicho Tribunal respecto de la persona cuyos datos personales se mencionan a continuación:</p>",
        f"<p align='justify' style='{LINE_STYLE}'>{imp_a}.</p>",
        f"<p align='justify' style='{LINE_STYLE}'>SENTENCIA N° {sent_n}, DE FECHA: {sent_f}. “Se Resuelve: {res_a}.” Fdo.: {firm_a}.</p>",
        f"<p align='justify' style='{LINE_STYLE}'>Asimismo, se informa que la sentencia antes señalada quedó firme con fecha {firmeza}.</p>",
        f"<p align='justify' style='{LINE_STYLE}'>Se adjuntan al presente oficio copia digital de la misma y del cómputo de pena respectivo.</p>",
    ])
    st.markdown(cuerpo_html, unsafe_allow_html=True)

    saludo_html = f"<p align='center' style='{LINE_STYLE}'>Sin otro particular, saludo a Ud. atentamente.</p>"
    st.markdown(saludo_html, unsafe_allow_html=True)

    html_copy_button("Copiar", fecha_html + cuerpo_html + saludo_html, key="copy_cons")

# ───── TAB 2 : Juez Electoral ──────────────────────────────────────
with tabs[2]:
    loc_a  = dialog_link(loc, 'loc')
    fecha  = fecha_alineada(loc_a, punto=True)

    fecha_html = f"<p align='right' style='{LINE_STYLE}'>{fecha}</p>"
    st.markdown(fecha_html, unsafe_allow_html=True)

    car_a   = f"<b>{dialog_link(caratula,'carat')}</b>"
    trib_a  = f"<b>{dialog_link(tribunal,'trib')}</b>"
    imp_a   = dialog_link(st.session_state.get('imp0_datos',''),'imp0_datos')
    sent_n  = dialog_link(sent_num,'snum')
    sent_f  = dialog_link(sent_fecha,'sfecha')
    res_a   = dialog_link(resuelvo,'sres')
    firm_a  = dialog_link(firmantes,'sfirmantes')  # Key corregido
    firmeza = dialog_link(sent_firmeza,'sfirmeza')  # Key corregido

    cuerpo_html = "".join([
        f"<p align='justify' style='{LINE_STYLE}'><b>SR. JUEZ ELECTORAL:</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>S………………./………………D</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>-Av. Concepción Arenales esq. W. Paunero, Córdoba-</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'>En los autos caratulados: {car_a}, que se tramitan por ante {trib_a}, de la ciudad de Córdoba, Provincia de Córdoba, con la intervención de esta <b>Oficina de Servicios Procesales (OSPRO)</b>, se ha dispuesto librar a Ud. el presente oficio, a fin de informar lo resuelto por dicho Tribunal respecto de la persona cuyos datos personales se mencionan a continuación:</p>",
        f"<p align='justify' style='{LINE_STYLE}'>{imp_a}.</p>",
        f"<p align='justify' style='{LINE_STYLE}'>SENTENCIA N° {sent_n}, DE FECHA: {sent_f}. “Se Resuelve: {res_a}”. Fdo.: {firm_a}.</p>",
        f"<p align='justify' style='{LINE_STYLE}'>Asimismo, se informa que la sentencia antes señalada quedó firme con fecha {firmeza}.</p>",
        f"<p align='justify' style='{LINE_STYLE}'>Se adjuntan al presente oficio copia digital de la misma y del cómputo de pena respectivo.</p>",
    ])
    st.markdown(cuerpo_html, unsafe_allow_html=True)

    saludo_html = f"<p align='center' style='{LINE_STYLE}'>Sin otro particular, saludo a Ud. atentamente.</p>"
    st.markdown(saludo_html, unsafe_allow_html=True)

    html_copy_button("Copiar", fecha_html + cuerpo_html + saludo_html, key="copy_electoral")
# ───── TAB 3 : Policía Documentación ────────────────────────────────
with tabs[3]:
    loc_a  = dialog_link(loc, 'loc')
    fecha  = fecha_alineada(loc_a, punto=True)

    fecha_html = f"<p align='right' style='{LINE_STYLE}'>{fecha}</p>"
    st.markdown(fecha_html, unsafe_allow_html=True)

    car_a   = dialog_link(caratula, 'carat', bold=True)
    trib_a  = dialog_link(tribunal, 'trib', bold=True)
    imp_a   = dialog_link(st.session_state.get('imp0_datos',''),'imp0_datos')
    sent_n  = dialog_link(sent_num,'snum')
    sent_f  = dialog_link(sent_fecha,'sfecha')
    res_a   = dialog_link(resuelvo,'sres')
    firm_a  = dialog_link(firmantes,'sfirmantes')
    firmeza = dialog_link(sent_firmeza,'sfirmeza')
    comp_txt = dialog_link(st.session_state.get('imp0_computo',''),'imp0_computo')
    tipo     = st.session_state.get('imp0_computo_tipo','Efec.')
    if str(tipo).startswith('Efec'):
        comp_label = "el cómputo de pena respectivo"
    else:
        comp_label = "la resolución que fija la fecha de cumplimiento de los arts. 27 y 27 bis del C.P."

    cuerpo_html = "".join([
        f"<p align='justify' style='{LINE_STYLE}'><b>Sr.&nbsp;Titular de la División de Documentación Personal </b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>Policía de la Provincia de Córdoba</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>S ______/_______D:</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'>En los autos caratulados: {car_a}, que se tramitan ante {trib_a}, con intervención de esta <b>Oficina de Servicios Procesales (OSPRO)</b>, se ha resuelto enviar el presente oficio a fin de informar lo resuelto por dicho Tribunal respecto de la persona cuyos datos se mencionan a continuación, a saber:</p>",
        f"<p align='justify' style='{LINE_STYLE}'>{imp_a}.</p>",
        f"<p align='justify' style='{LINE_STYLE}'>SENTENCIA N° {sent_n}, DE FECHA {sent_f} “Se resuelve: {res_a}”. (Fdo.: {firm_a}).</p>",
        f"<p align='justify' style='{LINE_STYLE}'>Se transcribe a continuación {comp_label}: {comp_txt}.</p>",
        f"<p align='justify' style='{LINE_STYLE}'>Fecha de firmeza de la Sentencia: {firmeza}.</p>",
    ])
    st.markdown(cuerpo_html, unsafe_allow_html=True)

    saludo_html = f"<p align='center' style='{LINE_STYLE}'>Saluda a Ud. atentamente.</p>"
    st.markdown(saludo_html, unsafe_allow_html=True)

    html_copy_button("Copiar", fecha_html + cuerpo_html + saludo_html, key="copy_poldoc")

# ───── TAB 4 : Registro Civil ───────────────────────────────────────
with tabs[4]:
    loc_a  = dialog_link(loc, 'loc')
    fecha  = fecha_alineada(loc_a, punto=True)

    fecha_html = f"<p align='right' style='{LINE_STYLE}'>{fecha}</p>"
    st.markdown(fecha_html, unsafe_allow_html=True)

    car_a   = dialog_link(caratula, 'carat', bold=True)
    trib_a  = dialog_link(tribunal, 'trib', bold=True)
    imp_a   = dialog_link(st.session_state.get('imp0_datos',''),'imp0_datos')
    sent_n  = dialog_link(sent_num,'snum')
    sent_f  = dialog_link(sent_fecha,'sfecha')
    res_a   = dialog_link(resuelvo,'sres')
    firm_a  = dialog_link(firmantes,'sfirmantes')
    firmeza = dialog_link(sent_firmeza,'sfirmeza')

    cuerpo_html = "".join([
        f"<p align='justify' style='{LINE_STYLE}'><b>Sr/a Director/a del </b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>Registro Civil y Capacidad de las Personas</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>S/D:</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'>En los autos caratulados: {car_a}, que se tramitan por ante {trib_a}, de la ciudad de Córdoba, Provincia de Córdoba, con intervención de esta <b>Oficina de Servicios Procesales (OSPRO)</b>, se ha dispuesto librar a Ud. el presente oficio, a fin de informar lo resuelto por dicho Tribunal respecto de la persona cuyos datos se mencionan a continuación:</p>",
        f"<p align='justify' style='{LINE_STYLE}'>{imp_a}.</p>",
        f"<p align='justify' style='{LINE_STYLE}'>SENTENCIA N° {sent_n}, DE FECHA {sent_f}: “Se Resuelve: {res_a}”. Fdo.: {firm_a}.</p>",
        f"<p align='justify' style='{LINE_STYLE}'>Asimismo, se informa que la sentencia antes señalada quedó firme con fecha {firmeza}.</p>",
        f"<p align='justify' style='{LINE_STYLE}'>Se adjuntan al presente oficio copia digital de la misma y del cómputo de pena respectivo.</p>",
    ])
    st.markdown(cuerpo_html, unsafe_allow_html=True)

    saludo_html = f"<p align='center' style='{LINE_STYLE}'>Sin otro particular, saludo a Ud. atentamente.</p>"
    st.markdown(saludo_html, unsafe_allow_html=True)

    html_copy_button("Copiar", fecha_html + cuerpo_html + saludo_html, key="copy_regciv")

# ───── TAB 5 : Reg. Condenados Sexuales ────────────────────────────
with tabs[5]:
    loc_a  = dialog_link(loc, 'loc')
    fecha  = fecha_alineada(loc_a, punto=True)

    fecha_html = f"<p align='right' style='{LINE_STYLE}'>{fecha}</p>"
    st.markdown(fecha_html, unsafe_allow_html=True)

    car_a   = dialog_link(caratula, 'carat', bold=True)
    trib_a  = dialog_link(tribunal, 'trib', bold=True)
    imp_a   = dialog_link(st.session_state.get('imp0_datos',''),'imp0_datos')
    sent_n  = dialog_link(sent_num,'snum')
    sent_f  = dialog_link(sent_fecha,'sfecha')
    res_a   = dialog_link(resuelvo,'sres')
    firm_a  = dialog_link(firmantes,'sfirmantes')
    firmeza = dialog_link(sent_firmeza,'sfirmeza')
    extincion_a    = dialog_link(st.session_state.get('imp0_computo',''),'imp0_computo')
    condena_a      = dialog_link(st.session_state.get('imp0_condena',''),'imp0_condena')
    servicio_a     = dialog_link(st.session_state.get('imp0_servicio_penitenciario',''),'imp0_servicio_penitenciario')
    legajo_a       = dialog_link(st.session_state.get('imp0_legajo',''),'imp0_legajo')
    delitos_a      = dialog_link(st.session_state.get('imp0_delitos',''),'imp0_delitos')
    liberacion_a   = dialog_link(st.session_state.get('imp0_liberacion',''),'imp0_liberacion')
    antecedentes_a = dialog_link(st.session_state.get('imp0_antecedentes',''),'imp0_antecedentes')
    tratamientos_a = dialog_link(st.session_state.get('imp0_tratamientos',''),'imp0_tratamientos')

    cuerpo_html = "".join([
        f"<p align='justify' style='{LINE_STYLE}'><b>Al Sr. Titular del </b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>Registro Provincial de Personas Condenadas </b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>por Delitos contra la Integridad Sexual</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>S./D.</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'>En los autos caratulados: {car_a}, que se tramitan por ante {trib_a}, con intervención de esta <b>Oficina de Servicios Procesales (OSPRO)</b>, se ha resuelto librar el presente a fin de registrar en dicha dependencia lo resuelto por Sentencia N° {sent_n}, de fecha {sent_f} dictada por el mencionado Tribunal.</p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>I.&nbsp;DATOS PERSONALES</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'>{imp_a}.</p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>II.&nbsp;IDENTIFICACIÓN DACTILAR</b> (Adjuntar Ficha Dactiloscópica).</p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>III.&nbsp;DATOS DE CONDENA Y LIBERACIÓN</b> (adjuntar copia de la sentencia).</p>",
        f"<p align='justify' style='{LINE_STYLE}'>&nbsp;&nbsp;&nbsp;•&nbsp;Condena impuesta: {condena_a}</p>",
        f"<p align='justify' style='{LINE_STYLE}'>&nbsp;&nbsp;&nbsp;•&nbsp;Fecha en que la sentencia quedó firme: {firmeza}, Legajo: {legajo_a}.</p>",
        f"<p align='justify' style='{LINE_STYLE}'>&nbsp;&nbsp;&nbsp;•&nbsp;Fecha de extinción de la pena: {extincion_a}</p>",
        f"<p align='justify' style='{LINE_STYLE}'>&nbsp;&nbsp;&nbsp;•&nbsp;Servicio Correccional o Penitenciario: {servicio_a}</p>",
        f"<p align='justify' style='{LINE_STYLE}'>&nbsp;&nbsp;&nbsp;•&nbsp;Delito (con el tipo de delito y la fecha): {delitos_a}</p>",
        f"<p align='justify' style='{LINE_STYLE}'>&nbsp;&nbsp;&nbsp;•&nbsp;Liberación (fecha y motivo): {liberacion_a}</p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>IV.&nbsp;HISTORIAL DE DELITOS Y CONDENAS ANTERIORES.</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'>(consignar monto y fecha de la pena, tipo de delito y descripción, correccional o penitenciario y fecha de liberación)</p>",
        f"<p align='justify' style='{LINE_STYLE}'>&nbsp;&nbsp;&nbsp;{antecedentes_a}</p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>V.&nbsp;TRATAMIENTOS MÉDICOS Y PSICOLÓGICOS.</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'>(adjuntar copia de documentación respaldatoria y consignar fecha aproximada, descripción y tipo de tratamiento, hospital o institución e indicar duración de internación)</p>",
        f"<p align='justify' style='{LINE_STYLE}'>&nbsp;&nbsp;&nbsp;{tratamientos_a}</p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>VI.&nbsp;OTROS DATOS DE INTERÉS.</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'>&nbsp;&nbsp;&nbsp;Se le hace saber que {trib_a} resolvió mediante Sentencia N° {sent_n} de fecha {sent_f} lo siguiente “{res_a}.”.</p>",
        f"<p align='justify' style='{LINE_STYLE}'>&nbsp;&nbsp;&nbsp;Fdo.: {firm_a}.</p>",
        f"<p align='justify' style='{LINE_STYLE}'>Se adjuntan copias digitales de ficha RNR, sentencia firme y cómputo.</p>",
    ])
    st.markdown(cuerpo_html, unsafe_allow_html=True)

    saludo_html = f"<p align='center' style='{LINE_STYLE}'>Saludo a Ud. atentamente.</p>"
    st.markdown(saludo_html, unsafe_allow_html=True)

    html_copy_button("Copiar", fecha_html + cuerpo_html + saludo_html, key="copy_rcs")

# ───── TAB 6 : RNR ─────────────────────────────────────────────────
with tabs[6]:
    loc_a  = dialog_link(loc, 'loc')
    fecha  = fecha_alineada(loc_a, punto=True)

    fecha_html = f"<p align='right' style='{LINE_STYLE}'>{fecha}</p>"
    st.markdown(fecha_html, unsafe_allow_html=True)

    car_a   = dialog_link(caratula, 'carat', bold=True)
    trib_a  = dialog_link(tribunal, 'trib', bold=True)
    imp_a   = dialog_link(st.session_state.get('imp0_datos',''),'imp0_datos')
    sent_n  = dialog_link(sent_num,'snum')
    sent_f  = dialog_link(sent_fecha,'sfecha')
    res_a   = dialog_link(resuelvo,'sres')
    firm_a  = dialog_link(firmantes,'sfirmantes')
    firmeza = dialog_link(sent_firmeza,'sfirmeza')
    comp_txt = dialog_link(st.session_state.get('imp0_computo',''),'imp0_computo')
    tipo     = st.session_state.get('imp0_computo_tipo','Efec.')
    if str(tipo).startswith('Efec'):
        comp_label = "el cómputo de pena respectivo"
    else:
        comp_label = "la resolución que fija la fecha de cumplimiento de los arts. 27 y 27 bis del C.P."

    cuerpo_html = "".join([
        f"<p align='justify' style='{LINE_STYLE}'><b>Al Sr. Director del </b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>Registro Nacional de Reincidencia</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>S/D:</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'>De acuerdo a lo dispuesto por el art.&nbsp;2º de la Ley&nbsp;22.177, remito a Ud. testimonio de la parte dispositiva de la resolución dictada en los autos caratulados: {car_a}, que se tramitan por ante {trib_a}, de la ciudad de Córdoba, Provincia de Córdoba, con intervención de esta <b>Oficina de Servicios Procesales (OSPRO)</b>, en contra de:</p>",
        f"<p align='justify' style='{LINE_STYLE}'>{imp_a}.</p>",
        f"<p align='justify' style='{LINE_STYLE}'>SENTENCIA N° {sent_n}, DE FECHA {sent_f}: “{res_a}.” (Fdo.: {firm_a}).</p>",
        f"<p align='justify' style='{LINE_STYLE}'>Se transcribe a continuación {comp_label}: {comp_txt}.</p>",
        f"<p align='justify' style='{LINE_STYLE}'>Fecha de firmeza de la sentencia: {firmeza}.</p>",
    ])
    st.markdown(cuerpo_html, unsafe_allow_html=True)

    saludo_html = f"<p align='center' style='{LINE_STYLE}'>Saluda a Ud. atentamente.</p>"
    st.markdown(saludo_html, unsafe_allow_html=True)

    html_copy_button("Copiar", fecha_html + cuerpo_html + saludo_html, key="copy_rnr")
