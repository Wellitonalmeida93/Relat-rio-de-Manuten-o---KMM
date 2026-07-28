from playwright.sync_api import sync_playwright
import pandas as pd
import requests
import time
import os
import re

URL_WEBHOOK_PRINCIPAL = "https://script.google.com/macros/s/AKfycbwYy133M99sXk_d1yIsH68eIAnw-a4MUnCsk0YvN33h_lP6kX8-H-3y_l0wP_R3Z08m/exec"

def extrair_numero(valor):
    """Extrai apenas o número (positivo ou negativo) de um texto."""
    if not valor or str(valor).strip().upper() in ["NÃO CONTROLADA", "NAO CONTROLADA", "NAN", ""]:
        return 999999
    val_limpo = str(valor).replace('.', '').strip()
    match = re.search(r'(-?\d+)', val_limpo)
    if match:
        return int(match.group(1))
    return 999999

def executar_robo_principal():
    print("🚀 Iniciando Robô 1: Painel de Manutenção KMM...")
    
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

        print("2. Navegando até 'Painel de Manutenção'...")
        clicar_menu("Manutenção de Veículos")
        pagina.wait_for_load_state("networkidle")
        time.sleep(2)

        clicar_menu("Painel de Manutenção")
        pagina.wait_for_load_state("networkidle")
        time.sleep(8)

        print("3. Extraindo colunas visíveis da grade ExtJS...")
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

        if dados_capturados:
            headers = dados_capturados['headers']
            rows = dados_capturados['rows']

            df = pd.DataFrame(rows, columns=headers if len(headers) == len(rows[0]) else None)
            if df.columns.tolist() == list(range(len(df.columns))):
                df.columns = [f"Col_{i}" for i in range(len(df.columns))]

            print(f"   -> Encontrados {len(df)} registros com alinhamento correto!")

            # Identifica as colunas chaves
            col_dias = next((c for c in df.columns if 'dia' in str(c).lower()), None)
            col_km = next((c for c in df.columns if 'km' in str(c).lower() or 'hor' in str(c).lower()), None)
            col_tabela = next((c for c in df.columns if any(p in str(c).lower() for p in ['tabela', 'plano', 'equipamento'])), None)

            dados_vencidas = [df.columns.tolist()]
            dados_a_vencer = [df.columns.tolist()]

            for _, row in df.iterrows():
                val_dias = extrair_numero(row[col_dias]) if col_dias else 999999
                val_km = extrair_numero(row[col_km]) if col_km else 999999
                tabela_plano = str(row[col_tabela]).upper() if col_tabela else ""

                # 1. Regra de Vencidas (Qualquer valor negativo)
                if val_dias < 0 or val_km < 0:
                    dados_vencidas.append(row.tolist())
                    continue

                # 2. Regra de À Vencer
                # 🚨 EXCEÇÃO: Carreta Baú 60k -> Avalia APENAS DIAS
                if "SEMI REBOQUE BAU - 60.000 KM" in tabela_plano or "BAU - 60.000" in tabela_plano:
                    if 0 <= val_dias <= 15:
                        dados_a_vencer.append(row.tolist())
                # DEMAIS VEÍCULOS: Avalia DIAS (0 a 15) OU KM (0 a 1000)
                else:
                    if (0 <= val_dias <= 15) or (0 <= val_km <= 1000):
                        dados_a_vencer.append(row.tolist())

            print(f"4. Enviando -> Vencidas: {len(dados_vencidas)-1} | À Vencer: {len(dados_a_vencer)-1}")

            payload = {
                "vencidas": dados_vencidas,
                "a_vencer": dados_a_vencer
            }

            resposta = requests.post(URL_WEBHOOK_PRINCIPAL, json=payload)
            if resposta.status_code == 200 and "Sucesso" in resposta.text:
                print(" ✨ PLANILHA PRINCIPAL ATUALIZADA COM SUCESSO!")
            else:
                print(f"[ERRO Webhook]: {resposta.text}")
        else:
            print("[ERRO] Nenhuma linha foi extraída do KMM.")

if __name__ == "__main__":
    executar_robo_principal()
