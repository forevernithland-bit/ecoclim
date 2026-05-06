import streamlit as st
import pandas as pd
import datetime
import utils

def renderizar():
    st.markdown("## 📝 Novo Orçamento")
    
    # Garante que os catálogos estejam carregados
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
        
        # Inicia a tabela ou atualiza a existente com a nova coluna
        if 'df_orc' not in st.session_state:
            st.session_state.df_orc = pd.DataFrame([{"Produto da Base": "", "Produto Manual": "", "Quantidade": 1, "Venda (R$)": 0.0, "Venda Total": 0.0} for _ in range(5)])
        else:
            # Trava de segurança para quem está com o cache antigo
            if "Venda Total" not in st.session_state.df_orc.columns:
                st.session_state.df_orc["Venda Total"] = 0.0
        
        cfg = {
            "Produto da Base": st.column_config.SelectboxColumn("Produto", options=[""] + lista_p + ["OUTRO"], width="large"), 
            "Produto Manual": st.column_config.TextColumn("Produto Manual", width="medium"),
            "Quantidade": st.column_config.NumberColumn("Qtd", min_value=1, step=1),
            "Venda (R$)": st.column_config.NumberColumn("Preço Un. (R$)", format="R$ %,.2f"),
            "Venda Total": st.column_config.NumberColumn("Venda Total (R$)", format="R$ %,.2f", disabled=True)
        }
        
        df_ed = st.data_editor(st.session_state.df_orc, column_config=cfg, num_rows="dynamic", use_container_width=True)
        
        # Reseta o index para evitar erros ao adicionar novas linhas
        df_ed = df_ed.reset_index(drop=True)
        
        # Força as colunas para números para evitar erros
        df_ed['Quantidade'] = pd.to_numeric(df_ed['Quantidade'], errors='coerce').fillna(1).astype(int)
        df_ed['Venda (R$)'] = pd.to_numeric(df_ed['Venda (R$)'], errors='coerce').fillna(0.0).astype(float)
        
        # Garante que Venda Total existe no df_ed (caso extremo)
        if "Venda Total" not in df_ed.columns:
            df_ed["Venda Total"] = 0.0

        precisa_atualizar = False
        
        # Puxa o preço automaticamente da base se o campo estiver vazio
        for i in range(len(df_ed)):
            p = df_ed.at[i, 'Produto da Base']
            if p in lista_p and df_ed.at[i, 'Venda (R$)'] == 0:
                df_ed.at[i, 'Venda (R$)'] = float(cat_p.loc[cat_p['Item'] == p, 'Venda (R$)'].values[0])
                precisa_atualizar = True
                
        # Lógica matemática: Qtd x Preço Un. = Venda Total
        nova_venda_total = df_ed['Venda (R$)'] * df_ed['Quantidade']
        if not df_ed['Venda Total'].equals(nova_venda_total):
            df_ed['Venda Total'] = nova_venda_total
            precisa_atualizar = True
        
        if precisa_atualizar:
            st.session_state.df_orc = df_ed
            st.rerun()
            
        st.session_state.df_orc = df_ed
        
        # Subtotal correto
        total_equip = df_ed['Venda Total'].sum()
        st.markdown(f"**Subtotal Equipamentos:** :blue[{utils.to_br_currency(total_equip)}]")

    with st.container(border=True):
        st.subheader("🛠️ 2. Serviços / Diversos")
        
        # 2.1 Serviço Principal
        lista_s = st.session_state.db_servicos['Item'].tolist()
        s_sel = st.selectbox("Selecionar Serviço Principal:", [""] + lista_s + ["Manual"])
        if s_sel == "Manual": 
            d_s = st.text_area("Descreva o Serviço:")
            v_s = st.number_input("Valor do Serviço (R$):", min_value=0.0, format="%.2f")
        elif s_sel != "":
            d_s = f"{s_sel}\n{st.session_state.db_servicos.loc[st.session_state.db_servicos['Item']==s_sel, 'Descrição'].values[0]}"
            v_s = float(st.session_state.db_servicos.loc[st.session_state.db_servicos['Item']==s_sel, 'Venda (R$)'].values[0])
            st.write(f"Valor do Serviço: {utils.to_br_currency(v_s)}")
        else: 
            d_s, v_s = "", 0.0
        
        # 2.2 Materiais Extras / Terceiros
        lista_o = st.session_state.db_outros['Item'].tolist()
        o_sel = st.selectbox("Adicionar Outros/Diversos:", [""] + lista_o + ["Manual"])
        if o_sel == "Manual": 
            d_o = st.text_area("Descreva Diversos:")
            v_o = st.number_input("Valor Adicional (R$):", min_value=0.0, format="%.2f")
        elif o_sel != "":
            d_o = f"{o_sel}\n{st.session_state.db_outros.loc[st.session_state.db_outros['Item']==o_sel, 'Descrição'].values[0]}"
            v_o = float(st.session_state.db_outros.loc[st.session_state.db_outros['Item']==o_sel, 'Venda (R$)'].values[0])
            st.write(f"Valor Adicional: {utils.to_br_currency(v_o)}")
        else: 
            d_o, v_o = "", 0.0

    # Matemática Final: Equipamentos + Serviço + Diversos
    total_geral = total_equip + v_s + v_o
    
    st.markdown(f"<h3 style='color:#004488;'>💰 INVESTIMENTO TOTAL: {utils.to_br_currency(total_geral)}</h3>", unsafe_allow_html=True)
    obs = st.text_area("Observações no PDF:", value="Material Hidráulico não incluído na proposta")

    if st.button("🚀 GERAR PDF E SALVAR NO SISTEMA", type="primary"):
        if nome_c:
            custo_real_equip = 0.0
            resumo_produtos = []
            detalhamento_snapshot = []
            
            for _, row in df_ed.iterrows():
                nome_p = row['Produto da Base']
                desc_m = row['Produto Manual']
                qtd = int(row['Quantidade'])
                venda_un = float(row['Venda (R$)'])
                
                if qtd <= 0 or (nome_p == "" and desc_m.strip() == ""): 
                    continue
                
                if nome_p in lista_p:
                    c_un = float(cat_p.loc[cat_p['Item'] == nome_p, 'Custo (R$)'].values[0])
                    custo_real_equip += (c_un * qtd)
                    resumo_produtos.append(f"{qtd}x {nome_p}")
                    detalhamento_snapshot.append({"Item": nome_p, "Descrição Manual": "", "Qtd": qtd, "Custo Un.": c_un, "Venda Un.": venda_un})
                elif desc_m.strip() != "":
                    resumo_produtos.append(f"{qtd}x {desc_m}")
                    detalhamento_snapshot.append({"Item": "OUTRO / MANUAL", "Descrição Manual": desc_m, "Qtd": qtd, "Custo Un.": 0.0, "Venda Un.": venda_un})

            if s_sel != "":
                if s_sel == "Manual":
                    detalhamento_snapshot.append({"Item": "OUTRO / MANUAL", "Descrição Manual": d_s, "Qtd": 1, "Custo Un.": 0.0, "Venda Un.": v_s})
                else:
                    c_s = float(st.session_state.db_servicos.loc[st.session_state.db_servicos['Item']==s_sel, 'Custo (R$)'].values[0])
                    detalhamento_snapshot.append({"Item": s_sel, "Descrição Manual": "", "Qtd": 1, "Custo Un.": c_s, "Venda Un.": v_s})
                    resumo_produtos.append(f"1x {s_sel}")
                    
            if o_sel != "":
                if o_sel == "Manual":
                    detalhamento_snapshot.append({"Item": "OUTRO / MANUAL", "Descrição Manual": d_o, "Qtd": 1, "Custo Un.": 0.0, "Venda Un.": v_o})
                else:
                    c_o = float(st.session_state.db_outros.loc[st.session_state.db_outros['Item']==o_sel, 'Custo (R$)'].values[0])
                    detalhamento_snapshot.append({"Item": o_sel, "Descrição Manual": "", "Qtd": 1, "Custo Un.": c_o, "Venda Un.": v_o})
                    resumo_produtos.append(f"1x {o_sel}")

            num_orc = f"ORC-{datetime.datetime.now().strftime('%y%m%d-%H%M')}"
            
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
                    "status_projeto": "Orçamento Enviado",
                    "detalhamento_itens": detalhamento_snapshot
                }).execute()
                st.success(f"✅ Orçamento {num_orc} salvo com sucesso.")
            except Exception as e:
                st.error(f"Erro ao salvar no banco: {e}")

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
