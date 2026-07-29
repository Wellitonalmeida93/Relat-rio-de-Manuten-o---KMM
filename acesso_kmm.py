from playwright.sync_api import sync_playwright
import pandas as pd
import os
import re
import requests

# ==============================================================
# SEGURANÇA: Buscando credenciais
# ==============================================================
USUARIO = os.getenv("KMM_USER", "matheusd")
SENHA = os.getenv("KMM_PASS", "328254Ma")

def capturar_e_limpar_relatorio():
    print("🚀 Iniciando automação KMM em segundo plano (Modo Invisível)...")

    with sync_playwright() as p:
        navegador = p.chromium.launch(headless=True)
        contexto = navegador.new_context()
        pagina = contexto.new_page()

        print("1. Acessando o portal KMM...")
        pagina.goto("https://kmm.pizzattolog.com.br/index.cfm")

        print("2. Preenchendo credenciais...")
        pagina.locator("input[type='text']").first.fill(USUARIO)
        campo_senha = pagina.locator("input[type='password']").first
        campo_senha.fill(SENHA)
        campo_senha.press("Enter")

        pagina.wait_for_load_state("networkidle")
        pagina.wait_for_timeout(3000)

        def clicar_menu(texto):
            for frame in [pagina] + pagina.frames:
                try:
                    elem = frame.get_by_text(texto, exact=False).first
                    if elem.is_visible():
                        elem.click()
                        return True
                except Exception:
                    continue
            return False

        print("3. Navegando nos menus até o MANUT35...")
        clicar_menu("Manutenção de Veículos")
        pagina.wait_for_timeout(1500)

        clicar_menu("Relatórios")
        pagina.wait_for_timeout(1500)

        clicar_menu("Relatório de Tabelas de Manutenção nos Equipamentos (MANUT35)")
        pagina.wait_for_load_state("networkidle")
        pagina.wait_for_timeout(3000)

        print("4. Clicando em 'Confirmar'...")
        for frame in pagina.frames:
            try:
                btn = frame.get_by_text("Confirmar", exact=False).first
                if btn.is_visible():
                    btn.click()
                    break
            except Exception:
                continue

        print("5. Aguardando processamento dos dados no servidor...")
        pagina.wait_for_load_state("networkidle")
        pagina.wait_for_timeout(8000)

        print("6. Coletando e carregando todos os registros (Scroll)...")
        for _ in range(25):
            pagina.keyboard.press("PageDown")
            pagina.wait_for_timeout(150)
            for f in pagina.frames:
                try:
                    f.evaluate("window.scrollBy(0, 1000);")
                    f.evaluate("let s = document.querySelector('.x-grid3-scroller'); if(s) s.scrollTop += 1000;")
                except Exception:
                    pass

        pagina.wait_for_timeout(2000)

        print("7. Capturando dados da tela...")
        linhas_brutas = []

        for frame in pagina.frames:
            try:
                texto_completo = frame.locator("body").inner_text()
                if texto_completo and "Frota" in texto_completo:
                    linhas = texto_completo.split("\n")
                    for l in linhas:
                        l_limpa = l.strip()
                        if l_limpa:
                            partes = [p.strip() for p in l_limpa.split("\t") if p.strip()]
                            if not partes:
                                partes = [l_limpa]
                            linhas_brutas.append(partes)
            except Exception:
                continue

        navegador.close()

        print("8. Aplicando tratamento dos dados...")
        if linhas_brutas:
            max_cols = max(len(linha) for linha in linhas_brutas)
            colunas_temp = [f"Coluna_{i+1}" for i in range(max_cols)]
            linhas_padronizadas = [linha + [""] * (max_cols - len(linha)) for linha in linhas_brutas]

            df = pd.DataFrame(linhas_padronizadas, columns=colunas_temp)

            idx_cabecalho = None
            for idx, row in df.iterrows():
                if str(row.iloc[0]).strip().lower() == "frota":
                    idx_cabecalho = idx
                    break

            if idx_cabecalho is not None:
                novas_colunas = df.iloc[idx_cabecalho].values
                df_limpo = df.iloc[idx_cabecalho + 1:].copy()
                df_limpo.columns = novas_colunas
                df_limpo.reset_index(drop=True, inplace=True)
                df_limpo = df_limpo.dropna(how='all').drop_duplicates()
                df_final = df_limpo
            else:
                df_final = df.iloc[15:].reset_index(drop=True)

            coluna_status = None
            coluna_km = None
            coluna_dias = None
            coluna_tabela = None

            for col in df_final.columns:
                col_str = str(col).lower().replace("ç", "c").replace("ã", "a")
                if "status" in col_str:
                    coluna_status = col
                elif "km" in col_str and not coluna_km:
                    coluna_km = col
                elif ("dias" in col_str or "dia" in col_str) and not coluna_dias:
                    coluna_dias = col
                elif "tabela" in col_str and not coluna_tabela:
                    coluna_tabela = col

            url_sheets = "https://script.google.com/macros/s/AKfycbwEMY8eHwKIGtd2fuHpvMmh_a14EAGzdf8Qgg41AKCiE_pOD4ifQFx4epFZklFYu46w/exec"
            dados_para_sheets = {}

            if coluna_status:
                for status_val, df_grupo in df_final.groupby(coluna_status):

                    status_nome = str(status_val).strip()
                    status_lower = status_nome.lower()

                    if status_lower in ["ok", "nan", ""]:
                        continue

                    df_sub = df_grupo.copy()

                    if "vencer" in status_lower and "vencida" not in status_lower:
                        cond_km = pd.Series(True, index=df_sub.index)
                        cond_dias = pd.Series(True, index=df_sub.index)

                        if coluna_km:
                            is_nao_controlada_km = df_sub[coluna_km].astype(str).str.lower().str.contains("nao controlada|não controlada")
                            s_km = df_sub[coluna_km].astype(str).str.replace(r'[^\d,-]', '', regex=True).str.replace(',', '.')
                            km_num = pd.to_numeric(s_km, errors='coerce')
                            cond_km = (km_num <= 5000) | is_nao_controlada_km

                            if coluna_tabela:
                                is_tabela_excecao = df_sub[coluna_tabela].astype(str).str.upper().str.contains(
                                    "TABELA BASICA RODANTE SEMI REBOQUE BAU - 60.000 KM",
                                    regex=False
                                )
                                cond_km = cond_km | is_tabela_excecao

                        if coluna_dias:
                            is_nao_controlada_dias = df_sub[coluna_dias].astype(str).str.lower().str.contains("nao controlada|não controlada")
                            s_dias = df_sub[coluna_dias].astype(str).str.replace(r'[^\d,-]', '', regex=True).str.replace(',', '.')
                            dias_num = pd.to_numeric(s_dias, errors='coerce')
                            cond_dias = (dias_num <= 15) | is_nao_controlada_dias

                        df_sub = df_sub[cond_km & cond_dias]

                    if not df_sub.empty:
                        nome_aba = re.sub(r'[\:\*\[\]\?\\\/]', '', status_nome)[:30]

                        matriz = [df_sub.columns.tolist()]
                        matriz.extend(df_sub.fillna("").astype(str).values.tolist())

                        dados_para_sheets[nome_aba] = matriz

            if not dados_para_sheets:
                dados_para_sheets["Sem Registros"] = [
                    ["Mensagem"],
                    ["Nenhum registro encontrado"]
                ]

            print("📤 Enviando para Google Sheets...")

            resposta = requests.post(
                url_sheets,
                json=dados_para_sheets,
                timeout=300
            )

            print("Status:", resposta.status_code)
            print("Resposta:", resposta.text)

            print("\\n" + "="*60)
            print(" ✨ PROCESSO CONCLUÍDO COM SUCESSO!")
            print(" 📊 Dados enviados para o Google Sheets!")
            print("="*60)

        else:
            print("\\n[ERRO] Nenhum dado foi capturado.")

if __name__ == "__main__":
    capturar_e_limpar_relatorio()
