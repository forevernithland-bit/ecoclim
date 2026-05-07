import streamlit as st
import pandas as pd
import utils

def renderizar():
    st.markdown("## ⚙️ Configurações e Catálogos")
    
    tabs = st.tabs(["🛒 Produtos", "🛠️ Serviços", "🤝 Outros / Terceiros", "📊 Taxas"])
    
    def processar_upload(uploaded_file):
        df = pd.read_excel(uploaded_file)
        
        # Garante que vai ler os nomes das colunas exatamente como estão na sua nova planilha
        df.columns = df.columns.str.strip().str.upper()
        
        new_df = pd.DataFrame()
        
        # Puxa a coluna PRODUTO
        if "PRODUTO" in df.columns: 
            new_df["Item"] = df["PRODUTO"]
        elif "ITEM" in df.columns: 
            new_df["Item"] = df["ITEM"]
        else: 
            new_df["Item"] = "Sem Nome"
        
        # Puxa a coluna CUSTO
        if "CUSTO" in df.columns: 
            new_df["Custo (R$)"] = pd.to_numeric(df["CUSTO"], errors='coerce').fillna(0.0)
        elif "VALOR" in df.columns: 
            new_df["Custo (R$)"] = pd.to_numeric(df["VALOR"], errors='coerce').fillna(0.0)
        else: 
            new_df["Custo (R$)"] = 0.0
        
        # Puxa a coluna DESCRIÇÃO perfeitamente
        if "DESCRIÇÃO" in df.columns: 
            new_df["Descrição"] = df["DESCRIÇÃO"].fillna("")
        elif "DESCRICAO" in df.columns: 
            new_df["Descrição"] = df["DESCRICAO"].fillna("")
        else: 
            new_df["Descrição"] = ""
        
        # Preenche os campos de cálculo financeiro
        new_df["Margem (%)"] = 0.0
        new_df["Lucro (R$)"] = 0.0
        new_df["Venda (R$)"] = new_df["Custo (R$)"]
        
        return new_df

    def exibir_aba(table_name, titulo):
        df = utils.load_catalog(table_name)
        
        upl = st.file_uploader(f"Importar Planilha ({titulo})", type=["xlsx"], key=f"upl_{table_name}")
        if upl:
            if st.button(f"Processar Planilha - {titulo}"):
                df_novo = processar_upload(upl)
                
                # Junta o banco atual com a planilha nova
                df = pd.concat([df, df_novo], ignore_index=True).drop_duplicates(subset=['Item'], keep='last')
                st.session_state[f'df_tmp_{table_name}'] = df
                st.success("✅ Planilha processada! Verifique a tabela abaixo e clique em 'Gravar Alterações'.")
        
        if f'df_tmp_{table_name}' in st.session_state:
            df = st.session_state[f'df_tmp_{table_name}']

        cfg = {
            "Item": st.column_config.TextColumn("Item", width="medium"),
            "Descrição": st.column_config.TextColumn("Descrição / Detalhes", width="large"),
            "Custo (R$)": st.column_config.NumberColumn("Custo (R$)", format="R$ %.2f"),
            "Margem (%)": st.column_config.NumberColumn("Margem (%)", format="%.2f %%"),
            "Lucro (R$)": st.column_config.NumberColumn("Lucro (R$)", format="R$ %.2f", disabled=True),
            "Venda (R$)": st.column_config.NumberColumn("Venda (R$)", format="R$ %.2f")
        }
        
        df_edit = st.data_editor(df, column_config=cfg, num_rows="dynamic", use_container_width=True, key=f"ed_{table_name}")
        
        # Matemática da Tabela
        df_edit['Custo (R$)'] = pd.to_numeric(df_edit['Custo (R$)'], errors='coerce').fillna(0.0)
        df_edit['Margem (%)'] = pd.to_numeric(df_edit['Margem (%)'], errors='coerce').fillna(0.0)
        df_edit['Venda (R$)'] = pd.to_numeric(df_edit['Venda (R$)'], errors='coerce').fillna(0.0)
        
        for i in range(len(df_edit)):
            c = df_edit.at[i, 'Custo (R$)']
            m = df_edit.at[i, 'Margem (%)']
            v = df_edit.at[i, 'Venda (R$)']
            
            if m > 0 and v <= c:
                v_novo = c * (1 + m/100)
                df_edit.at[i, 'Venda (R$)'] = v_novo
                df_edit.at[i, 'Lucro (R$)'] = v_novo - c
            else:
                df_edit.at[i, 'Lucro (R$)'] = v - c

        if st.button(f"💾 Gravar Alterações ({titulo})", type="primary", key=f"btn_{table_name}"):
            utils.save_catalog(table_name, df_edit)
            if f'df_tmp_{table_name}' in st.session_state:
                del st.session_state[f'df_tmp_{table_name}']
            
            # Limpa o cache da tela de orçamentos para ele buscar a nova descrição na hora!
            for key in ['db_produtos', 'db_servicos', 'db_outros', 'df_orc', 'df_orc_prev']:
                if key in st.session_state:
                    del st.session_state[key]
                    
            st.success(f"Catálogo de {titulo} atualizado no banco de dados!")
            st.rerun()

    with tabs[0]: exibir_aba('catalogo_produtos', 'Produtos')
    with tabs[1]: exibir_aba('catalogo_servicos', 'Serviços')
    with tabs[2]: exibir_aba('catalogo_outros', 'Terceiros')
    
    with tabs[3]:
        st.subheader("📊 Taxas e Impostos")
        df_t = utils.load_taxas()
        cfg_t = {
            "Item": st.column_config.TextColumn("Descrição da Taxa"),
            "Taxa (%)": st.column_config.NumberColumn("Taxa (%)", format="%.2f %%")
        }
        df_t_ed = st.data_editor(df_t, column_config=cfg_t, num_rows="dynamic", use_container_width=True)
        if st.button("💾 Gravar Taxas", type="primary"):
            utils.save_taxas(df_t_ed)
            st.success("Taxas salvas!")
