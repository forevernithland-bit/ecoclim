import streamlit as st
import pandas as pd
import numpy as np
import utils

# =============================================================================
# FUNÇÃO DE SALVAMENTO BLINDADA (EXCLUSIVA DO FINANCEIRO)
# Resolve o erro PGRST204 (Coluna não encontrada no cache)
# =============================================================================
def salvar_fin_blindado(nome_tabela, df, ano):
    supabase = st.session_state.supabase
    
    # Lista de meses para conversão
    meses_lista = ['JANEIRO', 'FEVEREIRO', 'MARÇO', 'ABRIL', 'MAIO', 'JUNHO', 
                   'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO']
    
    dados_para_enviar = []
    
    for _, linha in df.iterrows():
        # Criamos o registro com nomes de colunas em MINÚSCULAS (Padrão Supabase)
        registro = {
            "ano": int(ano),
            "meses": str(linha["MESES"]).strip()
        }
        
        for m in meses_lista:
            # Converte o nome do mês para minúsculo para bater com o banco
            col_banco = m.lower()
            
            # Caso especial: Se o seu banco estiver como 'marco' (sem cedilha)
            if col_banco == 'março':
                # Tentamos enviar como 'março', se der erro o bloco try/except abaixo trata
                pass 
                
            registro[col_banco] = float(linha[m]) if pd.notna(linha[m]) else 0.0
            
        dados_para_enviar.append(registro)

    try:
        # 1. Deleta os registros antigos do ano para evitar erro de duplicata
        supabase.table(nome_tabela).delete().eq("ano", ano).execute()
        
        # 2. Tenta inserir os novos dados
        try:
            supabase.table(nome_tabela).insert(dados_para_enviar).execute()
        except Exception as e_insert:
            # Plano B: Se falhar por causa da cedilha em 'março', tentamos 'marco'
            if 'março' in str(e_insert).lower():
                for d in dados_para_enviar:
                    if 'março' in d: d['marco'] = d.pop('março')
                supabase.table(nome_tabela).insert(dados_para_enviar).execute()
            else:
                raise e_insert
                
        return True
    except Exception as e:
        st.error(f"Erro ao salvar no banco: {e}")
        return False

