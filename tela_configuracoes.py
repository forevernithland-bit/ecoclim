import streamlit as st
import pandas as pd
import io
import utils
import gestao_click

# Margem padrão por palavra-chave no nome do item, aplicada automaticamente
# sempre que um item entra pela importação de Excel (Configurações →
# Produtos/Serviços/Terceiros → Importar Planilha). Sem isso, item novo entra
# com margem 0% (Venda = Custo) até alguém editar na mão — decisão do Breno
# (2026-09-02): Trocador de Calor já nasce com 24,5%, tanto os que já existem
# no catálogo quanto qualquer um novo importado daqui pra frente.
MARGEM_POR_PALAVRA_CHAVE = [
    ("TROCADOR DE CALOR", 24.5),
]


def _margem_automatica_item(nome_item):
    """Margem (%) padrão pro item pela palavra-chave no nome, ou None se
    nenhuma regra bater (nesse caso quem chama decide, nunca inventa aqui)."""
    nome_norm = str(nome_item or "").strip().upper()
    for chave, margem in MARGEM_POR_PALAVRA_CHAVE:
        if chave in nome_norm:
            return margem
    return None


def renderizar():
    st.markdown("## ⚙️ Configurações e Catálogos")

    tabs = st.tabs(["🛒 Produtos", "🛠️ Serviços", "🤝 Outros / Terceiros", "📊 Taxas", "📦 Kits em Lote", "👷‍♂️ Instaladores"])
    
    # =========================================================================
    # FUNÇÕES DE IMPORTAÇÃO/EXPORTAÇÃO DE CATÁLOGOS
    # =========================================================================
    def gerar_modelo_excel(df_dados=None):
        if df_dados is not None and not df_dados.empty:
            df_modelo = pd.DataFrame({
                "ITEM": df_dados.get("Item", ""),
                "DESCRIÇÃO": df_dados.get("Descrição", ""),
                "CUSTO": df_dados.get("Custo (R$)", 0.0)
            })
        else:
            df_modelo = pd.DataFrame(columns=["ITEM", "DESCRIÇÃO", "CUSTO"])
            
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_modelo.to_excel(writer, index=False, sheet_name='MODELO_IMPORTACAO')
        return output.getvalue()

    def processar_upload_excel(arquivo_subido):
        df_excel = pd.read_excel(arquivo_subido)
        df_excel.columns = df_excel.columns.str.strip().str.upper()
        df_final = pd.DataFrame()
        
        if "PRODUTO" in df_excel.columns: df_final["Item"] = df_excel["PRODUTO"]
        elif "ITEM" in df_excel.columns: df_final["Item"] = df_excel["ITEM"]
        else: df_final["Item"] = "Sem Nome"
        
        if "CUSTO" in df_excel.columns: df_final["Custo (R$)"] = pd.to_numeric(df_excel["CUSTO"], errors='coerce').fillna(0.0)
        else: df_final["Custo (R$)"] = 0.0
        
        if "DESCRIÇÃO" in df_excel.columns: df_final["Descrição"] = df_excel["DESCRIÇÃO"].fillna("")
        elif "DESCRICAO" in df_excel.columns: df_final["Descrição"] = df_excel["DESCRICAO"].fillna("")
        else: df_final["Descrição"] = ""
        
        # Margem 0% (Venda = Custo) é só o piso — item cujo nome bate com uma
        # regra de MARGEM_POR_PALAVRA_CHAVE (ex.: Trocador de Calor) já entra
        # com a margem certa, sem precisar editar linha por linha depois.
        df_final["Margem (%)"] = df_final["Item"].apply(lambda n: _margem_automatica_item(n) or 0.0)
        df_final["Venda (R$)"] = (df_final["Custo (R$)"] * (1 + df_final["Margem (%)"] / 100)).round(2)
        df_final["Lucro (R$)"] = (df_final["Venda (R$)"] - df_final["Custo (R$)"]).round(2)
        return df_final

    # =========================================================================
    # FUNÇÕES DE IMPORTAÇÃO/EXPORTAÇÃO ESPECÍFICAS PARA TAXAS
    # =========================================================================
    def gerar_modelo_taxas(df_dados=None):
        if df_dados is not None and not df_dados.empty:
            df_modelo = pd.DataFrame({
                "ITEM": df_dados.get("Item", ""),
                "TAXA (%)": df_dados.get("Taxa (%)", 0.0)
            })
        else:
            df_modelo = pd.DataFrame(columns=["ITEM", "TAXA (%)"])
            
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_modelo.to_excel(writer, index=False, sheet_name='TAXAS_IMPOSTOS')
        return output.getvalue()

    def processar_upload_taxas(arquivo_subido):
        df_excel = pd.read_excel(arquivo_subido)
        df_excel.columns = df_excel.columns.str.strip().str.upper()
        df_final = pd.DataFrame()
        
        if "ITEM" in df_excel.columns: df_final["Item"] = df_excel["ITEM"]
        elif "TAXA" in df_excel.columns and "NOME" in df_excel.columns: df_final["Item"] = df_excel["NOME"]
        else: df_final["Item"] = "Sem Nome"
        
        col_taxa = next((col for col in df_excel.columns if "TAXA" in col), None)
        if col_taxa:
            df_final["Taxa (%)"] = pd.to_numeric(df_excel[col_taxa], errors='coerce').fillna(0.0)
        else:
            df_final["Taxa (%)"] = 0.0
            
        return df_final

    # =========================================================================
    # RENDERIZAÇÃO DAS ABAS DE CATÁLOGOS (PRODUTOS, SERVIÇOS, TERCEIROS)
    # =========================================================================
    def exibir_aba_catalogo(nome_tabela, titulo_aba):
        df_atual = utils.load_catalog(nome_tabela)
        
        st.markdown(f"#### 📥 Importar Planilha de {titulo_aba}")
        
        col_file, col_btn = st.columns([3, 1])
        with col_file:
            arquivo_excel = st.file_uploader(f"Selecione o arquivo (.xlsx)", type=["xlsx"], key=f"upload_{nome_tabela}", label_visibility="collapsed")
        with col_btn:
            st.download_button(
                label="📥 Baixar Modelo (.xlsx)",
                data=gerar_modelo_excel(df_atual),
                file_name=f"modelo_importacao_{titulo_aba.lower()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
            
        if arquivo_excel:
            if st.button(f"Processar Planilha - {titulo_aba}"):
                df_novo = processar_upload_excel(arquivo_excel)
                df_combinado = pd.concat([df_atual, df_novo], ignore_index=True).drop_duplicates(subset=['Item'], keep='last')
                df_combinado = df_combinado.reset_index(drop=True)
                st.session_state[f'temp_df_{nome_tabela}'] = df_combinado
                st.success("✅ Dados processados! Verifique na tabela e clique em Gravar.")

        if f'temp_df_{nome_tabela}' in st.session_state:
            df_atual = st.session_state[f'temp_df_{nome_tabela}']

        colunas_padrao = ["Item", "Descrição", "Custo (R$)", "Margem (%)", "Lucro (R$)", "Venda (R$)"]
        for col in colunas_padrao:
            if col not in df_atual.columns:
                df_atual[col] = "" if "Item" in col or "Desc" in col else 0.0

        st.markdown("---")
        st.markdown("#### ⚡ Margem Automática em Massa")
        col_m1, col_m2 = st.columns([1, 3])
        margem_digitada = col_m1.number_input("Margem (%)", min_value=0.0, format="%.2f", key=f"val_margem_{nome_tabela}")
        
        if col_m2.button(f"Aplicar {margem_digitada}% a todos os itens acima", key=f"btn_massa_{nome_tabela}"):
            df_atual['Margem (%)'] = margem_digitada
            df_atual['Custo (R$)'] = pd.to_numeric(df_atual['Custo (R$)'], errors='coerce').fillna(0.0)
            df_atual['Venda (R$)'] = (df_atual['Custo (R$)'] * (1 + (df_atual['Margem (%)'] / 100))).round(2)
            df_atual['Lucro (R$)'] = (df_atual['Venda (R$)'] - df_atual['Custo (R$)']).round(2)
            st.session_state[f'temp_df_{nome_tabela}'] = df_atual
            st.rerun()

        st.markdown("#### 📋 Edição do Catálogo")
        
        termo_busca = st.text_input("🔍 Buscar Item ou Descrição...", key=f"busca_{nome_tabela}").strip().lower()

        if termo_busca:
            mascara = df_atual.apply(
                lambda row: utils.bate_busca(termo_busca, row.get('Item', ''), row.get('Descrição', '')),
                axis=1
            )
            df_exibicao = df_atual[mascara].copy()
        else:
            df_exibicao = df_atual.copy()

        config_editor = {
            "Item": st.column_config.TextColumn("Item", width="medium"),
            "Descrição": st.column_config.TextColumn("Descrição / Detalhes", width="large"),
            "Custo (R$)": st.column_config.NumberColumn("Custo", format="R$ %.2f"),
            "Margem (%)": st.column_config.NumberColumn("Margem %", format="%.2f %%"),
            "Lucro (R$)": st.column_config.NumberColumn("Lucro", format="R$ %.2f", disabled=True),
            "Venda (R$)": st.column_config.NumberColumn("Preço Venda", format="R$ %.2f")
        }
        if "NCM" in df_exibicao.columns:
            config_editor["NCM"] = st.column_config.TextColumn("NCM", width="small", help="Obrigatório pra emitir Nota Fiscal desse item no Gestão Click. Não chutar — pesquisar em fonte de contabilidade confiável.")
        if "Código Externo (GC)" in df_exibicao.columns:
            config_editor["Código Externo (GC)"] = st.column_config.TextColumn("Cód. Gestão Click", width="small", disabled=True, help="Preenchido automaticamente na primeira sincronização — não editar na mão.")
        if "Código de Barra" in df_exibicao.columns:
            config_editor["Código de Barra"] = st.column_config.TextColumn("Cód. Barra", width="small")
        
        editor_key = f"editor_{nome_tabela}"
        df_editor = st.data_editor(df_exibicao, column_config=config_editor, num_rows="dynamic", use_container_width=True, key=editor_key)
        
        # Matemática Segura em tempo real
        df_editor['Custo (R$)'] = pd.to_numeric(df_editor['Custo (R$)'], errors='coerce').fillna(0.0)
        df_editor['Margem (%)'] = pd.to_numeric(df_editor['Margem (%)'], errors='coerce').fillna(0.0)
        df_editor['Venda (R$)'] = pd.to_numeric(df_editor['Venda (R$)'], errors='coerce').fillna(0.0)
        df_editor['Lucro (R$)'] = pd.to_numeric(df_editor['Lucro (R$)'], errors='coerce').fillna(0.0)

        precisa_atualizar_matematica = False

        if editor_key in st.session_state:
            edits = st.session_state[editor_key].get("edited_rows", {})
            for row_idx_str, changes in edits.items():
                try:
                    row_idx = int(row_idx_str)
                    actual_idx = df_exibicao.index[row_idx]
                    
                    if "Venda (R$)" in changes and "Margem (%)" not in changes and "Custo (R$)" not in changes:
                        # Usuário digitou o Preço de Venda manualmente
                        c = df_editor.at[actual_idx, 'Custo (R$)']
                        v = df_editor.at[actual_idx, 'Venda (R$)']
                        m_calc = round(((v / c) - 1) * 100, 2) if c > 0 else 0.0
                        l_calc = round(v - c, 2)
                        df_editor.at[actual_idx, 'Margem (%)'] = m_calc
                        df_editor.at[actual_idx, 'Lucro (R$)'] = l_calc
                        precisa_atualizar_matematica = True
                        
                    elif "Margem (%)" in changes or "Custo (R$)" in changes:
                        # Usuário alterou a Margem ou Custo manualmente
                        c = df_editor.at[actual_idx, 'Custo (R$)']
                        m = df_editor.at[actual_idx, 'Margem (%)']
                        v_calc = round(c * (1 + (m / 100)), 2)
                        l_calc = round(v_calc - c, 2)
                        df_editor.at[actual_idx, 'Venda (R$)'] = v_calc
                        df_editor.at[actual_idx, 'Lucro (R$)'] = l_calc
                        precisa_atualizar_matematica = True
                except Exception:
                    pass

            # Varredura de segurança para calcular linhas que ficaram fora do dicionário de edições (ex: novas linhas)
            for idx in df_editor.index:
                c = df_editor.at[idx, 'Custo (R$)']
                m = df_editor.at[idx, 'Margem (%)']
                v = df_editor.at[idx, 'Venda (R$)']
                l = df_editor.at[idx, 'Lucro (R$)']
                
                v_calc = round(c * (1 + (m / 100)), 2)
                l_calc = round(v_calc - c, 2)
                
                # Se for uma edição manual do preço de venda, não forçamos o cálculo padrão
                is_manual_venda = False
                for row_idx_str, changes in edits.items():
                    try:
                        if df_exibicao.index[int(row_idx_str)] == idx and "Venda (R$)" in changes and "Margem (%)" not in changes and "Custo (R$)" not in changes:
                            is_manual_venda = True
                    except: pass
                
                if not is_manual_venda:
                    if abs(v - v_calc) > 0.01 or abs(l - l_calc) > 0.01:
                        df_editor.at[idx, 'Venda (R$)'] = v_calc
                        df_editor.at[idx, 'Lucro (R$)'] = l_calc
                        precisa_atualizar_matematica = True

        if precisa_atualizar_matematica:
            if termo_busca:
                df_temp = df_atual.copy()
                df_temp.update(df_editor)
                linhas_apagadas = df_exibicao.index.difference(df_editor.index)
                if not linhas_apagadas.empty:
                    df_temp = df_temp.drop(linhas_apagadas)
                linhas_novas = df_editor[~df_editor.index.isin(df_atual.index)]
                if not linhas_novas.empty:
                    df_temp = pd.concat([df_temp, linhas_novas])
                df_temp = df_temp.reset_index(drop=True)
            else:
                df_temp = df_editor.reset_index(drop=True)

            st.session_state[f'temp_df_{nome_tabela}'] = df_temp
            st.rerun()

        if st.button(f"💾 GRAVAR ALTERAÇÕES", type="primary", use_container_width=True, key=f"save_{nome_tabela}"):
            if termo_busca:
                df_salvar = df_atual.copy()
                df_salvar.update(df_editor)
                linhas_apagadas = df_exibicao.index.difference(df_editor.index)
                if not linhas_apagadas.empty:
                    df_salvar = df_salvar.drop(linhas_apagadas)
                linhas_novas = df_editor[~df_editor.index.isin(df_atual.index)]
                if not linhas_novas.empty:
                    df_salvar = pd.concat([df_salvar, linhas_novas])
                df_salvar = df_salvar.reset_index(drop=True)
            else:
                df_salvar = df_editor.reset_index(drop=True)
                
            linhas_salvas = utils.save_catalog(nome_tabela, df_salvar)
            if f'temp_df_{nome_tabela}' in st.session_state: del st.session_state[f'temp_df_{nome_tabela}']

            if nome_tabela == 'catalogo_produtos' and linhas_salvas:
                sem_ncm = [r['item'] for r in linhas_salvas if not r.get('ncm')]
                erros_sync = []
                supabase_sync = utils.get_supabase_client()
                with st.spinner("Sincronizando com o Gestão Click..."):
                    for row in linhas_salvas:
                        try:
                            gestao_click.garantir_produto(supabase_sync, row, tabela='catalogo_produtos')
                        except gestao_click.GestaoClickError as e:
                            erros_sync.append(f"{row['item']}: {e}")
                if erros_sync:
                    st.warning("Alguns itens não sincronizaram com o Gestão Click agora (o catálogo aqui foi salvo normalmente): " + "; ".join(erros_sync))
                if sem_ncm:
                    st.warning(f"⚠️ {len(sem_ncm)} item(ns) sem NCM — não vai dar pra emitir Nota Fiscal deles até preencher: {', '.join(sem_ncm)}")
                st.toast("Itens atualizados no ERP Ecoclim e no Gestão Click Ecoclim!", icon="✅")
                st.success("Itens atualizados no ERP Ecoclim e no Gestão Click Ecoclim!")
            else:
                st.success(f"Catálogo atualizado com sucesso!")
            st.rerun()

    with tabs[0]: exibir_aba_catalogo('catalogo_produtos', 'Produtos')
    with tabs[1]: exibir_aba_catalogo('catalogo_servicos', 'Serviços')
    with tabs[2]: exibir_aba_catalogo('catalogo_outros', 'Terceiros')
    
    # =========================================================================
    # ABA: TAXAS
    # =========================================================================
    with tabs[3]:
        st.subheader("📊 Taxas e Impostos")
        df_atual_taxas = utils.load_taxas()
        
        st.markdown("#### 📥 Importar Planilha de Taxas")
        col_file_taxas, col_btn_taxas = st.columns([3, 1])
        
        with col_file_taxas:
            arquivo_excel_taxas = st.file_uploader("Selecione o arquivo (.xlsx)", type=["xlsx"], key="upload_taxas", label_visibility="collapsed")
        
        with col_btn_taxas:
            st.download_button(
                label="📥 Baixar Dados Atuais (.xlsx)",
                data=gerar_modelo_taxas(df_atual_taxas),
                file_name="taxas_atuais_exportadas.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
            
        if arquivo_excel_taxas:
            if st.button("Processar Planilha - Taxas"):
                df_novo_taxas = processar_upload_taxas(arquivo_excel_taxas)
                df_combinado_taxas = pd.concat([df_atual_taxas, df_novo_taxas], ignore_index=True).drop_duplicates(subset=['Item'], keep='last')
                df_combinado_taxas = df_combinado_taxas.reset_index(drop=True)
                st.session_state['temp_df_taxas'] = df_combinado_taxas
                st.success("✅ Taxas processadas! Verifique na tabela e clique em Gravar.")

        if 'temp_df_taxas' in st.session_state:
            df_atual_taxas = st.session_state['temp_df_taxas']

        st.markdown("#### 📋 Edição de Taxas")
        df_t_edit = st.data_editor(df_atual_taxas, use_container_width=True, num_rows="dynamic", key="editor_taxas")
        
        if st.button("💾 Gravar Taxas", type="primary", use_container_width=True):
            utils.save_taxas(df_t_edit)
            if 'temp_df_taxas' in st.session_state: 
                del st.session_state['temp_df_taxas']
            st.success("✅ Taxas salvas com sucesso no banco de dados!")
            st.rerun()
            
    # =========================================================================
    # ABA: KITS EM LOTE (MESTRE-DETALHE)
    # =========================================================================
    with tabs[4]:
        st.subheader("📦 Configuração de Kits para Orçamentos em Lote")
        st.caption("Passo 1: Crie o Kit. Passo 2: Adicione os equipamentos dentro dele.")
        
        df_prod_opt = utils.load_catalog('catalogo_produtos')
        df_serv_opt = utils.load_catalog('catalogo_servicos')
        lista_prod = df_prod_opt['Item'].dropna().tolist() if not df_prod_opt.empty else []
        lista_serv = df_serv_opt['Item'].dropna().tolist() if not df_serv_opt.empty else []
        
        modelos_capa = [
            "Aquecedor Solar Tradicional", "Aquecedor Solar a Vácuo Acoplado", 
            "Aquecedor Solar Modular", "Aquecedor de Piscina - Tradicional", 
            "Aquecedor de Piscina - Trocador de Calor", "Sistema de Pressurização"
        ]

        try:
            res_kits = st.session_state.supabase.table('config_kits_lote').select('*').order('id').execute()
            df_kits = pd.DataFrame(res_kits.data)
        except Exception:
            df_kits = pd.DataFrame()

        if df_kits.empty:
            df_kits = pd.DataFrame([{"nome_kit": "", "servico_base": "", "modelo_capa": "", "itens": []}])
        
        st.markdown("#### 1. Informações Base do Kit")
        cfg_kits = {
            "id": None, 
            "itens": None, 
            "nome_kit": st.column_config.TextColumn("Nome do Arquivo (Ex: Acoplado 16 Tubos)", width="medium"),
            "servico_base": st.column_config.SelectboxColumn("Serviço de Instalação", options=[""] + lista_serv, width="medium"),
            "modelo_capa": st.column_config.SelectboxColumn("Modelo da Capa PDF", options=modelos_capa, width="medium")
        }

        for col in ["nome_kit", "servico_base", "modelo_capa", "itens"]:
            if col not in df_kits.columns: df_kits[col] = [] if col == "itens" else ""

        df_kits_edit = st.data_editor(df_kits, column_config=cfg_kits, num_rows="dynamic", use_container_width=True, key="editor_kits_lote", hide_index=True)

        if st.button("💾 GRAVAR NOMES E SERVIÇOS DOS KITS", type="primary", use_container_width=True):
            dados_salvar = []
            for _, row in df_kits_edit.iterrows():
                if str(row.get('nome_kit', '')).strip() != "":
                    itens_atuais = row.get('itens', [])
                    if not isinstance(itens_atuais, list): itens_atuais = []
                    
                    dados_salvar.append({
                        "nome_kit": row['nome_kit'],
                        "servico_base": str(row.get('servico_base', '')),
                        "modelo_capa": str(row.get('modelo_capa', modelos_capa[0])),
                        "itens": itens_atuais
                    })
            try:
                st.session_state.supabase.table('config_kits_lote').delete().neq("nome_kit", "____").execute()
                if dados_salvar:
                    st.session_state.supabase.table('config_kits_lote').insert(dados_salvar).execute()
                st.success("✅ Nomes e Serviços salvos! Agora configure os produtos abaixo.")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar kits: {e}")

        st.markdown("---")
        st.markdown("#### 2. Equipamentos do Kit")
        
        nomes_kits_salvos = [k for k in df_kits['nome_kit'].dropna().tolist() if k.strip() != ""]
        
        if nomes_kits_salvos:
            kit_sel = st.selectbox("Selecione o Kit para adicionar/editar os produtos:", nomes_kits_salvos)
            
            kit_row = df_kits[df_kits['nome_kit'] == kit_sel].iloc[0]
            kit_itens = kit_row.get('itens', [])
            if not isinstance(kit_itens, list): kit_itens = []
            
            df_itens = pd.DataFrame(kit_itens)
            if df_itens.empty:
                df_itens = pd.DataFrame([{"Produto": "", "Quantidade": 0} for _ in range(3)])
                
            for col in ["Produto", "Quantidade"]:
                if col not in df_itens.columns: df_itens[col] = "" if col == "Produto" else 0

            cfg_itens = {
                "Produto": st.column_config.SelectboxColumn("Equipamento (Produto)", options=[""] + lista_prod, width="large"),
                "Quantidade": st.column_config.NumberColumn("Qtd", min_value=0, step=1)
            }

            df_itens_edit = st.data_editor(df_itens, column_config=cfg_itens, num_rows="dynamic", use_container_width=True, key=f"edit_itens_{kit_sel}", hide_index=True)

            if st.button(f"💾 SALVAR PRODUTOS NO KIT: {kit_sel}", type="primary"):
                novos_itens = []
                for _, r in df_itens_edit.iterrows():
                    p = str(r.get('Produto', '')).strip()
                    
                    try:
                        q = int(r.get('Quantidade', 0))
                    except (ValueError, TypeError):
                        q = 0
                        
                    if p != "" and q > 0:
                        novos_itens.append({"Produto": p, "Quantidade": q})
                        
                try:
                    st.session_state.supabase.table('config_kits_lote').update({"itens": novos_itens}).eq("nome_kit", kit_sel).execute()
                    st.success(f"✅ Equipamentos do kit '{kit_sel}' salvos com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")
        else:
            st.info("Crie e grave um kit na tabela acima primeiro.")

    # =========================================================================
    # ABA: INSTALADORES
    # =========================================================================
    with tabs[5]:
        st.subheader("👷‍♂️ Gestão de Instaladores")
        st.caption("Cadastre os dados dos técnicos e instaladores parceiros da Ecoclim.")

        try:
            res_inst = st.session_state.supabase.table('config_instaladores').select('*').order('nome').execute()
            df_inst = pd.DataFrame(res_inst.data)
        except Exception:
            df_inst = pd.DataFrame()

        colunas_inst = ["nome", "email", "pix", "endereco", "telefone"]
        for col in colunas_inst:
            if col not in df_inst.columns:
                df_inst[col] = ""

        cfg_inst = {
            "id": None,
            "nome": st.column_config.TextColumn("Nome do Instalador", width="medium", required=True),
            "email": st.column_config.TextColumn("E-mail", width="medium"),
            "pix": st.column_config.TextColumn("Chave PIX", width="medium"),
            "endereco": st.column_config.TextColumn("Endereço Completo", width="large"),
            "telefone": st.column_config.TextColumn("Telefone / WhatsApp", width="medium")
        }

        df_inst_editado = st.data_editor(
            df_inst[colunas_inst],
            column_config=cfg_inst,
            num_rows="dynamic",
            use_container_width=True,
            key="editor_instaladores",
            hide_index=True
        )

        st.markdown("<br>", unsafe_allow_html=True)
        
        if st.button("💾 GRAVAR INSTALADORES", type="primary", use_container_width=True):
            dados_salvar = []
            for _, row in df_inst_editado.iterrows():
                if str(row.get('nome', '')).strip() != "":
                    dados_salvar.append({
                        "nome": str(row.get('nome', '')).strip(),
                        "email": str(row.get('email', '')).strip(),
                        "pix": str(row.get('pix', '')).strip(),
                        "endereco": str(row.get('endereco', '')).strip(),
                        "telefone": str(row.get('telefone', '')).strip()
                    })

            try:
                st.session_state.supabase.table('config_instaladores').delete().neq("nome", "____").execute() 
                if dados_salvar:
                    st.session_state.supabase.table('config_instaladores').insert(dados_salvar).execute()
                st.success("✅ Equipe de instaladores salva com sucesso!")
                st.rerun()
            except Exception as e:
                st.error(f"⚠️ Erro ao salvar. Certifique-se de ter criado a tabela 'config_instaladores' no Supabase. Erro: {e}")
