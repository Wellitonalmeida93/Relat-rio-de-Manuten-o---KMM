from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import pandas as pd
import requests
import time
import io
import os

# Webhook da Nova Planilha de Manutenção Externa
URL_WEBHOOK = "https://script.google.com/macros/s/AKfycbzhscaxcYlRi5urF2Rtp13Uv4T9eKQGWSgk-bSL1di7dtRVGdn-hZRWCMuHULKVGtGOXw/exec"

def executar_robo_manutencao_externa():
    print("🚀 Iniciando Robô: Relatório de Manutenção Externa...")
    
    usuario = os.environ.get("KMM_USER", "matheusd")
    senha = os.environ.get("KMM_PASS", "328254Ma")

    with sync_playwright() as p:
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

        print("7. Extraindo tabela de dados do KMM...")
        dfs_encontrados = []
        
        # Estratégia 1: Leitura de tabelas HTML puras
        for frame in pagina.frames:
            try:
                html_content = frame.content()
                if "Frota" in html_content or "Placa" in html_content:
                    tables = pd.read_html(io.StringIO(html_content))
                    for t in tables:
                        if len(t) > 0:
                            dfs_encontrados.append(t)
            except:
                continue

        # Estratégia 2: Fallback por texto bruto caso não ache tabela HTML
        if not dfs_encontrados:
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
            
            if linhas_brutas:
                max_cols = max(len(linha) for linha in linhas_brutas)
                linhas_padronizadas = [linha + [""] * (max_cols - len(linha)) for linha in linhas_brutas]
                dfs_encontrados.append(pd.DataFrame(linhas_padronizadas))

        navegador.close()

        print("8. Processando e limpando o relatório...")
        df_final = None

        for df_temp in dfs_encontrados:
            # Procura a linha que contém o cabeçalho 'Frota'
            idx_cabecalho = None
            for idx, row in df_temp.iterrows():
                texto_linha = " ".join([str(v).lower() for v in row.values])
                if "frota" in texto_linha and ("placa" in texto_linha or "os" in texto_linha or "oficina" in texto_linha):
                    idx_cabecalho = idx
                    break

            if idx_cabecalho is not None:
                # Corta tudo acima do cabeçalho
                df_certo = df_temp.iloc[idx_cabecalho:].reset_index(drop=True)
                df_certo.columns = [str(c).strip() for c in df_certo.iloc[0].values]
                df_certo = df_certo.iloc[1:].reset_index(drop=True)
                
                # Remove linhas duplicadas de cabeçalho e vazias
                df_certo = df_certo[df_certo[df_certo.columns[0]].astype(str).str.lower() != str(df_certo.columns[0]).lower()]
                df_certo.fillna("", inplace=True)
                df_certo.dropna(how='all', inplace=True)
                df_certo.drop_duplicates(inplace=True)
                df_certo.reset_index(drop=True, inplace=True)
                
                df_final = df_certo
                break

        if df_final is not None and len(df_final) > 0:
            # Prepara matriz para envio
            dados_envio = [df_final.columns.tolist()] + df_final.values.tolist()

            print(f"9. Enviando {len(df_final)} registros para o Google Sheets...")
            resposta = requests.post(URL_WEBHOOK, json={"dados": dados_envio})

            if resposta.status_code == 200 and "Sucesso" in resposta.text:
                print("\n==================================================")
                print(" ✨ PLANILHA ONLINE ATUALIZADA COM SUCESSO!")
                print(f" 📊 Total de registros enviados: {len(df_final)}")
                print("==================================================")
            else:
                print(f"\n[ERRO] Falha ao enviar para o Google Sheets: {resposta.text}")
        else:
            print("\n[ERRO] Nenhum registro com o cabeçalho 'Frota' foi localizado.")

if __name__ == "__main__":
    executar_robo_manutencao_externa()
