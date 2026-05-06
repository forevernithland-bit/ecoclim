import streamlit as st
import pandas as pd
import numpy as np
import utils

def renderizar():
    st.markdown('<div class="financeiro">', unsafe_allow_html=True)
    st.subheader("📊 Controle Financeiro")
    
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

        if st.button("🔄 Recarregar Dados"): st.session_state.pop('ano_dados_atual', None); st.rerun()

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
    for m in [c for c in colunas_visiveis if c != "MESES"]: df_p_display[m] = df_p_display[m].apply(lambda x: utils.to_br_currency(x, False))
    styled_df_p = df_p_display.style.set_properties(subset=[utils.mes_atual_nome] if utils.mes_atual_nome in colunas_visiveis and ano_selecionado == utils.ano_atual else [], **{'background-color': '#e0f0ff', 'font-weight': 'bold'})
    df_p_edit_str = st.data_editor(styled_df_p, hide_index=True, column_config=col_cfg, use_container_width=True, height=295)

    if not df_p_edit_str.equals(df_p_display):
        for m in [c for c in colunas_visiveis if c != "MESES"]: st.session_state.df_p.loc[:, m] = df_p_edit_str[m].apply(utils.parse_br_currency)
        utils.save_to_supabase('patrimonio', st.session_state.df_p, ano_selecionado); st.toast("💾 Salvo!", icon="✅"); st.rerun()

    df_n = st.session_state.df_p.set_index('MESES')
    pat_liq = df_n.loc[['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS']].sum()
    pat_tot = pat_liq + df_n.loc['IMÓVEIS'] + df_n.loc['VEÍCULOS']
    var_abs = pat_tot.diff().fillna(0); var_pct = (pat_tot.pct_change().fillna(0) * 100).round(2)

    for i, m in enumerate(utils.meses_pt):
        if (ano_selecionado > utils.ano_atual) or (ano_selecionado == utils.ano_atual and i > utils.mes_hoje_idx - 1):
            var_abs[m] = 0; var_pct[m] = 0

    # LINHAS DE RESUMO DO PATRIMÔNIO NOMEADAS
    df_res_p = pd.DataFrame({'MESES': ['PATRIMÔNIO LÍQUIDO', 'PATRIMÔNIO TOTAL', 'VAR MENSAL (R$)', 'VAR MENSAL (%)']})
    for m in utils.meses_pt: df_res_p[m] = [pat_liq[m], pat_tot[m], var_abs[m], f"{var_pct[m]:.2f}%"]
    styled_res_p = df_res_p[colunas_visiveis].style.apply(lambda row: [f'background-color: {"#FF9900" if row["MESES"] == "PATRIMÔNIO TOTAL" else "#FFF2CC" if "LÍQUIDO" in row["MESES"] else "white"}; font-weight: bold; color: black; border-left: {"3px solid #4A90E2" if col == utils.mes_atual_nome and ano_selecionado == utils.ano_atual else "none"}' for col in colunas_visiveis], axis=1)
    st.dataframe(styled_res_p.format(lambda x: x if isinstance(x, str) and "%" in x else utils.to_br_currency(x, False)), hide_index=True, column_config=col_cfg, use_container_width=True, height=175)

    # --------------------------
    # 9.2 ENTRADAS (E AUTO-SYNC DA ECOCLIM)
    # --------------------------
    # Puxa o Lucro Estimado de Serviços Ativos e joga na linha ECOCLIM (Mês Atual)
    if ano_selecionado == utils.ano_atual:
        try:
            res_servicos = st.session_state.supabase.table('servicos_andamento').select('lucro_estimado, status_projeto').execute()
            df_serv = pd.DataFrame(res_servicos.data)
            if not df_serv.empty:
                lucro_ativo = df_serv[df_serv['status_projeto'].isin(['Em Andamento', 'Concluído PIX', 'Concluído CARTÃO'])]['lucro_estimado'].sum()
                idx_ecoclim = st.session_state.df_e.index[st.session_state.df_e['MESES'] == 'ECOCLIM'].tolist()[0]
                st.session_state.df_e.at[idx_ecoclim, utils.mes_atual_nome] = float(lucro_ativo)
        except: pass

    df_e_display = st.session_state.df_e[colunas_visiveis].copy()
    for m in [c for c in colunas_visiveis if c != "MESES"]: df_e_display[m] = df_e_display[m].apply(lambda x: utils.to_br_currency(x, False))
    styled_df_e = df_e_display.style.set_properties(subset=[utils.mes_atual_nome] if utils.mes_atual_nome in colunas_visiveis and ano_selecionado == utils.ano_atual else [], **{'background-color': '#e0f0ff', 'font-weight': 'bold'})
    df_e_edit_str = st.data_editor(styled_df_e, hide_index=True, column_config=col_cfg, use_container_width=True, height=190)

    if not df_e_edit_str.equals(df_e_display):
        for m in [c for c in colunas_visiveis if c != "MESES"]: st.session_state.df_e.loc[:, m] = df_e_edit_str[m].apply(utils.parse_br_currency)
        utils.save_to_supabase('entradas', st.session_state.df_e, ano_selecionado); st.toast("💾 Salvo!", icon="✅"); st.rerun()

    df_e_n = st.session_state.df_e.set_index('MESES'); tot_ent = df_e_n.sum()
    df_res_e = pd.DataFrame({'MESES': ['TOTAL RECEBIMENTOS:']})
    for m in utils.meses_pt: df_res_e[m] = [tot_ent[m]]
    styled_res_e = df_res_e[colunas_visiveis].style.apply(lambda row: [f'background-color: #9BC2E6; font-weight: bold; color: black; border-left: {"3px solid #4A90E2" if col == utils.mes_atual_nome and ano_selecionado == utils.ano_atual else "none"}' for col in colunas_visiveis], axis=1)
    st.dataframe(styled_res_e.format(lambda x: utils.to_br_currency(x, False)), hide_index=True, column_config=col_cfg, use_container_width=True, height=75)

    # --------------------------
    # 9.3 RENDIMENTOS
    # --------------------------
    st.markdown("#### 📈 Rendimento Mensal (Investimentos)")
    xp_val = df_n.loc['INVESTIMENTO XP']; inter_val = df_n.loc['CONTA INTER']
    xp_var = xp_val.diff().fillna(0); inter_var = inter_val.diff().fillna(0); rend_total = xp_var + inter_var; prev_bal = (xp_val + inter_val).shift(1).fillna(0)
    
    # LINHAS DE RENDIMENTO NOMEADAS
    df_rend = pd.DataFrame({'MESES': ['RESULTADO XP', 'RESULTADO INTER', 'RENDIMENTO TOTAL', '% RETORNO MÊS', 'SALÁRIO + RENDIMENTO MÊS']})
    
    for i, m in enumerate(utils.meses_pt):
        if (ano_selecionado > utils.ano_atual) or (ano_selecionado == utils.ano_atual and i > utils.mes_hoje_idx - 1): df_rend[m] = [0, 0, 0, "0,00%", 0]
        else:
            rt = rend_total[m]; pb = prev_bal[m]; pct_val = (rt / pb * 100) if pb > 0 else 0
            df_rend[m] = [xp_var[m], inter_var[m], rt, f"{pct_val:.2f}%".replace(".", ","), tot_ent[m] + rt]
    styled_rend = df_rend[colunas_visiveis].style.apply(lambda row: [f'background-color: {"#FF9900" if row["MESES"] == "RENDIMENTO TOTAL" else "#FFF2CC" if "%" in row["MESES"] else "#9BC2E6" if "SALÁRIO" in row["MESES"] else "white"}; font-weight: bold; color: black; border-left: {"3px solid #4A90E2" if col == utils.mes_atual_nome and ano_selecionado == utils.ano_atual else "none"}' for col in colunas_visiveis], axis=1)
    st.dataframe(styled_rend.format(lambda x: x if isinstance(x, str) and "%" in x else utils.to_br_currency(x, False)), hide_index=True, column_config=col_cfg, use_container_width=True, height=215)
    st.markdown('</div></div>', unsafe_allow_html=True)

    # --------------------------
    # 9.4 GRÁFICOS E MÉTRICAS
    # --------------------------
    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    meses_calculo = utils.meses_pt if ano_selecionado < utils.ano_atual else utils.meses_pt[:utils.mes_hoje_idx]
    media_entradas = tot_ent[meses_calculo].mean(); media_rend_r = rend_total[meses_calculo].mean(); media_rend_p = (rend_total[meses_calculo] / prev_bal[meses_calculo].replace(0, np.nan)).mean() * 100
    idx_ref = 11 if ano_selecionado < utils.ano_atual else (utils.mes_hoje_idx - 1 if utils.mes_hoje_idx > 0 else 0)

    c1.metric("💰 MÉDIA ENTRADAS FIXAS", utils.to_br_currency(media_entradas))
    c2.metric("🎯 LIMITE DE GASTO (MÉDIA REND.)", utils.to_br_currency(media_rend_r))
    c3.metric("📈 MÉDIA RETORNO (%)", f"{media_rend_p:.2f}%".replace(".", ","))
    c4.metric("🏛️ PATRIMÔNIO ATUAL", utils.to_br_currency(pat_tot.iloc[idx_ref]))

    st.write("---")
    g1, g2 = st.columns(2)
    with g1:
        st.subheader("Aumento de Patrimônio Total"); st.line_chart(pat_tot[utils.meses_pt])
        st.subheader("Rendimento Mensal (R$)"); st.bar_chart(rend_total[utils.meses_pt])
    with g2:
        st.subheader("Salário + Rendimento Mensal"); st.area_chart(tot_ent[utils.meses_pt] + rend_total[utils.meses_pt])
        st.subheader("Faturamento Ecoclim"); st.line_chart(df_e_n.loc['ECOCLIM'][utils.meses_pt])
