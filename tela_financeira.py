import streamlit as st
import pandas as pd
import numpy as np
import utils

def carregar_periodo_visivel():
    """Busca o período salvo no cofre oculto do Supabase ou na sessão"""
    if 'periodo_visivel' in st.session_state:
        return st.session_state.periodo_visivel
    try:
        res = st.session_state.supabase.table('entradas').select('*').eq('ano', 2000).eq('MESES', 'CFG_PERIODO').execute()
        if res.data:
            idx_ini = int(res.data[0].get('JANEIRO', 0))
            idx_fim = int(res.data[0].get('FEVEREIRO', 11))
            st.session_state.periodo_visivel = (utils.meses_pt[idx_ini], utils.meses_pt[idx_fim])
            return st.session_state.periodo_visivel
    except:
        pass
    st.session_state.periodo_visivel = ("JANEIRO", "DEZEMBRO")
    return st.session_state.periodo_visivel

def salvar_periodo_visivel(m_ini, m_fim):
    """Salva a escolha do slider no Supabase para não perder no logout"""
    st.session_state.periodo_visivel = (m_ini, m_fim)
    try:
        idx_ini = utils.meses_pt.index(m_ini)
        idx_fim = utils.meses_pt.index(m_fim)
        st.session_state.supabase.table('entradas').delete().eq('ano', 2000).eq('MESES', 'CFG_PERIODO').execute()
        st.session_state.supabase.table('entradas').insert({
            'ano': 2000, 
            'MESES': 'CFG_PERIODO', 
            'JANEIRO': float(idx_ini), 
            'FEVEREIRO': float(idx_fim)
        }).execute()
    except:
        pass

def limpar_e_garantir_linhas(df, lista_contas):
    """Função blindada: Remove linhas fantasmas, garante as reais e ordena perfeitamente."""
    # 1. Remover lixo (linhas em branco ou nulas)
    if not df.empty and 'MESES' in df.columns:
        df = df[df['MESES'].astype(str).str.strip() != '']
        df = df[df['MESES'].notna()]
    else:
        df = pd.DataFrame(columns=["MESES"] + utils.meses_pt)
        
    # 2. Garantir que todas as contas oficiais existam
    contas_existentes = df['MESES'].tolist()
    linhas_novas = []
    for c in lista_contas:
        if c not in contas_existentes:
            linhas_novas.append({"MESES": c, **{m: 0.0 for m in utils.meses_pt}})
    
    if linhas_novas:
        df = pd.concat([df, pd.DataFrame(linhas_novas)], ignore_index=True)
        
    # 3. Forçar a ordem exata e remover possíveis duplicatas
    df = df.drop_duplicates(subset=['MESES'], keep='last')
    df['MESES'] = pd.Categorical(df['MESES'], categories=lista_contas, ordered=True)
    df = df.sort_values('MESES').reset_index(drop=True)
    return df

def get_dec_val(series):
    """Função auxiliar segura para extrair Dezembro"""
    return series.get('DEZEMBRO', 0) if 'DEZEMBRO' in series else 0

