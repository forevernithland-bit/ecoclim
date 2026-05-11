import streamlit as st
import pandas as pd
import datetime
import utils

def atualizar_df_completo(df_base, df_tela, meses_visiveis):
    df_tela = df_tela[df_tela['MESES'].astype(str).str.strip() != '']
    df_novo = pd.DataFrame({"MESES": df_tela["MESES"]})
    for m in utils.meses_pt:
        if m in meses_visiveis:
            df_novo[m] = pd.to_numeric(df_tela[m], errors='coerce').fillna(0.0)
        else:
            valores_antigos = [df_base[df_base["MESES"] == cat].iloc[0][m] if not df_base[df_base["MESES"] == cat].empty else 0.0 for cat in df_novo["MESES"]]
            df_novo[m] = valores_antigos
    return df_novo

def garantir_linhas(df, lista_contas):
    if df.empty or 'MESES' not in df.columns:
        return pd.DataFrame({"MESES": lista_contas, **{m: 0.0 for m in utils.meses_pt}})
    for c in lista_contas:
        if c not in df['MESES'].values:
            df = pd.concat([df, pd.DataFrame([{"MESES": c, **{m: 0.0 for m in utils.meses_pt}}])], ignore_index=True)
    df['MESES'] = pd.Categorical(df['MESES'], categories=lista_contas, ordered=True)
    return df.sort_values('MESES').reset_index(drop=True)

