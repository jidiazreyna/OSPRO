import html
import re


def dialog_link(texto: str, clave: str, placeholder: str | None = None) -> str:
    """Return a clickable link used to trigger dialogs.

    The element is rendered as ``<a class="dlg-link" data-key="...">`` so that
    both the PySide6 application (which relies on ``href`` attributes) and the
    web frontend can intercept clicks without recargar la página ni abrir una
    pestaña nueva.
    """

    if not texto.strip():
        texto = placeholder or f"[{clave}]"
    safe = html.escape(texto).replace("\n", "<br/>")
    style = "color:blue;text-decoration:none;cursor:pointer;"
    return (
        f'<a class="dlg-link" data-key="{clave}" href="{clave}" '
        f'style="{style}">{safe}</a>'
    )


def dialog_link_html(html_text: str, clave: str, placeholder: str | None = None) -> str:
    """Igual que :func:`dialog_link` pero conserva etiquetas básicas."""

    if not html_text.strip():
        return dialog_link("", clave, placeholder)
    style = (
        "color:blue;text-decoration:none;cursor:pointer;",
        "font-family:'Times New Roman';font-size:12pt;",
    )
    style_str = "".join(style)
    safe = html_text.replace("\n", "<br/>")
    return (
        f'<a class="dlg-link" data-key="{clave}" href="{clave}" '
        f'style="{style_str}">{safe}</a>'
    )


def strip_dialog_links(html_text: str) -> str:
    """Return ``html_text`` without ``a.dlg-link`` elements."""

    pattern = r"<a[^>]*class=['\"]dlg-link['\"][^>]*>(.*?)</a>"
    return re.sub(pattern, r"\1", html_text, flags=re.DOTALL)


def _strip_dialog_styles(html_text: str) -> str:
    """Remove inline styles and ``<u>`` tags from dialog triggers."""

    html_text = re.sub(
        r"(<a[^>]*class=['\"]dlg-link['\"][^>]*?)\s+style=(\"[^\"]*\"|'[^']*')",
        r"\1",
        html_text,
        flags=re.IGNORECASE,
    )
    html_text = re.sub(r"</?u[^>]*>", "", html_text, flags=re.IGNORECASE)
    return html_text


def strip_color(html_text: str) -> str:
    """Remove CSS ``color`` declarations so text defaults to black."""

    return re.sub(r"(?<!-)color\s*:[^;\"']*;?", "", html_text, flags=re.IGNORECASE)


def create_clipboard_html(html_data: str) -> str:
    """Return ``html_data`` packaged for the Windows clipboard."""

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

