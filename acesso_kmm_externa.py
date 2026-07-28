from playwright.sync_api import sync_playwright
import pandas as pd
import requests
import time
import os

# 🔗 URL do Webhook da Planilha Externa
URL_WEBHOOK_EXTERNA = "https://script.google.com/macros/s/AKfycbwUY4i91G2lGbXMua7HyC2LLK4Rkkp5-z4zYCec_NKe9EVHHH1mznGne7uSQP-nOXYJJA/exec"

def executar_robo_manutencao_externa():
    print("🚀 Iniciando Robô 2: Relatório de Manutenção Externa...")
    
    usuario = os.environ.get("KMM_USER", "matheusd")
    senha = os.environ.get("KMM_PASS", "328254Ma")

    with sync_playwright() as p:
        navegador = p.chromium.launch(headless=True)
        # Resolução Full HD obrigatória
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
            try:
                pagina.get_by_text(texto, exact=False).first.click(force=True)
                return True
            except:
                return False

        print("2. Navegando até 'Veículos em manutenção'...")
        clicar_menu("Manutenção de Veículos")
        pagina.wait_for_load_state("networkidle")
        time.sleep(2)

        clicar_menu("Veículos em manutenção")
        pagina.wait_for_load_state("networkidle")
        
        # Pausa crucial para os frames internos terminarem de renderizar
        print("   -> Aguardando formulário da tela carregar...")
        time.sleep(6)

        print("3. Selecionando '--Manutenção Externa--'...")
        selecionado = False

        for frame in pagina.frames:
            try:
                # Espera a presença do texto 'Filial' ou select no frame
                txt_frame = frame.locator("body").inner_text(timeout=2000)
                if "FILIAL" in txt_frame.upper() or "EXTERNA" in txt_frame.upper():
                    
                    # Tentativa 1: Seleção direta via API do Playwright
                    selects = frame.locator("select").all()
                    for sel in selects:
                        try:
                            sel.select_option(label="--Manutenção Externa--", timeout=2000)
                            sel.dispatch_event("change")
                            selecionado = True
                            print("   -> Seleção realizada com sucesso via Playwright!")
                            break
                        except:
                            pass

                    # Tentativa 2: JS Nativo varrendo as opções
                    if not selecionado:
                        res = frame.evaluate('''() => {
                            let selects = document.querySelectorAll('select');
                            for (let sel of selects) {
                                for (let i = 0; i < sel.options.length; i++) {
                                    let txt = sel.options[i].text.toUpperCase();
                                    if (txt.includes('MANUTENÇÃO EXTERNA') || txt.includes('MANUTENCAO EXTERNA') || txt.includes('EXTERNA')) {
                                        sel.selectedIndex = i;
                                        sel.dispatchEvent(new Event('change', { bubbles: true }));
                                        sel.dispatchEvent(new Event('blur', { bubbles: true }));
                                        return sel.options[i].text;
                                    }
                                }
                            }
                            return null;
                        }''')
                        if res:
                            selecionado = True
                            print(f"   -> Seleção realizada via JS: '{res}'")
                            break
            except:
                continue

            if selecionado:
                break

        if not selecionado:
            print("   [AVISO] Tentando selecionar por clique no elemento do ExtJS...")
            for frame in pagina.frames:
                try:
                    trigger = frame.locator(".x-form-arrow-trigger, input").first
                    if trigger.is_visible(timeout=1000):
                        trigger.click(force=True)
                        time.sleep(1)
                        opcao = frame.get_by_text("--Manutenção Externa--", exact=False).first
                        if opcao.is_visible(timeout=1000):
                            opcao.click(force=True)
                            selecionado = True
                            print("   -> Seleção realizada via clique no Combo ExtJS!")
                            break
                except:
                    continue

        time.sleep(2)

        print("4. Clicando no botão 'Confirmar'...")
        confirmado = False
        for frame in pagina.frames:
            try:
                res = frame.evaluate('''() => {
                    let btns = document.querySelectorAll('button, input[type="button"], input[type="submit"], a, span, div, td');
                    for (let b of btns) {
                        if (b.innerText && b.innerText.trim().toUpperCase() === 'CONFIRMAR') {
                            b.click();
                            return true;
                        }
                    }
                    return false;
                }''')
                if res:
                    confirmado = True
                    print("   -> Botão 'Confirmar' clicado com sucesso via DOM!")
                    break
            except:
                continue

        if not confirmado:
            try:
                pagina.get_by_text("Confirmar", exact=False).first.click(force=True)
            except:
                pass

        print("5. Aguardando a busca e renderização dos dados...")
        pagina.wait_for_load_state("networkidle")
        time.sleep(12)

        # Rola o scroll interno da grade ExtJS para carregar todas as linhas
        for _ in range(6):
            for f in pagina.frames:
                try:
                    f.evaluate("let s = document.querySelector('.x-grid3-scroller'); if(s) { s.scrollTop += 500; }")
                except:
                    pass
            time.sleep(0.3)

        print("6. Extraindo dados da grade ExtJS...")
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

        if not dados_capturados:
            raise RuntimeError("❌ [ERRO CRÍTICO] Nenhuma linha foi encontrada na tabela do KMM. Verifique se existem registros de Manutenção Externa abertos no momento!")

        headers = dados_capturados['headers']
        rows = dados_capturados['rows']

        df = pd.DataFrame(rows, columns=headers if len(headers) == len(rows[0]) else None)
        if df.columns.tolist() == list(range(len(df.columns))):
            df.columns = [f"Col_{i}" for i in range(len(df.columns))]

        df.fillna("", inplace=True)
        df.drop_duplicates(inplace=True)

        dados_envio = [df.columns.tolist()] + df.values.tolist()

        print(f"7. Enviando {len(df)} registros para a Planilha Externa...")
        resposta = requests.post(URL_WEBHOOK_EXTERNA, json={"dados": dados_envio})

        if resposta.status_code != 200 or "Sucesso" not in resposta.text:
            raise RuntimeError(f"❌ [ERRO GOOGLE SHEETS] Falha no Webhook: Código {resposta.status_code} - Resposta: {resposta.text}")

        print(" ✨ PLANILHA ATUALIZADA COM SUCESSO NO GOOGLE SHEETS!")

if __name__ == "__main__":
    executar_robo_manutencao_externa()
