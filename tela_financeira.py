import streamlit as st
import pandas as pd
import numpy as np
import utils

def renderizar():
    st.markdown('<div class="financeiro">', unsafe_allow_html=True)
    
    with st.sidebar:
        st.image("logo.png", width=150)
        ano_selecionado = st.selectbox("Ano Fiscal", options=[2025, 2026, 2027, 2028], index=1)
        st.write("---")
        st.markdown("### 👁️ Linha do Tempo")
        
        if 'mes_inicio_fin' not in st.session_state:
            st.session_state.mes_inicio_fin = 'JANEIRO'
            st.session_state.mes_fim_fin = 'DEZEMBRO'

        mes_inicio, mes_fim = st.select_slider(
            "Período Visível:", 
            options=utils.meses_pt, 
            value=(st.session_state.mes_inicio_fin, st.session_state.mes_fim_fin)
        )
        
        st.session_state.mes_inicio_fin = mes_inicio
        st.session_state.mes_fim_fin = mes_fim
            
        colunas_visiveis = ["MESES"] + utils.meses_pt[utils.meses_pt.index(mes_inicio):utils.meses_pt.index(mes_fim) + 1]

        if st.button("🔄 Recarregar Dados"): 
            st.session_state.pop('ano_dados_atual', None)
            st.rerun()

    contas_p = ['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS', 'IMÓVEIS', 'VEÍCULOS']
    contas_e = ['ECOCLIM', 'AIRNB', 'CONS INVESTIMENTOS', 'MAGGI CONSORCIOS']
    
    if 'ano_dados_atual' not in st.session_state or st.session_state.ano_dados_atual != ano_selecionado:
        st.session_state.df_p = utils.load_year_data('patrimonio', contas_p, ano_selecionado)
        st.session_state.df_e = utils.load_year_data('entradas', contas_e, ano_selecionado)
        st.session_state.ano_dados_atual = ano_selecionado

    # Função anti-lixo blindada contra erros de tipagem no Supabase
    def garantir_linhas(df, lista_contas):
        if df.empty or 'MESES' not in df.columns:
            return pd.DataFrame({"MESES": lista_contas, **{m: 0.0 for m in utils.meses_pt}})
        
        # Converte para string antes de filtrar para evitar erros no banco de dados
        df['MESES'] = df['MESES'].astype(str)
        df = df[df['MESES'].isin(lista_contas)].copy()
        
        for c in lista_contas:
            if c not in df['MESES'].values:
                df = pd.concat([df, pd.DataFrame([{"MESES": c, **{m: 0.0 for m in utils.meses_pt}}])], ignore_index=True)
        
        # Força a ordem sem usar Pandas Categorical (que quebra o Supabase)
        df['sort_idx'] = df['MESES'].apply(lambda x: lista_contas.index(x) if x in lista_contas else 99)
        df = df.sort_values('sort_idx').drop(columns=['sort_idx']).reset_index(drop=True)
        return df

    st.session_state.df_p = garantir_linhas(st.session_state.df_p, contas_p)
    st.session_state.df_e = garantir_linhas(st.session_state.df_e, contas_e)

    for m in utils.meses_pt:
        st.session_state.df_p[m] = pd.to_numeric(st.session_state.df_p[m], errors='coerce').fillna(0.0)
        st.session_state.df_e[m] = pd.to_numeric(st.session_state.df_e[m], errors='coerce').fillna(0.0)

    col_cfg = {"MESES": st.column_config.TextColumn("CONTA", width=220, disabled=True)}
    for m in utils.meses_pt: col_cfg[m] = st.column_config.NumberColumn(m, width=100, format="R$ %,.2f") 

    st.markdown('<div class="container-tabelas">', unsafe_allow_html=True)
    
    # --- 1. PATRIMÔNIO (Com detecção exata de alteração no ENTER) ---
    st.markdown("#### 🏛️ Posição Patrimonial e Investimentos")
    df_p_editado = st.data_editor(st.session_state.df_p[colunas_visiveis], hide_index=True, column_config=col_cfg, use_container_width=True, key="editor_p")

    mudou_p = False
    for m in [c for c in colunas_visiveis if c != "MESES"]:
        if not np.allclose(st.session_state.df_p[m].fillna(0), pd.to_numeric(df_p_editado[m], errors='coerce').fillna(0)):
            mudou_p = True
            break

    if mudou_p:
        for m in [c for c in colunas_visiveis if c != "MESES"]: 
            st.session_state.df_p[m] = pd.to_numeric(df_p_editado[m], errors='coerce').fillna(0.0)
        
        # Clona e garante que MESES seja texto antes de enviar para a nuvem
        df_to_save_p = st.session_state.df_p.copy()
        df_to_save_p['MESES'] = df_to_save_p['MESES'].astype(str)
        utils.save_to_supabase('patrimonio', df_to_save_p, ano_selecionado)
        st.toast("✅ Patrimônio gravado!", icon="💾")
        st.rerun()

    df_n = st.session_state.df_p.set_index('MESES')
    pat_liq = df_n[df_n.index.isin(['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS'])].sum()
    pat_tot = pat_liq + df_n[df_n.index == 'IMÓVEIS'].sum() + df_n[df_n.index == 'VEÍCULOS'].sum()
    var_abs = pat_tot.diff().fillna(0)
    var_pct = (pat_tot.pct_change().replace([np.inf, -np.inf], 0).fillna(0) * 100).round(2)

    df_res_p = pd.DataFrame({'MESES': ['PATRIMÔNIO LÍQUIDO', 'PATRIMÔNIO TOTAL', 'VAR. MENSAL (R$)', 'VAR. MENSAL (%)']})
    for m in utils.meses_pt: df_res_p[m] = [pat_liq.get(m, 0), pat_tot.get(m, 0), var_abs.get(m, 0), f"{var_pct.get(m, 0):.2f}%"]
    styled_res_p = df_res_p[colunas_visiveis].style.apply(lambda row: [f'background-color: {"#FF9900" if row["MESES"] == "PATRIMÔNIO TOTAL" else "#FFF2CC" if "LÍQUIDO" in row["MESES"] else "white"}; color: black; font-weight: bold' for _ in colunas_visiveis], axis=1)
    st.dataframe(styled_res_p.format(lambda x: x if isinstance(x, str) else utils.to_br_currency(x, False)), hide_index=True, column_config=col_cfg, use_container_width=True)

    st.markdown("---")
    
    # --- 2. RECEBIMENTOS (Automáticos ECOCLIM removidos) ---
    st.markdown("#### 💰 Recebimentos e Pró-labore")

    df_e_editado = st.data_editor(st.session_state.df_e[colunas_visiveis], hide_index=True, column_config=col_cfg, use_container_width=True, key="ed_e")
    
    mudou_e = False
    for m in [c for c in colunas_visiveis if c != "MESES"]:
        if not np.allclose(st.session_state.df_e[m].fillna(0), pd.to_numeric(df_e_editado[m], errors='coerce').fillna(0)):
            mudou_e = True
            break

    if mudou_e:
        for m in [c for c in colunas_visiveis if c != "MESES"]: 
            st.session_state.df_e[m] = pd.to_numeric(df_e_editado[m], errors='coerce').fillna(0.0)
        
        df_to_save_e = st.session_state.df_e.copy()
        df_to_save_e['MESES'] = df_to_save_e['MESES'].astype(str)
        utils.save_to_supabase('entradas', df_to_save_e, ano_selecionado)
        st.toast("✅ Recebimentos gravados!", icon="💰")
        st.rerun()

    tot_ent = st.session_state.df_e.set_index('MESES').sum()
    df_res_e = pd.DataFrame({'MESES': ['TOTAL RECEBIMENTOS']})
    for m in utils.meses_pt: df_res_e[m] = [tot_ent.get(m, 0)]
    styled_res_e = df_res_e[colunas_visiveis].style.set_properties(**{'background-color': '#9BC2E6', 'color': 'black', 'font-weight': 'bold'})
    st.dataframe(styled_res_e.format(lambda x: x if isinstance(x, str) else utils.to_br_currency(x, False)), hide_index=True, column_config=col_cfg, use_container_width=True)

    st.markdown("---")
    st.markdown("#### 📈 Rendimento Mensal (Investimentos)")
    
    xp_val = df_n[df_n.index == 'INVESTIMENTO XP'].sum(); inter_val = df_n[df_n.index == 'CONTA INTER'].sum()
    xp_var = xp_val.diff().fillna(0); inter_var = inter_val.diff().fillna(0)
    rend_tot = xp_var + inter_var; prev_bal = (xp_val + inter_val).shift(1).fillna(0)
    
    df_rend = pd.DataFrame({'MESES': ['RESULTADO XP', 'RESULTADO INTER', 'RENDIMENTO TOTAL', '% RETORNO MÊS', 'SALÁRIO + RENDIMENTO MÊS']})
    for i, m in enumerate(utils.meses_pt):
        if (ano_selecionado > utils.ano_atual) or (ano_selecionado == utils.ano_atual and i > utils.mes_hoje_idx - 1): df_rend[m] = [0, 0, 0, "0,00%", 0]
        else:
            rt = rend_tot.get(m, 0); pb = prev_bal.get(m, 0); pct = (rt/pb*100) if pb>0 else 0
            df_rend[m] = [xp_var.get(m, 0), inter_var.get(m, 0), rt, f"{pct:.2f}%", tot_ent.get(m, 0) + rt]
            
    styled_rend = df_rend[colunas_visiveis].style.apply(lambda row: [f'background-color: {"#FF9900" if row["MESES"] == "RENDIMENTO TOTAL" else "#FFF2CC" if "%" in row["MESES"] else "#9BC2E6" if "SALÁRIO" in row["MESES"] else "white"}; color: black; font-weight: bold' for _ in colunas_visiveis], axis=1)
    
    # Renderização liberta do "R$" na coluna das percentagens
    st.dataframe(styled_rend.format(lambda x: x if isinstance(x, str) else utils.to_br_currency(x, False)), hide_index=True, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    meses_calc = utils.meses_pt[:utils.mes_hoje_idx] if ano_selecionado == utils.ano_atual else utils.meses_pt
    media_ent = tot_ent[meses_calc].mean() if not tot_ent.empty else 0
    media_rend_r = rend_tot[meses_calc].mean() if not rend_tot.empty else 0
    pb_safe = prev_bal[meses_calc].replace(0, np.nan)
    media_rend_p = (rend_tot[meses_calc] / pb_safe).mean() * 100 if not pb_safe.isna().all() else 0.0
    idx_ref = 11 if ano_selecionado < utils.ano_atual else (utils.mes_hoje_idx - 1 if utils.mes_hoje_idx > 0 else 0)
    pat_atual = pat_tot.iloc[idx_ref] if len(pat_tot) > idx_ref else 0

    c1.metric("💰 MÉDIA ENTRADAS", utils.to_br_currency(media_ent))
    c2.metric("🎯 LIMITE DE GASTO", utils.to_br_currency(media_rend_r))
    c3.metric("📈 MÉDIA RETORNO (%)", f"{media_rend_p:.2f}%".replace(".", ","))
    c4.metric("🏛️ PATRIMÔNIO ATUAL", utils.to_br_currency(pat_atual))

    st.write("---")
    g1, g2 = st.columns(2)
    pat_chart = pd.to_numeric(pat_tot[utils.meses_pt], errors='coerce').fillna(0)
    rend_chart = pd.to_numeric(rend_tot[utils.meses_pt], errors='coerce').fillna(0)
    salario_chart = pd.to_numeric(tot_ent[utils.meses_pt] + rend_tot[utils.meses_pt], errors='coerce').fillna(0)
    eco_series = st.session_state.df_e.set_index('MESES')
    eco_vals = pd.to_numeric(eco_series[eco_series.index == 'ECOCLIM'].sum()[utils.meses_pt], errors='coerce').fillna(0)

    with g1:
        st.subheader("Aumento de Patrimônio Total"); st.line_chart(pat_chart)
        st.subheader("Rendimento Mensal (R$)"); st.bar_chart(rend_chart)
    with g2:
        st.subheader("Salário + Rendimento Mensal"); st.area_chart(salario_chart)
        st.subheader("Faturamento Ecoclim"); st.line_chart(eco_vals)
