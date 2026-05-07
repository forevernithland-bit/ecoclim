import streamlit as st
import pandas as pd
import datetime
import utils

def renderizar():
    st.markdown("## 📋 Gestão de Serviços em Andamento (CRM)")
    
    supabase = st.session_state.supabase
    
    # 1. CARREGAMENTO DOS DADOS
    try:
        res = supabase.table('servicos_andamento').select("*").order("id", desc=True).execute()
        df_orcamentos = pd.DataFrame(res.data)
    except Exception as e:
        st.error(f"Erro ao carregar serviços do banco de dados: {e}")
        return

    if df_orcamentos.empty:
        st.info("Nenhum orçamento ou serviço encontrado no banco de dados. Crie um novo orçamento para começar.")
        return

    # 2. EXIBIÇÃO DA TABELA PRINCIPAL
    st.markdown("### 📊 Lista de Projetos e Orçamentos")
    
    colunas_exibicao = ['id', 'numero_orcamento', 'nome_cliente', 'telefone_cliente', 'status_projeto', 'valor_venda_total', 'data_conclusao']
    colunas_existentes = [c for c in colunas_exibicao if c in df_orcamentos.columns]
    
    df_display = df_orcamentos[colunas_existentes].copy()
    
    st.info("Selecione uma linha abaixo para ver e editar os detalhes do projeto.")
    
    sel_orc = st.dataframe(
        df_display,
        use_container_width=True,
        on_select="rerun",
        selection_mode="single_row",
        hide_index=True
    )

    # 3. DETALHAMENTO DO PROJETO SELECIONADO
    def exibir_detalhes_avancados(row, supabase):
        st.markdown("---")
        st.markdown(f"### 🔍 Detalhes do Projeto: {row.get('nome_cliente', 'Sem Nome')}")
        
        c1, c2, c3 = st.columns(3)
        
        # Gestão de Status
        status_atual = row.get('status_projeto', 'Orçamento Enviado')
        opcoes_status = ["Orçamento Enviado", "Em Andamento", "Aguardando Peças", "Concluído PIX", "Concluído CARTÃO", "Cancelado"]
        if status_atual not in opcoes_status:
            opcoes_status.append(status_atual)
            
        novo_status = c1.selectbox("Status do Projeto", opcoes_status, index=opcoes_status.index(status_atual))
        
        # Gestão de Data
        data_conc = row.get('data_conclusao', None)
        if pd.isna(data_conc) or not data_conc:
            data_padrao = datetime.date.today()
        else:
            try:
                data_padrao = datetime.datetime.strptime(str(data_conc), '%Y-%m-%d').date()
            except:
                data_padrao = datetime.date.today()
                
        nova_data = c2.date_input("Data de Conclusão / Previsão", value=data_padrao)
        
        # ==========================================
        # BLINDAGEM DOS ITENS (FIM DO KEYERROR)
        # ==========================================
        itens_json = row.get('detalhamento_itens', [])
        if isinstance(itens_json, list) and len(itens_json) > 0:
            df_edit = pd.DataFrame(itens_json)
        else:
            df_edit = pd.DataFrame(columns=['Item', 'Qtd', 'Venda Un.', 'Custo Un.', 'Descrição'])
            
        # Essa é a mágica: se a coluna não existir, ele cria na hora!
        colunas_obrigatorias = {'Custo Un.': 0.0, 'Qtd': 0, 'Venda Un.': 0.0, 'Item': '', 'Descrição': ''}
        for col, default_val in colunas_obrigatorias.items():
            if col not in df_edit.columns:
                df_edit[col] = default_val

        # Converte tudo para número para evitar erros matemáticos
        df_edit['Custo Un.'] = pd.to_numeric(df_edit['Custo Un.'], errors='coerce').fillna(0.0)
        df_edit['Venda Un.'] = pd.to_numeric(df_edit['Venda Un.'], errors='coerce').fillna(0.0)
        df_edit['Qtd'] = pd.to_numeric(df_edit['Qtd'], errors='coerce').fillna(0)

        st.markdown("#### 🛒 Detalhamento de Equipamentos")
        config_itens = {
            "Item": st.column_config.TextColumn("Item", width="medium"),
            "Descrição": st.column_config.TextColumn("Descrição", width="large"),
            "Qtd": st.column_config.NumberColumn("Qtd", min_value=0),
            "Custo Un.": st.column_config.NumberColumn("Custo Un. (R$)", format="R$ %.2f"),
            "Venda Un.": st.column_config.NumberColumn("Venda Un. (R$)", format="R$ %.2f")
        }
        
        df_edit = st.data_editor(df_edit, column_config=config_itens, num_rows="dynamic", use_container_width=True, key=f"ed_itens_{row['id']}")
        
        # Matemática agora é 100% segura
        custo_materiais = (df_edit['Custo Un.'] * df_edit['Qtd']).sum()
        
        st.markdown("#### 🧮 Custos Adicionais e Fechamento")
        col_custo1, col_custo2 = st.columns(2)
        custo_extra_mat = col_custo1.number_input("Custos Adicionais (Materiais de instalação extras)", value=float(row.get('custo_adicional_materiais', 0.0)), format="%.2f")
        custo_terc = col_custo2.number_input("Custo com Terceirizados / Instaladores", value=float(row.get('custo_terceirizados', 0.0)), format="%.2f")
        
        venda_final = st.number_input("Valor Final Fechado com Cliente (R$)", value=float(row.get('valor_venda_total', 0.0)), format="%.2f")
        
        lucro_estimado = venda_final - custo_materiais - custo_extra_mat - custo_terc
        
        st.info(f"**Custo Operacional Total do Projeto:** {utils.to_br_currency(custo_materiais + custo_extra_mat + custo_terc)}  |  **Lucro Líquido Estimado:** {utils.to_br_currency(lucro_estimado)}")
        
        notas = st.text_area("Notas e Observações Internas (Para a equipe)", value=str(row.get('notas_internas', '')))
        
        # BOTÃO DE SALVAR
        if st.button("💾 SALVAR ALTERAÇÕES DO PROJETO", type="primary", use_container_width=True):
            dados_atualizados = {
                "status_projeto": novo_status,
                "data_conclusao": nova_data.strftime('%Y-%m-%d'),
                "detalhamento_itens": df_edit.to_dict('records'),
                "custo_adicional_materiais": custo_extra_mat,
                "custo_terceirizados": custo_terc,
                "valor_venda_total": venda_final,
                "lucro_estimado": lucro_estimado,
                "notas_internas": notas
            }
            
            try:
                supabase.table('servicos_andamento').update(dados_atualizados).eq('id', row['id']).execute()
                st.success("✅ Projeto atualizado com sucesso! (Lembre-se: se o status for Concluído PIX/CARTÃO, o lucro já será somado no Controle Financeiro).")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao atualizar projeto: {e}")

    # GATILHO DE EXIBIÇÃO
    if sel_orc.selection.rows: 
        exibir_detalhes_avancados(df_orcamentos.iloc[sel_orc.selection.rows[0]], supabase)
