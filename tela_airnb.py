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
    # CSS para comprimir layout e remover espaços inúteis
    st.markdown("""
        <style>
            .stTabs [data-baseweb="tab-list"] { gap: 8px; }
            .stTabs [data-baseweb="tab"] { height: 40px; padding-top: 10px; }
            div[data-testid="stVerticalBlock"] { gap: 0.5rem !important; }
            .main .block-container { padding-top: 1rem !important; }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("### 🏡 Gestão AirBnb / Locações")
    
    with st.sidebar:
        # Logo removida daqui, pois o app.py já cuida disso!
        ano_selecionado = st.selectbox("Ano", options=[2025, 2026, 2027, 2028], index=1, key="ano_airnb")
        st.markdown("---")
        if st.button("💾 SALVAR TUDO AGORA", type="primary", use_container_width=True):
            st.session_state.salvar_clicado = True

    # --- Lógica de Tempo ---
    hoje = datetime.date.today()
    if ano_selecionado == hoje.year:
        mes_atual_idx = hoje.month - 1
        meses_atuais = [utils.meses_pt[mes_atual_idx - 1], utils.meses_pt[mes_atual_idx]] if mes_atual_idx > 0 else [utils.meses_pt[mes_atual_idx]]
    else:
        meses_atuais = []

    # --- Carga de Dados ---
    contas_ent = ['AIRNB', 'LOCAÇÕES POR FORA']
    contas_sai = ['LIMPEZA', 'LUZ', 'ÁGUA', 'INTERNET', 'PISCINEIRO', 'PRODUTOS DE LIMPEZA', 'OUTROS']

    if 'ano_airnb_atual' not in st.session_state or st.session_state.ano_airnb_atual != ano_selecionado:
        st.session_state.df_airnb_ent = garantir_linhas(utils.load_year_data('airnb_entradas', contas_ent, ano_selecionado), contas_ent)
        st.session_state.df_airnb_sai = garantir_linhas(utils.load_year_data('airnb_saidas', contas_sai, ano_selecionado), contas_sai)
        st.session_state.ano_airnb_atual = ano_selecionado

    aba_p, aba_h = st.tabs(["📊 Painel Mensal", "🕰️ Histórico"])

    with aba_p:
        if not meses_atuais:
            st.info("Selecione o ano atual para o painel.")
        else:
            col_dados, col_res = st.columns([1.5, 1])

            with col_dados:
                cfg = {"MESES": st.column_config.TextColumn("CATEGORIA", width="small")}
                for m in meses_atuais: cfg[m] = st.column_config.NumberColumn(m, format="R$ %.2f")

                st.write("**📥 Entradas**")
                df_ent_ed = st.data_editor(st.session_state.df_airnb_ent[['MESES'] + meses_atuais], column_config=cfg, hide_index=True, use_container_width=True, height=120, key="airnb_ent_ed_tela")
                
                # Totais de Entrada formatados abaixo da tabela
                st.markdown("<div style='margin-top: -10px; margin-bottom: 15px;'>", unsafe_allow_html=True)
                for m in meses_atuais:
                    e_tot = pd.to_numeric(df_ent_ed[m], errors='coerce').fillna(0).sum()
                    st.markdown(f"<div style='text-align: right; font-size: 13px; color: #004488;'><b>Total Entrada {m}:</b> {utils.to_br_currency(e_tot)}</div>", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

                st.write("**📤 Saídas (Custos)**")
                df_sai_ed = st.data_editor(st.session_state.df_airnb_sai[['MESES'] + meses_atuais], column_config=cfg, hide_index=True, use_container_width=True, height=290, key="airnb_sai_ed_tela")
                
                # Totais de Custos formatados abaixo da tabela
                st.markdown("<div style='margin-top: -10px; margin-bottom: 5px;'>", unsafe_allow_html=True)
                for m in meses_atuais:
                    s_tot = pd.to_numeric(df_sai_ed[m], errors='coerce').fillna(0).sum()
                    st.markdown(f"<div style='text-align: right; font-size: 13px; color: #cc0000;'><b>Custo Total {m}:</b> {utils.to_br_currency(s_tot)}</div>", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

            with col_res:
                st.write("**💰 Resultado Líquido**")
                for m in meses_atuais:
                    e_tot = pd.to_numeric(df_ent_ed[m], errors='coerce').fillna(0).sum()
                    s_tot = pd.to_numeric(df_sai_ed[m], errors='coerce').fillna(0).sum()
                    liq = e_tot - s_tot
                    cor = "#006600" if liq >= 0 else "#cc0000"
                    bg = "#e6ffe6" if liq >= 0 else "#ffe6e6"

                    st.markdown(f"""
                        <div style="background-color: {bg}; padding: 15px; border-radius: 8px; border: 1px solid {cor}; text-align: center; margin-bottom: 25px;">
                            <p style="color: {cor}; margin: 0; font-size: 16px; font-weight: bold;">{m}</p>
                            <h2 style="color: {cor}; margin: 5px 0; font-size: 32px;">{utils.to_br_currency(liq)}</h2>
                            <div style="display: flex; justify-content: space-between; border-top: 1px solid {cor}; padding-top: 10px; font-size: 15px; color: {cor}; font-weight: bold;">
                                <span>Breno (50%):<br>{utils.to_br_currency(liq*0.5)}</span>
                                <span>Eunice (50%):<br>{utils.to_br_currency(liq*0.5)}</span>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                
                if st.button("💾 GRAVAR ALTERAÇÕES", type="primary", use_container_width=True, key="btn_salvar_corpo"):
                    st.session_state.salvar_clicado = True

            # Processamento real do clique de salvar
            if st.session_state.get('salvar_clicado', False):
                st.session_state.df_airnb_ent = atualizar_df_completo(st.session_state.df_airnb_ent, df_ent_ed, meses_atuais)
                st.session_state.df_airnb_sai = atualizar_df_completo(st.session_state.df_airnb_sai, df_sai_ed, meses_atuais)
                utils.save_to_supabase('airnb_entradas', st.session_state.df_airnb_ent, ano_selecionado)
                utils.save_to_supabase('airnb_saidas', st.session_state.df_airnb_sai, ano_selecionado)
                st.session_state.salvar_clicado = False
                st.success("✅ Alterações salvas com sucesso!")
                st.rerun()

    with aba_h:
        st.markdown("#### Histórico do Ano")
        st.dataframe(st.session_state.df_airnb_ent, use_container_width=True, hide_index=True)
        st.dataframe(st.session_state.df_airnb_sai, use_container_width=True, hide_index=True)
