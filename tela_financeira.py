import streamlit as st
import pandas as pd
import numpy as np
import utils

# =============================================================================
# FUNÇÃO BLINDADA DE SALVAMENTO (EXCLUSIVA DO FINANCEIRO)
# Resolve o problema de letras maiúsculas/minúsculas no Banco de Dados
# =============================================================================
def salvar_fin_no_banco(nome_tabela, df, ano):
    supabase = st.session_state.supabase
    
    # Prepara os dados em formato Minúsculo (Padrão do Banco de Dados)
    dados_min = []
    for _, linha in df.iterrows():
        reg = {"ano": ano, "meses": str(linha["MESES"])}
        for m in utils.meses_pt:
            reg[m.lower()] = float(linha[m]) if pd.notna(linha[m]) else 0.0
        dados_min.append(reg)
        
    try:
        # 1. Limpa o ano atual para evitar duplicatas
        supabase.table(nome_tabela).delete().eq("ano", ano).execute()
        
        # 2. Tenta inserir em minúsculas
        try:
            supabase.table(nome_tabela).insert(dados_min).execute()
        except Exception as e_min:
            # Caso o banco tenha a coluna 'marco' sem cedilha
            if 'março' in str(e_min).lower():
                for d in dados_min: 
                    d['marco'] = d.pop('março')
                supabase.table(nome_tabela).insert(dados_min).execute()
            else:
                # Se falhar por outro motivo, tenta forçar em Maiúsculo como último recurso
                dados_mai = []
                for _, linha in df.iterrows():
                    reg_m = {"ano": ano, "MESES": str(linha["MESES"])}
                    for m in utils.meses_pt: reg_m[m] = float(linha[m]) if pd.notna(linha[m]) else 0.0
                    dados_mai.append(reg_m)
                supabase.table(nome_tabela).insert(dados_mai).execute()
                
    except Exception as e:
        st.error(f"Erro crítico ao conectar com banco: {e}")

