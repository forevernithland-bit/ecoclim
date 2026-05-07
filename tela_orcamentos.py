import streamlit as st
import pandas as pd
import datetime
import utils

def renderizar():
    st.markdown("## 📝 Novo Orçamento")
    if st.button("🔄 ATUALIZAR DADOS"):
        for key in ['db_produtos', 'db_servicos', 'db_outros', 'df_orc', 'df_orc_prev']:
            if key in st.session_state: del st.session_state[key]
        st.rerun()

    if 'db_produtos' not in st.session_state: st.session_state.db_produtos = utils.load_catalog('catalogo_produtos')
    if 'db_servicos' not in st.session_state: st.session_state.db_servicos = utils.load_catalog('catalogo_servicos')
    if 'db_outros' not in st.session_state: st.session_state.db_outros = utils.load_catalog('catalogo_outros')

    cat_p = st.session_state.db_produtos
    lista_p = cat_p['Item'].tolist() if not cat_p.empty else []
    
    with st.container(border=True):
        st.subheader("👤 Cliente")
        c1, c2 = st.columns(2)
        nome_c = c1.text_input("Nome", key="nome_c")
        tel_c = c2.text_input("WhatsApp", placeholder="(31) 99715-1596")
        capa = st.selectbox("Capa", ["AQUECEDOR SOLAR TRADICIONAL", "AQUECEDOR SOLAR A VÁCUO ACOPLADO", "AQUECEDOR SOLAR MODULAR", "AQUECEDOR DE PISCINA - TRADICIONAL", "AQUECEDOR DE PISCINA - TROCADOR DE CALOR", "SISTEMAS DE PRESSURIZAÇÃO"], index=1)

    with st.container(border=True):
        st.subheader("⚙️ Equipamentos")
        if 'df_orc' not in st.session_state:
            st.session_state.df_orc = pd.DataFrame([{"Produto da Base": "", "Produto Manual": "", "Descrição": "", "Quantidade": 0, "Venda (R$)": 0.0, "Venda Total": 0.0} for _ in range(5)])
        if 'df_orc_prev' not in st.session_state:
            st.session_state.df_orc_prev = st.session_state.df_orc.copy()
        
        cfg = {"Produto da Base": st.column_config.SelectboxColumn("Produto", options=[""] + lista_p + ["OUTRO"], width="medium"), "Descrição": st.column_config.TextColumn("Detalhes", width="large"), "Venda (R$)": st.column_config.NumberColumn("Venda Un.", format="R$ %,.2f")}
        df_ed = st.data_editor(st.session_state.df_orc, column_config=cfg, num_rows="dynamic", use_container_width=True)
        
        precisa_atualizar = False
        for i in range(len(df_ed)):
            p = df_ed.at[i, 'Produto da Base']
            p_prev = st.session_state.df_orc_prev.at[i, 'Produto da Base'] if i < len(st.session_state.df_orc_prev) else ""
            if p != p_prev and p in lista_p:
                match = cat_p[cat_p['Item'] == p]
                if not match.empty:
                    # PUXANDO COLUNA VENDA (R$) DA BASE
                    df_ed.at[i, 'Venda (R$)'] = float(match['Venda (R$)'].values[0])
                    df_ed.at[i, 'Descrição'] = str(match['Descrição'].values[0])
                    if df_ed.at[i, 'Quantidade'] == 0: df_ed.at[i, 'Quantidade'] = 1
                    precisa_atualizar = True
        
        df_ed['Venda Total'] = df_ed['Venda (R$)'] * df_ed['Quantidade']
        if precisa_atualizar:
            st.session_state.df_orc = df_ed; st.session_state.df_orc_prev = df_ed.copy(); st.rerun()
        st.session_state.df_orc = df_ed; st.session_state.df_orc_prev = df_ed.copy()
        
        total_equip = df_ed['Venda Total'].sum()
        st.write(f"Subtotal: {utils.to_br_currency(total_equip)}")

    # (Restante dos botões de salvar e PDF seguem o padrão robusto anterior)
