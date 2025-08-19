# app.py
import re
import uuid
import html
import json
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components
from core import (
    autocompletar,
    extraer_caratula,
    normalizar_caratula,
    PENITENCIARIOS,
    DEPOSITOS,
    JUZ_NAVFYG,
    TRIBUNALES,
    MAX_IMPUTADOS,
)  # lógica de autocompletado y listas
from helpers import dialog_link, strip_dialog_links, create_clipboard_html

CARACTER_ENTREGA = ["definitivo", "de depositario judicial"]

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
/* Scroll horizontal para los títulos de las pestañas de oficios */
div[role="tablist"] {
    overflow-x: auto;
    overflow-y: hidden;
    padding-bottom: 8px;
}
div[role="tablist"]::-webkit-scrollbar {
    height: 8px;
}
</style>
<script>
(function() {
  const doc = window.parent.document;
  function bindWheel() {
    const el = doc.querySelector('div[role="tablist"]');
    if (!el || el.dataset.wheelbound) return;
    el.dataset.wheelbound = '1';
    el.addEventListener('wheel', (evt) => {
      if (evt.deltaY !== 0) {
        evt.preventDefault();
        el.scrollLeft += evt.deltaY;
      }
    }, {passive: false});
  }
  const obs = new MutationObserver(bindWheel);
  obs.observe(doc.body, {childList: true, subtree: true});
  bindWheel();
})();
</script>
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


# ────────── combos editables (selectbox + texto libre) ──────────────
def combo_editable(label: str, opciones: list[str], *, key: str) -> str:
    """Combobox que permite elegir de la lista o escribir un valor nuevo."""
    actual = st.session_state.get(key, "")
    opts = list(opciones)
    if actual and actual not in opts:
        opts.append(actual)
    return st.selectbox(label, opts, key=key)


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

def res_decomiso() -> str:
    txt = resuelvo
    plano = " ".join(txt.splitlines())
    pattern = r"\b([IVXLCDM]+|\d+)[\.\)]\s+([\s\S]*?)(?=\b(?:[IVXLCDM]+|\d+)[\.\)]\s+|$)"
    partes = []
    for m in re.finditer(pattern, plano, re.IGNORECASE):
        num, t = m.group(1), m.group(2).strip()
        if re.search(r"decomis", t, re.IGNORECASE):
            partes.append(f"{num}. {t}")
    return " ".join(partes) if partes else (resuelvo or "…")

# ────────── callback: normaliza la carátula después de editar ───────
def _normalizar_caratula():
    raw  = st.session_state.carat
    auto = extraer_caratula(normalizar_caratula(raw))
    if auto != raw:
        # solo actualizar estado; NO llamar a st.rerun() aquí
        st.session_state.carat = auto
        st.session_state["_carat_norm_rerun"] = True  # por si querés saber que normalizó


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
        if k == "carat":
            _normalizar_caratula()  # sin st.rerun()




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

def connect_tabs(a: str, b: str) -> None:
    """Draw a line between two tabs identified by their titles."""
    uid = re.sub(r"\W+", "_", f"related_indicator_{a}_{b}")
    js = f"""
    <script>
    (function() {{
      const doc = parent.document;
      const win = parent;
      function draw() {{
        const id = {json.dumps(uid)};
        const old = doc.getElementById(id); if (old) old.remove();
        const tabs = Array.from(doc.querySelectorAll('button[role="tab"]'));
        const ta = tabs.find(el => el.innerText.trim() === {json.dumps(a)});
        const tb = tabs.find(el => el.innerText.trim() === {json.dumps(b)});
        if (!ta || !tb) return;
        const ra = ta.getBoundingClientRect();
        const rb = tb.getBoundingClientRect();
        const sx = win.scrollX || doc.documentElement.scrollLeft;
        const sy = win.scrollY || doc.documentElement.scrollTop;
        const div = doc.createElement('div');
        div.id = id;
        div.style.position = 'absolute';
        div.style.background = '#0068c9';
        div.style.height = '2px';
        div.style.top = (ra.bottom + sy) + 'px';
        div.style.left = (ra.left + sx + ra.width/2) + 'px';
        div.style.width = (rb.left + sx + rb.width/2 - (ra.left + sx + ra.width/2)) + 'px';
        doc.body.appendChild(div);
      }}
      draw();
      doc.addEventListener('click', draw);
      win.addEventListener('resize', draw);
      win.addEventListener('scroll', draw, {{passive: true}});
      const tabList = doc.querySelector('div[role="tablist"]');
      if (tabList) tabList.addEventListener('scroll', draw, {{passive: true}});
    }})();
    </script>
    """
    _html_compat(js, height=0)



def switch_tab(name: str) -> None:
    js = f"""
    <script>
      const tabs = parent.document.querySelectorAll('button[role="tab"]');
      const t = Array.from(tabs).find(el => el.innerText.trim() === {json.dumps(name)});
      if (t) t.click();
    </script>
    """
    _html_compat(js, height=0)


