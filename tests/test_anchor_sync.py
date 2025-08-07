import pytest
from pathlib import Path

pytest.importorskip('playwright.sync_api')
from playwright.sync_api import sync_playwright


def test_anchor_updates_input_when_blurred():
    js = Path(__file__).resolve().parents[1] / 'inline_edit.js'
    script = js.read_text()
    html = f"""<!DOCTYPE html><html><body>
    <input id='campo' value=''>
    <div id='container'></div>
    <script>{script}</script>
    <script>
    const span = document.createElement('span');
    span.setAttribute('contenteditable','true');
    span.dataset.target = 'campo';
    document.getElementById('container').appendChild(span);
    </script>
    </body></html>"""
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception:
            pytest.skip('chromium not available')
        page = browser.new_page()
        page.set_content(html)
        span = page.locator('[contenteditable]')
        span.fill('nuevo')
        span.evaluate('el => el.blur()')
        value = page.eval_on_selector('#campo', 'el => el.value')
        browser.close()
    assert value == 'nuevo'


def test_anchor_updates_input_with_ctrl_enter():
    js = Path(__file__).resolve().parents[1] / 'inline_edit.js'
    script = js.read_text()
    html = f"""<!DOCTYPE html><html><body>
    <input id='campo' value=''>
    <div id='container'></div>
    <script>{script}</script>
    <script>
    const span = document.createElement('span');
    span.setAttribute('contenteditable','true');
    span.dataset.target = 'campo';
    document.getElementById('container').appendChild(span);
    </script>
    </body></html>"""
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception:
            pytest.skip('chromium not available')
        page = browser.new_page()
        page.set_content(html)
        span = page.locator('[contenteditable]')
        span.fill('nuevo')
        span.press('Control+Enter')
        value = page.eval_on_selector('#campo', 'el => el.value')
        browser.close()
    assert value == 'nuevo'
