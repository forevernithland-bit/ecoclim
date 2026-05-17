import streamlit as st
import pandas as pd
import numpy as np
import io
import utils

# =============================================================================
# MOTORES DE BANCO DE DADOS BLINDADOS (ESPECÍFICOS POR ANO)
# =============================================================================
def carregar_dados_fin(nome_tabela, lista_contas, ano):
    supabase = st.session_state.supabase
    try:
        res = supabase.table(nome_tabela).select("*").eq("ano", ano).execute()
        df_banco = pd.DataFrame(res.data)
        if df_banco.empty:
            df_novo = pd.DataFrame({"MESES": lista_contas})
            for mes in utils.meses_pt: df_novo[mes] = 0.0
            return df_novo
        
        mapeamento = {"meses": "MESES", "marco": "MARÇO"}
        for m in utils.meses_pt:
            if m != "MARÇO": mapeamento[m.lower()] = m
        
        df_banco = df_banco.rename(columns=mapeamento)
        
        colunas_ordenadas = ["MESES"] + utils.meses_pt
        for col in colunas_ordenadas:
            if col not in df_banco.columns: df_banco[col] = 0.0 if col != "MESES" else ""
        
        df_banco = df_banco[df_banco['MESES'].isin(lista_contas)]
        df_banco['MESES'] = pd.Categorical(df_banco['MESES'], categories=lista_contas, ordered=True)
        return df_banco.sort_values('MESES')[colunas_ordenadas].reset_index(drop=True)
    except Exception as e:
        return pd.DataFrame({"MESES": lista_contas, **{m: 0.0 for m in utils.meses_pt}})

def salvar_dados_fin(nome_tabela, df, ano):
    supabase = st.session_state.supabase
    dados_finais = []
    for _, linha in df.iterrows():
        registro = {
            "ano": ano,
            "meses": linha["MESES"],
            "janeiro": float(linha["JANEIRO"]),
            "fevereiro": float(linha["FEVEREIRO"]),
            "marco": float(linha["MARÇO"]),
            "abril": float(linha["ABRIL"]),
            "maio": float(linha["MAIO"]),
            "junho": float(linha["JUNHO"]),
            "julho": float(linha["JULHO"]),
            "agosto": float(linha["AGOSTO"]),
            "setembro": float(linha["SETEMBRO"]),
            "outubro": float(linha["OUTUBRO"]),
            "novembro": float(linha["NOVEMBRO"]),
            "dezembro": float(linha["DEZEMBRO"])
        }
        dados_finais.append(registro)
    try:
        supabase.table(nome_tabela).delete().eq("ano", ano).execute()
        supabase.table(nome_tabela).insert(dados_finais).execute()
    except Exception as e:
        st.error(f"Erro ao salvar tabela {nome_tabela}: {e}")

def carregar_periodo_visivel():
    if 'periodo_visivel_financeiro' in st.session_state:
        return st.session_state.periodo_visivel_financeiro
    try:
        res = st.session_state.supabase.table('fin_configuracoes').select('*').eq('chave', 'periodo_visivel').execute()
        if res.data:
            return (res.data[0].get('valor1', 'JANEIRO'), res.data[0].get('valor2', 'DEZEMBRO'))
    except: pass
    return ("JANEIRO", "DEZEMBRO")

def salvar_periodo_visivel(m_ini, m_fim):
    st.session_state.periodo_visivel_financeiro = (m_ini, m_fim)
    try:
        st.session_state.supabase.table('fin_configuracoes').delete().eq('chave', 'periodo_visivel').execute()
        st.session_state.supabase.table('fin_configuracoes').insert({
            'chave': 'periodo_visivel', 'valor1': m_ini, 'valor2': m_fim
        }).execute()
    except: pass

def limpar_e_garantir_linhas(df, lista_contas):
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

