import html


def anchor(texto: str, clave: str, placeholder: str = None) -> str:
    """Devuelve un enlace HTML plano.

    Además imprime el HTML generado para ayudar en la depuración del flujo
    de *anchor-links* dentro de la aplicación Streamlit.  De esta manera
    puede verificarse desde la consola si cada ``data-anchor`` se crea con
    la clave correcta.
    """
    if not texto.strip():
        texto = placeholder or f"[{clave}]"
    style = (
        "color:blue;text-decoration:none;",
        "font-family:'Times New Roman';font-size:12pt;",
    )
    style_str = "".join(style)
    safe = html.escape(texto).replace("\n", "<br/>")
    html_link = f'<a href="#" data-anchor="{clave}" onclick="return false;" style="{style_str}">{safe}</a>'
    print("HTML anchor:", html_link)
    return html_link


def anchor_html(html_text: str, clave: str, placeholder: str = None) -> str:
    """Igual que anchor pero conserva etiquetas básicas"""
    if not html_text.strip():
        return anchor("", clave, placeholder)
    style = (
        "color:blue;text-decoration:none;",
        "font-family:'Times New Roman';font-size:12pt;",
    )
    style_str = "".join(style)
    safe = html_text.replace("\n", "<br/>")
    return f'<a href="#" data-anchor="{clave}" onclick="return false;" style="{style_str}">{safe}</a>'


def strip_anchors(html_text: str) -> str:
    """Return ``html_text`` without ``<a>`` tags but keeping their content."""
    import re
    return re.sub(r"<a[^>]*>(.*?)</a>", r"\1", html_text, flags=re.DOTALL)


def _strip_anchor_styles(html: str) -> str:
    """Remove style attributes and ``<u>`` tags from anchor elements."""
    import re
    html = re.sub(
        r"(<a[^>]+?)\s+style=(\"[^\"]*\"|'[^']*')",
        r"\1",
        html,
        flags=re.IGNORECASE,
    )
    html = re.sub(r'</?u[^>]*>', '', html, flags=re.IGNORECASE)
    return html


def strip_color(html: str) -> str:
    """Remove CSS ``color`` declarations so text defaults to black."""
    import re
    return re.sub(r"(?<!-)color\s*:[^;\"']*;?", '', html, flags=re.IGNORECASE)


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
