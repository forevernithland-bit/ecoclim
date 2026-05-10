import streamlit as st
import pandas as pd
import datetime
import utils

def atualizar_df_completo(df_base, df_tela, meses_visiveis):
    """Função inteligente para garantir que se vc adicionar uma linha, ela exista em todos os meses"""
    df_tela = df_tela[df_tela['MESES'].astype(str).str.strip() != ''] # Remove linhas em branco
    df_novo = pd.DataFrame({"MESES": df_tela["MESES"]})
    
    for m in utils.meses_pt:
        if m in meses_visiveis:
            df_novo[m] = pd.to_numeric(df_tela[m], errors='coerce').fillna(0.0)
        else:
            valores_antigos = []
            for _, row in df_novo.iterrows():
                categoria = row["MESES"]
                match = df_base[df_base["MESES"] == categoria]
                if not match.empty:
                    valores_antigos.append(match.iloc[0][m])
                else:
                    valores_antigos.append(0.0)
            df_novo[m] = valores_antigos
    return df_novo

def renderizar():
    st.markdown("## 🏡 AirBnb e Locações")
    
    # Adicionando o seletor de Ano na barra lateral para blindar contra viradas de ano
    with st.sidebar:
        st.image("logo.png", width=150)
        ano_selecionado = st.selectbox("Ano de Referência", options=[2025, 2026, 2027, 2028], index=1, key="ano_airnb")

    # --- Lógica do Tempo Dinâmica ---
    hoje = datetime.date.today()
    
    # Se estiver olhando o ano atual, separa entre mês atual/anterior e antigos
    if ano_selecionado == hoje.year:
        mes_atual_idx = hoje.month - 1
        mes_atual_nome = utils.meses_pt[mes_atual_idx]
        
        if mes_atual_idx > 0:
            mes_anterior_nome = utils.meses_pt[mes_atual_idx - 1]
            meses_atuais = [mes_anterior_nome, mes_atual_nome]
            meses_antigos = utils.meses_pt[:mes_atual_idx - 1]
        else: # É Janeiro! Não existe mês anterior no mesmo ano.
            meses_atuais = [mes_atual_nome]
            meses_antigos = []
    else:
        # Se você selecionar um ano passado (ex: 2026 estando em 2027), 
        # todos os meses vão para o histórico!
        meses_atuais = []
        meses_antigos = utils.meses_pt

    # --- Carregar Dados do Supabase com base no ano ---
    if 'ano_airnb_atual' not in st.session_state or st.session_state.ano_airnb_atual != ano_selecionado:
        st.session_state.df_airnb_ent = utils.load_year_data('airnb_entradas', ['AIRNB', 'LOCAÇÕES POR FORA'], ano_selecionado)
        st.session_state.df_airnb_sai = utils.load_year_data('airnb_saidas', ['LIMPEZA', 'LUZ', 'ÁGUA', 'INTERNET', 'OUTROS'], ano_selecionado)
        st.session_state.ano_airnb_atual = ano_selecionado

    def get_col_config(meses_visiveis):
        cfg = {"MESES": st.column_config.TextColumn("CATEGORIA", width="medium")}
        for m in meses_visiveis: cfg[m] = st.column_config.NumberColumn(m, format="R$ %,.2f", min_value=0.0)
        return cfg

    # --- Construção da Interface ---
    aba_atual, aba_antigos = st.tabs(["🟢 Mês Atual & Anterior", "🕰️ Histórico do Ano"])

    with aba_atual:
        if not meses_atuais:
            st.info(f"Você está visualizando o ano de {ano_selecionado}. Como já passou, todos os meses estão disponíveis na aba 'Histórico do Ano'.")
        else:
            st.caption(f"Foco total! Você está gerenciando: **{' e '.join(meses_atuais)} de {ano_selecionado}**.")
            
            cols_ent = ['MESES'] + meses_atuais
            cfg_atual = get_col_config(meses_atuais)

            c1, c2 = st.columns(2)
            with c1:
                st.markdown("#### ⬆️ Entradas")
                df_ent_edit = st.data_editor(st.session_state.df_airnb_ent[cols_ent], column_config=cfg_atual, num_rows="dynamic", use_container_width=True, key="airnb_ent_atual")
            with c2:
                st.markdown("#### ⬇️ Saídas (Custos)")
                df_sai_edit = st.data_editor(st.session_state.df_airnb_sai[cols_ent], column_config=cfg_atual, num_rows="dynamic", use_container_width=True, key="airnb_sai_atual")

            st.markdown("### 💰 Resultado Líquido")
            cols_res = st.columns(len(meses_atuais))
            for i, m in enumerate(meses_atuais):
                ent_tot = pd.to_numeric(df_ent_edit[m], errors='coerce').fillna(0).sum()
                sai_tot = pd.to_numeric(df_sai_edit[m], errors='coerce').fillna(0).sum()
                liq = ent_tot - sai_tot
                
                # Cores dinâmicas: verde se lucrou, vermelho se deu prejuízo
                bg_color = "#e6ffe6" if liq >= 0 else "#ffe6e6"
                txt_color = "#006600" if liq >= 0 else "#cc0000"
                
                cols_res[i].markdown(
                    f"""
                    <div style="background-color: {bg_color}; padding: 15px; border-radius: 10px; border: 1px solid {txt_color}; text-align: center;">
                        <h4 style="color: {txt_color}; margin: 0;">{m}</h4>
                        <h2 style="color: {txt_color}; margin: 0;">{utils.to_br_currency(liq)}</h2>
                    </div>
                    """, unsafe_allow_html=True
                )

            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("💾 SALVAR ALTERAÇÕES (MÊS ATUAL)", type="primary", use_container_width=True):
                st.session_state.df_airnb_ent = atualizar_df_completo(st.session_state.df_airnb_ent, df_ent_edit, meses_atuais)
                st.session_state.df_airnb_sai = atualizar_df_completo(st.session_state.df_airnb_sai, df_sai_edit, meses_atuais)
                utils.save_to_supabase('airnb_entradas', st.session_state.df_airnb_ent, ano_selecionado)
                utils.save_to_supabase('airnb_saidas', st.session_state.df_airnb_sai, ano_selecionado)
                st.success("✅ Dados atualizados com sucesso!")
                st.rerun()

    with aba_antigos:
        if not meses_antigos:
            st.info("Não há histórico de meses anteriores neste ano ainda.")
        else:
            st.caption(f"Histórico: **{', '.join(meses_antigos)}** de {ano_selecionado}.")
            cols_ant = ['MESES'] + meses_antigos
            cfg_ant = get_col_config(meses_antigos)

            st.markdown("#### ⬆️ Entradas Históricas")
            df_ent_ant = st.data_editor(st.session_state.df_airnb_ent[cols_ant], column_config=cfg_ant, num_rows="dynamic", use_container_width=True, key="airnb_ent_ant")
            
            st.markdown("#### ⬇️ Saídas Históricas")
            df_sai_ant = st.data_editor(st.session_state.df_airnb_sai[cols_ant], column_config=cfg_ant, num_rows="dynamic", use_container_width=True, key="airnb_sai_ant")

            st.markdown("### 📊 Histórico de Lucros")
            cols_res_ant = st.columns(len(meses_antigos))
            for i, m in enumerate(meses_antigos):
                ent_tot_a = pd.to_numeric(df_ent_ant[m], errors='coerce').fillna(0).sum()
                sai_tot_a = pd.to_numeric(df_sai_ant[m], errors='coerce').fillna(0).sum()
                liq_a = ent_tot_a - sai_tot_a
                cor_a = "green" if liq_a >= 0 else "red"
                cols_res_ant[i].markdown(f"**{m}**: <br><span style='color:{cor_a}'>{utils.to_br_currency(liq_a)}</span>", unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("💾 SALVAR HISTÓRICO", type="secondary", use_container_width=True):
                st.session_state.df_airnb_ent = atualizar_df_completo(st.session_state.df_airnb_ent, df_ent_ant, meses_antigos)
                st.session_state.df_airnb_sai = atualizar_df_completo(st.session_state.df_airnb_sai, df_sai_ant, meses_antigos)
                utils.save_to_supabase('airnb_entradas', st.session_state.df_airnb_ent, ano_selecionado)
                utils.save_to_supabase('airnb_saidas', st.session_state.df_airnb_sai, ano_selecionado)
                st.success("✅ Histórico antigo salvo!")
                st.rerun()