# =============================================================================
# MOTORES DE EXPORTAÇÃO E IMPORTAÇÃO GLOBAL (COM ESTEIRA DE LIMPEZA ANTI-NAN)
# =============================================================================
def exportar_base_completa_excel():
    supabase = st.session_state.supabase
    try:
        res_p = supabase.table('fin_patrimonio').select("*").order("ano", desc=False).execute()
        res_e = supabase.table('fin_entradas').select("*").order("ano", desc=False).execute()
        
        df_p_raw = pd.DataFrame(res_p.data)
        df_e_raw = pd.DataFrame(res_e.data)
        
        mapeamento = {"ano": "ANO", "meses": "MESES", "marco": "MARÇO"}
        for m in utils.meses_pt:
            if m != "MARÇO": mapeamento[m.lower()] = m
            
        colunas_finais = ["ANO", "MESES"] + utils.meses_pt
        
        if not df_p_raw.empty:
            df_p_raw = df_p_raw.rename(columns=mapeamento)
            df_p_final = df_p_raw[[c for c in colunas_finais if c in df_p_raw.columns]]
        else:
            df_p_final = pd.DataFrame(columns=colunas_finais)
            
        if not df_e_raw.empty:
            df_e_raw = df_e_raw.rename(columns=mapeamento)
            df_e_final = df_e_raw[[c for c in colunas_finais if c in df_e_raw.columns]]
        else:
            df_e_final = pd.DataFrame(columns=colunas_finais)
            
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_p_final.to_excel(writer, sheet_name='PATRIMONIO', index=False)
            df_e_final.to_excel(writer, sheet_name='RECEBIMENTOS', index=False)
        return output.getvalue()
    except Exception as e:
        st.error(f"Erro ao gerar exportação global: {e}")
        return None

def importar_base_completa_excel(file_buffer):
    supabase = st.session_state.supabase
    try:
        xls = pd.ExcelFile(file_buffer)
        if 'PATRIMONIO' not in xls.sheet_names or 'RECEBIMENTOS' not in xls.sheet_names:
            st.error("Arquivo inválido! O Excel precisa conter as abas 'PATRIMONIO' e 'RECEBIMENTOS'.")
            return False
            
        df_p_xls = pd.read_excel(xls, 'PATRIMONIO')
        df_e_xls = pd.read_excel(xls, 'RECEBIMENTOS')
        
        def processar_aba(df, nome_tabela_banco):
            df.columns = df.columns.str.strip().str.upper()
            
            # 1. Esteira de Limpeza: Remove linhas fantasmas do Excel
            if 'ANO' not in df.columns or 'MESES' not in df.columns: return
            df = df.dropna(subset=['ANO', 'MESES'])
            
            # 2. Esteira de Limpeza: Força colunas de meses a virarem números (Texto e Vazios viram 0.0)
            for col in utils.meses_pt:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
                else:
                    df[col] = 0.0
                    
            dados_finais = []
            anos_presentes = set()
            
            for _, linha in df.iterrows():
                try:
                    ano_linha = int(linha["ANO"])
                except: continue # Se o ano for inválido, pula a linha
                
                anos_presentes.add(ano_linha)
                
                # Agora temos 100% de certeza que os dados são Floats limpos
                registro = {
                    "ano": ano_linha,
                    "meses": str(linha["MESES"]).strip(),
                    "janeiro": float(linha["JANEIRO"]),
                    "fevereiro": float(linha["FEVEREIRO"]),
                    "marco": float(linha["MARÇO"]),
                    "abril": float(linha["ABRIL"]),
                    "maio": float(linha["MAIO"]),
                    "junho": float(linha["JUNHO"]),
                    "julho": float(linha["JULHO"]),
                    "agosto": float(linha["AGOSTO"]),
                    "setembro": float(linha["SETEMBRO"]),
                    "outubro": float(linha["OUTUBRO"]),
                    "novembro": float(linha["NOVEMBRO"]),
                    "dezembro": float(linha["DEZEMBRO"])
                }
                dados_finais.append(registro)
                
            # Limpa do banco apenas os anos que vieram no arquivo para evitar duplicidade
            for a in anos_presentes:
                supabase.table(nome_tabela_banco).delete().eq("ano", a).execute()
                
            if dados_finais:
                supabase.table(nome_tabela_banco).insert(dados_finais).execute()
                
        processar_aba(df_p_xls, 'fin_patrimonio')
        processar_aba(df_e_xls, 'fin_entradas')
        return True
    except Exception as e:
        st.error(f"Erro crítico durante a importação do Excel: {e}")
        return False

