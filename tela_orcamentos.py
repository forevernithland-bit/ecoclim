import streamlit as st
import pandas as pd
import utils

def renderizar():
    st.markdown("## 📝 Novo Orçamento")
    
    if 'db_produtos' not in st.session_state:
        st.session_state.db_produtos = utils.load_catalog('catalogo_produtos')
        st.session_state.db_servicos = utils.load_catalog('catalogo_servicos')
        st.session_state.db_outros = utils.load_catalog('catalogo_outros')

    cat_p = st.session_state.db_produtos
    lista_p = cat_p['Item'].tolist()
    
    cat_s = st.session_state.db_servicos
    lista_s = cat_s['Item'].tolist()
    
    cat_o = st.session_state.db_outros
    lista_o = cat_o['Item'].tolist()
    
    with st.container(border=True):
        st.subheader("👤 Cliente")
        c1, c2 = st.columns(2)
        nome_c = c1.text_input("Nome do Cliente")
        tel_c = c2.text_input("WhatsApp")
        capa = st.selectbox("Modelo para Capa", [
            "AQUECEDOR SOLAR TRADICIONAL", 
            "AQUECEDOR SOLAR A VÁCUO ACOPLADO", 
            "AQUECEDOR SOLAR MODULAR", 
            "AQUECEDOR DE PISCINA - TRADICIONAL", 
            "AQUECEDOR DE PISCINA - TROCADOR DE CALOR", 
            "SISTEMAS DE PRESSURIZAÇÃO"
        ])

    with st.container(border=True):
        st.subheader("⚙️ 1. Equipamentos")
        mostrar_pdf = st.checkbox("Mostrar Preços Unitários no PDF?", value=True)
        if 'df_orc' not in st.session_state:
            st.session_state.df_orc = pd.DataFrame([{"Produto da Base": "", "Produto Manual": "", "Quantidade": 1, "Venda (R$)": 0.0} for _ in range(5)])
        
        cfg = {
            "Produto da Base": st.column_config.SelectboxColumn("Produto", options=[""] + lista_p + ["OUTRO"], width="large"), 
            "Produto Manual": st.column_config.TextColumn("Produto Manual", width="medium"),
            "Venda (R$)": st.column_config.NumberColumn("Preço Un.", format="R$ %,.2f")
        }
        df_ed = st.data_editor(st.session_state.df_orc, column_config=cfg, num_rows="dynamic", use_container_width=True)
        
        for i in range(len(df_ed)):
            p = df_ed.at[i, 'Produto da Base']
            if p in lista_p and df_ed.at[i, 'Venda (R$)'] == 0:
                df_ed.at[i, 'Venda (R$)'] = float(cat_p.loc[cat_p['Item'] == p, 'Venda (R$)'].values[0])
                st.session_state.df_orc = df_ed
                st.rerun()
        
        st.session_state.df_orc = df_ed
        total_e = sum(df_ed['Quantidade'] * df_ed['Venda (R$)'])
        st.write(f"**Subtotal Equipamentos:** {utils.to_br_currency(total_e)}")

    with st.container(border=True):
        st.subheader("🛠️ 2. Serviços / Diversos")
        s_sel = st.selectbox("Selecionar Serviço:", [""] + lista_s + ["Manual"])
        if s_sel == "Manual": 
            d_s = st.text_area("Descreva:")
            v_s = st.number_input("Valor:", min_value=0.0, format="%.2f")
        elif s_sel != "":
            d_s = f"{s_sel}\n{cat_s.loc[cat_s['Item']==s_sel, 'Descrição'].values[0]}"
            v_s = float(cat_s.loc[cat_s['Item']==s_sel, 'Venda (R$)'].values[0])
            st.write(f"Valor: {utils.to_br_currency(v_s)}")
        else: 
            d_s, v_s = "", 0.0
        
        o_sel = st.selectbox("Selecionar Diversos:", [""] + lista_o + ["Manual"])
        if o_sel == "Manual": 
            d_o = st.text_area("Descreva: ")
            v_o = st.number_input("Valor Adicional:", min_value=0.0, format="%.2f")
        elif o_sel != "":
            d_o = f"{o_sel}\n{cat_o.loc[cat_o['Item']==o_sel, 'Descrição'].values[0]}"
            v_o = float(cat_o.loc[cat_o['Item']==o_sel, 'Venda (R$)'].values[0])
            st.write(f"Valor: {utils.to_br_currency(v_o)}")
        else: 
            d_o, v_o = "", 0.0

    total_g = total_e + v_s + v_o
    st.markdown(f"<h3 style='color:#004488;'>💰 INVESTIMENTO TOTAL: {utils.to_br_currency(total_g)}</h3>", unsafe_allow_html=True)
    obs = st.text_area("Notas (Aparece no PDF):", value="Material Hidráulico não incluído na proposta")

    if st.button("🚀 GUARDAR CRM E GERAR PDF", type="primary"):
        if nome_c:
            try:
                st.session_state.supabase.table("clientes_orcamentos").insert({
                    "nome": nome_c, 
                    "telefone": tel_c, 
                    "produto_ref": capa, 
                    "valor_total": total_g, 
                    "status": "Em fase de orçamento"
                }).execute()
                st.success("Guardado no CRM!")
            except Exception as e: 
                st.warning(f"Erro ao guardar no Supabase: {e}")
            
            pdf_bytes = utils.gerar_pdf_orcamento(nome_c, tel_c, capa, df_ed, d_s, v_s, d_o, v_o, total_g, obs, mostrar_pdf)
            st.download_button(
                label="📥 DESCARREGAR ORÇAMENTO (PDF)", 
                data=pdf_bytes, 
                file_name=f"Orcamento_{nome_c}.pdf", 
                mime="application/pdf", 
                use_container_width=True
            )
        else: 
            st.error("Por favor, digite o nome do cliente!")
