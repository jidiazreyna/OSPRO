import html


def anchor(texto: str, clave: str, placeholder: str = None) -> str:
    """Devuelve un enlace HTML plano"""
    if not texto.strip():
        texto = placeholder or f"[{clave}]"
    style = (
        "color:blue;text-decoration:none;"
        "font-family:'Times New Roman';font-size:12pt;"
    )
    safe = html.escape(texto).replace("\n", "<br/>")
    return f'<a href="{clave}" style="{style}">{safe}</a>'


def anchor_html(html_text: str, clave: str, placeholder: str = None) -> str:
    """Igual que anchor pero conserva etiquetas básicas"""
    if not html_text.strip():
        return anchor("", clave, placeholder)
    style = (
        "color:blue;text-decoration:none;"
        "font-family:'Times New Roman';font-size:12pt;"
    )
    safe = html_text.replace("\n", "<br/>")
    return f'<a href="{clave}" style="{style}">{safe}</a>'