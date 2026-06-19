import streamlit as st
import pandas as pd
import datetime
import utils

def renderizar():
    # CSS para responsividade no celular
    st.markdown("""
        <style>
        @media screen and (max-width: 768px) {
            div[data-testid="stDataFrame"] { overflow-x: auto !important; }
            div[data-testid="column"] { width: 100% !important; min-width: 100% !important; display: block !important; margin-bottom: 0.8rem !important; }
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("## 📈 Relatórios Gerenciais")
    st.caption("Visão estratégica de faturamento, lucro e margem dos serviços executados.")
    
    hoje = datetime.date.today()
    ano_atual = hoje.year
    
    try:
        res = st.session_state.supabase.table('servicos_andamento').select('nome_cliente, status_projeto, valor_venda_total, lucro_estimado, data_conclusao').execute()
        df = pd.DataFrame(res.data)
    except Exception as e:
        st.error(f"Erro ao conectar com o banco de dados: {e}")
        return
        
    if df.empty:
        st.info("Nenhum dado encontrado no sistema.")
        return

    # Filtramos apenas os serviços FINALIZADOS/EXECUTADOS (Concluído PIX ou Cartão)
    status_finalizados = ["Concluído PIX", "Concluído CARTÃO"]
    df_fin = df[df['status_projeto'].isin(status_finalizados)].copy()
    
    if df_fin.empty:
        st.warning("Ainda não há serviços finalizados para gerar os relatórios.")
        return
        
    df_fin['data_conclusao'] = pd.to_datetime(df_fin['data_conclusao'], errors='coerce')
    df_fin = df_fin.dropna(subset=['data_conclusao'])
    
    # Levanta os anos disponíveis na base de dados
    anos_disponiveis = sorted(list(set(df_fin['data_conclusao'].dt.year.astype(int)) | {ano_atual}), reverse=True)
    
    # Seletores de Ano e Mês
    c_ano, c_mes, c_vazio = st.columns([1.5, 1.5, 5])
    ano_sel = c_ano.selectbox("Selecione o Ano", anos_disponiveis, index=anos_disponiveis.index(ano_atual))
    
    opcoes_mes = ["Ano Completo (Mês a Mês)"] + utils.meses_pt
    mes_sel = c_mes.selectbox("Selecione o Mês", opcoes_mes, index=0)

    # Filtro pelo ano selecionado
    df_ano = df_fin[df_fin['data_conclusao'].dt.year == ano_sel].copy()
    df_ano['Mes_idx'] = df_ano['data_conclusao'].dt.month
    
    st.markdown("---")

    # =========================================================================
    # VISÃO 1: ANO COMPLETO (MÊS A MÊS)
    # =========================================================================
    if mes_sel == "Ano Completo (Mês a Mês)":
        dados_meses = []
        for i, mes_nome in enumerate(utils.meses_pt):
            mes_idx = i + 1
            df_mes = df_ano[df_ano['Mes_idx'] == mes_idx]
            
            fat = pd.to_numeric(df_mes['valor_venda_total'], errors='coerce').fillna(0).sum()
            lucro = pd.to_numeric(df_mes['lucro_estimado'], errors='coerce').fillna(0).sum()
            margem = (lucro / fat * 100) if fat > 0 else 0.0
            
            dados_meses.append({
                "Mês": mes_nome,
                "Faturamento (R$)": fat,
                "Lucro Líquido (R$)": lucro,
                "Margem Líquida (%)": margem
            })
            
        df_relatorio = pd.DataFrame(dados_meses)
        
        tot_fat_ano = df_relatorio["Faturamento (R$)"].sum()
        tot_lucro_ano = df_relatorio["Lucro Líquido (R$)"].sum()
        margem_ano = (tot_lucro_ano / tot_fat_ano * 100) if tot_fat_ano > 0 else 0.0
        
        st.markdown(f"### 📊 Resumo Consolidado ({ano_sel})")
        col1, col2, col3 = st.columns(3)
        col1.metric("Faturamento Bruto Total", utils.to_br_currency(tot_fat_ano))
        col2.metric("Lucro Líquido Total", utils.to_br_currency(tot_lucro_ano))
        col3.metric("Margem Líquida Média", f"{margem_ano:.2f}%".replace(".", ","))
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Abas com os Gráficos
        t_fat, t_luc, t_mar, t_tab = st.tabs(["💰 Faturamento", "💵 Lucro Líquido", "📈 Margem Média", "📋 Dados Detalhados"])
        
        df_graficos = df_relatorio.set_index("Mês")
        
        with t_fat:
            st.markdown("#### Faturamento Bruto Mês a Mês")
            st.bar_chart(df_graficos["Faturamento (R$)"], color="#004488")
        
        with t_luc:
            st.markdown("#### Lucro Líquido Mês a Mês")
            st.bar_chart(df_graficos["Lucro Líquido (R$)"], color="#006600")
            
        with t_mar:
            st.markdown("#### Margem Líquida Média (%)")
            st.line_chart(df_graficos["Margem Líquida (%)"], color="#FF9900")
            
        with t_tab:
            df_disp = df_relatorio.copy()
            df_disp["Faturamento"] = df_disp["Faturamento (R$)"].apply(lambda x: utils.to_br_currency(x))
            df_disp["Lucro Líquido"] = df_disp["Lucro Líquido (R$)"].apply(lambda x: utils.to_br_currency(x))
            df_disp["Margem Média"] = df_disp["Margem Líquida (%)"].apply(lambda x: f"{x:.2f}%".replace(".", ","))
            st.dataframe(df_disp[["Mês", "Faturamento", "Lucro Líquido", "Margem Média"]], use_container_width=True, hide_index=True)

    # =========================================================================
    # VISÃO 2: MÊS ESPECÍFICO (DETALHADO)
    # =========================================================================
    else:
        mes_idx_selecionado = utils.meses_pt.index(mes_sel) + 1
        df_mes_especifico = df_ano[df_ano['Mes_idx'] == mes_idx_selecionado].copy()
        
        tot_fat_mes = pd.to_numeric(df_mes_especifico['valor_venda_total'], errors='coerce').fillna(0).sum()
        tot_lucro_mes = pd.to_numeric(df_mes_especifico['lucro_estimado'], errors='coerce').fillna(0).sum()
        margem_mes = (tot_lucro_mes / tot_fat_mes * 100) if tot_fat_mes > 0 else 0.0
        
        st.markdown(f"### 📊 Resumo do Mês ({mes_sel} / {ano_sel})")
        col1, col2, col3 = st.columns(3)
        col1.metric("Faturamento do Mês", utils.to_br_currency(tot_fat_mes))
        col2.metric("Lucro Líquido do Mês", utils.to_br_currency(tot_lucro_mes))
        col3.metric("Margem Líquida do Mês", f"{margem_mes:.2f}%".replace(".", ","))
        
        if df_mes_especifico.empty:
            st.info("Nenhum serviço finalizado registrado neste mês.")
        else:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("#### 📋 Serviços Executados no Período")
            
            df_mes_especifico['Dia'] = df_mes_especifico['data_conclusao'].dt.strftime('%d/%m/%Y')
            df_mes_especifico['Faturamento'] = df_mes_especifico['valor_venda_total'].apply(lambda x: utils.to_br_currency(x))
            df_mes_especifico['Lucro'] = df_mes_especifico['lucro_estimado'].apply(lambda x: utils.to_br_currency(x))
            
            df_mes_especifico['Margem (%)'] = df_mes_especifico.apply(
                lambda r: f"{(r['lucro_estimado'] / r['valor_venda_total'] * 100):.1f}%" if r['valor_venda_total'] > 0 else "0.0%", axis=1
            )
            
            colunas_mostrar = ['Dia', 'nome_cliente', 'status_projeto', 'Faturamento', 'Lucro', 'Margem (%)']
            
            st.dataframe(
                df_mes_especifico[colunas_mostrar].rename(columns={'nome_cliente': 'Cliente', 'status_projeto': 'Status'}), 
                use_container_width=True, 
                hide_index=True
            )
