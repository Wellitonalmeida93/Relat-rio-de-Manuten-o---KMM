from playwright.sync_api import sync_playwright
import pandas as pd
import requests
import time
import os

# Webhook da Nova Planilha de Manutenção Externa
URL_WEBHOOK = "https://script.google.com/macros/s/AKfycbzhscaxcYlRi5urF2Rtp13Uv4T9eKQGWSgk-bSL1di7dtRVGdn-hZRWCMuHULKVGtGOXw/exec"

def executar_robo_manutencao_externa():
    print("🚀 Iniciando Robô: Relatório de Manutenção Externa...")
    
    # Credenciais (Pega do GitHub Secrets na nuvem ou usa o padrão localmente)
    usuario = os.environ.get("KMM_USER", "matheusd")
    senha = os.environ.get("KMM_PASS", "328254Ma")

    with sync_playwright() as p:
        # headless=True para execução otimizada
        navegador = p.chromium.launch(headless=True)
        contexto = navegador.new_context()
        pagina = contexto.new_page()

        print("1. Acessando o KMM e efetuando login...")
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
                    break
                else:
                    opcao = frame.get_by_text("--Manutenção Externa--", exact=False).first
                    if opcao.is_visible(timeout=1000):
                        opcao.click(force=True)
                        break
            except:
                continue

        time.sleep(2)

        print("4. Clicando no botão 'Confirmar' no final da tela...")
        for frame in pagina.frames:
            try:
                btn_confirmar = frame.get_by_text("Confirmar", exact=False).first
                if btn_confirmar.is_visible(timeout=1000):
                    btn_confirmar.scroll_into_view_if_needed()
                    btn_confirmar.click(force=True)
                    break
            except:
                continue

        print("5. Aguardando o KMM carregar os dados...")
        pagina.wait_for_load_state("networkidle")
        time.sleep(8)

        print("6. Rolando a tela para carregar todos os registros...")
        for _ in range(15):
            pagina.keyboard.press("PageDown")
            time.sleep(0.15)
            for f in pagina.frames:
                try:
                    f.evaluate("window.scrollBy(0, 1000);")
                    f.evaluate("let s = document.querySelector('.x-grid3-scroller'); if(s) s.scrollTop += 1000;")
                except:
                    pass

        time.sleep(2)

        print("7. Capturando a tabela da tela...")
        linhas_brutas = []
        for frame in pagina.frames:
            try:
                texto_completo = frame.locator("body").inner_text()
                if texto_completo and len(texto_completo) > 100:
                    linhas = texto_completo.split("\n")
                    for l in linhas:
                        l_limpa = l.strip()
                        if l_limpa:
                            partes = [p.strip() for p in l_limpa.split("\t") if p.strip()]
                            if not partes:
                                partes = [l_limpa]
                            linhas_brutas.append(partes)
            except:
                continue

        navegador.close()

        print("8. Tratando dados e localizando o cabeçalho dinâmico...")
        if linhas_brutas:
            max_cols = max(len(linha) for linha in linhas_brutas)
            linhas_padronizadas = [linha + [""] * (max_cols - len(linha)) for linha in linhas_brutas]
            
            df_temp = pd.DataFrame(linhas_padronizadas)

            # Localiza a linha do cabeçalho
            idx_cabecalho = None
            for idx, row in df_temp.iterrows():
                valores_linha = [str(v).strip().lower() for v in row.values]
                if "frota" in valores_linha and ("num. os" in valores_linha or "placa" in valores_linha):
                    idx_cabecalho = idx
                    break

            if idx_cabecalho is not None:
                # Corta tudo acima do cabeçalho
                df = df_temp.iloc[idx_cabecalho:].reset_index(drop=True)
                df.columns = [str(c).strip() for c in df.iloc[0].values]
                df = df.iloc[1:].reset_index(drop=True)

                # Limpeza final
                df = df[df[df.columns[0]] != df.columns[0]]
                df.fillna("", inplace=True)
                df.dropna(how='all', inplace=True)
                df.drop_duplicates(inplace=True)
                df.reset_index(drop=True, inplace=True)

                # Prepara matriz de dados (Cabeçalho + Linhas) para envio via JSON
                dados_envio = [df.columns.tolist()] + df.values.tolist()

                print(f"9. Enviando {len(df)} registros para o Google Sheets...")
                resposta = requests.post(URL_WEBHOOK, json={"dados": dados_envio})

                if resposta.status_code == 200 and "Sucesso" in resposta.text:
                    print("\n==================================================")
                    print(" ✨ PLANILHA ONLINE ATUALIZADA COM SUCESSO!")
                    print(f" 📊 Total de registros enviados: {len(df)}")
                    print("==================================================")
                else:
                    print(f"\n[ERRO] Falha ao enviar para o Google Sheets: {resposta.text}")
            else:
                print("\n[ERRO] Cabeçalho com 'Frota' não foi encontrado na tabela.")
        else:
            print("\n[ERRO] Nenhum dado capturado da página.")

if __name__ == "__main__":
    executar_robo_manutencao_externa()