# ────────── helpers: acceso dinámico a imputados ───────────────────
def imp_key(field: str, idx: int | None = None) -> str:
    """Devuelve la clave en session_state para el imputado seleccionado."""
    if idx is None:
        idx = st.session_state.get("imp_sel", 0)
    return f"imp{idx}_{field}"


def imp_val(field: str, idx: int | None = None, default: str = "") -> str:
    """Obtiene el valor de un campo del imputado actual."""
    return st.session_state.get(imp_key(field, idx), default)


TAB_NAMES = [
    "Migraciones", "Consulado", "Juez Electoral", "Policía Documentación",
    "Registro Civil", "Reg. Condenados Sexuales", "RNR", "Complejo Carcelario",
    "Juzgado Niñez-Adolescencia", "RePAT", "Fiscalía Instrucción",
    "Automotores Secuestrados", "Registro Automotor", "Decomiso (Reg. Automotor)",
    "Decomiso Con Traslado", "Comisaría Traslado", "Decomiso Sin Traslado",
]



# ────────── barra lateral: datos generales ──────────────────────────
with st.sidebar:
    tab_dest = st.selectbox("Ir a oficio", TAB_NAMES, key="tab_select")
    st.header("Datos generales")
    loc       = st.text_input("Localidad", value="Córdoba", key="loc")
    st.text_input(
        "Carátula",
        key="carat",
        on_change=_normalizar_caratula,   # ← NUEVO
    )
    caratula = st.session_state.carat     # ← reemplaza a tu caratula_raw

    tribunal  = combo_editable("Tribunal", TRIBUNALES, key="trib")

    col1, col2 = st.columns(2)
    with col1:
        sent_num   = st.text_input("Sentencia Nº", key="snum")
    with col2:
        sent_fecha = st.text_input("Fecha sentencia", key="sfecha")

    sent_firmeza = st.text_input("Firmeza sentencia", key="sfirmeza")
    resuelvo     = st.text_area("Resuelvo", height=80, key="sres")
    firmantes    = st.text_input("Firmantes", key="sfirmantes")  # Corregido key
    consulado    = st.text_input("Consulado", key="consulado")
    deposito     = combo_editable("Depósito", DEPOSITOS, key="deposito")

    rodado       = st.text_input("Decomisado/secuestrado", key="rodado")
    st.write("Reg. automotor / Comisaría:")
    col_rc = st.columns(2)
    regn      = col_rc[0].text_input("Reg. N°", key="regn")
    comisaria = col_rc[1].text_input("Comisaría N°", key="comisaria")
    dep_def    = combo_editable("Carácter de la entrega", CARACTER_ENTREGA, key="dep_def")
    titular_veh = st.text_input("Titular del vehículo", key="titular_veh")
    st.write("Inf. Téc. Iden. Matrícula:")
    col_it = st.columns(2)
    itim_num   = col_it[0].text_input("N°", key="itim_num")
    itim_fecha = col_it[1].text_input("Fecha", key="itim_fecha")

    # Nº de imputados dinámico
    n = st.number_input(
        "Número de imputados", 1, MAX_IMPUTADOS, st.session_state.n_imputados,
        key="n_imp",
    )

    st.session_state.n_imputados = n
    # 👇 Reservo el lugar para los expanders acá
    imp_expanders_slot = st.container()
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
    with imp_expanders_slot:   # 👈 se dibujan debajo de "Número de imputados"
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
                combo_editable(
                    "Servicio Correccional o Penitenciario",
                    PENITENCIARIOS,
                    key=f"{k}_servicio_penitenciario",
                )
                st.text_input("Legajo", key=f"{k}_legajo")
                st.text_input("Delito (con el tipo de delito y la fecha)", key=f"{k}_delitos")
                st.text_input("Liberación (fecha y motivo)", key=f"{k}_liberacion")
                st.text_area("Historial de delitos y condenas anteriores", key=f"{k}_antecedentes", height=80)
                st.text_area("Tratamientos médicos y psicológicos", key=f"{k}_tratamientos", height=80)
                combo_editable(
                    "Juzgado de Niñez, Adolescencia, V.F. y Género",
                    JUZ_NAVFYG,
                    key=f"{k}_juz_navfyg",
                )
                st.text_input("Expediente de V.F. relacionado", key=f"{k}_ee_relacionado")


# ────────── panel principal: selector de imputado + tabs ───────────
st.selectbox(
    "Imputado",
    list(range(st.session_state.n_imputados)),
    format_func=lambda i: f"Imputado {i+1}" + (
        f" – {st.session_state.get(f'imp{i}_nom', '')}" if st.session_state.get(f'imp{i}_nom', '') else ""
    ),
    key="imp_sel",
)