def renderizar():
    st.markdown("## 🏡 Dashboard AirBnb e Locações")
    
    with st.sidebar:
        st.image("logo.png", width=150)
        ano_selecionado = st.selectbox("Ano de Referência", options=[2025, 2026, 2027, 2028], index=1, key="ano_airnb")
        if st.button("💾 GRAVAR DADOS", type="primary", use_container_width=True):
            st.session_state.salvar_clicado = True

    # --- Lógica do Tempo ---
    hoje = datetime.date.today()
    if ano_selecionado == hoje.year:
        mes_atual_idx = hoje.month - 1
        meses_atuais = [utils.meses_pt[mes_atual_idx - 1], utils.meses_pt[mes_atual_idx]] if mes_atual_idx > 0 else [utils.meses_pt[mes_atual_idx]]
        meses_antigos = utils.meses_pt[:mes_atual_idx - 1] if mes_atual_idx > 0 else []
    else:
        meses_atuais, meses_antigos = [], utils.meses_pt

    # --- Dados ---
    contas_ent = ['AIRNB', 'LOCAÇÕES POR FORA']
    contas_sai = ['LIMPEZA', 'LUZ', 'ÁGUA', 'INTERNET', 'PISCINEIRO', 'PRODUTOS DE LIMPEZA', 'OUTROS']

    if 'ano_airnb_atual' not in st.session_state or st.session_state.ano_airnb_atual != ano_selecionado:
        st.session_state.df_airnb_ent = garantir_linhas(utils.load_year_data('airnb_entradas', contas_ent, ano_selecionado), contas_ent)
        st.session_state.df_airnb_sai = garantir_linhas(utils.load_year_data('airnb_saidas', contas_sai, ano_selecionado), contas_sai)
        st.session_state.ano_airnb_atual = ano_selecionado

    aba_atual, aba_antigos = st.tabs(["📊 Painel Mensal", "🕰️ Histórico"])

    with aba_atual:
        if not meses_atuais:
            st.info("Selecione o ano atual para ver o painel mensal.")
        else:
            # DIVISÃO DA TELA: Tabelas na esquerda, Resultados na direita
            col_dados, col_resumo = st.columns([1.4, 1])

            with col_dados:
                cfg = {"MESES": st.column_config.TextColumn("CATEGORIA", width="medium")}
                for m in meses_atuais: cfg[m] = st.column_config.NumberColumn(m, format="R$ %,.2f")

                # --- ENTRADAS ---
                st.markdown("#### 📥 Entradas")
                df_ent_edit = st.data_editor(st.session_state.df_airnb_ent[['MESES'] + meses_atuais], column_config=cfg, num_rows="fixed", hide_index=True, use_container_width=True, height=115, key="airnb_ent_ed")
                
                for m in meses_atuais:
                    v = pd.to_numeric(df_ent_edit[m], errors='coerce').fillna(0).sum()
                    st.markdown(f"<div style='text-align: right; font-size: 13px; color: #004488;'><b>Total Entrada {m}:</b> {utils.to_br_currency(v)}</div>", unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)

                # --- SAÍDAS ---
                st.markdown("#### 📤 Saídas (Custos)")
                df_sai_edit = st.data_editor(st.session_state.df_airnb_sai[['MESES'] + meses_atuais], column_config=cfg, num_rows="fixed", hide_index=True, use_container_width=True, height=285, key="airnb_sai_ed")
                
                for m in meses_atuais:
                    v = pd.to_numeric(df_sai_edit[m], errors='coerce').fillna(0).sum()
                    st.markdown(f"<div style='text-align: right; font-size: 13px; color: #cc0000;'><b>Custo Total {m}:</b> {utils.to_br_currency(v)}</div>", unsafe_allow_html=True)

            with col_resumo:
                st.markdown("#### 💰 Resultado Líquido")
                for m in meses_atuais:
                    e = pd.to_numeric(df_ent_edit[m], errors='coerce').fillna(0).sum()
                    s = pd.to_numeric(df_sai_edit[m], errors='coerce').fillna(0).sum()
                    liq = e - s
                    breno = liq * 0.5
                    eunice = liq * 0.5
                    cor = "#006600" if liq >= 0 else "#cc0000"
                    bg = "#e6ffe6" if liq >= 0 else "#ffe6e6"

                    st.markdown(f"""
                        <div style="background-color: {bg}; padding: 15px; border-radius: 12px; border: 2px solid {cor}; text-align: center; margin-bottom: 20px;">
                            <h3 style="color: {cor}; margin: 0; font-size: 20px;">{m}</h3>
                            <h1 style="color: {cor}; margin: 10px 0; font-size: 38px;">{utils.to_br_currency(liq)}</h1>
                            <div style="display: flex; justify-content: space-around; border-top: 1px solid {cor}; padding-top: 10px;">
                                <div style="color: {cor}; font-size: 14px;"><b>Breno (50%):</b><br>{utils.to_br_currency(breno)}</div>
                                <div style="color: {cor}; font-size: 14px;"><b>Eunice (50%):</b><br>{utils.to_br_currency(eunice)}</div>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)

            # Lógica de Gravação Automática via botão da sidebar
            if st.session_state.get('salvar_clicado', False):
                st.session_state.df_airnb_ent = atualizar_df_completo(st.session_state.df_airnb_ent, df_ent_edit, meses_atuais)
                st.session_state.df_airnb_sai = atualizar_df_completo(st.session_state.df_airnb_sai, df_sai_edit, meses_atuais)
                utils.save_to_supabase('airnb_entradas', st.session_state.df_airnb_ent, ano_selecionado)
                utils.save_to_supabase('airnb_saidas', st.session_state.df_airnb_sai, ano_selecionado)
                st.session_state.salvar_clicado = False
                st.success("Dados Salvos!")
                st.rerun()

    with aba_antigos:
        if not meses_antigos:
            st.info("Sem histórico.")
        else:
            cfg_a = get_col_config(meses_antigos)
            st.markdown("#### Histórico de Entradas")
            df_ent_a = st.data_editor(st.session_state.df_airnb_ent[['MESES'] + meses_antigos], column_config=cfg_a, use_container_width=True, key="ent_hist")
            st.markdown("#### Histórico de Saídas")
            df_sai_a = st.data_editor(st.session_state.df_airnb_sai[['MESES'] + meses_antigos], column_config=cfg_a, use_container_width=True, key="sai_hist")
            
            if st.button("💾 Gravar Histórico", use_container_width=True):
                st.session_state.df_airnb_ent = atualizar_df_completo(st.session_state.df_airnb_ent, df_ent_a, meses_antigos)
                st.session_state.df_airnb_sai = atualizar_df_completo(st.session_state.df_airnb_sai, df_sai_a, meses_antigos)
                utils.save_to_supabase('airnb_entradas', st.session_state.df_airnb_ent, ano_selecionado)
                utils.save_to_supabase('airnb_saidas', st.session_state.df_airnb_sai, ano_selecionado)
                st.success("Histórico Salvo!")
                st.rerun()

def get_col_config(meses):
    cfg = {"MESES": st.column_config.TextColumn("CATEGORIA", width="medium")}
    for m in meses: cfg[m] = st.column_config.NumberColumn(m, format="R$ %,.2f")
    return cfg
