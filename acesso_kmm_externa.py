from playwright.sync_api import sync_playwright
import pandas as pd
import requests
import time
import os

# 🔗 URL do Novo Webhook Implantado
URL_WEBHOOK_EXTERNA = "https://script.google.com/macros/s/AKfycbwUY4i91G2lGbXMua7HyC2LLK4Rkkp5-z4zYCec_NKe9EVHHH1mznGne7uSQP-nOXYJJA/exec"

def executar_robo_manutencao_externa():
    print("🚀 Iniciando Robô 2: Relatório de Manutenção Externa...")
    
    usuario = os.environ.get("KMM_USER", "matheusd")
    senha = os.environ.get("KMM_PASS", "328254Ma")

    with sync_playwright() as p:
        navegador = p.chromium.launch(headless=True)
        # Resolução Full HD obrigatória para a nuvem
        contexto = navegador.new_context(viewport={"width": 1920, "height": 1080})
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

        print("4. Clicando em 'Confirmar'...")
        for frame in pagina.frames:
            try:
                btn = frame.get_by_text("Confirmar", exact=False).first
                if btn.is_visible(timeout=1000):
                    btn.scroll_into_view_if_needed()
                    btn.click(force=True)
                    break
            except:
                continue

        pagina.wait_for_load_state("networkidle")
        time.sleep(10)

        print("5. Extraindo dados da grade ExtJS...")
        dados_capturados = None

        for frame in pagina.frames:
            try:
                res = frame.evaluate('''() => {
                    let hdCells = document.querySelectorAll('.x-grid3-header .x-grid3-hd-inner');
                    let headers = [];
                    let validIndices = [];

                    hdCells.forEach((hd, idx) => {
                        let txt = hd.innerText ? hd.innerText.replace(/\\n/g, ' ').trim() : '';
                        if (txt && !txt.includes('cancelBubble') && !txt.includes('ppmVEICU') && hd.offsetParent !== null) {
                            headers.push(txt);
                            validIndices.push(idx);
                        }
                    });

                    let rowElems = document.querySelectorAll('.x-grid3-row');
                    let rows = [];

                    rowElems.forEach(row => {
                        let cells = row.querySelectorAll('.x-grid3-cell-inner');
                        let rowData = [];
                        validIndices.forEach(i => {
                            if (cells[i]) {
                                rowData.push(cells[i].innerText.trim());
                            } else {
                                rowData.push('');
                            }
                        });
                        if (rowData.some(val => val !== '')) {
                            rows.push(rowData);
                        }
                    });

                    return { headers: headers, rows: rows };
                }''')

                if res and res.get('rows') and len(res['rows']) > 0:
                    dados_capturados = res
                    break
            except:
                continue

        navegador.close()

        # Trava de segurança: lança erro no GitHub Actions se vier zerado
        if not dados_capturados:
            raise RuntimeError("❌ [ERRO CRÍTICO] Nenhuma linha foi encontrada na tabela do KMM. Verifique se a busca carregou dados na tela!")

        headers = dados_capturados['headers']
        rows = dados_capturados['rows']

        df = pd.DataFrame(rows, columns=headers if len(headers) == len(rows[0]) else None)
        if df.columns.tolist() == list(range(len(df.columns))):
            df.columns = [f"Col_{i}" for i in range(len(df.columns))]

        df.fillna("", inplace=True)
        df.drop_duplicates(inplace=True)

        dados_envio = [df.columns.tolist()] + df.values.tolist()

        print(f"6. Enviando {len(df)} registros para a Planilha Externa...")
        resposta = requests.post(URL_WEBHOOK_EXTERNA, json={"dados": dados_envio})

        # Trava de segurança: lança erro no GitHub Actions se o Sheets rejeitar
        if resposta.status_code != 200 or "Sucesso" not in resposta.text:
            raise RuntimeError(f"❌ [ERRO GOOGLE SHEETS] Falha no Webhook: Código {resposta.status_code} - Resposta: {resposta.text}")

        print(" ✨ PLANILHA ATUALIZADA COM SUCESSO NO GOOGLE SHEETS!")

if __name__ == "__main__":
    executar_robo_manutencao_externa()