tabs = st.tabs(TAB_NAMES)
connect_tabs("Registro Automotor", "Decomiso (Reg. Automotor)")
connect_tabs("Decomiso Con Traslado", "Comisaría Traslado")
switch_tab(tab_dest)
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
    imp_a = dialog_link(imp_val('datos'), imp_key('datos'))
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
    imp_a  = dialog_link(imp_val('datos'), imp_key('datos'))
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
    imp_a   = dialog_link(imp_val('datos'), imp_key('datos'))
    sent_n  = dialog_link(sent_num,'snum')
    sent_f  = dialog_link(sent_fecha,'sfecha')
    res_a   = dialog_link(resuelvo,'sres')
    firm_a  = dialog_link(firmantes,'sfirmantes')  # Key corregido
    firmeza = dialog_link(sent_firmeza,'sfirmeza')  # Key corregido

    cuerpo_html = "".join([
        f"<p align='justify' style='{LINE_STYLE}'><b>SR. JUEZ ELECTORAL:</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>S………………./………………D</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>-Av. Concepción Arenales esq. Wenceslao Paunero, Bº Rogelio Martínez, Córdoba.</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>Tribunales Federales de Córdoba-</b></p>",
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
    imp_a   = dialog_link(imp_val('datos'), imp_key('datos'))
    sent_n  = dialog_link(sent_num,'snum')
    sent_f  = dialog_link(sent_fecha,'sfecha')
    res_a   = dialog_link(resuelvo,'sres')
    firm_a  = dialog_link(firmantes,'sfirmantes')
    firmeza = dialog_link(sent_firmeza,'sfirmeza')
    comp_txt = dialog_link(imp_val('computo'), imp_key('computo'))
    tipo     = imp_val('computo_tipo', default='Efec.')
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
    imp_a   = dialog_link(imp_val('datos'), imp_key('datos'))
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
    imp_a   = dialog_link(imp_val('datos'), imp_key('datos'))
    sent_n  = dialog_link(sent_num,'snum')
    sent_f  = dialog_link(sent_fecha,'sfecha')
    res_a   = dialog_link(resuelvo,'sres')
    firm_a  = dialog_link(firmantes,'sfirmantes')
    firmeza = dialog_link(sent_firmeza,'sfirmeza')
    extincion_a    = dialog_link(imp_val('computo'), imp_key('computo'))
    condena_a      = dialog_link(imp_val('condena'), imp_key('condena'))
    servicio_a     = dialog_link(imp_val('servicio_penitenciario'), imp_key('servicio_penitenciario'))
    legajo_a       = dialog_link(imp_val('legajo'), imp_key('legajo'))
    delitos_a      = dialog_link(imp_val('delitos'), imp_key('delitos'))
    liberacion_a   = dialog_link(imp_val('liberacion'), imp_key('liberacion'))
    antecedentes_a = dialog_link(imp_val('antecedentes'), imp_key('antecedentes'))
    tratamientos_a = dialog_link(imp_val('tratamientos'), imp_key('tratamientos'))

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
    imp_a   = dialog_link(imp_val('datos'), imp_key('datos'))
    sent_n  = dialog_link(sent_num,'snum')
    sent_f  = dialog_link(sent_fecha,'sfecha')
    res_a   = dialog_link(resuelvo,'sres')
    firm_a  = dialog_link(firmantes,'sfirmantes')
    firmeza = dialog_link(sent_firmeza,'sfirmeza')
    comp_txt = dialog_link(imp_val('computo'), imp_key('computo'))
    tipo     = imp_val('computo_tipo', default='Efec.')
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

# ───── TAB 7 : Complejo Carcelario ────────────────────────────────
with tabs[7]:
    loc_a  = dialog_link(loc, 'loc')
    fecha  = fecha_alineada(loc_a)

    fecha_html = f"<p align='right' style='{LINE_STYLE}'>{fecha}</p>"
    st.markdown(fecha_html, unsafe_allow_html=True)

    car_a   = f"<b>{dialog_link(caratula,'carat')}</b>"
    trib_a  = f"<b>{dialog_link(tribunal,'trib')}</b>"
    sent_n  = dialog_link(sent_num,'snum')
    sent_f  = dialog_link(sent_fecha,'sfecha')
    res_a   = dialog_link(resuelvo,'sres')
    firm_a  = dialog_link(firmantes,'sfirmantes')
    establecimiento = imp_val('servicio_penitenciario').upper()
    establecimiento_a = dialog_link(establecimiento, imp_key('servicio_penitenciario'))
    nombre_a = dialog_link(imp_val('nom'), imp_key('nom'))
    dni_a    = dialog_link(imp_val('dni'), imp_key('dni'))

    cuerpo_html = "".join([
        f"<p align='justify' style='{LINE_STYLE}'><b>AL SEÑOR DIRECTOR </b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>DEL {establecimiento_a}</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>S/D:</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'>En los autos caratulados: {car_a}, que se tramitan por ante {trib_a}, con intervención de esta <b>Oficina de Servicios Procesales (OSPRO)</b>, me dirijo a Ud. a los fines de informar lo resuelto con relación a {nombre_a}, DNI {dni_a}, mediante Sentencia N° {sent_n}, de fecha {sent_f}: “{res_a}”. (Fdo.: {firm_a}).</p>",
    ])
    st.markdown(cuerpo_html, unsafe_allow_html=True)

    saludo_html = f"<p align='center' style='{LINE_STYLE}'>Sin otro particular, lo saludo atentamente.</p>"
    st.markdown(saludo_html, unsafe_allow_html=True)

    html_copy_button("Copiar", fecha_html + cuerpo_html + saludo_html, key="copy_comcar")

# ───── TAB 8 : Juzgado Niñez-Adolescencia ─────────────────────────
with tabs[8]:
    loc_a  = dialog_link(loc, 'loc')
    fecha  = fecha_alineada(loc_a, punto=True)

    fecha_html = f"<p align='right' style='{LINE_STYLE}'>{fecha}</p>"
    st.markdown(fecha_html, unsafe_allow_html=True)

    car_a   = f"<b>{dialog_link(caratula,'carat')}</b>"
    trib_a  = f"<b>{dialog_link(tribunal,'trib')}</b>"
    sent_n  = dialog_link(sent_num,'snum')
    sent_f  = dialog_link(sent_fecha,'sfecha')
    res_a   = dialog_link(resuelvo,'sres')
    firm_a  = dialog_link(firmantes,'sfirmantes')
    juz = imp_val('juz_navfyg', default='Juzgado de Niñez, Adolescencia, Violencia Familiar y de Género de ….. Nom. – Sec. N° …..')
    if juz.startswith('Juzgado de Niñez,'):
        juz = juz.replace(', Violencia', ',\nViolencia').replace('Género de ', 'Género de \n')
    elif 'modalidad doméstica -causas graves-' in juz:
        juz = juz.replace(', modalidad', ',\nmodalidad').replace('-causas graves- de', '-causas graves-\nde')
    juz_a = dialog_link(juz, imp_key('juz_navfyg'))
    ee_rel = imp_val('ee_relacionado', default='………….')
    ee_rel_a = dialog_link(ee_rel, imp_key('ee_relacionado'))
    nombre_a = dialog_link(imp_val('nom'), imp_key('nom'))
    dni_a    = dialog_link(imp_val('dni'), imp_key('dni'))

    cuerpo_html = "".join([
        f"<p align='justify' style='{LINE_STYLE}'><b>{juz_a}</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>S/D:</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'>En los autos caratulados: {car_a}, que se tramitan por ante {trib_a}, con conocimiento e intervención de esta <b>Oficina de Servicios Procesales (OSPRO)</b>, se ha dispuesto librar a Ud. el presente, a fin de comunicarle lo resuelto por el mencionado Tribunal con relación a {nombre_a}, DNI {dni_a}, mediante Sentencia N° {sent_n}, de fecha {sent_f}: “Se Resuelve: {res_a}” (Fdo.: {firm_a}).</p>",
        f"<p align='justify' style='{LINE_STYLE}'>Se adjuntan al presente oficio copia digital de la sentencia y del cómputo de pena respectivo.</p>",
        f"<p align='justify' style='{LINE_STYLE}'>Expediente de V.F. relacionado al presente n° {ee_rel_a}</p>",
    ])
    st.markdown(cuerpo_html, unsafe_allow_html=True)

    saludo_html = f"<p align='center' style='{LINE_STYLE}'>Sin otro particular, saludo a Ud. atentamente.</p>"
    st.markdown(saludo_html, unsafe_allow_html=True)

    html_copy_button("Copiar", fecha_html + cuerpo_html + saludo_html, key="copy_jninez")

# ───── TAB 9 : RePAT ───────────────────────────────────────────────
with tabs[9]:
    loc_a  = dialog_link(loc, 'loc')
    fecha  = fecha_alineada(loc_a, punto=True)

    fecha_html = f"<p align='right' style='{LINE_STYLE}'>{fecha}</p>"
    st.markdown(fecha_html, unsafe_allow_html=True)

    car_a   = f"<b>{dialog_link(caratula,'carat')}</b>"
    trib_a  = f"<b>{dialog_link(tribunal,'trib')}</b>"
    sent_n  = dialog_link(sent_num,'snum')
    sent_f  = dialog_link(sent_fecha,'sfecha')
    res_a   = dialog_link(resuelvo,'sres')
    firm_a  = dialog_link(firmantes,'sfirmantes')
    firmeza = dialog_link(sent_firmeza,'sfirmeza')
    imp_a   = dialog_link(imp_val('datos'), imp_key('datos'))

    cuerpo_html = "".join([
        f"<p align='justify' style='{LINE_STYLE}'><b>SR. DIRECTOR DEL REGISTRO PROVINCIAL </b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>DE ANTECEDENTES DE TRÁNSITO (RePAT)</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>S/D:</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'>En los autos caratulados: {car_a}, que se tramitan por ante {trib_a}, de esta ciudad de Córdoba, provincia de Córdoba, con intervención de esta <b>Oficina de Servicios Procesales - OSPRO -</b>, se ha dispuesto librar a Ud. el presente a fin de comunicar lo resuelto por dicho Tribunal, respecto de la persona cuyos datos se detallan a continuación:</p>",
        f"<p align='justify' style='{LINE_STYLE}'>{imp_a}.</p>",
        f"<p align='justify' style='{LINE_STYLE}'>SENTENCIA N° {sent_n}, DE FECHA {sent_f}: “Se resuelve: {res_a}”. (Fdo.: {firm_a}).</p>",
        f"<p align='justify' style='{LINE_STYLE}'>Asimismo, se informa que la sentencia condenatoria antes referida quedó firme con fecha {firmeza}.</p>",
        f"<p align='justify' style='{LINE_STYLE}'>Se adjuntan al presente oficio copia digital Sentencia y de cómputo de pena respectivos.</p>",
    ])
    st.markdown(cuerpo_html, unsafe_allow_html=True)

    saludo_html = f"<p align='center' style='{LINE_STYLE}'>Saludo a Ud. atentamente.</p>"
    st.markdown(saludo_html, unsafe_allow_html=True)

    html_copy_button("Copiar", fecha_html + cuerpo_html + saludo_html, key="copy_repat")

# ───── TAB 10 : Fiscalía Instrucción ───────────────────────────────
with tabs[10]:
    loc_a  = dialog_link(loc, 'loc')
    fecha  = fecha_alineada(loc_a, punto=True)

    fecha_html = f"<p align='right' style='{LINE_STYLE}'>{fecha}</p>"
    st.markdown(fecha_html, unsafe_allow_html=True)

    car_a   = f"<b>{dialog_link(caratula,'carat')}</b>"
    trib_a  = f"<b>{dialog_link(tribunal,'trib')}</b>"
    sent_n  = dialog_link(sent_num,'snum')
    sent_f  = dialog_link(sent_fecha,'sfecha')
    firm_a  = dialog_link(firmantes,'sfirmantes')
    plano = resuelvo.replace('\n', ' ')
    pattern = r"\b([IVXLCDM]+|\d+)[\.\)]\s+([\s\S]*?)(?=\b(?:[IVXLCDM]+|\d+)[\.\)]\s+|$)"
    partes = []
    for m in re.finditer(pattern, plano, re.DOTALL | re.IGNORECASE):
        num, txt = m.group(1), m.group(2).strip()
        if re.search(r"investig|esclarec|antecedente|instruc", txt, re.IGNORECASE):
            partes.append(f"{num}. {txt}")
    res = " ".join(partes) if partes else resuelvo
    res_a = dialog_link(res, 'sres')

    cuerpo_html = "".join([
        f"<p align='justify' style='{LINE_STYLE}'><b>Sr/a Fiscal de </b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>Instrucción que por turno corresponda</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>S/D:</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'>En los autos caratulados: {car_a}, que se tramitan por ante {trib_a}, con intervención de la <b>Oficina de Servicios Procesales (OSPRO)</b>, se ha dispuesto librar a Ud. el presente, por disposición de la Cámara señalada y conforme a lo resuelto en la sentencia dictada en la causa de referencia, los antecedentes obrantes en el expediente mencionado, a los fines de investigar la posible comisión de un delito perseguible de oficio.</p>",
        f"<p align='justify' style='{LINE_STYLE}'>Se transcribe a continuación la parte pertinente de la misma: “Se resuelve: {res_a}”. (Fdo.: {firm_a}).</p>",
    ])
    st.markdown(cuerpo_html, unsafe_allow_html=True)

    saludo_html = f"<p align='center' style='{LINE_STYLE}'>Sin otro particular, saludo a Ud. atte.</p>"
    st.markdown(saludo_html, unsafe_allow_html=True)

    html_copy_button("Copiar", fecha_html + cuerpo_html + saludo_html, key="copy_fiscinst")

# ───── TAB 11 : Automotores Secuestrados ───────────────────────────
with tabs[11]:
    loc_a  = dialog_link(loc, 'loc')
    fecha  = fecha_alineada(loc_a, punto=True)

    fecha_html = f"<p align='right' style='{LINE_STYLE}'>{fecha}</p>"
    st.markdown(fecha_html, unsafe_allow_html=True)

    car_a       = f"<b>{dialog_link(caratula,'carat')}</b>"
    trib_a      = f"<b>{dialog_link(tribunal,'trib')}</b>"
    rodado_a    = dialog_link(rodado, 'rodado')
    deposito_a  = dialog_link(deposito, 'deposito')
    dep_def_a   = dialog_link(dep_def, 'dep_def')
    titular_a   = dialog_link(titular_veh, 'titular_veh')
    itim_n_a    = dialog_link(itim_num, 'itim_num')
    itim_f_a    = dialog_link(itim_fecha, 'itim_fecha')

    cuerpo_html = "".join([
        f"<p align='justify' style='{LINE_STYLE}'><b>A LA OFICINA DE</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>AUTOMOTORES SECUESTRADOS EN </b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>CAUSAS PENALES, TRIBUNAL SUPERIOR DE JUSTICIA.</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>S/D:</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'>En los autos caratulados: {car_a}, que se tramitan por ante {trib_a}, con intervención de esta <b>Oficina de Servicios Procesales (OSPRO)</b>, se ha resuelto enviar a Ud. el presente a fines de solicitarle que establezca lo necesario para que, por intermedio de quien corresponda, se coloque a la orden y disposición del Tribunal señalado, el rodado {rodado_a}, vehículo que se encuentra en el {deposito_a}.</p>",
        f"<p align='justify' style='{LINE_STYLE}'>Se hace saber a Ud. que dicha petición obedece a que el Tribunal mencionado ha dispuesto la entrega del referido vehículo en carácter {dep_def_a} a su titular registral {titular_a}. Para mayor recaudo se adjunta al presente, en documento informático, copia de la resolución que dispuso la medida.</p>",
        f"<p align='justify' style='{LINE_STYLE}'>Finalmente, se informa que a dicho rodado, se le realizó el correspondiente Informe Técnico de Identificación de Matrículas N° {itim_n_a} de fecha {itim_f_a}, concluyendo el mismo que la unidad no presenta adulteración en sus matrículas identificatorias.</p>",
    ])
    st.markdown(cuerpo_html, unsafe_allow_html=True)

    saludo_html = f"<p align='center' style='{LINE_STYLE}'>Saludo a Ud. muy atentamente.</p>"
    st.markdown(saludo_html, unsafe_allow_html=True)

    html_copy_button("Copiar", fecha_html + cuerpo_html + saludo_html, key="copy_autosec")

# ───── TAB 12 : Registro Automotor ─────────────────────────────────
with tabs[12]:
    loc_a  = dialog_link(loc, 'loc')
    fecha  = fecha_alineada(loc_a, punto=True)

    fecha_html = f"<p align='right' style='{LINE_STYLE}'>{fecha}</p>"
    st.markdown(fecha_html, unsafe_allow_html=True)

    car_a    = f"<b>{dialog_link(caratula,'carat')}</b>"
    trib_a   = f"<b>{dialog_link(tribunal,'trib')}</b>"
    sent_n   = dialog_link(sent_num,'snum')
    sent_f   = dialog_link(sent_fecha,'sfecha')
    res      = res_decomiso()
    res_a    = dialog_link(res,'sres')
    firm_a   = dialog_link(firmantes,'sfirmantes')
    regn_a   = dialog_link(regn,'regn')
    rodado_a = dialog_link(rodado,'rodado')

    cuerpo_html = "".join([
        f"<p align='justify' style='{LINE_STYLE}'><b>AL SR. TITULAR DEL REGISTRO DE LA</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>PROPIEDAD DEL AUTOMOTOR N° {regn_a}</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>S/D:</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'>&emsp;En los autos caratulados: {car_a}, que se tramitan por ante {trib_a}, con intervención de esta<b> Oficina de Servicios </b><b>Procesales – OSPRO –</b>, se ha dispuesto librar a Ud. el presente, a fin de informarle que mediante Sentencia N° {sent_n} de fecha {sent_f}, dicho Tribunal resolvió ordenar el <b>DECOMISO</b> del {rodado_a}.</p>",
        f"<p align='justify' style='{LINE_STYLE}'>Se transcribe a continuación la parte pertinente de la misma:</p>",
        f"<p align='justify' style='{LINE_STYLE}'>&ldquo;SE RESUELVE: {res_a}&rdquo;. (Fdo.: {firm_a}).</p>",
    ])
    st.markdown(cuerpo_html, unsafe_allow_html=True)

    saludo_html = f"<p align='center' style='{LINE_STYLE}'>Sin otro particular, saludo a Ud. atte.</p>"
    st.markdown(saludo_html, unsafe_allow_html=True)

    html_copy_button("Copiar", fecha_html + cuerpo_html + saludo_html, key="copy_regauto")

# ───── TAB 13 : Decomiso (Reg. Automotor) ──────────────────────────
with tabs[13]:
    loc_a  = dialog_link(loc, 'loc')
    fecha  = fecha_alineada(loc_a, punto=True)

    fecha_html = f"<p align='right' style='{LINE_STYLE}'>{fecha}</p>"
    st.markdown(fecha_html, unsafe_allow_html=True)

    car_a    = f"<b>{dialog_link(caratula,'carat')}</b>"
    trib_a   = f"<b>{dialog_link(tribunal,'trib')}</b>"
    sent_n   = dialog_link(sent_num,'snum')
    sent_f   = dialog_link(sent_fecha,'sfecha')
    res      = res_decomiso()
    res_a    = dialog_link(res,'sres')
    firm_a   = dialog_link(firmantes,'sfirmantes')
    rodado_a = dialog_link(rodado,'rodado')
    deposito_a = dialog_link(deposito,'deposito')
    regn_a   = dialog_link(regn,'regn')

    cuerpo_html = "".join([
        f"<p align='justify' style='{LINE_STYLE}'><b>A LA SRA. SECRETARIA PENAL</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>DEL TRIBUNAL SUPERIOR DE JUSTICIA</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>DRA. MARIA PUEYRREDON DE MONFARRELL</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>S______/_______D:</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'>En los autos caratulados: {car_a}, que se tramitan por ante {trib_a}, con conocimiento e intervención de esta <b>Oficina de Servicios</b> <b>Procesales – OSPRO –</b>, se ha dispuesto librar a Ud. el presente a fin de poner en conocimiento lo resuelto por la Sentencia N° {sent_n} del {sent_f}, dictada por el tribunal mencionado, en virtud de la cual se ordenó el <b>DECOMISO</b> de los siguientes objetos:</p>",
        f"<table border='1' cellspacing='0' cellpadding='2'><tr><th>Tipos de elementos</th><th>Ubicación actual</th></tr><tr><td>{rodado_a}</td><td>{deposito_a}</td></tr></table>",
        f"<p align='justify' style='{LINE_STYLE}'>Pongo en su conocimiento que la mencionada sentencia se encuentra firme, transcribiéndose a continuación la parte pertinente de la misma:</p>",
        f"<p align='justify' style='{LINE_STYLE}'>&ldquo;SE RESUELVE: {res_a}&rdquo;. (Fdo.: {firm_a}).</p>",
        f"<p align='justify' style='{LINE_STYLE}'>Asimismo, se informa que en el día de la fecha se comunicó dicha resolución al Registro del Automotor donde está radicado el vehículo, Nº {regn_a}.</p>",
    ])
    st.markdown(cuerpo_html, unsafe_allow_html=True)

    saludo_html = f"<p align='center' style='{LINE_STYLE}'>Sin otro particular, saludo a Ud. muy atentamente.</p>"
    st.markdown(saludo_html, unsafe_allow_html=True)

    html_copy_button("Copiar", fecha_html + cuerpo_html + saludo_html, key="copy_decomregauto")

# ───── TAB 14 : Decomiso Con Traslado ──────────────────────────
with tabs[14]:
    loc_a  = dialog_link(loc, 'loc')
    fecha  = fecha_alineada(loc_a, punto=True)

    fecha_html = f"<p align='right' style='{LINE_STYLE}'>{fecha}</p>"
    st.markdown(fecha_html, unsafe_allow_html=True)

    car_a       = f"<b>{dialog_link(caratula,'carat')}</b>"
    trib_a      = f"<b>{dialog_link(tribunal,'trib')}</b>"
    sent_n      = dialog_link(sent_num,'snum')
    sent_f      = dialog_link(sent_fecha,'sfecha')
    res         = res_decomiso()
    res_a       = dialog_link(res,'sres')
    firm_a      = dialog_link(firmantes,'sfirmantes')
    rodado_a    = dialog_link(rodado,'rodado')
    comisaria_a = dialog_link(comisaria,'comisaria')

    cuerpo_html = "".join([
        f"<p align='justify' style='{LINE_STYLE}'><b>A LA SRA. SECRETARIA PENAL</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>DEL TRIBUNAL SUPERIOR DE JUSTICIA</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>DRA. MARIA PUEYRREDON DE MONFARRELL</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>S/D:</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'>En los autos caratulados: {car_a}, que se tramitan por ante {trib_a}, con intervención de esta <b>Oficina de Servicios Procesales</b> <b>- OSPRO -</b>, se ha dispuesto librar a Ud. el presente, a fin de informarle que mediante Sentencia N° {sent_n} de {sent_f}, dicho Tribunal resolvió ordenar el <b>DECOMISO</b> de los siguientes objetos:</p>",
        f"<table border='1' cellspacing='0' cellpadding='2'><tr><th>Descripción del objeto</th><th>Ubicación Actual</th></tr><tr><td>{rodado_a}</td><td>Comisaría {comisaria_a}</td></tr></table>",
        f"<p align='justify' style='{LINE_STYLE}'>Se hace saber a Ud. que el/los elemento/s referido/s se encuentra/n en la Cría. {comisaria_a} de la Policía de Córdoba y en el día de la fecha se libró oficio a dicha dependencia policial a los fines de remitir al Depósito General de Efectos Secuestrados el/los objeto/s decomisado/s.</p>",
        f"<p align='justify' style='{LINE_STYLE}'>Asimismo, informo que la sentencia referida se encuentra firme, transcribiéndose a continuación la parte pertinente de la misma: &ldquo;SE RESUELVE: {res_a}&rdquo;. (Fdo.: {firm_a}).</p>",
    ])
    st.markdown(cuerpo_html, unsafe_allow_html=True)

    saludo_html = f"<p align='center' style='{LINE_STYLE}'>Sin otro particular, saludo a Ud. muy atentamente.</p>"
    st.markdown(saludo_html, unsafe_allow_html=True)

    html_copy_button("Copiar", fecha_html + cuerpo_html + saludo_html, key="copy_decom_ct")

# ───── TAB 15 : Comisaría Traslado ─────────────────────────────
with tabs[15]:
    loc_a  = dialog_link(loc, 'loc')
    fecha  = fecha_alineada(loc_a, punto=True)

    fecha_html = f"<p align='right' style='{LINE_STYLE}'>{fecha}</p>"
    st.markdown(fecha_html, unsafe_allow_html=True)

    car_a       = f"<b>{dialog_link(caratula,'carat')}</b>"
    trib_a      = f"<b>{dialog_link(tribunal,'trib')}</b>"
    sent_n      = dialog_link(sent_num,'snum')
    sent_f      = dialog_link(sent_fecha,'sfecha')
    res         = res_decomiso()
    res_a       = dialog_link(res,'sres')
    firm_a      = dialog_link(firmantes,'sfirmantes')
    rodado_a    = dialog_link(rodado,'rodado')
    comisaria_a = dialog_link(comisaria,'comisaria')

    cuerpo_html = "".join([
        f"<p align='justify' style='{LINE_STYLE}'><b>AL SR. TITULAR</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>DE LA COMISARÍA N° {comisaria_a} </b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>DE LA POLICÍA DE CÓRDOBA</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>S/D:</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'>En los autos caratulados: {car_a}, que se tramitan por ante {trib_a}, con intervención de esta <b>Oficina de Servicios Procesales</b> <b>- OSPRO -</b>, se ha dispuesto librar a Ud. el presente, a los fines de solicitarle que personal a su cargo Traslade los efectos que a continuación se detallan al Depósito General de Efectos Secuestrados -sito en calle Abdel Taier n° 270, B° Comercial, de esta ciudad de Córdoba-, para que sean allí recibidos:</p>",
        f"<p align='justify' style='{LINE_STYLE}'>{rodado_a}</p>",
        f"<p align='justify' style='{LINE_STYLE}'>Lo solicitado obedece a directivas generales impartidas por la Secretaría Penal del T.S.J, de la cual depende esta Oficina, para los casos en los que se haya dictado la pena de decomiso y los objetos aún estén en las Comisarías, Subcomisarías y otras dependencias policiales.</p>",
        f"<p align='justify' style='{LINE_STYLE}'>Se transcribe a continuación la parte pertinente de la Sentencia que así lo ordena:</p>",
        f"<p align='justify' style='{LINE_STYLE}'>Sentencia N° {sent_n} de fecha {sent_f}, &ldquo;{res_a}&rdquo;. (Fdo.: {firm_a}), elemento/s que fuera/n secuestrado/s en las presentes actuaciones y que actualmente se encuentra/n en el Depósito de la Comisaría a su cargo.</p>",
    ])
    st.markdown(cuerpo_html, unsafe_allow_html=True)

    saludo_html = f"<p align='center' style='{LINE_STYLE}'>Sin otro particular, saludo a Ud. muy atentamente.</p>"
    st.markdown(saludo_html, unsafe_allow_html=True)

    html_copy_button("Copiar", fecha_html + cuerpo_html + saludo_html, key="copy_comis_trasl")

# ───── TAB 16 : Decomiso Sin Traslado ─────────────────────────
with tabs[16]:
    loc_a  = dialog_link(loc, 'loc')
    fecha  = fecha_alineada(loc_a, punto=True)

    fecha_html = f"<p align='right' style='{LINE_STYLE}'>{fecha}</p>"
    st.markdown(fecha_html, unsafe_allow_html=True)

    car_a      = f"<b>{dialog_link(caratula,'carat')}</b>"
    trib_a     = f"<b>{dialog_link(tribunal,'trib')}</b>"
    sent_n     = dialog_link(sent_num,'snum')
    sent_f     = dialog_link(sent_fecha,'sfecha')
    res        = res_decomiso()
    res_a      = dialog_link(res,'sres')
    firm_a     = dialog_link(firmantes,'sfirmantes')
    rodado_a   = dialog_link(rodado,'rodado')
    deposito_a = dialog_link(deposito,'deposito')

    cuerpo_html = "".join([
        f"<p align='justify' style='{LINE_STYLE}'><b>A LA SRA. SECRETARIA PENAL</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>DEL TRIBUNAL SUPERIOR DE JUSTICIA</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>DRA. MARIA PUEYRREDON DE MONFARRELL</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'><b>S______/_______D:</b></p>",
        f"<p align='justify' style='{LINE_STYLE}'>En los autos caratulados: {car_a}, que se tramitan por ante {trib_a}, con conocimiento e intervención de esta <b>Oficina de Servicios</b> <b>Procesales ‑ OSPRO ‑</b>, se ha dispuesto librar a Ud. el presente a fin de poner en conocimiento lo resuelto por la Sentencia N° {sent_n} del {sent_f}, dictada por la Cámara mencionada, en virtud de la cual se ordenó el <b>DECOMISO</b> de los siguientes objetos:</p>",
        f"<table border='1' cellspacing='0' cellpadding='2'><tr><th>TIPOS DE ELEMENTOS</th><th>UBICACIÓN ACTUAL</th></tr><tr><td>{rodado_a}</td><td>{deposito_a}</td></tr></table>",
        f"<p align='justify' style='{LINE_STYLE}'>Pongo en su conocimiento que la mencionada resolución se encuentra firme, transcribiéndose a continuación la parte pertinente de la misma: &ldquo;SE RESUELVE: {res_a}&rdquo;. (Fdo.: {firm_a}).</p>",
    ])
    st.markdown(cuerpo_html, unsafe_allow_html=True)

    saludo_html = f"<p align='center' style='{LINE_STYLE}'>Sin otro particular, saludo a Ud. muy atentamente.</p>"
    st.markdown(saludo_html, unsafe_allow_html=True)

    html_copy_button("Copiar", fecha_html + cuerpo_html + saludo_html, key="copy_decom_st")
