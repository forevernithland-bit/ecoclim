import streamlit as st
import pandas as pd
import numpy as np
import utils

def renderizar():
    st.markdown('<div class="financeiro">', unsafe_allow_html=True)
    st.subheader("📊 Controle Financeiro e Patrimônio")
    
    with st.sidebar:
        ano_selecionado = st.selectbox("Ano Fiscal", options=[2025, 2026, 2027, 2028], index=1)
        st.write("---")
        st.markdown("### 👁️ Linha do Tempo")
        
        pref_inicio, pref_fim = utils.load_user_settings()
        if pref_inicio not in utils.meses_pt: pref_inicio = "JANEIRO"
        if pref_fim not in utils.meses_pt: pref_fim = utils.mes_atual_nome
            
        mes_inicio, mes_fim = st.select_slider("Período Visível:", options=utils.meses_pt, value=(pref_inicio, pref_fim))
        if (mes_inicio != pref_inicio) or (mes_fim != pref_fim): utils.save_user_settings(mes_inicio, mes_fim)
            
        idx_inicio = utils.meses_pt.index(mes_inicio)
        idx_fim = utils.meses_pt.index(mes_fim)
        colunas_visiveis = ["MESES"] + utils.meses_pt[idx_inicio:idx_fim + 1]

        if st.button("🔄 Recarregar Dados"): 
            st.session_state.pop('ano_dados_atual', None)
            st.rerun()

    contas_p = ['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS', 'IMÓVEIS', 'VEÍCULOS']
    contas_e = ['ECOCLIM', 'AIRNB', 'CONS INVESTIMENTOS', 'MAGGI CONSORCIOS']
    
    if 'ano_dados_atual' not in st.session_state or st.session_state.ano_dados_atual != ano_selecionado:
        st.session_state.df_p = utils.load_year_data('patrimonio', contas_p, ano_selecionado)
        st.session_state.df_e = utils.load_year_data('entradas', contas_e, ano_selecionado)
        st.session_state.ano_dados_atual = ano_selecionado

    col_cfg = {"MESES": st.column_config.TextColumn("MESES", width=220, disabled=True)}
    for m in utils.meses_pt: col_cfg[m] = st.column_config.TextColumn(m, width=80) 

    st.markdown('<div class="container-tabelas">', unsafe_allow_html=True)
    
    # --------------------------
    # 9.1 PATRIMÔNIO
    # --------------------------
    df_p_display = st.session_state.df_p[colunas_visiveis].copy()
    for m in [c for c in colunas_visiveis if c != "MESES"]: 
        df_p_display[m] = df_p_display[m].apply(lambda x: utils.to_br_currency(x, False))
        
    styled_df_p = df_p_display.style.set_properties(
        subset=[utils.mes_atual_nome] if utils.mes_atual_nome in colunas_visiveis and ano_selecionado == utils.ano_atual else [], 
        **{'background-color': '#e0f0ff', 'font-weight': 'bold'}
    )
    
    st.markdown("#### 🏛️ Posição Patrimonial e Investimentos")
    df_p_edit_str = st.data_editor(styled_df_p, hide_index=True, column_config=col_cfg, use_container_width=True, height=295)

    if not df_p_edit_str.equals(df_p_display):
        for m in [c for c in colunas_visiveis if c != "MESES"]: 
            st.session_state.df_p.loc[:, m] = df_p_edit_str[m].apply(utils.parse_br_currency)
        utils.save_to_supabase('patrimonio', st.session_state.df_p, ano_selecionado)
        st.toast("💾 Salvo!", icon="✅")
        st.rerun()

    df_n = st.session_state.df_p.set_index('MESES')
    
    contas_liq = ['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS']
    pat_liq = df_n[df_n.index.isin(contas_liq)].sum()
    
    imoveis = df_n[df_n.index == 'IMÓVEIS'].sum()
    veiculos = df_n[df_n.index == 'VEÍCULOS'].sum()
    
    pat_tot = pat_liq + imoveis + veiculos
    var_abs = pat_tot.diff().fillna(0)
    var_pct = (pat_tot.pct_change().fillna(0) * 100).round(2)

    for i, m in enumerate(utils.meses_pt):
        if (ano_selecionado > utils.ano_atual) or (ano_selecionado == utils.ano_atual and i > utils.mes_hoje_idx - 1):
            var_abs[m] = 0
            var_pct[m] = 0

    # LINHAS DE RESUMO DO PATRIMÔNIO NOMEADAS
    df_res_p = pd.DataFrame({'MESES': ['PATRIMÔNIO LÍQUIDO', 'PATRIMÔNIO TOTAL', 'VAR MENSAL (R$)', 'VAR MENSAL (%)']})
    for m in utils.meses_pt: df_res_p[m] = [pat_liq.get(m, 0), pat_tot.get(m, 0), var_abs.get(m, 0), f"{var_pct.get(m, 0):.2f}%"]
    
    styled_res_p = df_res_p[colunas_visiveis].style.apply(lambda row: [f'background-color: {"#FF9900" if row["MESES"] == "PATRIMÔNIO TOTAL" else "#FFF2CC" if "LÍQUIDO" in row["MESES"] else "white"}; font-weight: bold; color: black; border-left: {"3px solid #4A90E2" if col == utils.mes_atual_nome and ano_selecionado == utils.ano_atual else "none"}' for col in colunas_visiveis], axis=1)
    
    # -> CORREÇÃO DO LAMBDA AQUI: Protegendo palavras contra formatação numérica
    st.dataframe(styled_res_p.format(lambda x: x if isinstance(x, str) else utils.to_br_currency(x, False)), hide_index=True, column_config=col_cfg, use_container_width=True, height=175)

    st.markdown("---")

    # --------------------------
    # 9.2 ENTRADAS (E AUTO-SYNC DA ECOCLIM)
    # --------------------------
    st.markdown("#### 💰 Recebimentos e Pró-labore")
    
    if ano_selecionado == utils.ano_atual:
        try:
            res_servicos = st.session_state.supabase.table('servicos_andamento').select('lucro_estimado, status_projeto').execute()
            df_serv = pd.DataFrame(res_servicos.data)
            if not df_serv.empty:
                lucro_ativo = df_serv[df_serv['status_projeto'].isin(['Em Andamento', 'Concluído PIX', 'Concluído CARTÃO'])]['lucro_estimado'].sum()
                idx_ecoclim_list = st.session_state.df_e.index[st.session_state.df_e['MESES'] == 'ECOCLIM'].tolist()
                if idx_ecoclim_list:
                    st.session_state.df_e.at[idx_ecoclim_list[0], utils.mes_atual_nome] = float(lucro_ativo)
        except Exception as e: 
            pass

    df_e_display = st.session_state.df_e[colunas_visiveis].copy()
    for m in [c for c in colunas_visiveis if c != "MESES"]: 
        df_e_display[m] = df_e_display[m].apply(lambda x: utils.to_br_currency(x, False))
        
    styled_df_e = df_e_display.style.set_properties(
        subset=[utils.mes_atual_nome] if utils.mes_atual_nome in colunas_visiveis and ano_selecionado == utils.ano_atual else [], 
        **{'background-color': '#e0f0ff', 'font-weight': 'bold'}
    )
    
    df_e_edit_str = st.data_editor(styled_df_e, hide_index=True, column_config=col_cfg, use_container_width=True, height=190)

    if not df_e_edit_str.equals(df_e_display):
        for m in [c for c in colunas_visiveis if c != "MESES"]: 
            st.session_state.df_e.loc[:, m] = df_e_edit_str[m].apply(utils.parse_br_currency)
        utils.save_to_supabase('entradas', st.session_state.df_e, ano_selecionado)
        st.toast("💾 Salvo!", icon="✅")
        st.rerun()

    df_e_n = st.session_state.df_e.set_index('MESES')
    tot_ent = df_e_n.sum()
    df_res_e = pd.DataFrame({'MESES': ['TOTAL RECEBIMENTOS:']})
    for m in utils.meses_pt: df_res_e[m] = [tot_ent.get(m, 0)]
    
    styled_res_e = df_res_e[colunas_visiveis].style.apply(lambda row: [f'background-color: #9BC2E6; font-weight: bold; color: black; border-left: {"3px solid #4A90E2" if col == utils.mes_atual_nome and ano_selecionado == utils.ano_atual else "none"}' for col in colunas_visiveis], axis=1)
    
    # -> CORREÇÃO DO LAMBDA AQUI: Protegendo palavras contra formatação numérica
    st.dataframe(styled_res_e.format(lambda x: x if isinstance(x, str) else utils.to_br_currency(x, False)), hide_index=True, column_config=col_cfg, use_container_width=True, height=75)

    st.markdown("---")

    # --------------------------
    # 9.3 RENDIMENTOS
    # --------------------------
    st.markdown("#### 📈 Rendimento Mensal (Investimentos)")
    
    xp_val = df_n[df_n.index == 'INVESTIMENTO XP'].sum()
    inter_val = df_n[df_n.index == 'CONTA INTER'].sum()
    
    xp_var = xp_val.diff().fillna(0)
    inter_var = inter_val.diff().fillna(0)
    rend_total = xp_var + inter_var
    prev_bal = (xp_val + inter_val).shift(1).fillna(0)
    
    df_rend = pd