def renderizar():
    st.markdown('<div class="financeiro">', unsafe_allow_html=True)
    st.subheader("📊 Controle Financeiro e Patrimônio")
    
    with st.sidebar:
        ano_selecionado = st.selectbox("Ano Fiscal", options=[2025, 2026, 2027, 2028], index=1)
        st.write("---")
        st.markdown("### 👁️ Linha do Tempo")
        
        pref_inicio, pref_fim = carregar_periodo_visivel()
        mes_inicio, mes_fim = st.select_slider("Período Visível na Tela:", options=utils.meses_pt, value=(pref_inicio, pref_fim))
        
        if (mes_inicio, mes_fim) != (pref_inicio, pref_fim):
            salvar_periodo_visivel(mes_inicio, mes_fim)
            st.rerun()
            
        colunas_visiveis = ["MESES"] + utils.meses_pt[utils.meses_pt.index(mes_inicio):utils.meses_pt.index(mes_fim) + 1]

        if st.button("🔄 Recarregar Dados do Banco"): 
            st.session_state.pop('ano_dados_atual', None)
            st.rerun()

    contas_p = ['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS', 'IMÓVEIS', 'VEÍCULOS']
    contas_e = ['ECOCLIM', 'AIRNB', 'CONS INVESTIMENTOS', 'MAGGI CONSORCIOS']
    
    if 'ano_dados_atual' not in st.session_state or st.session_state.ano_dados_atual != ano_selecionado:
        st.session_state.df_p = utils.load_year_data('patrimonio', contas_p, ano_selecionado)
        st.session_state.df_e = utils.load_year_data('entradas', contas_e, ano_selecionado)
        st.session_state.ano_dados_atual = ano_selecionado

    # --- REGRA DO ANO PASSADO (Dezembro Herdeiro) ---
    df_p_prev = utils.load_year_data('patrimonio', contas_p, ano_selecionado - 1)
    df_p_prev = limpar_e_garantir_linhas(df_p_prev, contas_p)
    df_n_prev = df_p_prev.set_index('MESES')
    
    pat_liq_prev = df_n_prev[df_n_prev.index.isin(['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS'])].sum()
    pat_tot_prev_dec = get_dec_val(pat_liq_prev) + get_dec_val(df_n_prev[df_n_prev.index == 'IMÓVEIS'].sum()) + get_dec_val(df_n_prev[df_n_prev.index == 'VEÍCULOS'].sum())
    xp_val_prev_dec = get_dec_val(df_n_prev[df_n_prev.index == 'INVESTIMENTO XP'].sum())
    inter_val_prev_dec = get_dec_val(df_n_prev[df_n_prev.index == 'CONTA INTER'].sum())

    # Aplica a faxina nas tabelas atuais
    st.session_state.df_p = limpar_e_garantir_linhas(st.session_state.df_p, contas_p)
    st.session_state.df_e = limpar_e_garantir_linhas(st.session_state.df_e, contas_e)

    # Configuração de larguras (Régua oficial)
    col_cfg = {"MESES": st.column_config.TextColumn("CONTA", width=220, disabled=True)}
    for m in utils.meses_pt: 
        col_cfg[m] = st.column_config.NumberColumn(m, width=100, format="R$ %,.2f") 
        
    col_cfg_text = {"MESES": st.column_config.TextColumn("CONTA", width=220, disabled=True)}
    for m in utils.meses_pt:
        col_cfg_text[m] = st.column_config.TextColumn(m, width=100, disabled=True)

    st.markdown('<div class="container-tabelas">', unsafe_allow_html=True)
    
    # --------------------------
    # PATRIMÔNIO
    # --------------------------
    st.markdown("#### 🏛️ Posição Patrimonial e Investimentos")
    df_p_editado = st.data_editor(st.session_state.df_p[colunas_visiveis], hide_index=True, column_config=col_cfg, use_container_width=True, height=295, key="editor_p")

    # Salvamento super seguro (Apenas se houver diferença real)
    mudou_p = False
    for _, row in df_p_editado.iterrows():
        conta = row['MESES']
        idx_real = st.session_state.df_p.index[st.session_state.df_p['MESES'] == conta].tolist()
        if idx_real:
            idx = idx_real[0]
            for m in colunas_visiveis:
                if m != 'MESES':
                    val_novo = float(row[m]) if pd.notna(row[m]) else 0.0
                    val_antigo = float(st.session_state.df_p.at[idx, m]) if pd.notna(st.session_state.df_p.at[idx, m]) else 0.0
                    if abs(val_novo - val_antigo) > 0.01:
                        st.session_state.df_p.at[idx, m] = val_novo
                        mudou_p = True

    if mudou_p:
        utils.save_to_supabase('patrimonio', st.session_state.df_p, ano_selecionado)
        st.rerun()

    df_n = st.session_state.df_p.set_index('MESES')
    pat_liq = df_n[df_n.index.isin(['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS'])].sum()
    pat_tot = pat_liq + df_n[df_n.index == 'IMÓVEIS'].sum() + df_n[df_n.index == 'VEÍCULOS'].sum()
    
    # Cálculo com herança de Janeiro do ano anterior
    var_abs = pat_tot.copy()
    var_pct = pat_tot.copy()
    for i, m in enumerate(utils.meses_pt):
        if i == 0:
            var_abs[m] = pat_tot[m] - pat_tot_prev_dec
            var_pct[m] = (var_abs[m] / pat_tot_prev_dec * 100) if pat_tot_prev_dec != 0 else 0.0
        else:
            prev_m = utils.meses_pt[i-1]
            var_abs[m] = pat_tot[m] - pat_tot[prev_m]
            var_pct[m] = (var_abs[m] / pat_tot[prev_m] * 100) if pat_tot[prev_m] != 0 else 0.0

    dict_res_p = {'MESES': ['PATRIMÔNIO LÍQUIDO', 'PATRIMÔNIO TOTAL', 'VAR. MENSAL (R$)', 'VAR. MENSAL (%)']}
    for i, m in enumerate(utils.meses_pt):
        is_future = (ano_selecionado > utils.ano_atual) or (ano_selecionado == utils.ano_atual and i > utils.mes_hoje_idx - 1)
        if is_future:
            dict_res_p[m] = [utils.to_br_currency(0), utils.to_br_currency(0), utils.to_br_currency(0), "0,00%"]
        else:
            dict_res_p[m] = [
                utils.to_br_currency(pat_liq.get(m, 0)), 
                utils.to_br_currency(pat_tot.get(m, 0)), 
                utils.to_br_currency(var_abs.get(m, 0)), 
                f"{var_pct.get(m, 0):.2f}%".replace('.', ',')
            ]
            
    df_res_p = pd.DataFrame(dict_res_p)
    styled_res_p = df_res_p[colunas_visiveis].style.apply(lambda row: [f'background-color: {"#FF9900" if row["MESES"] == "PATRIMÔNIO TOTAL" else "#FFF2CC" if "LÍQUIDO" in row["MESES"] else "white"}; color: black; font-weight: bold' for _ in colunas_visiveis], axis=1)
    
    st.dataframe(styled_res_p, hide_index=True, column_config=col_cfg_text, use_container_width=True)

    st.markdown("---")
    st.markdown("#### 💰 Recebimentos e Pró-labore")
    
    if ano_selecionado == utils.ano_atual:
        try:
            res_serv = st.session_state.supabase.table('servicos_andamento').select('lucro_estimado, status_projeto').execute()
            df_serv = pd.DataFrame(res_serv.data)
            if not df_serv.empty:
                lucro = df_serv[df_serv['status_projeto'].isin(['Em Andamento', 'Concluído PIX', 'Concluído CARTÃO'])]['lucro_estimado'].sum()
                idx = st.session_state.df_e.index[st.session_state.df_e['MESES'] == 'ECOCLIM'].tolist()
                if idx: st.session_state.df_e.at[idx[0], utils.mes_atual_nome] = float(lucro)
        except: pass

    df_e_edit = st.data_editor(st.session_state.df_e[colunas_visiveis], hide_index=True, column_config=col_cfg, use_container_width=True, height=190, key="ed_e")
    
    mudou_e = False
    for _, row in df_e_edit.iterrows():
        conta = row['MESES']
        idx_real = st.session_state.df_e.index[st.session_state.df_e['MESES'] == conta].tolist()
        if idx_real:
            idx = idx_real[0]
            for m in colunas_visiveis:
                if m != 'MESES':
                    val_novo = float(row[m]) if pd.notna(row[m]) else 0.0
                    val_antigo = float(st.session_state.df_e.at[idx, m]) if pd.notna(st.session_state.df_e.at[idx, m]) else 0.0
                    if abs(val_novo - val_antigo) > 0.01:
                        st.session_state.df_e.at[idx, m] = val_novo
                        mudou_e = True

    if mudou_e:
        utils.save_to_supabase('entradas', st.session_state.df_e, ano_selecionado)
        st.rerun()

    tot_ent = st.session_state.df_e.set_index('MESES').sum()
    dict_res_e = {'MESES': ['TOTAL RECEBIMENTOS']}
    for i, m in enumerate(utils.meses_pt):
        is_future = (ano_selecionado > utils.ano_atual) or (ano_selecionado == utils.ano_atual and i > utils.mes_hoje_idx - 1)
        dict_res_e[m] = [utils.to_br_currency(0 if is_future else tot_ent.get(m, 0))]
        
    df_res_e = pd.DataFrame(dict_res_e)
    styled_res_e = df_res_e[colunas_visiveis].style.set_properties(**{'background-color': '#9BC2E6', 'color': 'black', 'font-weight': 'bold'})
    st.dataframe(styled_res_e, hide_index=True, column_config=col_cfg_text, use_container_width=True)

    st.markdown("---")
    st.markdown("#### 📈 Rendimento Mensal (Investimentos)")
    
    xp_val = df_n[df_n.index == 'INVESTIMENTO XP'].sum()
    inter_val = df_n[df_n.index == 'CONTA INTER'].sum()
    
    xp_var = xp_val.copy()
    inter_var = inter_val.copy()
    prev_bal = xp_val.copy()
    for i, m in enumerate(utils.meses_pt):
        if i == 0:
            xp_var[m] = xp_val[m] - xp_val_prev_dec
            inter_var[m] = inter_val[m] - inter_val_prev_dec
            prev_bal[m] = xp_val_prev_dec + inter_val_prev_dec
        else:
            prev_m = utils.meses_pt[i-1]
            xp_var[m] = xp_val[m] - xp_val[prev_m]
            inter_var[m] = inter_val[m] - inter_val[prev_m]
            prev_bal[m] = xp_val[prev_m] + inter_val[prev_m]

    rend_tot = xp_var + inter_var
            
    dict_rend = {'MESES': ['RESULTADO XP', 'RESULTADO INTER', 'RENDIMENTO TOTAL', '% RETORNO MÊS', 'SALÁRIO + RENDIMENTO MÊS']}
    for i, m in enumerate(utils.meses_pt):
        is_future = (ano_selecionado > utils.ano_atual) or (ano_selecionado == utils.ano_atual and i > utils.mes_hoje_idx - 1)
        if is_future:
            dict_rend[m] = [utils.to_br_currency(0), utils.to_br_currency(0), utils.to_br_currency(0), "0,00%", utils.to_br_currency(0)]
        else:
            rt = rend_tot.get(m, 0)
            pb = prev_bal.get(m, 0)
            pct = (rt/pb*100) if pb > 0 else 0
            dict_rend[m] = [
                utils.to_br_currency(xp_var.get(m, 0)),
                utils.to_br_currency(inter_var.get(m, 0)),
                utils.to_br_currency(rt),
                f"{pct:.2f}%".replace('.', ','),
                utils.to_br_currency(tot_ent.get(m, 0) + rt)
            ]
            
    df_rend = pd.DataFrame(dict_rend)
    styled_rend = df_rend[colunas_visiveis].style.apply(lambda row: [f'background-color: {"#FF9900" if row["MESES"] == "RENDIMENTO TOTAL" else "#FFF2CC" if "%" in row["MESES"] else "#9BC2E6" if "SALÁRIO" in row["MESES"] else "white"}; color: black; font-weight: bold' for _ in colunas_visiveis], axis=1)
    st.dataframe(styled_rend, hide_index=True, column_config=col_cfg_text, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    meses_calc = utils.meses_pt[:utils.mes_hoje_idx] if ano_selecionado == utils.ano_atual else utils.meses_pt
    media_ent = tot_ent[meses_calc].mean() if not tot_ent.empty else 0
    media_rend_r = rend_tot[meses_calc].mean() if not rend_tot.empty else 0
    
    pb_safe = prev_bal[meses_calc].replace(0, np.nan)
    media_rend_p = (rend_tot[meses_calc] / pb_safe).mean() * 100 if not pb_safe.isna().all() else 0
    
    idx_ref = 11 if ano_selecionado < utils.ano_atual else (utils.mes_hoje_idx - 1 if utils.mes_hoje_idx > 0 else 0)
    pat_atual = pat_tot.iloc[idx_ref] if len(pat_tot) > idx_ref else 0

    c1.metric("💰 MÉDIA ENTRADAS", utils.to_br_currency(media_ent))
    c2.metric("🎯 LIMITE DE GASTO", utils.to_br_currency(media_rend_r))
    c3.metric("📈 MÉDIA RETORNO (%)", f"{media_rend_p:.2f}%".replace(".", ","))
    c4.metric("🏛️ PATRIMÔNIO ATUAL", utils.to_br_currency(pat_atual))

    st.write("---")
    g1, g2 = st.columns(2)
    with g1:
        st.subheader("Aumento de Patrimônio Total"); st.line_chart(pat_tot[utils.meses_pt])
        st.subheader("Rendimento Mensal (R$)"); st.bar_chart(rend_tot[utils.meses_pt])
    with g2:
        st.subheader("Salário + Rendimento Mensal"); st.area_chart(tot_ent[utils.meses_pt] + rend_tot[utils.meses_pt])
        st.subheader("Faturamento Ecoclim")
        eco_series = st.session_state.df_e.set_index('MESES')
        eco_vals = eco_series[eco_series.index == 'ECOCLIM'].sum()
        st.line_chart(eco_vals[utils.meses_pt])
