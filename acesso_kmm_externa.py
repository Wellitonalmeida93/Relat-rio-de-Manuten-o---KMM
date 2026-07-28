from playwright.sync_api import sync_playwright
import pandas as pd
import requests
import time
import os

URL_WEBHOOK_EXTERNA = "https://script.google.com/macros/s/AKfycbzhscaxcYlRi5urF2Rtp13Uv4T9eKQGWSgk-bSL1di7dtRVGdn-hZRWCMuHULKVGtGOXw/exec"

def executar_robo_manutencao_externa():
    print("🚀 Iniciando Robô 2: Relatório de Manutenção Externa...")
    
    usuario = os.environ.get("KMM_USER", "matheusd")
    senha = os.environ.get("KMM_PASS", "328254Ma")

    with sync_playwright() as p:
        navegador = p.chromium.launch(headless=True)
        contexto = navegador.new_context()
        pagina = contexto.new_page()

        print("1. Acessando o KMM e fazendo login...")
        pagina.goto("https://kmm.pizzattolog.com.br/index.cfm")
        pagina.locator("input[type='text']").first.fill(usuario)
        campo_senha = pagina.locator("input[type='password']").first
        campo_senha.fill(senha)
        campo_senha.press("Enter")

        pagina.wait_for_load_state("networkidle")
        time.sleep(3)

        def clicar_menu(texto):
            for frame in pagina.frames:
                try:
                    elem = frame.get_by_text(texto, exact=False).first
                    if elem.is_visible(timeout=1000):
                        elem.click(force=True)
                        return True
                except:
                    continue
            pagina.get_by_text(texto, exact=False).first.click(force=True)

        print("2. Navegando até 'Veículos em manutenção'...")
        clicar_menu("Manutenção de Veículos")
        pagina.wait_for_load_state("networkidle")
        time.sleep(2)

        clicar_menu("Veículos em manutenção")
        pagina.wait_for_load_state("networkidle")
        time.sleep(3)

        print("3. Selecionando '--Manutenção Externa--'...")
        for frame in pagina.frames:
            try:
                select_elem = frame.locator("select").first
                if select_elem.is_visible(timeout=1000):
                    select_elem.click(force=True)
                    select_elem.select_option(label="--Manutenção Externa--")
                    select_elem.dispatch_event("change")
                    select_elem.press("Enter")
                    break
                else:
                    opcao = frame.get_by_text("--Manutenção Externa--", exact=False).first
                    if opcao.is_visible(timeout=1000):
                        opcao.click(force=True)
                        break
            except:
                continue

        time.sleep(2)

        print("4. Clicando no botão 'Confirmar'...")
        for frame in pagina.frames:
            try:
                btn = frame.get_by_text("Confirmar", exact=False).first
                if btn.is_visible(timeout=1000):
                    btn.scroll_into_view_if_needed()
                    btn.click(force=True)
                    break
            except:
                continue

        print("5. Aguardando o KMM carregar os dados...")
        pagina.wait_for_load_state("networkidle")
        time.sleep(8)

        # Rolagem para carregar grid ExtJS
        for _ in range(10):
            for f in pagina.frames:
                try:
                    f.evaluate("let s = document.querySelector('.x-grid3-scroller'); if(s) s.scrollTop += 1000;")
                except:
                    pass
            time.sleep(0.2)

        print("6. Extraindo dados da grade ExtJS do KMM...")
        dados_capturados = None

        for frame in pagina.frames:
            try:
                res = frame.evaluate('''() => {
                    let hdCells = document.querySelectorAll('.x-grid3-header .x-grid3-hd-inner');
                    let headers = [];
                    hdCells.forEach(hd => {
                        let txt = hd.innerText.replace(/\\n/g, ' ').trim();
                        if (txt) headers.push(txt);
                    });

                    let rowElems = document.querySelectorAll('.x-grid3-row');
                    let rows = [];
                    rowElems.forEach(row => {
                        let cells = row.querySelectorAll('.x-grid3-cell-inner');
                        let rowData = [];
                        cells.forEach(c => rowData.push(c.innerText.trim()));
                        if (rowData.length > 0) rows.push(rowData);
                    });

                    return { headers: headers, rows: rows };
                }''')

                if res and res.get('rows') and len(res['rows']) > 0:
                    dados_capturados = res
                    break
            except:
                continue

        navegador.close()

        if dados_capturados:
            headers = dados_capturados['headers']
            rows = dados_capturados['rows']

            max_cols = max(len(r) for r in rows)
            rows_padronizadas = [r + [""] * (max_cols - len(r)) for r in rows]

            df = pd.DataFrame(rows_padronizadas)
            if len(headers) == max_cols:
                df.columns = headers
            else:
                df.columns = [f"Col_{i}" for i in range(max_cols)]

            df.fillna("", inplace=True)
            df.drop_duplicates(inplace=True)

            dados_envio = [df.columns.tolist()] + df.values.tolist()

            print(f"7. Enviando {len(df)} registros para a Planilha Externa...")
            resposta = requests.post(URL_WEBHOOK_EXTERNA, json={"dados": dados_envio})

            if resposta.status_code == 200 and "Sucesso" in resposta.text:
                print(" ✨ PLANILHA 2 ATUALIZADA COM SUCESSO!")
            else:
                print(f"[ERRO Webhook]: {resposta.text}")
        else:
            print("[ERRO] Nenhuma linha foi extraída do KMM.")

if __name__ == "__main__":
    executar_robo_manutencao_externa()
