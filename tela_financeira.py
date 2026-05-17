import streamlit as st
import pandas as pd
import numpy as np
import utils

def carregar_periodo_visivel():
    """Busca o período salvo no cofre do Supabase (Ano 2000) ou retorna padrão"""
    if 'periodo_visivel_financeiro' in st.session_state:
        return st.session_state.periodo_visivel_financeiro
    try:
        res = st.session_state.supabase.table('entradas').select('*').eq('ano', 2000).eq('MESES', 'CFG_FIN_PERIODO').execute()
        if res.data:
            idx_ini = int(res.data[0].get('JANEIRO', 0))
            idx_fim = int(res.data[0].get('FEVEREIRO', 11))
            st.session_state.periodo_visivel_financeiro = (utils.meses_pt[idx_ini], utils.meses_pt[idx_fim])
            return st.session_state.periodo_visivel_financeiro
    except:
        pass
    return ("JANEIRO", "DEZEMBRO")

def salvar_periodo_visivel(m_ini, m_fim):
    """Salva a escolha do slider no Supabase (Ano 2000) para persistência"""
    st.session_state.periodo_visivel_financeiro = (m_ini, m_fim)
    try:
        idx_ini = utils.meses_pt.index(m_ini)
        idx_fim = utils.meses_pt.index(m_fim)
        st.session_state.supabase.table('entradas').delete().eq('ano', 2000).eq('MESES', 'CFG_FIN_PERIODO').execute()
        st.session_state.supabase.table('entradas').insert({
            'ano': 2000, 'MESES': 'CFG_FIN_PERIODO', 'JANEIRO': float(idx_ini), 'FEVEREIRO': float(idx_fim)
        }).execute()
    except:
        pass

def limpar_e_garantir_linhas(df, lista_contas):
    """Remove linhas fantasmas e garante a ordem correta das contas oficiais"""
    if not df.empty and 'MESES' in df.columns:
        df = df[df['MESES'].astype(str).str.strip() != '']
        df = df[df['MESES'].notna()]
    else:
        df = pd.DataFrame(columns=["MESES"] + utils.meses_pt)
        
    contas_existentes = df['MESES'].tolist()
    for c in lista_contas:
        if c not in contas_existentes:
            df = pd.concat([df, pd.DataFrame([{"MESES": c, **{m: 0.0 for m in utils.meses_pt}}])], ignore_index=True)
            
    df = df[df['MESES'].isin(lista_contas)]
    df['MESES'] = pd.Categorical(df['MESES'], categories=lista_contas, ordered=True)
    return df.sort_values('MESES').reset_index(drop=True)

