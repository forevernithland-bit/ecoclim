import streamlit as st
import pandas as pd
import utils

def renderizar():
    st.markdown("## ⚙️ Configurações e Catálogos")
    
    tabs = st.tabs(["🛒 Produtos", "🛠️ Serviços", "🤝 Outros / Terceiros", "📊 Taxas"])
    
    # --- FUNÇÃO DE IMPORTAÇÃO INTELIGENTE ---
    def processar_upload(uploaded_file):
        df = pd.read_excel(uploaded_file)
        # Limpa espaços e força maiúsculo para bater com o banco
        df.columns = df.columns.str.strip().str.upper()
        
        new_df = pd.DataFrame()
        
        # Mapeia colunas da sua planilha
        if "PRODUTO" in df.columns: new_df["Item"] = df["PRODUTO"]
        elif "ITEM" in df.columns: new_df["Item"] = df["ITEM"]
        else: new_df["Item"] = ""
        
        if "CUSTO" in df.columns: new_df["Custo (R$)"] = pd.to_numeric(df["CUSTO"], errors='coerce').fillna(0.0)
        else: new_df["Custo (R$)"] = 0.0
        
        if "DESCRIÇÃO" in df.columns: new_df["Descrição"] = df["DESCRIÇÃO"].fillna("")
        elif "DESCRICAO" in df.columns: new_df["Descrição"] = df["DESCRICAO"].fillna("")
        else: new_df["Descrição"] = ""
        
        new_df["Margem (%)"] = 0.0
        new_df["Lucro (R$)"] = 0.0
        new_df["Venda (R$)"] = new_df["Custo (R$)"]
        
        return new_df

    def exibir_aba(table_name, titulo):
        df = utils.load_catalog(table_name)
        
        # 1. ÁREA DE IMPORTAÇÃO
        st.markdown(f"#### 📥 Importar Planilha de {titulo}")
        upl = st.file_uploader(f"Selecione o arquivo Excel (.xlsx)", type=["xlsx"], key=f"upl_{table_name}")
        if upl:
            if st.button(f"Processar Arquivo - {titulo}"):
                df_importado = processar_upload(upl)
                # Mescla e zera o índice para evitar KeyError
                df = pd.concat([df, df_importado], ignore_index=True).drop_duplicates(subset=['Item'], keep='last')
                df = df.reset_index(drop=True)
                st.session_state[f'df_tmp_{table_name}'] = df
                st.success("✅ Planilha carregada! Verifique os dados abaixo e clique em Gravar.")

        if f'df_tmp_{table_name}' in st.session_state:
            df = st.session_state[f'df_tmp_{table_name}']

        # GARANTIA FINAL CONTRA KEYERROR
        df = df.reset_index(drop=True)

        st.markdown("---")
        
        # 2. FERRAMENTA DE MARGEM AUTOMÁTICA EM MASSA
        st.markdown("#### ⚡ Ações Rápidas: Margem Automática")
        c1, c2 = st.columns([1, 3])
        with c1:
            margem_global = st.number_input("Definir Margem (%)", min_value=0.0, format="%.2f", key=f"mg_{table_name}")
        with c2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button(f"Aplicar {margem_global}% a todos os itens da tabela", key=f"btn_mg_{table_name}"):
                # Matemática Vetorizada ultra segura e rápida
                df['Margem (%)'] = margem_global
                df['Custo (R$)'] = pd.to_numeric(df['Custo (R$)'], errors='coerce').fillna(0.0)
                df['Margem (%)'] = pd.to_numeric(df['Margem (%)'], errors='coerce').fillna(0.0)
                df['Venda (R$)'] = df['Custo (R$)'] * (1 + (df['Margem (%)']/100))
                df['Lucro (R$)'] = df['Venda (R$)'] - df['Custo (R$)']
                
                st.session_state[f'df_tmp_{table_name}'] = df
                st.rerun()

        st.markdown("#### 📋 Catálogo Atual")
        
        cfg = {
            "Item": st.column_config.TextColumn("Item", width="medium"),
            "Descrição": st.column_config.TextColumn("Descrição / Detalhes", width="large"),
            "Custo (R$)": st.column_config.NumberColumn("Custo", format="R$ %,.2f"),
            "Margem (%)": st.column_config.NumberColumn("Margem %", format="%.2f %%"),
            "Lucro (R$)": st.column_config.NumberColumn("Lucro", format="R$ %,.2f", disabled=True),
            "Venda (R$)": st.column_config.NumberColumn("Venda (Final)", format="R$ %,.2f")
        }
        
        # O Editor da Tabela
        df_edit = st.data_editor(df, column_config=cfg, num_rows="dynamic", use_container_width=True, key=f"ed_{table_name}")
        
        # Resetando índice do editor para blindar totalmente
        df_edit = df_edit.reset_index(drop=True)
        
        # Matemática protegida em tempo real
        df_edit['Custo (R$)'] = pd.to_numeric(df_edit['Custo (R$)'], errors='coerce').fillna(0.0)
        df_edit['Margem (%)'] = pd.to_numeric(df_edit['Margem (%)'], errors='coerce').fillna(0.0)
        df_edit['Venda (R$)'] = pd.to_numeric(df_edit['Venda (R$)'], errors='coerce').fillna(0.0)
        
        # Aplica Venda e Lucro onde a margem é maior que zero
        mask = df_edit['Margem (%)'] > 0
        df_edit.loc[mask, 'Venda (R$)'] = df_edit.loc[mask, 'Custo (R$)'] * (1 + (df_edit.loc[mask, 'Margem (%)'] / 100))
        df_edit['Lucro (R$)'] = df_edit['Venda (R$)'] - df_edit['Custo (R$)']

        st.markdown("<br>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🧮 ATUALIZAR CÁLCULOS NA TELA", use_container_width=True, key=f"atualizar_{table_name}"):
                st.session_state[f'df_tmp_{table_name}'] = df_edit
                st.rerun()
        with col2:
            if st.button(f"💾 GRAVAR ALTERAÇÕES", type="primary", use_container_width=True, key=f"btn_save_{table_name}"):
                utils.save_catalog(table_name, df_edit)
                if f'df_tmp_{table_name}' in st.session_state: del st.session_state[f'df_tmp_{table_name}']
                st.success(f"Catálogo de {titulo} atualizado com sucesso!")
                st.rerun()

    with tabs[0]: exibir_aba('catalogo_produtos', 'Produtos')
    with tabs[1]: exibir_aba('catalogo_servicos', 'Serviços')
    with tabs[2]: exibir_aba('catalogo_outros', 'Terceiros')
    
    with tabs[3]:
        st.subheader("📊 Taxas e Impostos")
        df_t = utils.load_taxas()
        df_t_ed = st.data_editor(df_t, use_container_width=True, num_rows="dynamic")
        if st.button("💾 Gravar Taxas", type="primary"):
            utils.save_taxas(df_t_ed)
            st.success("Taxas salvas!")
