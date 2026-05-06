import streamlit as st
import pandas as pd
import datetime
import utils

def renderizar():
    st.markdown("## 📝 Novo Orçamento")
    
    # Garante que os catálogos estejam carregados para buscar os CUSTOS
    if 'db_produtos' not in st.session_state:
        st.session_state.db_produtos = utils.load_catalog('catalogo_produtos')
        st.session_state.db_servicos = utils.load_catalog('catalogo_servicos')
        st.session_state.db_outros = utils.load_catalog('catalogo_outros')

    cat_p = st.session_state.db_produtos
    lista_p = cat_p['Item'].tolist()
    
    with st.container(border=True):
        st.subheader("👤 Dados do Cliente")
        c1, c2 = st.columns(2)
        nome_c = c1.text_input("Nome do Cliente", key="nome_cliente_orc")
        tel_c = c2.text_input("WhatsApp", key="tel_cliente_orc")
        capa = st.selectbox("Modelo para Capa", [
            "AQUECEDOR SOLAR TRADICIONAL", 
            "AQUECEDOR SOLAR A VÁCUO ACOPLADO", 
            "AQUECEDOR SOLAR MODULAR", 
            "AQUECEDOR DE PISCINA - TRADICIONAL", 
            "AQUECEDOR DE PISCINA - TROCADOR DE CALOR", 
            "SISTEMAS DE PRESSURIZAÇÃO"
        ])

    with st.container(border=True):
        st.subheader("⚙️ 1. Equipamentos")
        mostrar_pdf = st.checkbox("Mostrar Preços Unitários no PDF?", value=True)
        if 'df_orc' not in st.session_state:
            st.session_state.df_orc = pd.DataFrame([{"Produto da Base": "", "Produto Manual": "", "Quantidade": 1, "Venda (R$)": 0.0} for _ in range(5)])
        
        cfg = {
            "Produto da Base": st.column_config.SelectboxColumn("Produto", options=[""] + lista_p + ["OUTRO"], width="large"), 
            "Produto Manual": st.column_config.TextColumn("Produto Manual", width="medium"),
            "Venda (R$)": st.column_config.NumberColumn("Preço Un.", format="R$ %,.2f")
        }
        df_ed = st.data_editor(st.session_state.df_orc, column_config=cfg, num_rows="dynamic", use_container_width=True)
        
        # Lógica de Preço Automático
        for i in range(len(df_ed)):
            p = df_ed.at[i, 'Produto da Base']
            if p in lista_p and df_ed.at[i, 'Venda (R$)'] == 0:
                df_ed.at[i, 'Venda (R$)'] = float(cat_p.loc[cat_p['Item'] == p, 'Venda (R$)'].values[0])
                st.session_state.df_orc = df_ed
                st.rerun()
        
        st.session_state.df_orc = df_ed
        total_equip = sum(df_ed['Quantidade'] * df_ed['Venda (R$)'])
        st.write(f"**Subtotal Equipamentos:** {utils.to_br_currency(total_equip)}")

    with st.container(border=True):
        st.subheader("🛠️ 2. Serviços / Diversos")
        # Busca serviços e outros para compor o orçamento
        lista_s = st.session_state.db_servicos['Item'].tolist()
        s_sel = st.selectbox("Selecionar Serviço Principal:", [""] + lista_s + ["Manual"])
        if s_sel == "Manual": 
            d_s = st.text_area("Descreva o Serviço:")
            v_s = st.number_input("Valor do Serviço:", min_value=0.0, format="%.2f")
        elif s_sel != "":
            d_s = f"{s_sel}\n{st.session_state.db_servicos.loc[st.session_state.db_servicos['Item']==s_sel, 'Descrição'].values[0]}"
            v_s = float(st.session_state.db_servicos.loc[st.session_state.db_servicos['Item']==s_sel, 'Venda (R$)'].values[0])
            st.write(f"Valor: {utils.to_br_currency(v_s)}")
        else: d_s, v_s = "", 0.0
        
        lista_o = st.session_state.db_outros['Item'].tolist()
        o_sel = st.selectbox("Adicionar Outros/Diversos:", [""] + lista_o + ["Manual"])
        if o_sel == "Manual": 
            d_o = st.text_area("Descreva Diversos:")
            v_o = st.number_input("Valor Adicional:", min_value=0.0, format="%.2f")
        elif o_sel != "":
            d_o = f"{o_sel}\n{st.session_state.db_outros.loc[st.session_state.db_outros['Item']==o_sel, 'Descrição'].values[0]}"
            v_o = float(st.session_state.db_outros.loc[st.session_state.db_outros['Item']==o_sel, 'Venda (R$)'].values[0])
            st.write(f"Valor: {utils.to_br_currency(v_o)}")
        else: d_o, v_o = "", 0.0

    total_geral = total_equip + v_s + v_o
    st.markdown(f"<h3 style='color:#004488;'>💰 INVESTIMENTO TOTAL: {utils.to_br_currency(total_geral)}</h3>", unsafe_allow_html=True)
    obs = st.text_area("Observações no PDF:", value="Material Hidráulico não incluído na proposta")

    if st.button("🚀 GERAR PDF E ENVIAR PARA SERVIÇOS", type="primary"):
        if nome_c:
            # 1. CÁLCULO DE CUSTO (Oculto) para controle interno
            custo_real_equip = 0.0
            resumo_produtos = []
            for _, row in df_ed.iterrows():
                nome_p = row['Produto da Base']
                if nome_p in lista_p:
                    c_un = float(cat_p.loc[cat_p['Item'] == nome_p, 'Custo (R$)'].values[0])
                    custo_real_equip += (c_un * row['Quantidade'])
                    resumo_produtos.append(f"{int(row['Quantidade'])}x {nome_p}")
            
            # 2. GERAÇÃO DE NÚMERO DE ORÇAMENTO
            num_orc = f"ORC-{datetime.datetime.now().strftime('%y%m%d-%H%M')}"
            
            # 3. GRAVAÇÃO NO BANCO DE DADOS (MIGRAÇÃO)
            try:
                st.session_state.supabase.table("servicos_andamento").insert({
                    "numero_orcamento": num_orc,
                    "nome_cliente": nome_c, 
                    "telefone_cliente": tel_c, 
                    "produtos_adquiridos": ", ".join(resumo_produtos),
                    "servicos_adquiridos": d_s,
                    "valor_venda_total": total_geral,
                    "valor_custo_equipamentos": custo_real_equip,
                    "lucro_estimado": total_geral - custo_real_equip,
                    "status_projeto": "Orçamento Enviado"
                }).execute()
                st.success(f"✅ Orçamento {num_orc} migrado para 'Serviços em Andamento'!")
            except Exception as e:
                st.error(f"Erro ao migrar para serviços: {e}")

            # 4. GERAÇÃO DO PDF PARA DOWNLOAD
            pdf_bytes = utils.gerar_pdf_orcamento(nome_c, tel_c, capa, df_ed, d_s, v_s, d_o, v_o, total_geral, obs, mostrar_pdf)
            st.download_button(
                label="📥 BAIXAR PDF DO ORÇAMENTO", 
                data=pdf_bytes, 
                file_name=f"{num_orc}_{nome_c}.pdf", 
                mime="application/pdf", 
                use_container_width=True
            )
        else:
            st.error("Por favor, preencha o nome do cliente antes de gerar.")