def renderizar():
    st.markdown('<div class="financeiro">', unsafe_allow_html=True)
    
    with st.sidebar:
        ano_selecionado = st.selectbox("Ano Fiscal", options=[2025, 2026, 2027, 2028], index=1)
        st.write("---")
        st.markdown("### 👁️ Linha do Tempo")
        
        pref_ini, pref_fim = carregar_periodo_visivel()
        m_ini, m_fim = st.select_slider("Período Visível:", options=utils.meses_pt, value=(pref_ini, pref_fim))
        
        if (m_ini, m_fim) != (pref_ini, pref_fim):
            salvar_periodo_visivel(m_ini, m_fim)
            st.rerun()
            
        colunas_visiveis = ["MESES"] + utils.meses_pt[utils.meses_pt.index(m_ini):utils.meses_pt.index(m_fim) + 1]

        if st.button("🔄 Recarregar Banco"): 
            st.session_state.pop('ano_dados_atual', None)
            st.rerun()

    contas_p = ['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS', 'IMÓVEIS', 'VEÍCULOS']
    contas_e = ['ECOCLIM', 'AIRNB', 'CONS INVESTIMENTOS', 'MAGGI CONSORCIOS']
    
    if 'ano_dados_atual' not in st.session_state or st.session_state.ano_dados_atual != ano_selecionado:
        st.session_state.df_p = limpar_e_garantir_linhas(utils.load_year_data('patrimonio', contas_p, ano_selecionado), contas_p)
        st.session_state.df_e = limpar_e_garantir_linhas(utils.load_year_data('entradas', contas_e, ano_selecionado), contas_e)
        st.session_state.ano_dados_atual = ano_selecionado

    # --- HERANÇA DE DEZEMBRO (ANO ANTERIOR) ---
    df_p_prev = utils.load_year_data('patrimonio', contas_p, ano_selecionado - 1).set_index('MESES')
    pat_liq_prev_dec = df_p_prev.loc[df_p_prev.index.isin(['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS']), 'DEZEMBRO'].sum()
    pat_tot_prev_dec = pat_liq_prev_dec + df_p_prev.loc[df_p_prev.index.isin(['IMÓVEIS', 'VEÍCULOS']), 'DEZEMBRO'].sum()
    xp_prev_dec = df_p_prev.loc['INVESTIMENTO XP', 'DEZEMBRO'] if 'INVESTIMENTO XP' in df_p_prev.index else 0
    inter_prev_dec = df_p_prev.loc['CONTA INTER', 'DEZEMBRO'] if 'CONTA INTER' in df_p_prev.index else 0

    # Configuração de Colunas (Régua de Alinhamento)
    cfg_edit = {"MESES": st.column_config.TextColumn("CONTA", width=220, disabled=True)}
    cfg_text = {"MESES": st.column_config.TextColumn("CONTA", width=220, disabled=True)}
    for m in utils.meses_pt: 
        cfg_edit[m] = st.column_config.NumberColumn(m, width=100, format="R$ %,.2f")
        cfg_text[m] = st.column_config.TextColumn(m, width=100)

    st.markdown('<div class="container-tabelas">', unsafe_allow_html=True)
    
    # --------------------------
    # 1. PATRIMÔNIO
    # --------------------------
    st.markdown("#### 🏛️ Posição Patrimonial e Investimentos")
    
    # AQUI ESTÁ A MÁGICA: A 'key' agora depende do ano_selecionado. 
    # Isso obriga o Streamlit a destruir e recriar a tabela ao trocar de ano, impedindo o vazamento de dados.
    df_p_ed = st.data_editor(st.session_state.df_p[colunas_visiveis], hide_index=True, column_config=cfg_edit, use_container_width=True, height=285, key=f"ed_p_fin_{ano_selecionado}")

    if not df_p_ed.equals(st.session_state.df_p[colunas_visiveis]):
        for c in colunas_visiveis: 
            if c != "MESES": st.session_state.df_p[c] = df_p_ed[c]
        utils.save_to_supabase('patrimonio', st.session_state.df_p, ano_selecionado)
        st.rerun()

    df_n = st.session_state.df_p.set_index('MESES')
    pat_liq = df_n.loc[df_n.index.isin(['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS'])].sum()
    pat_tot = pat_liq + df_n.loc[df_n.index.isin(['IMÓVEIS', 'VEÍCULOS'])].sum()
    
    var_abs = pat_tot.copy()
    var_pct = pat_tot.copy()
    for i, m in enumerate(utils.meses_pt):
        val_atual = pat_tot[m]
        val_prev = pat_tot[utils.meses_pt[i-1]] if i > 0 else pat_tot_prev_dec
        var_abs[m] = val_atual - val_prev
        var_pct[m] = (var_abs[m] / val_prev * 100) if val_prev != 0 else 0.0

    dict_res_p = {'MESES': ['PATRIMÔNIO LÍQUIDO', 'PATRIMÔNIO TOTAL', 'VAR. MENSAL (R$)', 'VAR. MENSAL (%)']}
    for i, m in enumerate(utils.meses_pt):
        is_futuro = (ano_selecionado > utils.ano_atual) or (ano_selecionado == utils.ano_atual and i > (utils.mes_hoje_idx - 1))
        if is_futuro:
            dict_res_p[m] = ["R$ 0,00", "R$ 0,00", "R$ 0,00", "0,00%"]
        else:
            dict_res_p[m] = [utils.to_br_currency(pat_liq[m]), utils.to_br_currency(pat_tot[m]), utils.to_br_currency(var_abs[m]), f"{var_pct[m]:.2f}%".replace('.',',')]

    st.dataframe(pd.DataFrame(dict_res_p)[colunas_visiveis].style.apply(lambda r: [f'background-color: {"#FF9900" if r["MESES"] == "PATRIMÔNIO TOTAL" else "#FFF2CC" if "LÍQUIDO" in r["MESES"] else "white"}; color: black; font-weight: bold' for _ in colunas_visiveis], axis=1), hide_index=True, column_config=cfg_text, use_container_width=True)

    st.markdown("---")
    
    # --------------------------
    # 2. RECEBIMENTOS
    # --------------------------
    st.markdown("#### 💰 Recebimentos e Pró-labore")
    
    # A mesma proteção de 'key' aplicada aqui
    df_e_ed = st.data_editor(st.session_state.df_e[colunas_visiveis], hide_index=True, column_config=cfg_edit, use_container_width=True, height=190, key=f"ed_e_fin_{ano_selecionado}")
    
    if not df_e_ed.equals(st.session_state.df_e[colunas_visiveis]):
        for c in colunas_visiveis: 
            if c != "MESES": st.session_state.df_e[c] = df_e_ed[c]
        utils.save_to_supabase('entradas', st.session_state.df_e, ano_selecionado)
        st.rerun()

    tot_e = st.session_state.df_e.set_index('MESES').sum()
    dict_res_e = {'MESES': ['TOTAL RECEBIMENTOS']}
    for i, m in enumerate(utils.meses_pt):
        is_futuro = (ano_selecionado > utils.ano_atual) or (ano_selecionado == utils.ano_atual and i > (utils.mes_hoje_idx - 1))
        dict_res_e[m] = [utils.to_br_currency(0 if is_futuro else tot_e[m])]
        
    st.dataframe(pd.DataFrame(dict_res_e)[colunas_visiveis].style.set_properties(**{'background-color': '#9BC2E6', 'color': 'black', 'font-weight': 'bold'}), hide_index=True, column_config=cfg_text, use_container_width=True)

    st.markdown("---")
    
    # --------------------------
    # 3. RENDIMENTOS
    # --------------------------
    st.markdown("#### 📈 Rendimento Mensal (Investimentos)")
    xp_v = df_n.loc['INVESTIMENTO XP'] if 'INVESTIMENTO XP' in df_n.index else pd.Series(0.0, index=utils.meses_pt)
    it_v = df_n.loc['CONTA INTER'] if 'CONTA INTER' in df_n.index else pd.Series(0.0, index=utils.meses_pt)
    
    dict_rend = {'MESES': ['RESULTADO XP', 'RESULTADO INTER', 'RENDIMENTO TOTAL', '% RETORNO MÊS', 'SALÁRIO + RENDIMENTO MÊS']}
    for i, m in enumerate(utils.meses_pt):
        is_futuro = (ano_selecionado > utils.ano_atual) or (ano_selecionado == utils.ano_atual and i > (utils.mes_hoje_idx - 1))
        if is_futuro:
            dict_rend[m] = ["R$ 0,00", "R$ 0,00", "R$ 0,00", "0,00%", "R$ 0,00"]
        else:
            v_xp = xp_v[m] - (xp_v[utils.meses_pt[i-1]] if i > 0 else xp_prev_dec)
            v_it = it_v[m] - (it_v[utils.meses_pt[i-1]] if i > 0 else inter_prev_dec)
            r_tot = v_xp + v_it
            p_bal = (xp_v[utils.meses_pt[i-1]] + it_v[utils.meses_pt[i-1]]) if i > 0 else (xp_prev_dec + inter_prev_dec)
            pct = (r_tot / p_bal * 100) if p_bal > 0 else 0.0
            dict_rend[m] = [utils.to_br_currency(v_xp), utils.to_br_currency(v_it), utils.to_br_currency(r_tot), f"{pct:.2f}%".replace('.',','), utils.to_br_currency(tot_e[m] + r_tot)]
            
    st.dataframe(pd.DataFrame(dict_rend)[colunas_visiveis].style.apply(lambda r: [f'background-color: {"#FF9900" if r["MESES"] == "RENDIMENTO TOTAL" else "#FFF2CC" if "%" in r["MESES"] else "#9BC2E6" if "SALÁRIO" in r["MESES"] else "white"}; color: black; font-weight: bold' for _ in colunas_visiveis], axis=1), hide_index=True, column_config=cfg_text, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # --------------------------
    # 4. MÉTRICAS FINAIS
    # --------------------------
    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    meses_calc = utils.meses_pt[:utils.mes_hoje_idx] if ano_selecionado == utils.ano_atual else utils.meses_pt
    
    media_ent = tot_e[meses_calc].mean() if not tot_e.empty else 0
    
    # Rendimento Médio (R$)
    xp_var_full = xp_v - xp_v.shift(1).fillna(xp_prev_dec)
    it_var_full = it_v - it_v.shift(1).fillna(inter_prev_dec)
    rend_tot_full = xp_var_full + it_var_full
    media_rend_r = rend_tot_full[meses_calc].mean()
    
    # Rendimento Médio (%)
    prev_bal_full = (xp_v + it_v).shift(1).fillna(xp_prev_dec + inter_prev_dec)
    pb_safe = prev_bal_full[meses_calc].replace(0, np.nan)
    media_rend_p = (rend_tot_full[meses_calc] / pb_safe).mean() * 100
    
    pat_atual = pat_tot[utils.mes_atual_nome] if ano_selecionado == utils.ano_atual else pat_tot['DEZEMBRO']

    c1.metric("💰 MÉDIA ENTRADAS", utils.to_br_currency(media_ent))
    c2.metric("🎯 LIMITE DE GASTO", utils.to_br_currency(media_rend_r))
    c3.metric("📈 MÉDIA RETORNO (%)", f"{media_rend_p:.2f}%".replace(".", ","))
    c4.metric("🏛️ PATRIMÔNIO ATUAL", utils.to_br_currency(pat_atual))

    # --------------------------
    # 5. GRÁFICOS
    # --------------------------
    st.write("---")
    g1, g2 = st.columns(2)
    with g1:
        st.subheader("Evolução Patrimonial Total")
        st.line_chart(pat_tot[utils.meses_pt])
        st.subheader("Rendimento Mensal (R$)")
        st.bar_chart(rend_tot_full[utils.meses_pt])
    with g2:
        st.subheader("Salário + Rendimento")
        st.area_chart(tot_e[utils.meses_pt] + rend_tot_full[utils.meses_pt])
        st.subheader("Faturamento Ecoclim")
        st.line_chart(st.session_state.df_e.set_index('MESES').loc['ECOCLIM', utils.meses_pt])
