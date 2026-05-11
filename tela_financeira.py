import streamlit as st
import pandas as pd
import numpy as np
import utils

# =============================================================================
# FUNÇÕES DE BANCO DE DADOS (VERTICAL)
# =============================================================================
def carregar_fin_do_banco(nome_tabela, contas_padrao, ano):
    supabase = st.session_state.supabase
    df_novo = pd.DataFrame({"MESES": contas_padrao})
    for m in utils.meses_pt:
        df_novo[m] = 0.0

    try:
        res = supabase.table(nome_tabela).select("*").eq("ano", ano).execute()
        if res.data:
            for d in res.data:
                conta = d.get("conta")
                mes = d.get("mes")
                valor = float(d.get("valor", 0.0))
                if conta in contas_padrao and mes in utils.meses_pt:
                    df_novo.loc[df_novo["MESES"] == conta, mes] = valor
    except Exception as e:
        pass
    return df_novo

def salvar_fin_no_banco(nome_tabela, df, ano):
    supabase = st.session_state.supabase
    dados_para_enviar = []
    
    for _, linha in df.iterrows():
        conta = str(linha["MESES"]).strip()
        for m in utils.meses_pt:
            valor = float(linha[m]) if pd.notna(linha[m]) else 0.0
            dados_para_enviar.append({
                "conta": conta,
                "mes": m,
                "ano": int(ano),
                "valor": valor
            })

    try:
        supabase.table(nome_tabela).delete().eq("ano", ano).execute()
        if dados_para_enviar:
            supabase.table(nome_tabela).insert(dados_para_enviar).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar no banco (Tabela {nome_tabela}): {e}")
        return False

