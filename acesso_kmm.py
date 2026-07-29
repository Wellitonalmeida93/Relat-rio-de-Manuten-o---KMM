import requests
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

                is_nao_controlada_km = (
                    df_sub[coluna_km]
                    .astype(str)
                    .str.lower()
                    .str.contains("nao controlada|não controlada")
                )

                s_km = (
                    df_sub[coluna_km]
                    .astype(str)
                    .str.replace(r'[^\d,-]', '', regex=True)
                    .str.replace(',', '.')
                )

                km_num = pd.to_numeric(s_km, errors='coerce')

                cond_km = (km_num <= 5000) | is_nao_controlada_km

                if coluna_tabela:

                    is_tabela_excecao = (
                        df_sub[coluna_tabela]
                        .astype(str)
                        .str.upper()
                        .str.contains(
                            "TABELA BASICA RODANTE SEMI REBOQUE BAU - 60.000 KM",
                            regex=False
                        )
                    )

                    cond_km = cond_km | is_tabela_excecao

            if coluna_dias:

                is_nao_controlada_dias = (
                    df_sub[coluna_dias]
                    .astype(str)
                    .str.lower()
                    .str.contains("nao controlada|não controlada")
                )

                s_dias = (
                    df_sub[coluna_dias]
                    .astype(str)
                    .str.replace(r'[^\d,-]', '', regex=True)
                    .str.replace(',', '.')
                )

                dias_num = pd.to_numeric(s_dias, errors='coerce')

                cond_dias = (dias_num <= 15) | is_nao_controlada_dias

            df_sub = df_sub[cond_km & cond_dias]

        if not df_sub.empty:

            nome_aba = re.sub(r'[\:\*\[\]\?\\\/]', '', status_nome)[:30]

            matriz = [df_sub.columns.tolist()]
            matriz.extend(
                df_sub.fillna("").astype(str).values.tolist()
            )

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
print(" 📊 Dados enviados para o Google Sheets!")
