import streamlit as st
import pandas as pd
import numpy as np
import utils

def renderizar():
    st.markdown('<div class="financeiro">', unsafe_allow_html=True)
    st.subheader("📊 Controle Financeiro e Patrimônio")
    
    with st.sidebar:
        st.image("logo.png", width=150)
        ano_selecionado = st.selectbox("Ano Fiscal", options=[2025, 2026, 2027, 2028], index=1)
        st.write("---")
        pref_inicio, pref_fim = utils.load_user_settings()
        mes_inicio, mes_fim = st.select_slider("Linha do Tempo:", options=utils.meses_pt, value=(pref_inicio, pref_fim))
        colunas_visiveis = ["MESES"] + utils.meses_pt[utils.meses_pt.index(mes_inicio):utils.meses_pt.index(mes_fim) + 1]
        if st.button("🔄 Recarregar Dados"): st.session_state.pop('ano_dados_atual', None); st.rerun()

    # NOMES EXATOS DO SEU SUPABASE (SEM ACENTOS E COM AIRBNB)
    contas_p = ['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS', 'IMOVEIS', 'VEICULOS']
    contas_e = ['ECOCLIM', 'AIRBNB', 'CONS INVESTIMENTOS', 'MAGGI CONSORCIOS']
    
    if 'ano_dados_atual' not in st.session_state or st.session_state.ano_dados_atual != ano_selecionado:
        st.session_state.df_p = utils.load_year_data('patrimonio', contas_p, ano_selecionado)
        st.session_state.df_e = utils.load_year_data('entradas', contas_e, ano_selecionado)
        st.session_state.ano_dados_atual = ano_selecionado

    def garantir_linhas(df, lista):
        for c in lista:
            if c not in df['MESES'].values:
                df = pd.concat([df, pd.DataFrame([{"MESES": c, **{m: 0.0 for m in utils.meses_pt}}])], ignore_index=True)
        return df

    st.session_state.df_p = garantir_linhas(st.session_state.df_p, contas_p)
    st.session_state.df_e = garantir_linhas(st.session_state.df_e, contas_e)

    col_cfg = {"MESES": st.column_config.TextColumn("CONTA", width=220, disabled=True)}
    for m in utils.meses_pt: col_cfg[m] = st.column_config.NumberColumn(m, width=100, format="R$ %,.2f") 

    st.markdown("#### 🏛️ Patrimônio")
    df_p_edit = st.data_editor(st.session_state.df_p[colunas_visiveis], hide_index=True, column_config=col_cfg, use_container_width=True, key="ed_p")
    if not df_p_edit.equals(st.session_state.df_p[colunas_visiveis]):
        for m in [c for c in colunas_visiveis if c != "MESES"]: st.session_state.df_p.loc[:, m] = df_p_edit[m]
        utils.save_to_supabase('patrimonio', st.session_state.df_p, ano_selecionado); st.rerun()

    df_n = st.session_state.df_p.set_index('MESES')
    pat_liq = df_n[df_n.index.isin(['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS'])].sum()
    pat_tot = pat_liq + df_n[df_n.index == 'IMOVEIS'].sum() + df_n[df_n.index == 'VEICULOS'].sum()
    
    df_res_p = pd.DataFrame({'MESES': ['PATRIMÔNIO TOTAL']})
    for m in utils.meses_pt: df_res_p[m] = [pat_tot.get(m, 0)]
    st.dataframe(df_res_p[colunas_visiveis], hide_index=True, column_config=col_cfg, use_container_width=True)

    st.markdown("#### 💰 Recebimentos")
    # AUTO-SYNC ECOCLIM
    try:
        res_serv = st.session_state.supabase.table('servicos_andamento').select('lucro_estimado, status_projeto').execute()
        df_serv = pd.DataFrame(res_serv.data)
        if not df_serv.empty:
            lucro = df_serv[df_serv['status_projeto'].isin(['Em Andamento', 'Concluído PIX', 'Concluído CARTÃO'])]['lucro_estimado'].sum()
            idx = st.session_state.df_e.index[st.session_state.df_e['MESES'] == 'ECOCLIM'].tolist()
            if idx: st.session_state.df_e.at[idx[0], utils.mes_atual_nome] = float(lucro)
    except: pass

    df_e_edit = st.data_editor(st.session_state.df_e[colunas_visiveis], hide_index=True, column_config=col_cfg, use_container_width=True, key="ed_e")
    if not df_e_edit.equals(st.session_state.df_e[colunas_visiveis]):
        for m in [c for c in colunas_visiveis if c != "MESES"]: st.session_state.df_e.loc[:, m] = df_e_edit[m]
        utils.save_to_supabase('entradas', st.session_state.df_e, ano_selecionado); st.rerun()
