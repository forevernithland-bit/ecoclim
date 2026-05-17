import streamlit as st
import pandas as pd
import utils

def renderizar():
    st.markdown("## ⚙️ Configurações e Catálogos")
    
    # 1. ADICIONADA A 5ª ABA: "📦 Kits em Lote"
    tabs = st.tabs(["🛒 Produtos", "🛠️ Serviços", "🤝 Outros / Terceiros", "📊 Taxas", "📦 Kits em Lote"])
    
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
        
        df_final["Margem (%)"] = 0.0
        df_final["Lucro (R$)"] = 0.0
        df_final["Venda (R$)"] = df_final["Custo (R$)"]
        return df_final

    def exibir_aba_catalogo(nome_tabela, titulo_aba):
        df_atual = utils.load_catalog(nome_tabela)
        
        st.markdown(f"#### 📥 Importar Planilha de {titulo_aba}")
        arquivo_excel = st.file_uploader(f"Selecione o arquivo (.xlsx)", type=["xlsx"], key=f"upload_{nome_tabela}")
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
            df_atual['Venda (R$)'] = df_atual['Custo (R$)'] * (1 + (df_atual['Margem (%)'] / 100))
            df_atual['Lucro (R$)'] = df_atual['Venda (R$)'] - df_atual['Custo (R$)']
            st.session_state[f'temp_df_{nome_tabela}'] = df_atual
            st.rerun()

        st.markdown("#### 📋 Edição do Catálogo")
        config_editor = {
            "Item": st.column_config.TextColumn("Item", width="medium"),
            "Descrição": st.column_config.TextColumn("Descrição / Detalhes", width="large"),
            "Custo (R$)": st.column_config.NumberColumn("Custo", format="R$ %,.2f"),
            "Margem (%)": st.column_config.NumberColumn("Margem %", format="%.2f %%"),
            "Lucro (R$)": st.column_config.NumberColumn("Lucro", format="R$ %,.2f", disabled=True),
            "Venda (R$)": st.column_config.NumberColumn("Preço Venda", format="R$ %,.2f")
        }
        
        df_editor = st.data_editor(df_atual, column_config=config_editor, num_rows="dynamic", use_container_width=True, key=f"editor_{nome_tabela}")
        
        df_editor['Custo (R$)'] = pd.to_numeric(df_editor['Custo (R$)'], errors='coerce').fillna(0.0)
        df_editor['Margem (%)'] = pd.to_numeric(df_editor['Margem (%)'], errors='coerce').fillna(0.0)
        df_editor['Venda (R$)'] = pd.to_numeric(df_editor['Venda (R$)'], errors='coerce').fillna(0.0)
        
        mascara_margem = df_editor['Margem (%)'] > 0
        df_editor.loc[mascara_margem, 'Venda (R$)'] = df_editor.loc[mascara_margem, 'Custo (R$)'] * (1 + (df_editor.loc[mascara_margem, 'Margem (%)'] / 100))
        df_editor['Lucro (R$)'] = df_editor['Venda (R$)'] - df_editor['Custo (R$)']

        if st.button(f"💾 GRAVAR ALTERAÇÕES", type="primary", use_container_width=True, key=f"save_{nome_tabela}"):
            utils.save_catalog(nome_tabela, df_editor)
            if f'temp_df_{nome_tabela}' in st.session_state: del st.session_state[f'temp_df_{nome_tabela}']
            st.success(f"Catálogo atualizado!")
            st.rerun()

    with tabs[0]: exibir_aba_catalogo('catalogo_produtos', 'Produtos')
    with tabs[1]: exibir_aba_catalogo('catalogo_servicos', 'Serviços')
    with tabs[2]: exibir_aba_catalogo('catalogo_outros', 'Terceiros')
    with tabs[3]:
        st.subheader("📊 Taxas e Impostos")
        df_t = utils.load_taxas()
        df_t_edit = st.data_editor(df_t, use_container_width=True, num_rows="dynamic")
        if st.button("💾 Gravar Taxas", type="primary", use_container_width=True):
            utils.save_taxas(df_t_edit)
            st.success("Taxas salvas!")
            
    # 2. NOVA LÓGICA DA ABA DE KITS EM LOTE
    with tabs[4]:
        st.subheader("📦 Configuração de Kits para Orçamentos em Lote")
        st.caption("Crie a regra dos seus kits rápidos. O sistema cruzará os nomes daqui com o preço atualizado dos catálogos.")
        
        # Puxar opções para os selects
        df_prod_opt = utils.load_catalog('catalogo_produtos')
        df_serv_opt = utils.load_catalog('catalogo_servicos')
        lista_prod = df_prod_opt['Item'].dropna().tolist() if not df_prod_opt.empty else []
        lista_serv = df_serv_opt['Item'].dropna().tolist() if not df_serv_opt.empty else []
        
        modelos_capa = [
            "Aquecedor Solar Tradicional", "Aquecedor Solar a Vácuo Acoplado", 
            "Aquecedor Solar Modular", "Aquecedor de Piscina - Tradicional", 
            "Aquecedor de Piscina - Trocador de Calor", "Sistema de Pressurização"
        ]

        # Carregar configurações salvas no banco
        try:
            res_kits = st.session_state.supabase.table('config_kits_lote').select('*').execute()
            df_kits = pd.DataFrame(res_kits.data)
        except Exception:
            df_kits = pd.DataFrame()

        # Garantir colunas se estiver vazio
        if df_kits.empty:
            df_kits = pd.DataFrame([{"nome_kit": "", "produto_base": "", "servico_base": "", "modelo_capa": ""}])
        
        # Configurar Data Editor com Selectboxes
        cfg_kits = {
            "id": None, # Oculta o ID do banco
            "nome_kit": st.column_config.TextColumn("Nome do Arquivo (Ex: Acoplado_24tubos)", width="medium"),
            "produto_base": st.column_config.SelectboxColumn("Equipamento (Produto)", options=[""] + lista_prod, width="medium"),
            "servico_base": st.column_config.SelectboxColumn("Serviço de Instalação", options=[""] + lista_serv, width="medium"),
            "modelo_capa": st.column_config.SelectboxColumn("Modelo da Capa PDF", options=modelos_capa, width="medium")
        }

        df_kits_edit = st.data_editor(df_kits, column_config=cfg_kits, num_rows="dynamic", use_container_width=True, key="editor_kits_lote", hide_index=True)

        if st.button("💾 GRAVAR REGRAS DE KITS", type="primary", use_container_width=True):
            dados_salvar = []
            for _, row in df_kits_edit.iterrows():
                if str(row.get('nome_kit', '')).strip() != "":
                    dados_salvar.append({
                        "nome_kit": row['nome_kit'],
                        "produto_base": str(row.get('produto_base', '')),
                        "servico_base": str(row.get('servico_base', '')),
                        "modelo_capa": str(row.get('modelo_capa', modelos_capa[0]))
                    })
            
            try:
                # Limpa a tabela atual e insere os novos (forma mais simples de sync para tabelas curtas)
                st.session_state.supabase.table('config_kits_lote').delete().neq("nome_kit", "____").execute()
                if dados_salvar:
                    st.session_state.supabase.table('config_kits_lote').insert(dados_salvar).execute()
                st.success("✅ Kits em Lote configurados e salvos com sucesso!")
            except Exception as e:
                st.error(f"Erro ao salvar kits. A tabela 'config_kits_lote' foi criada? Erro: {e}")