# =============================================================================
# RENDERIZAÇÃO DA TELA
# =============================================================================
def renderizar():
    st.markdown('<div class="financeiro">', unsafe_allow_html=True)
    
    with st.sidebar:
        ano_selecionado = st.selectbox("Ano Fiscal", options=[2025, 2026, 2027, 2028], index=1)
        
        st.write("---")
        if st.button("💾 SALVAR TUDO AGORA", type="primary", use_container_width=True):
            st.session_state.salvar_fin_clicado = True

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

    def garantir_limpeza(df, lista):
        df['MESES'] = df['MESES'].astype(str).str.strip()
        df = df[df['MESES'].isin(lista)].copy()
        for c in lista:
            if c not in df['MESES'].values:
                df = pd.concat([df, pd.DataFrame([{"MESES": c, **{m: 0.0 for m in utils.meses_pt}}])], ignore_index=True)
        ordem = {val: idx for idx, val in enumerate(lista)}
        df['sort_idx'] = df['MESES'].map(ordem)
        df = df.sort_values('sort_idx').drop(columns=['sort_idx']).reset_index(drop=True)
        return df

    st.session_state.df_p = garantir_limpeza(st.session_state.df_p, contas_p)
    st.session_state.df_e = garantir_limpeza(st.session_state.df_e, contas_e)

    col_cfg = {"MESES": st.column_config.TextColumn("CONTA", width=220, disabled=True)}
    for m in utils.meses_pt: 
        col_cfg[m] = st.column_config.NumberColumn(m, width=110, format="R$ %,.2f") 

    st.markdown('<div class="container-tabelas">', unsafe_allow_html=True)
    
    # =========================================================================
    # 1. TABELA PATRIMÔNIO
    # =========================================================================
    st.markdown("#### 🏛️ Posição Patrimonial e Investimentos")
    df_p_editado = st.data_editor(st.session_state.df_p[colunas_visiveis], hide_index=True, column_config=col_cfg, use_container_width=True, key="editor_p")

    mudou_p = False
    for idx in df_p_editado.index:
        for m in [c for c in colunas_visiveis if c != "MESES"]:
            val_edit = pd.to_numeric(df_p_editado.at[idx, m], errors='coerce')
            val_state = pd.to_numeric(st.session_state.df_p.at[idx, m], errors='coerce')
            if abs((val_edit if pd.notna(val_edit) else 0) - (val_state if pd.notna(val_state) else 0)) > 0.01:
                st.session_state.df_p.at[idx, m] = val_edit
                mudou_p = True

    if mudou_p:
        salvar_fin_no_banco('patrimonio', st.session_state.df_p, ano_selecionado)
        st.toast("✅ Patrimônio atualizado!", icon="💾")

    df_n = st.session_state.df_p.set_index('MESES').apply(pd.to_numeric, errors='coerce').fillna(0)
    pat_liq = df_n[df_n.index.isin(['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS'])].sum()
    pat_tot = pat_liq + df_n[df_n.index == 'IMÓVEIS'].sum() + df_n[df_n.index == 'VEÍCULOS'].sum()
    var_abs = pat_tot.diff().fillna(0)
    var_pct = (pat_tot.pct_change().replace([np.inf, -np.inf], 0).fillna(0) * 100).round(2)

    df_res_p = pd.DataFrame({'MESES': ['PATRIMÔNIO LÍQUIDO', 'PATRIMÔNIO TOTAL', 'VAR. MENSAL (R$)', 'VAR. MENSAL (%)']})
    for m in utils.meses_pt: df_res_p[m] = [pat_liq.get(m, 0), pat_tot.get(m, 0), var_abs.get(m, 0), f"{var_pct.get(m, 0):.2f}%"]
    st.dataframe(df_res_p[colunas_visiveis].style.apply(lambda row: [f'background-color: {"#FF9900" if row["MESES"] == "PATRIMÔNIO TOTAL" else "#FFF2CC" if "LÍQUIDO" in row["MESES"] else "white"}; font-weight: bold' for _ in colunas_visiveis], axis=1).format(lambda x: x if isinstance(x, str) else utils.to_br_currency(x, False)), hide_index=True, column_config=col_cfg, use_container_width=True)

    st.markdown("---")
    
    # =========================================================================
    # 2. TABELA RECEBIMENTOS
    # =========================================================================
    st.markdown("#### 💰 Recebimentos e Pró-labore")
    df_e_editado = st.data_editor(st.session_state.df_e[colunas_visiveis], hide_index=True, column_config=col_cfg, use_container_width=True, key="ed_e")

    mudou_e = False
    for idx in df_e_editado.index:
        for m in [c for c in colunas_visiveis if c != "MESES"]:
            val_edit = pd.to_numeric(df_e_editado.at[idx, m], errors='coerce')
            val_state = pd.to_numeric(st.session_state.df_e.at[idx, m], errors='coerce')
            if abs((val_edit if pd.notna(val_edit) else 0) - (val_state if pd.notna(val_state) else 0)) > 0.01:
                st.session_state.df_e.at[idx, m] = val_edit
                mudou_e = True

    if mudou_e:
        salvar_fin_no_banco('entradas', st.session_state.df_e, ano_selecionado)
        st.toast("✅ Recebimentos atualizados!", icon="💰")

    tot_ent = st.session_state.df_e.set_index('MESES').apply(pd.to_numeric, errors='coerce').fillna(0).sum()
    df_res_e = pd.DataFrame({'MESES': ['TOTAL RECEBIMENTOS']})
    for m in utils.meses_pt: df_res_e[m] = [tot_ent.get(m, 0)]
    st.dataframe(df_res_e[colunas_visiveis].style.set_properties(**{'background-color': '#9BC2E6', 'font-weight': 'bold'}).format(lambda x: x if isinstance(x, str) else utils.to_br_currency(x, False)), hide_index=True, column_config=col_cfg, use_container_width=True)

    # =========================================================================
    # 3. LÓGICA DO BOTÃO "SALVAR TUDO AGORA"
    # =========================================================================
    if st.session_state.get('salvar_fin_clicado', False):
        salvar_fin_no_banco('patrimonio', st.session_state.df_p, ano_selecionado)
        salvar_fin_no_banco('entradas', st.session_state.df_e, ano_selecionado)
        st.session_state.salvar_fin_clicado = False
        st.success("✅ Banco de Dados Atualizado com Sucesso!")

    st.markdown("---")
    st.markdown("#### 📈 Rendimento Mensal (Investimentos)")
    
    xp_val = df_n[df_n.index == 'INVESTIMENTO XP'].sum()
    inter_val = df_n[df_n.index == 'CONTA INTER'].sum()
    xp_var = xp_val.diff().fillna(0)
    inter_var = inter_val.diff().fillna(0)
    rend_tot = xp_var + inter_var
    prev_bal = (xp_val + inter_val).shift(1).fillna(0)
    
    df_rend = pd.DataFrame({'MESES': ['RESULTADO XP', 'RESULTADO INTER', 'RENDIMENTO TOTAL', '% RETORNO MÊS', 'SALÁRIO + RENDIMENTO MÊS']})
    for i, m in enumerate(utils.meses_pt):
        if (ano_selecionado > utils.ano_atual) or (ano_selecionado == utils.ano_atual and i > utils.mes_hoje_idx - 1): df_rend[m] = [0, 0, 0, "0,00%", 0]
        else:
            rt = rend_tot.get(m, 0); pb = prev_bal.get(m, 0)
            pct = (rt/pb*100) if pb>0 else 0
            df_rend[m] = [xp_var.get(m, 0), inter_var.get(m, 0), rt, f"{pct:.2f}%", tot_ent.get(m, 0) + rt]
            
    st.dataframe(df_rend[colunas_visiveis].style.apply(lambda row: [f'background-color: {"#FF9900" if row["MESES"] == "RENDIMENTO TOTAL" else "#FFF2CC" if "%" in row["MESES"] else "#9BC2E6" if "SALÁRIO" in row["MESES"] else "white"}; font-weight: bold' for _ in colunas_visiveis], axis=1).format(lambda x: x if isinstance(x, str) else utils.to_br_currency(x, False)), hide_index=True, column_config=col_cfg, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    meses_calc = utils.meses_pt[:utils.mes_hoje_idx] if ano_selecionado == utils.ano_atual else utils.meses_pt
    media_ent = tot_ent[meses_calc].mean() if not tot_ent.empty else 0
    media_rend_r = rend_tot[meses_calc].mean() if not rend_tot.empty else 0
    pb_safe = prev_bal[meses_calc].replace(0, np.nan)
    media_rend_p = (rend_tot[meses_calc] / pb_safe).mean() * 100 if not pb_safe.isna().all() else 0.0
    idx_ref = 11 if ano_selecionado < utils.ano_atual else (utils.mes_hoje_idx - 1 if utils.mes_hoje_idx > 0 else 0)
    pat_at = pat_tot.iloc[idx_ref] if len(pat_tot) > idx_ref else 0

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
