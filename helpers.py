import html


def anchor(texto: str, clave: str, placeholder: str = None) -> str:
    """Devuelve un enlace HTML plano"""
    if not texto.strip():
        texto = placeholder or f"[{clave}]"
    style = (
            "color:black;text-decoration:none;",
        "font-family:'Times New Roman';font-size:12pt;",
    )
    style_str = "".join(style)
    safe = html.escape(texto).replace("\n", "<br/>")
    return f'<a href="{clave}" style="{style_str}">{safe}</a>'


def anchor_html(html_text: str, clave: str, placeholder: str = None) -> str:
    """Igual que anchor pero conserva etiquetas básicas"""
    if not html_text.strip():
        return anchor("", clave, placeholder)
    style = (
        "color:black;text-decoration:none;",
        "font-family:'Times New Roman';font-size:12pt;",
    )
    style_str = "".join(style)
    safe = html_text.replace("\n", "<br/>")
    return f'<a href="{clave}" style="{style_str}">{safe}</a>'


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
