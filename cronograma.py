import streamlit as st
import pandas as pd
import datetime
import utils

@st.dialog("📅 Cronograma de Instalações", width="large")
def modal_cronograma(df_servicos, lista_instaladores):
    st.markdown("<h4 style='color: #004488; margin-top: 0;'>Organize a agenda da equipe técnica</h4>", unsafe_allow_html=True)
    st.caption("As alterações feitas aqui **NÃO** afetam os dados financeiros oficiais do painel principal.")
    
    # Filtros dentro de um container com borda para um design mais limpo
    with st.container(border=True):
        c1, c2 = st.columns([1, 1.5])
        filtro_inst = c1.selectbox("👷 Filtro por Instalador", ["TODOS"] + lista_instaladores)
        filtro_tempo = c2.radio("🗓️ Visão de Tempo", ["Todas as Datas", "Esta Semana", "Este Mês"], horizontal=True)
    
    # Filtra rigorosamente apenas o que está "Em Andamento"
    df_cron = df_servicos[df_servicos['status_projeto'] == 'Em Andamento'].copy()
    
    if df_cron.empty:
        st.info("🎉 Nenhum serviço com status 'Em Andamento' no momento.")
        return
        
    # ====================================================================
    # MOTORES DA CAMADA DE SOMBRA (Leitura dos dados editados do cronograma)
    # ====================================================================
    def get_crono_equipamentos(row):
        d_ct = row.get('dados_contrato')
        # 1. Tenta ler o resumo digitado pelo usuário na tela do cronograma
        if isinstance(d_ct, dict) and 'crono_equipamentos' in d_ct and d_ct['crono_equipamentos']:
            return str(d_ct['crono_equipamentos'])
            
        # 2. Se não houver resumo salvo, puxa os dados oficiais do banco de dados 
        itens = row.get('detalhamento_itens')
        if not isinstance(itens, list): return ""
        arr = []
        for it in itens:
            qtd = float(it.get('Qtd', 0))
            nome = it.get('Item', '')
            if qtd > 0 and nome:
                arr.append(f"{int(qtd)}x {nome}")
        return " + ".join(arr)

    def get_crono_date(row):
        d_ct = row.get('dados_contrato')
        if isinstance(d_ct, dict) and 'crono_data' in d_ct and d_ct['crono_data']:
            try: return pd.to_datetime(d_ct['crono_data']).date()
            except: pass
        val = row.get('data_conclusao')
        if pd.notna(val):
            try: return pd.to_datetime(val).date()
            except: pass
        return pd.NaT

    def get_crono_valor(row):
        d_ct = row.get('dados_contrato')
        if isinstance(d_ct, dict) and 'crono_valor' in d_ct:
            try: return float(d_ct['crono_valor'])
            except: pass
        val = row.get('custo_terceirizados')
        if pd.notna(val):
            try: return float(val)
            except: pass
        return 0.0

    # Aplicação das funções
    df_cron['Equipamentos'] = df_cron.apply(get_crono_equipamentos, axis=1)
    df_cron['Data Agendada'] = df_cron.apply(get_crono_date, axis=1)
    df_cron['Valor Instalação'] = df_cron.apply(get_crono_valor, axis=1)
    
    # Aplicação dos filtros do usuário
    if filtro_inst != "TODOS":
        df_cron = df_cron[df_cron['instalador'] == filtro_inst]
        
    hoje = datetime.date.today()
    if filtro_tempo == "Esta Semana":
        start_w = hoje - datetime.timedelta(days=hoje.weekday())
        end_w = start_w + datetime.timedelta(days=6)
        df_cron = df_cron[(df_cron['Data Agendada'] >= start_w) & (df_cron['Data Agendada'] <= end_w)]
    elif filtro_tempo == "Este Mês":
        df_cron = df_cron[pd.to_datetime(df_cron['Data Agendada']).dt.month == hoje.month]
        
    cols_mostrar = ['id', 'instalador', 'nome_cliente', 'Equipamentos', 'Valor Instalação', 'Data Agendada']
    df_edit = df_cron[cols_mostrar].sort_values('Data Agendada', na_position='last')
    
    if df_edit.empty:
        st.warning("Nenhum agendamento encontrado para os filtros selecionados.")
        return

    # ====================================================================
    # SISTEMA DE ABAS (Edição vs Print/WhatsApp)
    # ====================================================================
    aba_edit, aba_zap = st.tabs(["✏️ 1. Editar Cronograma", "📲 2. Enviar para WhatsApp"])

    with aba_edit:
        st.caption("Ajuste as datas, valores e resuma o texto dos equipamentos livremente para facilitar a leitura da equipe.")
        
        cfg_colunas = {
            "id": None, 
            "instalador": st.column_config.SelectboxColumn("Instalador", options=lista_instaladores, width="medium"),
            "nome_cliente": st.column_config.TextColumn("Cliente", disabled=True, width="medium"),
            "Equipamentos": st.column_config.TextColumn("Equipamentos", disabled=False, width="large"),
            "Valor Instalação": st.column_config.NumberColumn("Valor Inst.", format="R$ %.2f", disabled=False, width="small"),
            "Data Agendada": st.column_config.DateColumn("Data Instalação", format="DD/MM/YYYY", disabled=False, width="medium")
        }
        
        df_final = st.data_editor(
            df_edit,
            column_config=cfg_colunas,
            use_container_width=True,
            hide_index=True,
            key="ed_cronograma_equipe"
        )
        
        total_remuneracao = df_final['Valor Instalação'].sum()
        
        st.markdown(f"""
            <div style='background-color: #f0fdf4; border: 1px solid #16a34a; border-radius: 8px; padding: 15px; margin-top: 15px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center;'>
                <span style='color: #16a34a; font-size: 16px; font-weight: 500;'>Resumo Financeiro ({filtro_tempo})</span>
                <span style='color: #166534; font-size: 18px; font-weight: 700;'>Total Instalações: {utils.to_br_currency(total_remuneracao)}</span>
            </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("💾 Gravar Novo Cronograma", type="primary", use_container_width=True):
                with st.spinner("Salvando planejamento..."):
                    for idx, row in df_final.iterrows():
                        id_bd = row['id']
                        row_orig = df_edit[df_edit['id'] == id_bd].iloc[0]
                        
                        full_orig = df_cron[df_cron['id'] == id_bd].iloc[0]
                        d_ct = full_orig.get('dados_contrato')
                        if not isinstance(d_ct, dict): d_ct = {}
                        
                        payload = {}
                        updated = False
                        
                        if row['instalador'] != row_orig['instalador']:
                            payload['instalador'] = str(row['instalador']) if pd.notna(row['instalador']) else ""
                            updated = True
                            
                        if row['Data Agendada'] != row_orig['Data Agendada']:
                            d_ct['crono_data'] = row['Data Agendada'].strftime('%Y-%m-%d') if pd.notna(row['Data Agendada']) else None
                            updated = True
                            
                        if row['Valor Instalação'] != row_orig['Valor Instalação']:
                            d_ct['crono_valor'] = float(row['Valor Instalação']) if pd.notna(row['Valor Instalação']) else 0.0
                            updated = True
                            
                        if row['Equipamentos'] != row_orig['Equipamentos']:
                            d_ct['crono_equipamentos'] = str(row['Equipamentos']) if pd.notna(row['Equipamentos']) else ""
                            updated = True
                            
                        if updated:
                            payload['dados_contrato'] = d_ct
                            st.session_state.supabase.table('servicos_andamento').update(payload).eq('id', int(id_bd)).execute()
                    
                    st.success("✅ Cronograma salvo com sucesso!")
                    st.rerun()

    with aba_zap:
        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
        st.info("💡 **Dica:** O que você digitou na tabela ao lado já aparece formatado aqui embaixo automaticamente!")
        
        # Constrói o texto do WhatsApp e o HTML dos Cartões ao vivo
        texto_zap = f"🗓️ *CRONOGRAMA DE INSTALAÇÕES*\n"
        texto_zap += f"👷 *Técnico:* {filtro_inst if filtro_inst != 'TODOS' else 'Equipe Geral'}\n"
        texto_zap += f"🔎 *Período:* {filtro_tempo}\n\n"

        html_cards = ""

        for idx, row in df_final.iterrows():
            dt_str = row['Data Agendada'].strftime('%d/%m/%Y') if pd.notna(row['Data Agendada']) else "A definir"
            vl_str = utils.to_br_currency(row['Valor Instalação'])
            equip = str(row['Equipamentos']).strip()
            
            # --- Formato Texto (WhatsApp) ---
            texto_zap += f"👤 *Cliente:* {row['nome_cliente']}\n"
            if filtro_inst == "TODOS":
                texto_zap += f"🛠️ *Instalador:* {row['instalador']}\n"
            texto_zap += f"📅 *Data:* {dt_str}\n"
            texto_zap += f"💰 *Valor:* {vl_str}\n"
            texto_zap += f"📦 *Equipamentos:*\n{equip}\n"
            texto_zap += "〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️\n\n"

            # --- Formato Cartão HTML (Print Screen) ---
            inst_html = f"<div style='font-size: 13px; color: #555; margin-bottom: 2px;'><strong>🛠️ Instalador:</strong> {row['instalador']}</div>" if filtro_inst == "TODOS" else ""
            html_cards += f"""
            <div style="background-color: #ffffff; border: 1px solid #d1d5db; border-left: 6px solid #004488; border-radius: 8px; padding: 15px; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                <h4 style="margin: 0 0 10px 0; color: #111; font-size: 18px;">👤 {row['nome_cliente']}</h4>
                {inst_html}
                <div style="font-size: 14px; color: #444; margin-bottom: 6px;"><strong>📅 Data Agendada:</strong> {dt_str}</div>
                <div style="font-size: 14px; color: #444; margin-bottom: 6px;"><strong>💰 Valor (Mão de Obra):</strong> <span style="color: #006600; font-weight: bold; font-size: 15px;">{vl_str}</span></div>
                <div style="font-size: 14px; color: #444; margin-top: 12px; background-color: #f8fafc; padding: 10px; border-radius: 6px; border: 1px solid #e2e8f0;">
                    <strong>📦 Equipamentos:</strong><br>
                    <span style="white-space: pre-wrap; display: block; margin-top: 4px; line-height: 1.5;">{equip}</span>
                </div>
            </div>
            """

        c_zap1, c_zap2 = st.columns([1, 1.2])
        
        with c_zap1:
            st.markdown("#### 📝 Copiar Texto")
            st.caption("A caixa abaixo tem um botão de cópia nativo. Basta clicar nele e colar no WhatsApp.")
            # A função st.code gera o botão "Copiar" no canto direito da caixa automaticamente!
            st.code(texto_zap.strip(), language="markdown")
            
        with c_zap2:
            st.markdown("#### 📸 Tirar Print Screen")
            st.caption("Role a página para baixo e tire um Print Screen. Os blocos se adaptam perfeitamente à tela do celular do instalador.")
            # Container HTML sem limites de altura para permitir um print scrolling de tela inteira
            st.markdown(f"<div>{html_cards}</div>", unsafe_allow_html=True)
