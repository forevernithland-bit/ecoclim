import streamlit as st
import pandas as pd
import utils

def renderizar():
    st.markdown("## 🛠️ Serviços em Andamento")
    st.info("Aqui você controla desde o orçamento enviado até a conclusão da instalação.")
    
    supabase = st.session_state.supabase
    
    # 1. Carregar Dados
    try:
        res = supabase.table('servicos_andamento').select('*').order('id', desc=True).execute()
        df = pd.DataFrame(res.data)
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return

    if df.empty:
        st.warning("Nenhum orçamento ou serviço encontrado no banco.")
        return

    # Barra de Pesquisa (Busca por Cliente ou N.º do Orçamento)
    busca = st.text_input("🔍 Pesquisar Cliente ou N.º Orçamento:", "")
    if busca:
        df = df[df['nome_cliente'].str.contains(busca, case=False, na=False) | 
                df['numero_orcamento'].str.contains(busca, case=False, na=False)]

    # 2. Interface de Tabela (Estilo Excel Ágil)
    st.write("### Painel de Controle Operacional")
    
    col_cfg = {
        "id": None,
        "numero_orcamento": st.column_config.TextColumn("ID Orçamento", width="small", disabled=True),
        "nome_cliente": st.column_config.TextColumn("Cliente", width="medium", disabled=True),
        "status_projeto": st.column_config.SelectboxColumn(
            "Status Atual", 
            options=["Orçamento Enviado", "Em Negociação", "Aprovado", "Em Execução", "Concluído", "Cancelado"],
            width="medium"
        ),
        "valor_venda_total": st.column_config.NumberColumn("Venda (R$)", format="R$ %,.2f", disabled=True),
        "valor_custo_equipamentos": st.column_config.NumberColumn("Custo Equip. (R$)", format="R$ %,.2f", disabled=True),
        "valor_custo_materiais_extras": st.column_config.NumberColumn("Mat. Extra (R$)", format="R$ %,.2f"),
        "instalador_responsavel": st.column_config.TextColumn("Instalador", width="medium"),
        "valor_pago_instalador": st.column_config.NumberColumn("Mão de Obra (R$)", format="R$ %,.2f"),
        "lucro_estimado": st.column_config.NumberColumn("LUCRO FINAL", format="R$ %,.2f", disabled=True),
        "link_pdf_drive": st.column_config.LinkColumn("Link PDF", width="small")
    }

    # Editor de dados
    df_edit = st.data_editor(
        df, 
        column_config=col_cfg, 
        use_container_width=True, 
        hide_index=True,
        num_rows="fixed"
    )

    # Cálculo dinâmico do Lucro na Tabela
    # Lucro = Venda - (Custo Equip + Materiais Extra + Mão de obra)
    df_edit['lucro_estimado'] = (
        df_edit['valor_venda_total'] - 
        (df_edit['valor_custo_equipamentos'] + 
         df_edit['valor_custo_materiais_extras'].fillna(0) + 
         df_edit['valor_pago_instalador'].fillna(0))
    ).astype(float)

    # Botão de Salvar Alterações
    if st.button("💾 Salvar Atualizações do Painel", type="primary"):
        with st.spinner("Sincronizando com o banco..."):
            for index, row in df_edit.iterrows():
                supabase.table('servicos_andamento').update({
                    "status_projeto": row['status_projeto'],
                    "valor_custo_materiais_extras": float(row['valor_custo_materiais_extras']),
                    "instalador_responsavel": row['instalador_responsavel'],
                    "valor_pago_instalador": float(row['valor_pago_instalador']),
                    "lucro_estimado": float(row['lucro_estimado'])
                }).eq('id', row['id']).execute()
        st.success("Dados atualizados com sucesso!")
        st.rerun()

    # 3. Resumo Financeiro do que está na tela
    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    total_venda = df_edit[df_edit['status_projeto'] != "Cancelado"]['valor_venda_total'].sum()
    total_lucro = df_edit[df_edit['status_projeto'] != "Cancelado"]['lucro_estimado'].sum()
    
    c1.metric("Volume em Orçamentos", utils.to_br_currency(total_venda))
    c2.metric("Expectativa de Lucro", utils.to_br_currency(total_lucro))
    c3.metric("Serviços Ativos", len(df_edit[df_edit['status_projeto'].isin(["Aprovado", "Em Execução"])]))
