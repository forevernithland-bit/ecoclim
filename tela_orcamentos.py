import streamlit as st
import pandas as pd
import datetime
import utils

def renderizar():
    st.markdown("## 📝 Novo Orçamento")
    
    if st.button("🔄 ATUALIZAR DADOS DO BANCO"):
        for key in ['db_produtos', 'db_servicos', 'db_outros', 'df_orc', 'df_orc_prev']:
            if key in st.session_state: del st.session_state[key]
        st.rerun()

    if 'db_produtos' not in st.session_state: st.session_state.db_produtos = utils.load_catalog('catalogo_produtos')
    if 'db_servicos' not in st.session_state: st.session_state.db_servicos = utils.load_catalog('catalogo_servicos')
    if 'db_outros' not in st.session_state: st.session_state.db_outros = utils.load_catalog('catalogo_outros')

    cat_p = st.session_state.db_produtos
    lista_p = cat_p['Item'].tolist() if not cat_p.empty else []
    
    with st.container(border=True):
        st.subheader("👤 Dados do Cliente")
        c1, c2 = st.columns(2)
        nome_c = c1.text_input("Nome do Cliente", key="nome_cliente_orc")
        tel_c = c2.text_input("WhatsApp", placeholder="(31) 99715-1596", key="tel_cliente_orc")
        capa = st.selectbox("Modelo para Capa", ["AQUECEDOR SOLAR TRADICIONAL", "AQUECEDOR SOLAR A VÁCUO ACOPLADO", "AQUECEDOR SOLAR MODULAR", "AQUECEDOR DE PISCINA - TRADICIONAL", "AQUECEDOR DE PISCINA - TROCADOR DE CALOR", "SISTEMAS DE PRESSURIZAÇÃO"], index=1)

    with st.container(border=True):
        st.subheader("⚙️ 1. Equipamentos")
        mostrar_pdf = st.checkbox("Mostrar Preços Unitários no PDF?", value=False)
        
        # AQUI FOI CORRIGIDO O ATTRIBUTE ERROR: Assegurando que a cópia sempre existe
        if 'df_orc' not in st.session_state:
            st.session_state.df_orc = pd.DataFrame([{"Produto da Base": "", "Produto Manual": "", "Descrição": "", "Quantidade": 0, "Venda (R$)": 0.0, "Venda Total": 0.0} for _ in range(5)])
        if 'df_orc_prev' not in st.session_state:
            st.session_state.df_orc_prev = st.session_state.df_orc.copy()
        
        cfg = {
            "Produto da Base": st.column_config.SelectboxColumn("Produto", options=[""] + lista_p + ["OUTRO"], width="medium"), 
            "Produto Manual": st.column_config.TextColumn("Produto Manual", width="medium"),
            "Descrição": st.column_config.TextColumn("Detalhes / Garantia", width="large"),
            "Quantidade": st.column_config.NumberColumn("Qtd", min_value=0, step=1),
            "Venda (R$)": st.column_config.NumberColumn("Preço Un. (Venda)", format="R$ %,.2f"),
            "Venda Total": st.column_config.NumberColumn("Venda Total", format="R$ %,.2f", disabled=True)
        }
        
        df_ed = st.data_editor(st.session_state.df_orc, column_config=cfg, num_rows="dynamic", use_container_width=True)
        df_ed = df_ed.reset_index(drop=True)
        
        precisa_atualizar = False
        for i in range(len(df_ed)):
            p = df_ed.at[i, 'Produto da Base']
            p_prev = st.session_state.df_orc_prev.at[i, 'Produto da Base'] if i < len(st.session_state.df_orc_prev) else ""
            if p != p_prev and p in lista_p:
                match = cat_p[cat_p['Item'] == p]
                if not match.empty:
                    df_ed.at[i, 'Venda (R$)'] = float(match['Venda (R$)'].values[0])
                    df_ed.at[i, 'Descrição'] = str(match['Descrição'].values[0]) if 'Descrição' in match.columns and str(match['Descrição'].values[0]) != 'nan' else ""
                    if df_ed.at[i, 'Quantidade'] == 0: df_ed.at[i, 'Quantidade'] = 1
                    precisa_atualizar = True
                
        df_ed['Venda Total'] = df_ed['Venda (R$)'] * df_ed['Quantidade']
        if precisa_atualizar:
            st.session_state.df_orc = df_ed
            st.session_state.df_orc_prev = df_ed.copy()
            st.rerun()
            
        st.session_state.df_orc = df_ed
        st.session_state.df_orc_prev = df_ed.copy()
        total_equip = df_ed['Venda Total'].sum()
        st.markdown(f"**Subtotal Equipamentos:** :blue[{utils.to_br_currency(total_equip)}]")

    with st.container(border=True):
        st.subheader("🛠️ 2. Serviços / Diversos")
        
        # DESCRIÇÃO DE SERVIÇOS ROBUSTA RESTAURADA
        lista_s = st.session_state.db_servicos['Item'].tolist() if not st.session_state.db_servicos.empty else []
        if 's_sel_atual' not in st.session_state: st.session_state.s_sel_atual = ""
        s_sel = st.selectbox("Selecionar Serviço Principal:", [""] + lista_s + ["Manual"])
        
        if s_sel != st.session_state.s_sel_atual:
            st.session_state.s_sel_atual = s_sel
            if s_sel == "Manual":
                st.session_state.desc_serv_txt, st.session_state.val_serv_num = "", 0.0
            elif s_sel != "":
                row = st.session_state.db_servicos.loc[st.session_state.db_servicos['Item']==s_sel]
                desc_bd = str(row['Descrição'].values[0]) if 'Descrição' in row.columns and str(row['Descrição'].values[0]) != 'nan' else ""
                st.session_state.desc_serv_txt = f"{s_sel}\n{desc_bd}".strip()
                st.session_state.val_serv_num = float(row['Venda (R$)'].values[0])
            else:
                st.session_state.desc_serv_txt, st.session_state.val_serv_num = "", 0.0
                
        d_s = st.text_area("Descrição do Serviço:", value=st.session_state.get('desc_serv_txt', ""), height=100)
        v_s = st.number_input("Valor do Serviço (R$):", value=float(st.session_state.get('val_serv_num', 0.0)), format="%.2f")
        
        lista_o = st.session_state.db_outros['Item'].tolist() if not st.session_state.db_outros.empty else []
        if 'o_sel_atual' not in st.session_state: st.session_state.o_sel_atual = ""
        o_sel = st.selectbox("Adicionar Outros/Diversos:", [""] + lista_o + ["Manual"])
        
        if o_sel != st.session_state.o_sel_atual:
            st.session_state.o_sel_atual = o_sel
            if o_sel == "Manual":
                st.session_state.desc_outros_txt, st.session_state.val_outros_num = "", 0.0
            elif o_sel != "":
                row = st.session_state.db_outros.loc[st.session_state.db_outros['Item']==o_sel]
                desc_bd = str(row['Descrição'].values[0]) if 'Descrição' in row.columns and str(row['Descrição'].values[0]) != 'nan' else ""
                st.session_state.desc_outros_txt = f"{o_sel}\n{desc_bd}".strip()
                st.session_state.val_outros_num = float(row['Venda (R$)'].values[0])
            else:
                st.session_state.desc_outros_txt, st.session_state.val_outros_num = "", 0.0

        d_o = st.text_area("Descrição Diversos:", value=st.session_state.get('desc_outros_txt', ""), height=80)
        v_o = st.number_input("Valor Adicional (R$):", value=float(st.session_state.get('val_outros_num', 0.0)), format="%.2f")

    total_geral = total_equip + v_s + v_o
    st.markdown(f"<h3 style='color:#004488;'>💰 INVESTIMENTO TOTAL: {utils.to_br_currency(total_geral)}</h3>", unsafe_allow_html=True)
    obs = st.text_area("Observações no PDF:", value="Material Hidráulico não incluído na proposta")

    def formatar_whatsapp(tel):
        digits = ''.join(filter(str.isdigit, tel))
        if len(digits) == 11: return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
        return tel

    c_p, c_s = st.columns(2)
    with c_p:
        if st.button("GERAR PRÉVIA DO PDF", use_container_width=True):
            if nome_c:
                tel_f = formatar_whatsapp(tel_c)
                st.session_state['pdf_previa'] = utils.gerar_pdf_orcamento(nome_c, tel_f, capa, df_ed, d_s, v_s, d_o, v_o, total_geral, obs, mostrar_pdf)
                st.session_state['nome_previa'] = nome_c
        if 'pdf_previa' in st.session_state and st.session_state.get('nome_previa') == nome_c:
            st.download_button("📥 BAIXAR RASCUNHO", data=st.session_state['pdf_previa'], file_name=f"RASCUNHO_{nome_c}.pdf", mime="application/pdf", use_container_width=True)
    with c_s:
        if st.button("SALVAR ORÇAMENTO NO SISTEMA", type="primary", use_container_width=True):
            if nome_c:
                num_orc = f"ORC-{datetime.datetime.now().strftime('%y%m%d-%H%M')}"
                try:
                    tel_f = formatar_whatsapp(tel_c)
                    snapshot = []
                    for _, r in df_ed.iterrows():
                        if r['Quantidade'] > 0: snapshot.append({"Item": r['Produto da Base'] or r['Produto Manual'], "Qtd": r['Quantidade'], "Venda Un.": r['Venda (R$)'], "Descrição": r['Descrição']})
                    st.session_state.supabase.table("servicos_andamento").insert({"numero_orcamento": num_orc, "nome_cliente": nome_c, "telefone_cliente": tel_f, "produtos_adquiridos": ", ".join([f"{int(r['Quantidade'])}x {r['Produto da Base']}" for _, r in df_ed.iterrows() if r['Quantidade']>0]), "servicos_adquiridos": d_s, "valor_venda_total": total_geral, "status_projeto": "Orçamento Enviado", "detalhamento_itens": snapshot}).execute()
                    st.session_state['pdf_oficial'] = utils.gerar_pdf_orcamento(nome_c, tel_f, capa, df_ed, d_s, v_s, d_o, v_o, total_geral, obs, mostrar_un=mostrar_pdf)
                    st.session_state['oficial_filename'] = f"{num_orc}_{nome_c}.pdf"; st.success(f"✅ Orçamento {num_orc} salvo!")
                except Exception as e: st.error(f"Erro: {e}")
        if 'pdf_oficial' in st.session_state:
            st.download_button("📥 BAIXAR OFICIAL", data=st.session_state['pdf_oficial'], file_name=st.session_state['oficial_filename'], mime="application/pdf", type="primary", use_container_width=True)
