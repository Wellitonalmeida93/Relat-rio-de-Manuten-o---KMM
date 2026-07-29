def executar_robo_principal():
    print("🚀 Iniciando Robô 1: Painel de Manutenção KMM...")
    
    usuario = os.environ.get("KMM_USER", "matheusd")
    senha = os.environ.get("KMM_PASS", "328254Ma")

    with sync_playwright() as p:
        navegador = p.chromium.launch(headless=True)
        contexto = navegador.new_context(viewport={"width": 1920, "height": 1080})
        pagina = contexto.new_page()

        print("1. Acessando o KMM e fazendo login...")
        pagina.goto("https://kmm.pizzattolog.com.br/index.cfm", wait_until="networkidle")
        
        # Espera o campo de login estar totalmente carregado
        pagina.locator("input[type='text']").first.wait_for(state="visible", timeout=30000)
        pagina.locator("input[type='text']").first.fill(usuario)
        
        campo_senha = pagina.locator("input[type='password']").first
        campo_senha.fill(senha)
        campo_senha.press("Enter")

        # Espera a página pós-login carregar a rede
        pagina.wait_for_load_state("networkidle")

        def clicar_menu(texto):
            """Procura o texto do menu em qualquer frame, espera ficar visível e clica."""
            for frame in pagina.frames:
                try:
                    elem = frame.get_by_text(texto, exact=False).first
                    # Espera dinâmica: só clica quando o menu realmente aparecer na tela
                    elem.wait_for(state="visible", timeout=5000)
                    elem.click()
                    return True
                except:
                    continue
            
            # Fallback caso não ache nos frames
            elem_main = pagina.get_by_text(texto, exact=False).first
            elem_main.wait_for(state="visible", timeout=5000)
            elem_main.click()

        print("2. Navegando até 'Painel de Manutenção'...")
        clicar_menu("Manutenção de Veículos")
        
        print(" -> Aguardando menu de relatórios...")
        clicar_menu("Painel de Manutenção")

        print(" -> Aguardando a tabela (ExtJS Grid) ser construída e populada...")
        
        # ESPERA DINÂMICA INTELIGENTE:
        # Percorre os frames até encontrar a tabela ExtJS e ESPERA que a primeira linha (.x-grid3-row) seja inserida no DOM
        frame_tabela = None
        for _ in range(30):  # Tenta por até 30 segundos sem travar o código fixo
            for frame in pagina.frames:
                try:
                    # Verifica se o elemento da linha existe e está visível
                    linha = frame.locator('.x-grid3-row').first
                    if linha.count() > 0:
                        linha.wait_for(state="visible", timeout=10000)
                        frame_tabela = frame
                        break
                except:
                    continue
            if frame_tabela:
                break
            pagina.wait_for_timeout(1000) # Espera 1s nativo antes de checar novamente

        print("3. Extraindo colunas e dados visíveis da grade ExtJS...")
        dados_capturados = None

        # Se encontrou o frame específico com as linhas, extrai diretamente dele
        frames_para_buscar = [frame_tabela] if frame_tabela else pagina.frames

        for frame in frames_para_buscar:
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
