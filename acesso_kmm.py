from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import pandas as pd
import requests
import time
import io
import os

# ⚠️ COLE AQUI A URL DO WEBHOOK DA SUA PRIMEIRA PLANILHA (Relatório Principal)
URL_WEBHOOK_PRINCIPAL = "SUA_URL_WEBHOOK_AQUI"

def executar_robo_principal():
    print("🚀 Iniciando Robô Principal: Painel de Manutenção KMM...")
    
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

        print("2. Navegando até 'Painel de Manutenção'...")
        clicar_menu("Manutenção de Veículos")
        pagina.wait_for_load_state("networkidle")
        time.sleep(2)

        # Clica no Painel principal (Ajuste o nome se no seu sistema for 'Relatórios' ou outro menu)
        clicar_menu("Painel de Manutenção") 
        pagina.wait_for_load_state("networkidle")
        time.sleep(8) # Aguarda carregar o painel inteiro

        print("3. Extraindo tabela de dados do KMM...")
        dfs_encontrados = []
        
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

        navegador.close()

        print("4. Processando os dados e aplicando regras de negócio...")
        df_final = None

        for df_temp in dfs_encontrados:
            idx_cabecalho = None
            for idx, row in df_temp.iterrows():
                texto_linha = " ".join([str(v).lower() for v in row.values])
                # Procura colunas vitais do painel principal
                if "frota" in texto_linha and ("dia" in texto_linha or "km" in texto_linha):
                    idx_cabecalho = idx
                    break

            if idx_cabecalho is not None:
                df_certo = df_temp.iloc[idx_cabecalho:].reset_index(drop=True)
                df_certo.columns = [str(c).strip() for c in df_certo.iloc[0].values]
                df_certo = df_certo.iloc[1:].reset_index(drop=True)
                
                df_certo = df_certo[df_certo[df_certo.columns[0]].astype(str).str.lower() != str(df_certo.columns[0]).lower()]
                df_certo.fillna("", inplace=True)
                df_certo.dropna(how='all', inplace=True)
                df_certo.drop_duplicates(inplace=True)
                df_certo.reset_index(drop=True, inplace=True)
                
                df_final = df_certo
                break

        if df_final is not None and len(df_final) > 0:
            
            # ---------------------------------------------------------
            # 🧠 MOTOR DE REGRAS DE NEGÓCIO (VENCIDAS / À VENCER)
            # ---------------------------------------------------------
            col_dias = next((c for c in df_final.columns if 'dia' in c.lower()), None)
            col_km = next((c for c in df_final.columns if 'km' in c.lower()), None)
            col_tabela = next((c for c in df_final.columns if 'tabela' in c.lower() or 'plano' in c.lower()), None)

            dados_vencidas = [df_final.columns.tolist()]
            dados_a_vencer = [df_final.columns.tolist()]

            for _, row in df_final.iterrows():
                try:
                    dias = int(float(row[col_dias])) if col_dias and str(row[col_dias]).strip() else 9999
                except:
                    dias = 9999

                try:
                    km = int(float(row[col_km])) if col_km and str(row[col_km]).strip() else 999999
                except:
                    km = 999999
                
                tabela_plano = str(row[col_tabela]).upper() if col_tabela else ""
                
                # Regra 1: Vencidas (Passou do prazo)
                if dias < 0 or km < 0:
                    dados_vencidas.append(row.tolist())
                    continue
                
                # Regra 2: À Vencer
                # 🚨 EXCEÇÃO: Carreta Baú 60k -> Avalia SÓ DIAS
                if "TABELA BASICA RODANTE SEMI REBOQUE BAU - 60.000 KM" in tabela_plano:
                    if 0 <= dias <= 15:
                        dados_a_vencer.append(row.tolist())
                # 🚗 REGRA GERAL: Avalia DIAS ou KM
                else:
                    if (0 <= dias <= 15) or (0 <= km <= 1000):
                        dados_a_vencer.append(row.tolist())

            # ---------------------------------------------------------
            
            print(f"5. Enviando dados para o Google Sheets (Vencidas: {len(dados_vencidas)-1} | À Vencer: {len(dados_a_vencer)-1})")
            
            payload = {
                "vencidas": dados_vencidas,
                "a_vencer": dados_a_vencer
            }
            
            resposta = requests.post(URL_WEBHOOK_PRINCIPAL, json=payload)

            if resposta.status_code == 200 and "Sucesso" in resposta.text:
                print("\n==================================================")
                print(" ✨ PLANILHA PRINCIPAL ATUALIZADA COM SUCESSO!")
                print("==================================================")
            else:
                print(f"\n[ERRO] Falha ao enviar para o Google Sheets: {resposta.text}")
        else:
            print("\n[ERRO] Cabeçalho com 'Frota' e 'Dias' não foi localizado.")

if __name__ == "__main__":
    executar_robo_principal()
