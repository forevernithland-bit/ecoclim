import streamlit as st
import pandas as pd
import datetime
import utils

@st.dialog("📅 Cronograma de Instalações", width="large")
def modal_cronograma(df_servicos, lista_instaladores):
    st.markdown("<h4 style='color: #004488; margin-top: 0;'>Organize a agenda da equipe técnica</h4>", unsafe_allow_html=True)
    st.caption("As alterações de Data, Valor e Equipamentos feitas aqui **NÃO** alteram os dados oficiais do Painel de Serviços.")
    
    with st.container(border=True):
        c1, c2 = st.columns([1, 1.5])
        filtro_inst = c1.selectbox("👷 Filtro por Instalador", ["TODOS"] + lista_instaladores)
        filtro_tempo = c2.radio("🗓️ Visão de Tempo", ["Todas as Datas", "Esta Semana", "Este Mês"], horizontal=True)
    
    df_cron = df_servicos[df_servicos['status_projeto'] == 'Em Andamento'].copy()
    
    if df_cron.empty:
        st.info("🎉 Nenhum serviço com status 'Em Andamento' no momento.")
        return
        
    # ====================================================================
    # MOTORES DA CAMADA DE SOMBRA
    # ====================================================================
    def get_crono_equipamentos(row):
        d_ct = row.get('dados_contrato')
        if isinstance(d_ct, dict) and 'crono_equipamentos' in d_ct and d_ct['crono_equipamentos']:
            return str(d_ct['crono_equipamentos'])
            
        itens = row.get('detalhamento_itens')
        if not isinstance(itens, list): return ""
        arr = []
        for it in itens:
            qtd = float(it.get('Qtd', 0))
            nome = it.get('Item', '')
            if qtd > 0 and nome:
                arr.append(f"{int(qtd)}x {nome}")
        return " + ".join(arr)

    def get_crono_data_str(row):
        d_ct = row.get('dados_contrato')
        if isinstance(d_ct, dict) and 'crono_data_str' in d_ct:
            return str(d_ct['crono_data_str'])
            
        val = row.get('data_conclusao')
        if pd.notna(val) and str(val).lower() not in ['nat', 'none', 'nan', '']:
            try: return pd.to_datetime(val).strftime('%d/%m/%Y')
            except: pass
        return ""

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

    # ====================================================================
    # MOTOR DE FILTRO DE DATAS (Data Invisível para manter a ordem)
    # ====================================================================
    def get_data_invisivel_filtro(row):
        texto = str(row['Data Agendada']).strip()
        try: return pd.to_datetime(texto, format='%d/%m/%Y').date()
        except: pass
        
        val = row.get('data_conclusao')
        if pd.notna(val) and str(val).lower() not in ['nat', 'none', 'nan', '']:
            try: return pd.to_datetime(val).date()
            except: pass
        return datetime.date(2000, 1, 1)

    # Aplicação das funções
    df_cron['Equipamentos'] = df_cron.apply(get_crono_equipamentos, axis=1)
    df_cron['Data Agendada'] = df_cron.apply(get_crono_data_str, axis=1)
    df_cron['Valor Instalação'] = df_cron.apply(get_crono_valor, axis=1)
    df_cron['Data_Filtro_Invisivel'] = df_cron.apply(get_data_invisivel_filtro, axis=1)
    
    if filtro_inst != "TODOS":
        df_cron = df_cron[df_cron['instalador'] == filtro_inst]
        
    hoje = datetime.date.today()
    if filtro_tempo == "Esta Semana":
        start_w = hoje - datetime.timedelta(days=hoje.weekday())
        end_w = start_w + datetime.timedelta(days=6)
        df_cron = df_cron[(df_cron['Data_Filtro_Invisivel'] >= start_w) & (df_cron['Data_Filtro_Invisivel'] <= end_w)]
    elif filtro_tempo == "Este Mês":
        df_cron = df_cron[pd.to_datetime(df_cron['Data_Filtro_Invisivel']).dt.month == hoje.month]
        
    cols_mostrar = ['id', 'instalador', 'nome_cliente', 'Equipamentos', 'Valor Instalação', 'Data Agendada', 'Data_Filtro_Invisivel']
    df_edit = df_cron[cols_mostrar].sort_values('Data_Filtro_Invisivel', na_position='last')
    
    if df_edit.empty:
        st.warning("Nenhum agendamento encontrado para os filtros selecionados.")
        return

    # ====================================================================
    # SISTEMA DE ABAS (Tabela vs WhatsApp)
    # ====================================================================
    aba_edit, aba_zap = st.tabs(["✏️ 1. Editar Cronograma", "📲 2. Enviar para WhatsApp"])

    with aba_edit:
        cfg_colunas = {
            "id": None, 
            "Data_Filtro_Invisivel": None, 
            "instalador": st.column_config.SelectboxColumn("Instalador", options=lista_instaladores, width=110),
            "nome_cliente": st.column_config.TextColumn("Cliente", disabled=True, width=170),
            "Equipamentos": st.column_config.TextColumn("Equipamentos Vendidos", disabled=False, width="large"),
            "Valor Instalação": st.column_config.NumberColumn("Valor Inst.", format="R$ %.2f", disabled=False, width=100),
            "Data Agendada": st.column_config.TextColumn("Data da Instalação", disabled=False, width=130, help="Escreva a data, 'A definir', ou deixe em branco.")
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
                        
                        # 1. Atualiza Instalador
                        if row['instalador'] != row_orig['instalador']:
                            payload['instalador'] = str(row['instalador']) if pd.notna(row['instalador']) else ""
                            updated = True
                            
                        # 2. Atualiza a Data de Agendamento (Texto Livre c/ Blindagem de Pandas)
                        val_data_nova = str(row['Data Agendada']).strip() if pd.notna(row['Data Agendada']) else ""
                        if val_data_nova.lower() in ['none', 'nan', 'nat']: val_data_nova = ""
                        
                        val_data_orig = str(row_orig['Data Agendada']).strip() if pd.notna(row_orig['Data Agendada']) else ""
                        if val_data_orig.lower() in ['none', 'nan', 'nat']: val_data_orig = ""
                        
                        if val_data_nova != val_data_orig:
                            d_ct['crono_data_str'] = val_data_nova
                            updated = True
                            
                        # 3. Atualiza o Valor da Instalação
                        if row['Valor Instalação'] != row_orig['Valor Instalação']:
                            d_ct['crono_valor'] = float(row['Valor Instalação']) if pd.notna(row['Valor Instalação']) else 0.0
                            updated = True
                            
                        # 4. Atualiza os Equipamentos
                        val_eq_nova = str(row['Equipamentos']).strip() if pd.notna(row['Equipamentos']) else ""
                        if val_eq_nova.lower() in ['none', 'nan']: val_eq_nova = ""
                        
                        val_eq_orig = str(row_orig['Equipamentos']).strip() if pd.notna(row_orig['Equipamentos']) else ""
                        if val_eq_orig.lower() in ['none', 'nan']: val_eq_orig = ""
                        
                        if val_eq_nova != val_eq_orig:
                            d_ct['crono_equipamentos'] = val_eq_nova
                            updated = True
                            
                        # Dispara para o banco se teve alteração
                        if updated:
                            payload['dados_contrato'] = d_ct
                            st.session_state.supabase.table('servicos_andamento').update(payload).eq('id', int(id_bd)).execute()
                    
                    st.success("✅ Cronograma salvo com sucesso!")
                    st.rerun()

    with aba_zap:
        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
        st.info("💡 **Dica:** O texto copia os dados exatamente como estão na tabela da aba anterior. Edite lá e copie aqui!")
        
        texto_zap = f"🗓️ *CRONOGRAMA DE INSTALAÇÕES*\n"
        texto_zap += f"👷 *Técnico:* {filtro_inst if filtro_inst != 'TODOS' else 'Equipe Geral'}\n"
        texto_zap += f"🔎 *Período:* {filtro_tempo}\n\n"

        for idx, row in df_final.iterrows():
            dt_str = str(row['Data Agendada']).strip()
            if dt_str.lower() in ['none', 'nan', '']: dt_str = "A definir"
                
            vl_str = utils.to_br_currency(row['Valor Instalação'])
            equip = str(row['Equipamentos']).strip()
            if equip.lower() in ['none', 'nan']: equip = ""
            
            texto_zap += f"👤 *Cliente:* {row['nome_cliente']}\n"
            if filtro_inst == "TODOS":
                texto_zap += f"🛠️ *Instalador:* {row['instalador']}\n"
            texto_zap += f"📅 *Data:* {dt_str}\n"
            texto_zap += f"💰 *Valor da Mão de Obra:* {vl_str}\n"
            texto_zap += f"📦 *Equipamentos:*\n{equip}\n"
            texto_zap += "〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️\n\n"

        st.markdown("#### 📝 Texto Pronto para Copiar")
        st.caption("A caixa abaixo tem um ícone de 'Copiar' (duas folhas) no canto superior direito. Passe o mouse, clique e cole no WhatsApp.")
        st.code(texto_zap.strip(), language="markdown")