# =============================================================================
# TELA FINANCEIRA
# =============================================================================
def renderizar():
    st.markdown('<div class="financeiro">', unsafe_allow_html=True)
    
    with st.sidebar:
        ano_fiscal = st.selectbox("Ano Fiscal", options=[2025, 2026, 2027, 2028], index=1)
        
        st.write("---")
        if st.button("💾 SALVAR TUDO AGORA", type="primary", use_container_width=True):
            res_p = salvar_fin_blindado('patrimonio', st.session_state.df_p, ano_fiscal)
            res_e = salvar_fin_blindado('entradas', st.session_state.df_e, ano_fiscal)
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
    
    if 'ano_dados_atual' not in st.session_state or st.session_state.ano_dados_atual != ano_fiscal:
        st.session_state.df_p = utils.load_year_data('patrimonio', contas_p, ano_fiscal)
        st.session_state.df_e = utils.load_year_data('entradas', contas_e, ano_fiscal)
        st.session_state.ano_dados_atual = ano_fiscal

    # Limpeza de linhas vazias
    def limpar(df, lista):
        df['MESES'] = df['MESES'].astype(str).str.strip()
        df = df[df['MESES'].isin(lista)].copy()
        for c in lista:
            if c not in df['MESES'].values:
                df = pd.concat([df, pd.DataFrame([{"MESES": c, **{m: 0.0 for m in utils.meses_pt}}])], ignore_index=True)
        ordem = {v: i for i, v in enumerate(lista)}
        df['ordem'] = df['MESES'].map(ordem)
        return df.sort_values('ordem').drop(columns=['ordem']).reset_index(drop=True)

    st.session_state.df_p = limpar(st.session_state.df_p, contas_p)
    st.session_state.df_e = limpar(st.session_state.df_e, contas_e)

    col_cfg = {"MESES": st.column_config.TextColumn("CONTA", width=220, disabled=True)}
    for m in utils.meses_pt: col_cfg[m] = st.column_config.NumberColumn(m, width=110, format="R$ %,.2f") 

    st.markdown('<div class="container-tabelas">', unsafe_allow_html=True)
    
    # --- PATRIMÔNIO ---
    st.markdown("#### 🏛️ Posição Patrimonial e Investimentos")
    df_p_ed = st.data_editor(st.session_state.df_p[colunas_v], hide_index=True, column_config=col_cfg, use_container_width=True, key="editor_p")

    if not df_p_ed.equals(st.session_state.df_p[colunas_v]):
        for m in [c for c in colunas_v if c != "MESES"]:
            st.session_state.df_p[m] = pd.to_numeric(df_p_ed[m], errors='coerce').fillna(0.0)
        salvar_fin_blindado('patrimonio', st.session_state.df_p, ano_fiscal)
        st.toast("✅ Patrimônio Salvo!", icon="💾")

    # Cálculos
    df_n = st.session_state.df_p.set_index('MESES').apply(pd.to_numeric, errors='coerce').fillna(0)
    pat_liq = df_n[df_n.index.isin(['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS'])].sum()
    pat_tot = pat_liq + df_n[df_n.index == 'IMÓVEIS'].sum() + df_n[df_n.index == 'VEÍCULOS'].sum()
    var_abs = pat_tot.diff().fillna(0)
    var_pct = (pat_tot.pct_change().replace([np.inf, -np.inf], 0).fillna(0) * 100).round(2)

    df_res_p = pd.DataFrame({'MESES': ['PATRIMÔNIO LÍQUIDO', 'PATRIMÔNIO TOTAL', 'VAR. MENSAL (R$)', 'VAR. MENSAL (%)']})
    for m in utils.meses_pt: df_res_p[m] = [pat_liq.get(m, 0), pat_tot.get(m, 0), var_abs.get(m, 0), f"{var_pct.get(m, 0):.2f}%"]
    st.dataframe(df_res_p[colunas_v].style.apply(lambda row: [f'background-color: {"#FF9900" if row["MESES"] == "PATRIMÔNIO TOTAL" else "#FFF2CC" if "LÍQUIDO" in row["MESES"] else "white"}; font-weight: bold' for _ in colunas_v], axis=1).format(lambda x: x if isinstance(x, str) else utils.to_br_currency(x, False)), hide_index=True, column_config=col_cfg, use_container_width=True)

    st.markdown("---")
    
    # --- RECEBIMENTOS ---
    st.markdown("#### 💰 Recebimentos e Pró-labore")
    df_e_ed = st.data_editor(st.session_state.df_e[colunas_v], hide_index=True, column_config=col_cfg, use_container_width=True, key="ed_e")

    if not df_e_ed.equals(st.session_state.df_e[colunas_v]):
        for m in [c for c in colunas_v if c != "MESES"]:
            st.session_state.df_e[m] = pd.to_numeric(df_e_ed[m], errors='coerce').fillna(0.0)
        salvar_fin_blindado('entradas', st.session_state.df_e, ano_fiscal)
        st.toast("✅ Recebimentos Salvos!", icon="💰")

    tot_ent = st.session_state.df_e.set_index('MESES').apply(pd.to_numeric, errors='coerce').fillna(0).sum()
    df_res_e = pd.DataFrame({'MESES': ['TOTAL RECEBIMENTOS']})
    for m in utils.meses_pt: df_res_e[m] = [tot_ent.get(m, 0)]
    st.dataframe(df_res_e[colunas_v].style.set_properties(**{'background-color': '#9BC2E6', 'font-weight': 'bold'}).format(lambda x: x if isinstance(x, str) else utils.to_br_currency(x, False)), hide_index=True, column_config=col_cfg, use_container_width=True)

    st.markdown("---")
    st.markdown("#### 📈 Rendimento Mensal (Investimentos)")
    
    xp_val = df_n[df_n.index == 'INVESTIMENTO XP'].sum()
    inter_val = df_n[df_n.index == 'CONTA INTER'].sum()
    xp_var, inter_var = xp_val.diff().fillna(0), inter_val.diff().fillna(0)
    rend_tot, prev_bal = (xp_var + inter_var), (xp_val + inter_val).shift(1).fillna(0)
    
    df_rend = pd.DataFrame({'MESES': ['RESULTADO XP', 'RESULTADO INTER', 'RENDIMENTO TOTAL', '% RETORNO MÊS', 'SALÁRIO + RENDIMENTO MÊS']})
    for i, m in enumerate(utils.meses_pt):
        if (ano_fiscal > utils.ano_atual) or (ano_fiscal == utils.ano_atual and i > utils.mes_hoje_idx - 1): df_rend[m] = [0, 0, 0, "0,00%", 0]
        else:
            rt, pb = rend_tot.get(m, 0), prev_bal.get(m, 0)
            pct = (rt/pb*100) if pb>0 else 0
            df_rend[m] = [xp_var.get(m, 0), inter_var.get(m, 0), rt, f"{pct:.2f}%", tot_ent.get(m, 0) + rt]
            
    st.dataframe(df_rend[colunas_v].style.apply(lambda row: [f'background-color: {"#FF9900" if row["MESES"] == "RENDIMENTO TOTAL" else "#FFF2CC" if "%" in row["MESES"] else "#9BC2E6" if "SALÁRIO" in row["MESES"] else "white"}; font-weight: bold' for _ in colunas_v], axis=1).format(lambda x: x if isinstance(x, str) else utils.to_br_currency(x, False)), hide_index=True, column_config=col_cfg, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Métricas
    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    m_calc = utils.meses_pt[:utils.mes_hoje_idx] if ano_fiscal == utils.ano_atual else utils.meses_pt
    media_ent = tot_ent[m_calc].mean()
    media_rend_r = rend_tot[m_calc].mean()
    pb_s = prev_bal[m_calc].replace(0, np.nan)
    media_rend_p = (rend_tot[m_calc] / pb_s).mean() * 100
    idx_r = 11 if ano_fiscal < utils.ano_atual else (utils.mes_hoje_idx - 1 if utils.mes_hoje_idx > 0 else 0)
    pat_at = pat_tot.iloc[idx_r] if len(pat_tot) > idx_r else 0

    c1.metric("💰 MÉDIA ENTRADAS", utils.to_br_currency(media_ent))
    c2.metric("🎯 LIMITE DE GASTO", utils.to_br_currency(media_rend_r))
    c3.metric("📈 MÉDIA RETORNO (%)", f"{media_rend_p:.2f}%".replace(".", ","))
    c4.metric("🏛️ PATRIMÔNIO ATUAL", utils.to_br_currency(pat_at))
