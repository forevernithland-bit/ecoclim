import streamlit as st
import pandas as pd
import utils

def renderizar():
    st.markdown("## ⚙️ Configurações e Base de Dados")
    
    col_exp1, col_exp2 = st.columns([2, 1])
    with col_exp2:
        df_download = utils.load_catalog('catalogo_produtos')
        excel_data = utils.to_excel(df_download)
        st.download_button("📥 Baixar Base de Equipamentos (Excel)", data=excel_data, file_name="Ecoclim_Equipamentos.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

    with st.expander("📤 Importar Dados via Planilha Excel", expanded=False):
        # (Lógica de importação mantida idêntica à sua)
        margem_padrao = st.number_input("Margem Padrão (%) para importação:", value=32.0, step=1.0)
        sobreescrever = st.checkbox("Aplicar margem nos itens que JÁ EXISTEM?", value=True)
        file = st.file_uploader("Subir .xlsx ou .csv", type=["xlsx", "csv"])
        
        if file and st.button("🚀 Sincronizar Equipamentos", type="primary"):
            df_ex = pd.read_csv(file) if file.name.endswith(".csv") else pd.read_excel(file)
            df_ex.columns = df_ex.columns.str.strip().str.upper()
            
            if "PRODUTO" in df_ex.columns and "CUSTO" in df_ex.columns:
                db_atual = utils.load_catalog('catalogo_produtos')
                for _, row in df_ex.iterrows():
                    item_nome = str(row["PRODUTO"]).strip()
                    if not item_nome or item_nome.lower() == "nan": continue
                    custo = float(row["CUSTO"]) if pd.notna(row["CUSTO"]) else 0.0
                    if item_nome in db_atual["Item"].values:
                        idx = db_atual.index[db_atual["Item"] == item_nome][0]
                        db_atual.at[idx, "Custo (R$)"] = custo
                        if sobreescrever: db_atual.at[idx, "Margem (%)"] = margem_padrao
                    else:
                        db_atual = pd.concat([db_atual, pd.DataFrame([{"Item": item_nome, "Custo (R$)": custo, "Margem (%)": margem_padrao, "Lucro (R$)": 0, "Venda (R$)": 0}])], ignore_index=True)
                
                db_atual['Venda (R$)'] = (db_atual['Custo (R$)'] * (1 + db_atual['Margem (%)'] / 100)).fillna(0).round().astype(float)
                utils.save_catalog('catalogo_produtos', db_atual)
                st.success("Sincronizado!"); st.rerun()

    # --- AS 4 ABAS ---
    tab1, tab2, tab3, tab4 = st.tabs(["🛒 Equipamentos", "🛠️ Serviços", "➕ Terceirizados", "💳 Pagamentos / Impostos"])
    
    def render_editor(table_name):
        df_db = utils.load_catalog(table_name)
        df_edit = st.data_editor(df_db, num_rows="dynamic", use_container_width=True, key=f"editor_{table_name}")
        df_edit['Venda (R$)'] = (df_edit['Custo (R$)'] * (1 + df_edit['Margem (%)'] / 100)).fillna(0).round().astype(float)
        df_edit['Lucro (R$)'] = (df_edit['Venda (R$)'] - df_edit['Custo (R$)']).astype(float)
        if st.button(f"💾 Gravar Alterações", key=f"btn_{table_name}"):
            utils.save_catalog(table_name, df_edit); st.success("Atualizado!"); st.rerun()

    with tab1: render_editor('catalogo_produtos')
    with tab2: render_editor('catalogo_servicos')
    with tab3: render_editor('catalogo_outros')
    
    with tab4:
        st.write("Adicione aqui as taxas de cartão (ex: Crédito 4x, Débito) e o imposto da Nota Fiscal.")
        df_taxas = utils.load_taxas()
        col_cfg = {"Item": st.column_config.TextColumn("Descrição (Ex: Crédito 10x)"), "Taxa (%)": st.column_config.NumberColumn("Taxa %", format="%.2f %%")}
        df_edit_taxas = st.data_editor(df_taxas, column_config=col_cfg, num_rows="dynamic", use_container_width=True, key="editor_taxas")
        if st.button("💾 Gravar Taxas"):
            utils.save_taxas(df_edit_taxas); st.success("Taxas atualizadas!"); st.rerun()