# =============================================================================
# RENDERIZAÇÃO DA TELA
# =============================================================================
def renderizar():
    st.markdown('<div class="financeiro">', unsafe_allow_html=True)
    
    with st.sidebar:
        ano_fiscal = st.selectbox("Ano Fiscal", options=[2025, 2026, 2027, 2028], index=1)
        
        st.write("---")
        if st.button("💾 SALVAR TUDO AGORA", type="primary", use_container_width=True):
            res_p = salvar_fin_no_banco('patrimonio', st.session_state.df_p, ano_fiscal)
            res_e = salvar_fin_no_banco('entradas', st.session_state.df_e, ano_fiscal)
            if res_p and res_e:
                st.success("✅ Tudo salvo com sucesso!")

        st.write("---")
        st.markdown("### 👁️ Linha do Tempo")
        if 'mes_inicio_fin' not in st.session_state:
            st.session_state.mes_inicio_fin = 'JANEIRO'
            st.session_state.mes_fim_fin = 'DEZEMBRO'

        mes_i, mes_f = st.select_slider(
            "Período Visível:", 
            options=utils.meses_pt, 
            value=(st.session_state.mes_inicio_fin, st.session_state.mes_fim_fin)
        )
        st.session_state.mes_inicio_fin, st.session_state.mes_fim_fin = mes_i, mes_f
        colunas_v = ["MESES"] + utils.meses_pt[utils.meses_pt.index(mes_i):utils.meses_pt.index(mes_f) + 1]

        if st.button("🔄 Recarregar Dados"): 
            st.session_state.pop('ano_dados_atual', None)
            st.rerun()

    contas_p = ['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS', 'IMÓVEIS', 'VEÍCULOS']
    contas_e = ['ECOCLIM', 'AIRNB', 'CONS INVESTIMENTOS', 'MAGGI CONSORCIOS']
    
    # -------------------------------------------------------------------------
    # CARREGAMENTO INTELIGENTE (Puxa o Dezembro do ano anterior para cálculo)
    # -------------------------------------------------------------------------
    if 'ano_dados_atual' not in st.session_state or st.session_state.ano_dados_atual != ano_fiscal:
        st.session_state.df_p = carregar_fin_do_banco('patrimonio', contas_p, ano_fiscal)
        st.session_state.df_e = carregar_fin_do_banco('entradas', contas_e, ano_fiscal)
        
        # Puxa o ano anterior no modo silencioso
        df_p_ant = carregar_fin_do_banco('patrimonio', contas_p, ano_fiscal - 1)
        df_n_ant = df_p_ant.set_index('MESES').apply(pd.to_numeric, errors='coerce').fillna(0)
        
        # Grava na memória os saldos do último Dezembro
        st.session_state.dez_ant_xp = df_n_ant.loc['INVESTIMENTO XP', 'DEZEMBRO'] if 'INVESTIMENTO XP' in df_n_ant.index else 0.0
        st.session_state.dez_ant_inter = df_n_ant.loc['CONTA INTER', 'DEZEMBRO'] if 'CONTA INTER' in df_n_ant.index else 0.0
        
        pat_liq_ant = df_n_ant[df_n_ant.index.isin(['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS'])].sum()
        pat_tot_ant = pat_liq_ant + df_n_ant[df_n_ant.index == 'IMÓVEIS'].sum() + df_n_ant[df_n_ant.index == 'VEÍCULOS'].sum()
        st.session_state.dez_ant_pat = pat_tot_ant['DEZEMBRO'] if 'DEZEMBRO' in pat_tot_ant.index else 0.0
        
        st.session_state.ano_dados_atual = ano_fiscal

    col_cfg = {"MESES": st.column_config.TextColumn("CONTA", width=220, disabled=True)}
    for m in utils.meses_pt: col_cfg[m] = st.column_config.NumberColumn(m, width=110, format="R$ %,.2f") 

    st.markdown('<div class="container-tabelas">', unsafe_allow_html=True)
    
    # --- 1. PATRIMÔNIO ---
    st.markdown("#### 🏛️ Posição Patrimonial e Investimentos")
    df_p_ed = st.data_editor(st.session_state.df_p[colunas_v], hide_index=True, column_config=col_cfg, use_container_width=True, key="editor_p")

    if not df_p_ed.equals(st.session_state.df_p[colunas_v]):
        for m in [c for c in colunas_v if c != "MESES"]:
            st.session_state.df_p[m] = pd.to_numeric(df_p_ed[m], errors='coerce').fillna(0.0)
        if salvar_fin_no_banco('patrimonio', st.session_state.df_p, ano_fiscal):
            st.toast("✅ Patrimônio Salvo!", icon="💾")
            st.rerun()

    # CÁLCULOS COM CORREÇÃO DE JANEIRO (Patrimônio)
    df_n = st.session_state.df_p.set_index('MESES').apply(pd.to_numeric, errors='coerce').fillna(0)
    pat_liq = df_n[df_n.index.isin(['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS'])].sum()
    pat_tot = pat_liq + df_n[df_n.index == 'IMÓVEIS'].sum() + df_n[df_n.index == 'VEÍCULOS'].sum()
    
    var_abs = pat_tot.diff().fillna(0)
    var_abs.iloc[0] = pat_tot.iloc[0] - st.session_state.get('dez_ant_pat', 0.0) # Ajuste Janeiro
    
    var_pct = (pat_tot.pct_change().replace([np.inf, -np.inf], 0).fillna(0) * 100)
    if st.session_state.get('dez_ant_pat', 0.0) != 0:
        var_pct.iloc[0] = ((pat_tot.iloc[0] - st.session_state.get('dez_ant_pat', 0.0)) / st.session_state.get('dez_ant_pat', 0.0)) * 100
    else:
        var_pct.iloc[0] = 0.0
    var_pct = var_pct.round(2)

    df_res_p = pd.DataFrame({'MESES': ['PATRIMÔNIO LÍQUIDO', 'PATRIMÔNIO TOTAL', 'VAR. MENSAL (R$)', 'VAR. MENSAL (%)']})
    for m in utils.meses_pt: df_res_p[m] = [pat_liq.get(m, 0), pat_tot.get(m, 0), var_abs.get(m, 0), f"{var_pct.get(m, 0):.2f}%"]
    st.dataframe(df_res_p[colunas_v].style.apply(lambda row: [f'background-color: {"#FF9900" if row["MESES"] == "PATRIMÔNIO TOTAL" else "#FFF2CC" if "LÍQUIDO" in row["MESES"] else "white"}; font-weight: bold' for _ in colunas_v], axis=1).format(lambda x: x if isinstance(x, str) else utils.to_br_currency(x, False)), hide_index=True, column_config=col_cfg, use_container_width=True)

    st.markdown("---")
    
    # --- 2. RECEBIMENTOS ---
    st.markdown("#### 💰 Recebimentos e Pró-labore")
    df_e_ed = st.data_editor(st.session_state.df_e[colunas_v], hide_index=True, column_config=col_cfg, use_container_width=True, key="ed_e")

    if not df_e_ed.equals(st.session_state.df_e[colunas_v]):
        for m in [c for c in colunas_v if c != "MESES"]:
            st.session_state.df_e[m] = pd.to_numeric(df_e_ed[m], errors='coerce').fillna(0.0)
        if salvar_fin_no_banco('entradas', st.session_state.df_e, ano_fiscal):
            st.toast("✅ Recebimentos Salvos!", icon="💰")
            st.rerun()

    tot_ent = st.session_state.df_e.set_index('MESES').apply(pd.to_numeric, errors='coerce').fillna(0).sum()
    df_res_e = pd.DataFrame({'MESES': ['TOTAL RECEBIMENTOS']})
    for m in utils.meses_pt: df_res_e[m] = [tot_ent.get(m, 0)]
    st.dataframe(df_res_e[colunas_v].style.set_properties(**{'background-color': '#9BC2E6', 'font-weight': 'bold'}).format(lambda x: x if isinstance(x, str) else utils.to_br_currency(x, False)), hide_index=True, column_config=col_cfg, use_container_width=True)

    st.markdown("---")
    
    # --- 3. RENDIMENTOS (Com correção de Janeiro) ---
    st.markdown("#### 📈 Rendimento Mensal (Investimentos)")
    
    xp_val = df_n[df_n.index == 'INVESTIMENTO XP'].sum()
    inter_val = df_n[df_n.index == 'CONTA INTER'].sum()
    
    xp_var, inter_var = xp_val.diff().fillna(0), inter_val.diff().fillna(0)
    
    # Ajuste Janeiro
    xp_var.iloc[0] = xp_val.iloc[0] - st.session_state.get('dez_ant_xp', 0.0)
    inter_var.iloc[0] = inter_val.iloc[0] - st.session_state.get('dez_ant_inter', 0.0)
    
    rend_tot = xp_var + inter_var
    
    prev_bal = (xp_val + inter_val).shift(1).fillna(0)
    prev_bal.iloc[0] = st.session_state.get('dez_ant_xp', 0.0) + st.session_state.get('dez_ant_inter', 0.0) # Base de cálculo da % de Janeiro
    
    df_rend = pd.DataFrame({'MESES': ['RESULTADO XP', 'RESULTADO INTER', 'RENDIMENTO TOTAL', '% RETORNO MÊS', 'SALÁRIO + RENDIMENTO MÊS']})
    for i, m in enumerate(utils.meses_pt):
        if (ano_fiscal > utils.ano_atual) or (ano_fiscal == utils.ano_atual and i > utils.mes_hoje_idx - 1): df_rend[m] = [0, 0, 0, "0,00%", 0]
        else:
            rt, pb = rend_tot.get(m, 0), prev_bal.get(m, 0)
            pct = (rt/pb*100) if pb>0 else 0
            df_rend[m] = [xp_var.get(m, 0), inter_var.get(m, 0), rt, f"{pct:.2f}%", tot_ent.get(m, 0) + rt]
            
    st.dataframe(df_rend[colunas_v].style.apply(lambda row: [f'background-color: {"#FF9900" if row["MESES"] == "RENDIMENTO TOTAL" else "#FFF2CC" if "%" in row["MESES"] else "#9BC2E6" if "SALÁRIO" in row["MESES"] else "white"}; font-weight: bold' for _ in colunas_v], axis=1).format(lambda x: x if isinstance(x, str) else utils.to_br_currency(x, False)), hide_index=True, column_config=col_cfg, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- MÉTRICAS DE RODAPÉ ---
    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    m_calc = utils.meses_pt[:utils.mes_hoje_idx] if ano_fiscal == utils.ano_atual else utils.meses_pt
    media_ent = tot_ent[m_calc].mean() if len(m_calc) > 0 else 0
    media_rend_r = rend_tot[m_calc].mean() if len(m_calc) > 0 else 0
    pb_s = prev_bal[m_calc].replace(0, np.nan)
    media_rend_p = (rend_tot[m_calc] / pb_s).mean() * 100 if len(m_calc) > 0 else 0
    
    idx_r = 11 if ano_fiscal < utils.ano_atual else (utils.mes_hoje_idx - 1 if utils.mes_hoje_idx > 0 else 0)
    pat_at = pat_tot.iloc[idx_r] if len(pat_tot) > idx_r else 0

    c1.metric("💰 MÉDIA ENTRADAS", utils.to_br_currency(media_ent))
    c2.metric("🎯 LIMITE DE GASTO", utils.to_br_currency(media_rend_r))
    c3.metric("📈 MÉDIA RETORNO (%)", f"{media_rend_p:.2f}%".replace(".", ","))
    c4.metric("🏛️ PATRIMÔNIO ATUAL", utils.to_br_currency(pat_at))

    st.write("---")
    g1, g2 = st.columns(2)
    with g1:
        st.subheader("Aumento de Patrimônio Total"); st.line_chart(pat_tot[utils.meses_pt])
        st.subheader("Rendimento Mensal (R$)"); st.bar_chart(rend_tot[utils.meses_pt])
    with g2:
        st.subheader("Salário + Rendimento Mensal"); st.area_chart(tot_ent[utils.meses_pt] + rend_tot[utils.meses_pt])
        eco_series = st.session_state.df_e.set_index('MESES')
        eco_vals = pd.to_numeric(eco_series[eco_series.index == 'ECOCLIM'].sum()[utils.meses_pt], errors='coerce').fillna(0)
        st.subheader("Faturamento Ecoclim"); st.line_chart(eco_vals)