# =============================================================================
# RENDERIZAÇÃO PRINCIPAL DA TELA
# =============================================================================
def renderizar():
    st.markdown('<div class="financeiro">', unsafe_allow_html=True)
    
    if "salvar_fin_clicado" not in st.session_state:
        st.session_state.salvar_fin_clicado = False
        
    with st.sidebar:
        ano_selecionado = st.selectbox("Ano Fiscal", options=[2025, 2026, 2027, 2028], index=1)
        
        st.write("---")
        if st.button("💾 SALVAR DADOS AGORA", type="primary", use_container_width=True, key="btn_salvar_lateral"):
            st.session_state.salvar_fin_clicado = True
        st.write("---")
        
        st.markdown("### 👁️ Linha do Tempo")
        
        pref_ini, pref_fim = carregar_periodo_visivel()
        m_ini, m_fim = st.select_slider("Período Visível:", options=utils.meses_pt, value=(pref_ini, pref_fim))
        
        if (m_ini, m_fim) != (pref_ini, pref_fim):
            salvar_periodo_visivel(m_ini, m_fim)
            st.rerun()
            
        colunas_visiveis = ["MESES"] + utils.meses_pt[utils.meses_pt.index(m_ini):utils.meses_pt.index(m_fim) + 1]

        if st.button("🔄 Recarregar Banco", use_container_width=True): 
            st.session_state.pop('ano_dados_atual', None)
            st.session_state.pop('db_df_p', None)
            st.session_state.pop('db_df_e', None)
            st.rerun()

    contas_p = ['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS', 'IMÓVEIS', 'VEÍCULOS']
    contas_e = ['ECOCLIM', 'AIRNB', 'CONS INVESTIMENTOS', 'MAGGI CONSORCIOS']
    
    if ('db_df_p' not in st.session_state or 
        'db_df_e' not in st.session_state or 
        'ano_dados_atual' not in st.session_state or 
        st.session_state.ano_dados_atual != ano_selecionado or 
        st.session_state.get('forcar_reload_fin', False)):
        
        st.session_state.db_df_p = limpar_e_garantir_linhas(carregar_dados_fin('fin_patrimonio', contas_p, ano_selecionado), contas_p)
        st.session_state.db_df_e = limpar_e_garantir_linhas(carregar_dados_fin('fin_entradas', contas_e, ano_selecionado), contas_e)
        st.session_state.ano_dados_atual = ano_selecionado
        st.session_state.forcar_reload_fin = False

    # --- HERANÇA DE DEZEMBRO (ANO ANTERIOR) ---
    df_p_prev = carregar_dados_fin('fin_patrimonio', contas_p, ano_selecionado - 1).set_index('MESES')
    pat_liq_prev_dec = df_p_prev.loc[df_p_prev.index.isin(['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS']), 'DEZEMBRO'].sum()
    pat_tot_prev_dec = pat_liq_prev_dec + df_p_prev.loc[df_p_prev.index.isin(['IMÓVEIS', 'VEÍCULOS']), 'DEZEMBRO'].sum()
    xp_prev_dec = df_p_prev.loc['INVESTIMENTO XP', 'DEZEMBRO'] if 'INVESTIMENTO XP' in df_p_prev.index else 0
    inter_prev_dec = df_p_prev.loc['CONTA INTER', 'DEZEMBRO'] if 'CONTA INTER' in df_p_prev.index else 0

    cfg_edit = {"MESES": st.column_config.TextColumn("CONTA", width=220, disabled=True)}
    cfg_text = {"MESES": st.column_config.TextColumn("CONTA", width=220, disabled=True)}
    for m in utils.meses_pt: 
        cfg_edit[m] = st.column_config.NumberColumn(m, width=100, format="R$ %,.2f")
        cfg_text[m] = st.column_config.TextColumn(m, width=100)

    st.markdown('<div class="container-tabelas">', unsafe_allow_html=True)
    
    # =============================================================================
    # ALINHAMENTO SUPERIOR DOS BOTÕES DE IMPORTAÇÃO/EXPORTAÇÃO GLOBAL 
    # =============================================================================
    c_titulo, c_exp, c_imp = st.columns([1.6, 1.1, 1.3])
    
    with c_titulo:
        st.markdown(f"<h4>🏛️ Patrimônio e Investimentos ({ano_selecionado})</h4>", unsafe_allow_html=True)
        
    with c_exp:
        arquivo_completo_excel = exportar_base_completa_excel()
        if arquivo_completo_excel:
            st.download_button(
                label="📤 EXPORTAR TODA BASE (EXCEL)",
                data=arquivo_completo_excel,
                file_name="ERP_ECOCLIM_FINANCEIRO_TOTAL.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="btn_exportar_total_global"
            )
            
    with c_imp:
        excel_subido_global = st.file_uploader("Importar base completa", type=["xlsx"], label_visibility="collapsed", key="file_uploader_global_fin")
        if excel_subido_global is not None:
            if st.button("🚀 CONFIRMAR IMPORTAÇÃO TOTAL", use_container_width=True, type="secondary", key="btn_executar_importacao_global"):
                with st.spinner("Substituindo dados históricos no Supabase..."):
                    if importar_base_completa_excel(excel_subido_global):
                        st.success("✅ Toda a base histórica do Excel foi gravada com sucesso!")
                        st.session_state.forcar_reload_fin = True
                        st.rerun()

    df_p_ed = st.data_editor(
        st.session_state.db_df_p[colunas_visiveis], 
        hide_index=True, 
        column_config=cfg_edit, 
        use_container_width=True, 
        height=285, 
        key=f"ed_p_fin_estavel_v9_{ano_selecionado}"
    )

    df_p_trabalho = st.session_state.db_df_p.copy()
    for c in colunas_visiveis: 
        if c != "MESES": df_p_trabalho[c] = df_p_ed[c]

    df_n = df_p_trabalho.set_index('MESES')
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
    st.markdown(f"#### 💰 Recebimentos e Pró-labore ({ano_selecionado})")
    df_e_ed = st.data_editor(
        st.session_state.db_df_e[colunas_visiveis], 
        hide_index=True, 
        column_config=cfg_edit, 
        use_container_width=True, 
        height=190, 
        key=f"ed_e_fin_estavel_v9_{ano_selecionado}"
    )
    
    df_e_trabalho = st.session_state.db_df_e.copy()
    for c in colunas_visiveis: 
        if c != "MESES": df_e_trabalho[c] = df_e_ed[c]

    tot_e = df_e_trabalho.set_index('MESES').sum()
    dict_res_e = {'MESES': ['TOTAL RECEBIMENTOS']}
    for i, m in enumerate(utils.meses_pt):
        is_futuro = (ano_selecionado > utils.ano_atual) or (ano_selecionado == utils.ano_atual and i > (utils.mes_hoje_idx - 1))
        dict_res_e[m] = [utils.to_br_currency(0 if is_futuro else tot_e[m])]
        
    st.dataframe(pd.DataFrame(dict_res_e)[colunas_visiveis].style.set_properties(**{'background-color': '#9BC2E6', 'color': 'black', 'font-weight': 'bold'}), hide_index=True, column_config=cfg_text, use_container_width=True)

    st.markdown("---")
    
    # --- BOTÃO DE SALVAMENTO MANUAL ---
    col_espaco, col_btn = st.columns([3, 1])
    if col_btn.button("💾 GRAVAR ALTERAÇÕES", type="primary", use_container_width=True, key="btn_gravar_rodape"):
        st.session_state.salvar_fin_clicado = True

    if st.session_state.salvar_fin_clicado:
        with st.spinner("Gravando e consolidando dados no Supabase..."):
            st.session_state.db_df_p = df_p_trabalho
            st.session_state.db_df_e = df_e_trabalho
            salvar_dados_fin('fin_patrimonio', st.session_state.db_df_p, ano_selecionado)
            salvar_dados_fin('fin_entradas', st.session_state.db_df_e, ano_selecionado)
        st.session_state.salvar_fin_clicado = False
        st.success("✅ Alterações fiscais gravadas com sucesso!")

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
    
    xp_var_full = xp_v - xp_v.shift(1).fillna(xp_prev_dec)
    it_var_full = it_v - it_v.shift(1).fillna(inter_prev_dec)
    rend_tot_full = xp_var_full + it_var_full
    media_rend_r = rend_tot_full[meses_calc].mean()
    
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
        st.line_chart(df_e_trabalho.set_index('MESES').loc['ECOCLIM', utils.meses_pt])
