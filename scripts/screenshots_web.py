"""Captura screenshots do frontend web (precisa da API rodando em localhost:8000).

Uso: uvicorn app.api:app --port 8000   e, em outro terminal,   python scripts/screenshots_web.py
Usa o Microsoft Edge instalado via Playwright (troque channel para usar outro navegador).
"""
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import sync_playwright

BASE = "http://localhost:8000"
OUT = Path(__file__).resolve().parents[1] / "reports" / "screenshots" / "web"
OUT.mkdir(parents=True, exist_ok=True)


def settle(page, ms=1500):
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(ms)  # animações dos gráficos


def shot_full(page, path, width=1440):
    """Página inteira com a barra lateral fixa: aumenta a janela até a altura do conteúdo."""
    h = page.evaluate("document.documentElement.scrollHeight")
    page.set_viewport_size({"width": width, "height": h})
    page.wait_for_timeout(1200)  # gráficos se redimensionam
    page.screenshot(path=str(path))
    page.set_viewport_size({"width": width, "height": 900})


with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge")
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
    page = ctx.new_page()

    def ask(name, q, full=True):
        page.goto(f"{BASE}/?q={quote(q)}#consulta")
        page.locator("#s-scope").filter(has_not_text="—").wait_for(timeout=60_000)
        settle(page)
        if full:
            shot_full(page, OUT / f"{name}.png")
        else:
            page.screenshot(path=str(OUT / f"{name}.png"))
        print("ok", name)

    ask("01_consulta_titular", "Quais direitos o titular pode exigir do controlador, como correção e portabilidade?")
    ask("02_consulta_cdc", "Qual o prazo para desistir de uma compra feita pela internet?")
    ask("03_consulta_falha", "A empresa sofreu um vazamento de dados. Ela precisa avisar a ANPD e os titulares?")
    ask("04_fora_de_escopo", "Qual é a receita de bolo de cenoura com cobertura de chocolate?", full=False)

    page.goto(f"{BASE}/#painel")
    page.locator("#o-chunks").filter(has_not_text="—").wait_for(timeout=60_000)
    settle(page, 2500)
    shot_full(page, OUT / "05_painel.png")
    print("ok 05_painel")

    page.goto(f"{BASE}/#avaliacao")
    page.locator("#ev-body tr.is-click").first.wait_for(timeout=60_000)
    page.select_option("#ev-filter", "miss")
    settle(page, 500)
    shot_full(page, OUT / "06_avaliacao_erros.png")
    print("ok 06_avaliacao_erros")


    # celular, tema claro
    mob = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True)
    mob.add_init_script("try { localStorage.setItem('ek-theme', 'light'); } catch (e) {}")
    m = mob.new_page()
    m.goto(f"{BASE}/?q={quote('O que a LGPD considera dado pessoal sensível?')}#consulta")
    m.locator("#s-scope").filter(has_not_text="—").wait_for(timeout=60_000)
    settle(m)
    m.locator("#r-stats").scroll_into_view_if_needed()
    m.wait_for_timeout(500)
    m.screenshot(path=str(OUT / "07_mobile_claro.png"))
    print("ok 07_mobile_claro")
    browser.close()
