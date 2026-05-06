import streamlit as st
import pandas as pd
import utils

def renderizar():
    st.markdown("## ⚙️ Configurações e Base de Dados")
    
    col_exp1, col_exp2 = st.columns([2, 1])
    with col_exp2:
        df_download = utils.load_catalog('catalogo_produtos')
        excel_data = utils.to_excel(df_download)
        st.download_button(
            label="📥 Baixar Base de Equipamentos (Excel)", 
            data=excel_data, 
            file_name="Ecoclim_Equipamentos.xlsx", 
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
            use_container_width=True
        )

    with st.expander("📤 Importar/Atualizar Dados via Planilha Excel", expanded=False):
        st.write("A planilha deve conter as colunas: **PRODUTO**, **FORNECEDOR**, **CUSTO**, **DESCRIÇÃO**")
        
        margem_padrao_importacao = st.number_input("Definir Margem Padrão (%) para os itens da planilha:", value=32.0, step=1.0, format="%.1f")
        sobreescrever_margem = st.checkbox(f"Aplicar esta margem de {margem_padrao_importacao}% inclusive nos itens que JÁ EXISTEM no sistema?", value=True)
        
        file = st.file_uploader("Subir .xlsx ou .csv", type=["xlsx", "csv"])
        
        if file:
            try:
                if file.name.endswith(".csv"): 
                    df_ex = pd.read_csv(file)
                else: 
                    df_ex = pd.read_excel(file)
                
                df_ex.columns = df_ex.columns.str.strip().str.upper()
                
                if "PRODUTO" in df_ex.columns and "CUSTO" in df_ex.columns:
                    if st.button("🚀 Sincronizar Equipamentos", type="primary"):
                        db_atual = utils.load_catalog('catalogo_produtos')
                        itens_atualizados = 0
                        itens_novos = 0
                        
                        for _, row in df_ex.iterrows():
                            item_nome = str(row["PRODUTO"]).strip()
                            if not item_nome or item_nome.lower() == "nan": continue
                            
                            custo = float(row["CUSTO"]) if pd.notna(row["CUSTO"]) else 0.0
                            desc = str(row["DESCRIÇÃO"]).strip() if "DESCRIÇÃO" in df_ex.columns and pd.notna(row["DESCRIÇÃO"]) else ""
                            forn = str(row["FORNECEDOR"]).strip() if "FORNECEDOR" in df_ex.columns and pd.notna(row["FORNECEDOR"]) else ""
                            
                            if item_nome in db_atual["Item"].values:
                                idx = db_atual.index[db_atual["Item"] == item_nome][0]
                                db_atual.at[idx, "Custo (R$)"] = custo
                                db_atual.at[idx, "Fornecedor"] = forn
                                if desc != "": db_atual.at[idx, "Descrição"] = desc
                                if sobreescrever_margem: db_atual.at[idx, "Margem (%)"] = margem_padrao_importacao
                                itens_atualizados += 1
                            else:
                                novo = pd.DataFrame([{"Item": item_nome, "Fornecedor": forn, "Custo (R$)": custo, "Margem (%)": margem_padrao_importacao, "Lucro (R$)": 0.0, "Venda (R$)": 0.0, "Descrição": desc}])
                                db_atual = pd.concat([db_atual, novo], ignore_index=True)
                                itens_novos += 1
                        
                        db_atual['Venda (R$)'] = (db_atual['Custo (R$)'] * (1 + db_atual['Margem (%)'] / 100)).fillna(0).round().astype(float)
                        db_atual['Lucro (R$)'] = (db_atual['Venda (R$)'] - db_atual['Custo (R$)']).astype(float)
                        utils.save_catalog('catalogo_produtos', db_atual)
                        
                        st.success(f"Sincronização Concluída! {itens_atualizados} atualizados, {itens_novos} adicionados.")
                        st.rerun()
                else:
                    st.error("Colunas obrigatórias não encontradas: PRODUTO, CUSTO.")
            except Exception as e: 
                st.error(f"Erro: {e}")

    tab1, tab2, tab3 = st.tabs(["🛒 Equipamentos", "🛠️ Serviços", "➕ Terceirizados"])
    
    def render_editor(table_name):
        df_db = utils.load_catalog(table_name)
        
        # --- CAMPO DE PESQUISA INTELIGENTE ---
        busca = st.text_input(f"🔍 Pesquisar em {table_name.split('_')[1].title()} (Busca por nome ou fornecedor)", "", key=f"busca_{table_name}")
        
        if busca:
            mask = df_db['Item'].str.contains(busca, case=False, na=False) | df_db['Fornecedor'].str.contains(busca, case=False, na=False)
            df_view = df_db[mask].copy()
        else:
            df_view = df_db.copy()

        col_cfg = {
            "Item": st.column_config.TextColumn("Item", width="large"),
            "Fornecedor": st.column_config.TextColumn("Fornecedor", width="medium"),
            "Custo (R$)": st.column_config.NumberColumn("Custo", format="R$ %,.2f"),
            "Margem (%)": st.column_config.NumberColumn("Margem", format="%.1f%%"),
            "Lucro (R$)": st.column_config.NumberColumn("Lucro", disabled=True, format="R$ %,.2f"),
            "Venda (R$)": st.column_config.NumberColumn("Venda (Final)", disabled=True, format="R$ %,.2f"),
            "Descrição": st.column_config.TextColumn("Descrição PDF", width="large")
        }
        
        df_edit = st.data_editor(df_view, num_rows="dynamic", column_config=col_cfg, use_container_width=True, key=f"editor_{table_name}")
        
        df_edit['Venda (R$)'] = (df_edit['Custo (R$)'] * (1 + df_edit['Margem (%)'] / 100)).fillna(0).round().astype(float)
        df_edit['Lucro (R$)'] = (df_edit['Venda (R$)'] - df_edit['Custo (R$)']).astype(float)
        
        if st.button(f"💾 Gravar Alterações: {table_name}"):
            if busca:
                df_restante = df_db[~mask]
                df_final = pd.concat([df_restante, df_edit], ignore_index=True)
            else:
                df_final = df_edit
                
            utils.save_catalog(table_name, df_final)
            st.success("Base de dados atualizada!")
            st.rerun()

    with tab1: render_editor('catalogo_produtos')
    with tab2: render_editor('catalogo_servicos')
    with tab3: render_editor('catalogo_outros')
