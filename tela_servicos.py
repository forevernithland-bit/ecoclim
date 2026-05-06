import streamlit as st
import pandas as pd
import utils

def renderizar():
    st.markdown("## 🛠️ Serviços em Andamento")
    st.write("Acompanhe e gira os orçamentos enviados e as instalações ativas.")
    
    supabase = st.session_state.supabase
    
    # 1. Carregar Dados da Base de Dados
    try:
        res = supabase.table('servicos_andamento').select('*').order('id', desc=True).execute()
        df = pd.DataFrame(res.data)
    except Exception as e:
        st.error(f"Erro ao carregar serviços: {e}")
        df = pd.DataFrame()

    if df.empty:
        st.info("Ainda não existem orçamentos ou serviços registados.")
        return

    # 2. Configurar a Tabela para Edição
    # Selecionamos apenas as colunas mais importantes para a visão geral
    colunas_visiveis = [
        'id', 'numero_orcamento', 'nome_cliente', 'status_projeto', 
        'valor_venda_total', 'valor_custo_equipamentos', 
        'valor_custo_materiais_extras', 'instalador_responsavel', 
        'valor_pago_instalador', 'lucro_estimado'
    ]
    
    df_view = df[colunas_visiveis].copy()
    
    # Filtro de Pesquisa Rápida
    busca = st.text_input("🔍 Pesquisar por Cliente ou N.º de Orçamento:")
    if busca:
        mask = df_view['nome_cliente'].str.contains(busca, case=False, na=False) | df_view['numero_orcamento'].str.contains(busca, case=False, na=False)
        df_view = df_view[mask]

    st.markdown("### Resumo Operacional e Financeiro")
    
    col_cfg = {
        "id": None, # Ocultar o ID interno
        "numero_orcamento": st.column_config.TextColumn("Nº Orçamento", disabled=True),
        "nome_cliente": st.column_config.TextColumn("Cliente", disabled=True),
        "status_projeto": st.column_config.SelectboxColumn(
            "Status", 
            options=["Orçamento Enviado", "Em Negociação", "Aprovado", "Em Execução", "Concluído", "Cancelado"],
            required=True
        ),
        "valor_venda_total": st.column_config.NumberColumn("Valor Venda", format="R$ %,.2f", disabled=True),
        "valor_custo_equipamentos": st.column_config.NumberColumn("Custo Equip.", format="R$ %,.2f", disabled=True),
        "valor_custo_materiais_extras": st.column_config.NumberColumn("Materiais Extras", format="R$ %,.2f"),
        "instalador_responsavel": st.column_config.TextColumn("Técnico/Instalador"),
        "valor_pago_instalador": st.column_config.NumberColumn("Pagamento Técnico", format="R$ %,.2f"),
        "lucro_estimado": st.column_config.NumberColumn("Lucro Final", format="R$ %,.2f", disabled=True)
    }

    # Data Editor
    df_edit = st.data_editor(
        df_view, 
        column_config=col_cfg, 
        use_container_width=True, 
        hide_index=True,
        num_rows="fixed"
    )

    # 3. Recálculo Automático do Lucro
    # Lucro = Venda - Custo Equipamentos - Materiais Extras - Pago ao Instalador
    df_edit['lucro_estimado'] = (
        df_edit['valor_venda_total'] - 
        df_edit['valor_custo_equipamentos'] - 
        df_edit['valor_custo_materiais_extras'].fillna(0) - 
        df_edit['valor_pago_instalador'].fillna(0)
    ).astype(float)

    # 4. Guardar Alterações
    if st.button("💾 Guardar Alterações", type="primary"):
        # Converter dataframe editado para dicionário para atualizar no Supabase
        records_to_update = df_edit.to_dict('records')
        
        sucesso = True
        with st.spinner("A guardar alterações..."):
            for record in records_to_update:
                try:
                    supabase.table('servicos_andamento').update({
                        'status_projeto': record['status_projeto'],
                        'valor_custo_materiais_extras': float(record['valor_custo_materiais_extras']) if pd.notna(record['valor_custo_materiais_extras']) else 0,
                        'instalador_responsavel': record['instalador_responsavel'] if pd.notna(record['instalador_responsavel']) else "",
                        'valor_pago_instalador': float(record['valor_pago_instalador']) if pd.notna(record['valor_pago_instalador']) else 0,
                        'lucro_estimado': float(record['lucro_estimado'])
                    }).eq('id', record['id']).execute()
                except Exception as e:
                    sucesso = False
                    st.error(f"Erro ao atualizar o registo {record['numero_orcamento']}: {e}")
        
        if sucesso:
            st.success("Painel de serviços atualizado com sucesso!")
            st.rerun()

    # Métricas de Resumo Rápido (Calculadas com base nos itens visíveis)
    st.write("---")
    st.markdown("### 📊 Indicadores dos Projetos Visíveis")
    c1, c2, c3, c4 = st.columns(4)
    vendas_ativas = df_edit[df_edit['status_projeto'].isin(['Aprovado', 'Em Execução', 'Concluído'])]['valor_venda_total'].sum()
    lucro_ativo = df_edit[df_edit['status_projeto'].isin(['Aprovado', 'Em Execução', 'Concluído'])]['lucro_estimado'].sum()
    
    c1.metric("Total Orçamentado", utils.to_br_currency(df_edit['valor_venda_total'].sum()))
    c2.metric("Vendas Aprovadas", utils.to_br_currency(vendas_ativas))
    c3.metric("Lucro Estimado (Aprovados)", utils.to_br_currency(lucro_ativo))
    c4.metric("Instalações Pendentes", len(df_edit[df_edit['status_projeto'].isin(['Aprovado', 'Em Execução'])]))
