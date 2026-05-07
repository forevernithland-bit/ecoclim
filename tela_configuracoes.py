import streamlit as st
import pandas as pd
import utils

def renderizar():
    st.markdown("## ⚙️ Configurações e Catálogos")
    tabs = st.tabs(["🛒 Produtos", "🛠️ Serviços", "🤝 Outros / Terceiros", "📊 Taxas"])
    
    def exibir_aba(table_name, titulo):
        df = utils.load_catalog(table_name)
        cfg = {
            "Item": st.column_config.TextColumn("Item", width="medium"),
            "Descrição": st.column_config.TextColumn("Descrição / Detalhes", width="large"),
            "Custo (R$)": st.column_config.NumberColumn("Custo", format="R$ %.2f"),
            "Margem (%)": st.column_config.NumberColumn("Margem %", format="%.2f %%"),
            "Lucro (R$)": st.column_config.NumberColumn("Lucro", format="R$ %.2f", disabled=True),
            "Venda (R$)": st.column_config.NumberColumn("Venda", format="R$ %.2f")
        }
        
        df_edit = st.data_editor(df, column_config=cfg, num_rows="dynamic", use_container_width=True, key=f"ed_{table_name}")
        
        # MOTOR DE CÁLCULO DE MARGEM AUTOMÁTICA
        for i in range(len(df_edit)):
            custo = float(df_edit.at[i, 'Custo (R$)'] or 0)
            margem = float(df_edit.at[i, 'Margem (%)'] or 0)
            venda = float(df_edit.at[i, 'Venda (R$)'] or 0)
            
            if margem > 0:
                venda_calc = custo * (1 + (margem/100))
                df_edit.at[i, 'Venda (R$)'] = venda_calc
                df_edit.at[i, 'Lucro (R$)'] = venda_calc - custo
            else:
                df_edit.at[i, 'Lucro (R$)'] = venda - custo

        if st.button(f"💾 Gravar Alterações ({titulo})", type="primary", key=f"btn_{table_name}"):
            utils.save_catalog(table_name, df_edit)
            st.success(f"Catálogo de {titulo} atualizado!")
            st.rerun()

    with tabs[0]: exibir_aba('catalogo_produtos', 'Produtos')
    with tabs[1]: exibir_aba('catalogo_servicos', 'Serviços')
    with tabs[2]: exibir_aba('catalogo_outros', 'Terceiros')
    with tabs[3]:
        st.subheader("📊 Taxas e Impostos")
        df_t = utils.load_taxas()
        df_t_ed = st.data_editor(df_t, use_container_width=True, num_rows="dynamic")
        if st.button("💾 Gravar Taxas", type="primary"): utils.save_taxas(df_t_ed); st.success("Taxas salvas!")
