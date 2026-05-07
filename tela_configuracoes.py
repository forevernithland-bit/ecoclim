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
        
        # Mapeia colunas da sua planilha (Sheet1)
        if "PRODUTO" in df.columns: new_df["Item"] = df["PRODUTO"]
        elif "ITEM" in df.columns: new_df["Item"] = df["ITEM"]
        
        if "CUSTO" in df.columns: new_df["Custo (R$)"] = pd.to_numeric(df["CUSTO"], errors='coerce').fillna(0.0)
        
        if "DESCRIÇÃO" in df.columns: new_df["Descrição"] = df["DESCRIÇÃO"].fillna("")
        elif "DESCRICAO" in df.columns: new_df["Descrição"] = df["DESCRICAO"].fillna("")
        
        new_df["Margem (%)"] = 0.0
        new_df["Lucro (R$)"] = 0.0
        new_df["Venda (R$)"] = new_df["Custo (R$)"] if "Custo (R$)" in new_df.columns else 0.0
        
        return new_df

    def exibir_aba(table_name, titulo):
        df = utils.load_catalog(table_name)
        
        # RESTAURADO: CAMPO DE IMPORTAÇÃO
        upl = st.file_uploader(f"Importar Planilha de {titulo} (.xlsx)", type=["xlsx"], key=f"upl_{table_name}")
        if upl:
            if st.button(f"Processar Arquivo - {titulo}"):
                df_importado = processar_upload(upl)
                # Mescla com o que já existe no banco para não perder nada
                df = pd.concat([df, df_importado], ignore_index=True).drop_duplicates(subset=['Item'], keep='last')
                st.session_state[f'df_tmp_{table_name}'] = df
                st.success("✅ Planilha carregada! Verifique os dados abaixo e clique em Gravar.")

        if f'df_tmp_{table_name}' in st.session_state:
            df = st.session_state[f'df_tmp_{table_name}']

        cfg = {
            "Item": st.column_config.TextColumn("Item", width="medium"),
            "Descrição": st.column_config.TextColumn("Descrição / Detalhes", width="large"),
            "Custo (R$)": st.column_config.NumberColumn("Custo", format="R$ %,.2f"),
            "Margem (%)": st.column_config.NumberColumn("Margem %", format="%.2f %%"),
            "Lucro (R$)": st.column_config.NumberColumn("Lucro", format="R$ %,.2f", disabled=True),
            "Venda (R$)": st.column_config.NumberColumn("Venda (Final)", format="R$ %,.2f")
        }
        
        # RESTAURADO: EDITOR COM CÁLCULO DE MARGEM
        df_edit = st.data_editor(df, column_config=cfg, num_rows="dynamic", use_container_width=True, key=f"ed_{table_name}")
        
        # Lógica matemática da Margem
        for i in range(len(df_edit)):
            custo = float(df_edit.at[i, 'Custo (R$)'] or 0)
            margem = float(df_edit.at[i, 'Margem (%)'] or 0)
            venda_atual = float(df_edit.at[i, 'Venda (R$)'] or 0)
            
            if margem > 0:
                venda_calc = custo * (1 + (margem/100))
                df_edit.at[i, 'Venda (R$)'] = venda_calc
                df_edit.at[i, 'Lucro (R$)'] = venda_calc - custo
            else:
                df_edit.at[i, 'Lucro (R$)'] = venda_atual - custo

        if st.button(f"💾 Gravar Alterações em {titulo}", type="primary", key=f"btn_{table_name}"):
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
