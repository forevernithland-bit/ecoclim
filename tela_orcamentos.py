import streamlit as st
import pandas as pd
import utils
from datetime import datetime

def renderizar():
    # Etiqueta de controlo para saber se o código atualizou
    st.caption("v3.0 - Gestão Ativa + Histórico")
    st.markdown("## 🛠️ Gestão de Serviços e Orçamentos")
    
    supabase = st.session_state.supabase
    agora = datetime.now()
    
    # 1. Carregar Dados
    try:
        res = supabase.table('servicos_andamento').select('*').order('id', desc=True).execute()
        df_raw = pd.DataFrame(res.data)
    except Exception as e:
        st.error(f"Erro ao ligar ao banco de dados: {e}")
        return

    # 2. Carregar Preços do Banco (Catalogo)
    try:
        p = utils.load_catalog('catalogo_produtos')
        s = utils.load_catalog('catalogo_servicos')
        o = utils.load_catalog('catalogo_outros')
        base_unificada = pd.concat([p, s, o], ignore_index=True)
        st.session_state.base_unificada = base_unificada
    except:
        st.session_state.base_unificada = pd.DataFrame()

    if df_raw.empty:
        st.info("Nenhum registo encontrado.")
        return

    # Tratamento de Datas
    df_raw['data_orcamento'] = pd.to_datetime(df_raw['data_orcamento'])
    df_raw['data_conclusao'] = pd.to_datetime(df_raw['data_conclusao'])
    
    # --- LÓGICA DE SEPARAÇÃO (ATIVA vs HISTÓRICO) ---
    def definir_destino(row):
        stt = row['status_projeto']
        # Se cancelado há mais de 50 dias -> Histórico
        if stt == 'Cancelado':
            if pd.notna(row['data_orcamento']) and (agora.date() - row['data_orcamento'].date()).days > 50:
                return 'Historico'
            return 'Orcamento'
        # Se concluído e já mudou o mês -> Histórico
        if stt in ['Concluído PIX', 'Concluído CARTÃO']:
            if pd.notna(row['data_conclusao']):
                if row['data_conclusao'].year < agora.year or (row['data_conclusao'].year == agora.year and row['data_conclusao'].month < agora.month):
                    return 'Historico'
            return 'Servico'
        if stt == 'Em Andamento': return 'Servico'
        return 'Orcamento'

    df_raw['Destino'] = df_raw.apply(definir_destino, axis=1)

    # --- INTERFACE DE ABAS ---
    tab_ativa, tab_hist = st.tabs(["📊 GESTÃO ATIVA", "📁 HISTÓRICO MENSAL"])

    col_view = {
        "nome_cliente": st.column_config.TextColumn("Cliente"),
        "produtos_adquiridos": st.column_config.TextColumn("Resumo Itens", width="large"),
        "valor_venda_total": st.column_config.NumberColumn("Venda", format="R$ %,.2f"),
        "lucro_estimado": st.column_config.NumberColumn("Lucro", format="R$ %,.2f"),
        "status_projeto": st.column_config.TextColumn("Status")
    }

    with tab_ativa:
        # SERVIÇOS
        st.subheader("✅ Serviços Ativos")
        df_serv = df_raw[df_raw['Destino'] == 'Servico']
        if not df_serv.empty:
            sel_s = st.dataframe(df_serv[['nome_cliente', 'produtos_adquiridos', 'valor_venda_total', 'lucro_estimado', 'status_projeto']], 
                                 column_config=col_view, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
            
            # Lucro Acumulado
            st.info(f"**💰 Lucro Estimado nos Serviços Ativos: {utils.to_br_currency(df_serv['lucro_estimado'].sum())}**")
            
            if sel_s.selection.rows:
                abrir_formulario(df_serv.iloc[sel_s.selection.rows[0]], supabase)
        
        st.markdown("---")
        
        # ORÇAMENTOS
        st.subheader("📝 Orçamentos em Aberto")
        df_orc = df_raw[df_raw['Destino'] == 'Orcamento']
        if not df_orc.empty:
            sel_o = st.dataframe(df_orc[['nome_cliente', 'produtos_adquiridos', 'valor_venda_total', 'lucro_estimado', 'status_projeto']], 
                                 column_config=col_view, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
            if sel_o.selection.rows:
                abrir_formulario(df_orc.iloc[sel_o.selection.rows[0]], supabase)

    with tab_hist:
        st.subheader("📁 Arquivo de Meses Anteriores")
        df_h = df_raw[df_raw['Destino'] == 'Historico']
        if df_h.empty:
            st.write("O histórico está vazio.")
        else:
            df_h['Mes_Ref'] = df_h['data_conclusao'].dt.strftime('%m/%Y').fillna("Cancelados")
            for mes in sorted(df_h['Mes_Ref'].unique(), reverse=True):
                with st.expander(f"📅 Período: {mes}"):
                    df_mes = df_h[df_h['Mes_Ref'] == mes]
                    st.table(df_mes[['nome_cliente', 'valor_venda_total', 'lucro_estimado', 'status_projeto']])
                    st.success(f"Lucro total no período: {utils.to_br_currency(df_mes['lucro_estimado'].sum())}")

def abrir_formulario(item, supabase):
    st.markdown(f"### 📋 Editar: {item['nome_cliente']}")
    
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            n_status = st.selectbox("Status", ["Orçamento Enviado", "Em Negociação", "Em Andamento", "Concluído PIX", "Concluído CARTÃO", "Cancelado"], 
                                    index=["Orçamento Enviado", "Em Negociação", "Em Andamento", "Concluído PIX", "Concluído CARTÃO", "Cancelado"].index(item['status_projeto']))
        with c2:
            n_inst = st.text_input("Instalador", value=item['instalador_responsavel'] or "")
        with c3:
            n_p_inst = st.number_input("Pago ao Instalador", value=float(item['valor_pago_instalador'] or 0.0))

        # --- MEMÓRIA DE CÁLCULO ---
        st.write("**Memória de Cálculo (Itens e Lucros)**")
        
        # Carregar ou Criar Dados
        if not item.get('detalhamento_itens'):
            df_itens = pd.DataFrame([{"Item": "OUTRO / MANUAL", "Descrição": item['produtos_adquiridos'], "Qtd": 1, "Custo Un.": float(item['valor_custo_equipamentos']), "Venda Un.": float(item['valor_venda_total'])}])
        else:
            df_itens = pd.DataFrame(item['detalhamento_itens'])

        # Colunas calculadas
        df_itens["Lucro Un."] = df_itens["Venda Un."] - df_itens["Custo Un."]
        df_itens["Lucro Total"] = df_itens["Lucro Un."] * df_itens["Qtd"]

        opcoes_banco = ["OUTRO / MANUAL"] + st.session_state.base_unificada['Item'].tolist()
        
        config_tabela = {
            "Item": st.column_config.SelectboxColumn("Puxar do Banco", options=opcoes_banco, width="medium"),
            "Custo Un.": st.column_config.NumberColumn("Custo Un.", format="R$ %,.2f"),
            "Venda Un.": st.column_config.NumberColumn("Venda Un.", format="R$ %,.2f"),
            "Lucro Un.": st.column_config.NumberColumn("Lucro Un.", format="R$ %,.2f", disabled=True),
            "Lucro Total": st.column_config.NumberColumn("Lucro Total", format="R$ %,.2f", disabled=True)
        }

        df_editado = st.data_editor(df_itens, column_config=config_tabela, num_rows="dynamic", use_container_width=True, key=f"ed_{item['id']}")

        # Lógica de Auto-Preenchimento
        for i in range(len(df_editado)):
            nome = df_editado.iloc[i]['Item']
            if nome != "OUTRO / MANUAL" and df_editado.iloc[i]['Custo Un.'] == 0:
                match = st.session_state.base_unificada[st.session_state.base_unificada['Item'] == nome]
                if not match.empty:
                    df_editado.at[i, 'Custo Un.'] = float(match['Custo (R$)'].values[0])
                    df_editado.at[i, 'Venda Un.'] = float(match['Venda (R$)'].values[0])
                    st.rerun()

        # Recalcular Totais
        total_v = (df_editado['Venda Un.'] * df_editado['Qtd']).sum()
        total_c = (df_editado['Custo Un.'] * df_editado['Qtd']).sum()
        lucro_l = total_v - (total_c + n_p_inst)

        st.metric("LUCRO LÍQUIDO FINAL", utils.to_br_currency(lucro_l))

        if st.button("💾 Gravar Dados do Projeto", type="primary"):
            # Se mudou para concluído hoje, grava a data
            data_concl = item['data_conclusao']
            if n_status in ['Concluído PIX', 'Concluído CARTÃO'] and item['status_projeto'] not in ['Concluído PIX', 'Concluído CARTÃO']:
                data_concl = datetime.now().date().isoformat()

            resumo = ", ".join([f"{int(r['Qtd'])}x {r['Item']}" for _, r in df_editado.iterrows()])
            
            supabase.table('servicos_andamento').update({
                "status_projeto": n_status, "instalador_responsavel": n_inst, "valor_pago_instalador": n_p_inst,
                "valor_venda_total": total_v, "valor_custo_equipamentos": total_c, "lucro_estimado": lucro_l,
                "produtos_adquiridos": resumo, "detalhamento_itens": df_editado.to_dict('records'),
                "data_conclusao": str(data_concl) if data_concl else None
            }).eq('id', item['id']).execute()
            st.success("Atualizado!")
            st.rerun()
