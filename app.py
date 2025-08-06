# app.py  – versión resumida
import streamlit as st
import streamlit.components.v1 as components
from core import autocompletar   # ← función principal
from datetime import datetime
from helpers import anchor, strip_anchors


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

# ───────── helpers comunes ──────────────────────────────────────────
MESES_ES = ["enero","febrero","marzo","abril","mayo","junio",
            "julio","agosto","septiembre","octubre","noviembre","diciembre"]

# listado básico de tribunales para el cuadro de diálogo
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


# relación entre anchors y widgets a mostrar en el cuadro de diálogo
ANCHOR_FIELDS = {
    "caratula": ("Carátula", "text", "carat"),
    "tribunal": ("Tribunal", "select", "trib"),
    "snum": ("Sentencia N°", "text", "snum"),
    "sfecha": ("Fecha sentencia", "text", "sfecha"),
    "sfirmeza": ("Firmeza sentencia", "text", "sfirmeza"),
    "sres": ("Resuelvo", "textarea", "sres"),
    "sfirmaza": ("Firmantes", "text", "sfirmaza"),
    "imp0_datos": ("Datos personales", "textarea", "imp0_datos"),
    "consulado": ("Consulado", "text", "consulado"),
}


def _mostrar_dialogo(clave: str) -> None:
    campo = ANCHOR_FIELDS.get(clave)
    if not campo:
        return
    titulo, tipo, estado = campo
    valor_actual = st.session_state.get(estado, "")
    with st.modal(titulo):
        if tipo == "text":
            nuevo = st.text_input(titulo, valor_actual, key=f"dlg_{estado}")
        elif tipo == "textarea":
            nuevo = st.text_area(titulo, valor_actual, key=f"dlg_{estado}")
        elif tipo == "select":
            idx = TRIBUNALES.index(valor_actual) if valor_actual in TRIBUNALES else 0
            nuevo = st.selectbox(titulo, TRIBUNALES, index=idx, key=f"dlg_{estado}")
        else:
            nuevo = valor_actual
        col_a, col_b = st.columns(2)
        if col_a.button("Aceptar", key=f"ok_{estado}"):
            st.session_state[estado] = nuevo
            st.experimental_set_query_params()
            st.experimental_rerun()
        if col_b.button("Cancelar", key=f"cancel_{estado}"):
            st.experimental_set_query_params()
            st.experimental_rerun()

def fecha_alineada(loc: str, fecha=None, punto=False):
    d = fecha or datetime.now()
    txt = f"{loc}, {d.day} de {MESES_ES[d.month-1]} de {d.year}"
    return txt + ("." if punto else "")

# ───────── estado de sesión ─────────────────────────────────────────
if "n_imputados" not in st.session_state: st.session_state.n_imputados = 1
if "datos_autocompletados" not in st.session_state: st.session_state.datos_autocompletados = {}

# si hay un parámetro de consulta ``anchor`` mostramos el diálogo correspondiente
_params = st.experimental_get_query_params()
_anchor_clicked = _params.get("anchor", [None])[0]
if _anchor_clicked:
    _mostrar_dialogo(_anchor_clicked)

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

    car_a = f"<b>{anchor(caratula, 'caratula')}</b>"
    trib_a = f"<b>{anchor(tribunal, 'tribunal')}</b>"
    imp_a = anchor(st.session_state.get('imp0_datos',''), 'imp0_datos')
    sent_n_a = anchor(sent_num, 'snum')
    sent_f_a = anchor(sent_fecha, 'sfecha')
    res_a = anchor(resuelvo, 'sres')
    firm_a = anchor(firmantes, 'sfirmaza')
    sent_firmeza_a = anchor(sent_firmeza, 'sfirmeza')
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
        texto = strip_anchors(cuerpo + saludo).replace("<br>", "\n")
        copy_to_clipboard(texto)

# ---------- plantilla Consulado ----------
with tabs[1]:
    fecha_txt = fecha_alineada(loc, punto=True)
    st.markdown(f"<p style='text-align:right'>{fecha_txt}</p>", unsafe_allow_html=True)
    car_a = f"<b>{anchor(caratula, 'caratula')}</b>"
    trib_a = f"<b>{anchor(tribunal, 'tribunal')}</b>"
    pais_a = anchor(consulado, 'consulado')
    imp_a = anchor(st.session_state.get('imp0_datos',''), 'imp0_datos')
    sent_n_a = anchor(sent_num, 'snum')
    sent_f_a = anchor(sent_fecha, 'sfecha')
    res_a = anchor(resuelvo, 'sres')
    firm_a = anchor(firmantes, 'sfirmaza')
    sent_firmeza_a = anchor(sent_firmeza, 'sfirmeza')
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
        texto = strip_anchors(cuerpo + saludo).replace("<br>", "\n")
        copy_to_clipboard(texto)

# ---------- plantilla Juez Electoral ----------
with tabs[2]:
    fecha_txt = fecha_alineada(loc, punto=True)
    st.markdown(f"<p style='text-align:right'>{fecha_txt}</p>", unsafe_allow_html=True)
    car_a = f"<b>{anchor(caratula, 'caratula')}</b>"
    trib_a = f"<b>{anchor(tribunal, 'tribunal')}</b>"
    imp_a = anchor(st.session_state.get('imp0_datos',''), 'imp0_datos')
    sent_n_a = anchor(sent_num, 'snum')
    sent_f_a = anchor(sent_fecha, 'sfecha')
    res_a = anchor(resuelvo, 'sres')
    firm_a = anchor(firmantes, 'sfirmaza')
    sent_firmeza_a = anchor(sent_firmeza, 'sfirmeza')
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
        texto = strip_anchors(cuerpo + saludo).replace("<br>", "\n")
        copy_to_clipboard(texto)


# ───────── manejo de clics en anchors ───────────────────────────────
ANCHOR_JS = """
<script>
const doc = window.parent.document;
doc.addEventListener('click', function(e) {
  const a = e.target.closest('a[data-anchor]');
  if (a) {
    e.preventDefault();
    const params = new URLSearchParams(window.parent.location.search);
    params.set('anchor', a.getAttribute('data-anchor'));
    window.parent.location.search = params.toString();
  }
}, true);
</script>
"""
components.html(ANCHOR_JS, height=0, width=0)
