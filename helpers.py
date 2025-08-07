# helpers.py
import html
import re

def dialog_link(texto: str, key: str, placeholder: str | None = None, *, bold: bool = False) -> str:
    """Return an editable HTML span linked to ``key``.

    ``texto`` es el contenido inicial.  Si está vacío, se mostrará
    ``placeholder`` (o puntos suspensivos si tampoco se provee un
    placeholder).  El ``key`` se replica en los atributos ``data-key`` y
    ``data-target`` para que ``inline_edit.js`` pueda sincronizar el valor
    con el campo correspondiente cuando el usuario presiona ``Ctrl+Enter``
    o el elemento pierde el foco.
    """

    contenido = texto.strip()
    if not contenido:
        contenido = placeholder if placeholder is not None else "…"

    safe = html.escape(contenido)
    span = (
        f'<span contenteditable="true" '
        f'spellcheck="false" '
        f'class="editable" '
        f'style="color:blue;" '
        f'data-origin="" '  # 👈 seguimiento origen
        f'data-key="{key}" data-target="{key}">{safe}</span>'
    )
    return f"<b>{span}</b>" if bold else span

def dialog_link_html(html_text: str, clave: str, placeholder: str | None = None) -> str:
    """Igual que :func:dialog_link pero conserva etiquetas básicas."""

    if not html_text.strip():
        return dialog_link("", clave, placeholder)
    style = (
        "color:blue;",
        "font-family:'Times New Roman';font-size:12pt;",
    )
    style_str = "".join(style)
    safe = html_text.replace("\n", "<br/>")
    return (
        f'<span class="editable" data-key="{clave}" data-target="{clave}" '
        f'data-origin="" contenteditable="true" style="{style_str}">{safe}</span>'
    )  # 👈 origen sincronizado

def strip_dialog_links(html_text: str) -> str:
    """Return `html_text without span.editable elements."""

    pattern = r"<span[^>]*class=['\"]editable['\"][^>]*>(.*?)</span>"
    return re.sub(pattern, r"\1", html_text, flags=re.DOTALL)

def _strip_dialog_styles(html_text: str) -> str:
    """Remove inline styles and `<u> tags from editable spans."""

    html_text = re.sub(
        r"(<span[^>]*class=['\"]editable['\"][^>]*?)\s+style=(\"[^\"]*\"|'[^']*')",
        r"\1",
        html_text,
        flags=re.IGNORECASE,
    )
    html_text = re.sub(r"</?u[^>]*>", "", html_text, flags=re.IGNORECASE)
    return html_text

def strip_color(html_text: str) -> str:
    """Remove CSS `color declarations so text defaults to black."""

    return re.sub(r"(?<!-)color\s*:[^;\"']*;?", "", html_text, flags=re.IGNORECASE)

def create_clipboard_html(html_data: str) -> str:
    """Return `html_data packaged for the Windows clipboard."""

    start_marker = "<!--StartFragment-->"
    end_marker = "<!--EndFragment-->"

    start_fragment = html_data.find(start_marker)
    end_fragment = html_data.find(end_marker)

    if start_fragment == -1:
        start_fragment = 0
    else:
        start_fragment += len(start_marker)

    if end_fragment == -1:
        end_fragment = len(html_data)

    html_header = """Version:0.9
StartHTML:{0:010d}
EndHTML:{1:010d}
StartFragment:{2:010d}
EndFragment:{3:010d}
StartSelection:{2:010d}
EndSelection:{3:010d}
"""

    html_bytes = html_data.encode("utf-8")
    temp_header = html_header.format(0, 0, 0, 0)
    start_html = len(temp_header)
    end_html = start_html + len(html_bytes)

    fragment_start = start_html + start_fragment
    fragment_end = start_html + end_fragment

    final_header = html_header.format(
        start_html, end_html, fragment_start, fragment_end
    )
    return final_header + html_data

# --- Aliases for backward compatibility ---------------------------------
anchor = dialog_link
anchor_html = dialog_link_html
strip_anchors = strip_dialog_links
_strip_anchor_styles = _strip_dialog_styles
