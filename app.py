import streamlit as st
import pandas as pd
import numpy as np
import datetime
import re
import os
from supabase import create_client
from fpdf import FPDF

# ==========================================
# 1. CONFIGURAÇÃO E CONEXÃO
# ==========================================
st.set_page_config(page_title="Ecoclim ERP", layout="wide", page_icon="🌤️")

@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"].strip()
    key = st.secrets["SUPABASE_KEY"].strip()
    return create_client(url, key)

try:
    supabase = init_connection()
except Exception as e:
    st.error(f"Erro na conexão Supabase: {e}")

# ==========================================
# 2. VARIÁVEIS E FORMATAÇÃO
# ==========================================
meses_pt = ['JANEIRO', 'FEVEREIRO', 'MARÇO', 'ABRIL', 'MAIO', 'JUNHO', 'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO']
hoje = datetime.datetime.now()
ano_atual = hoje.year
mes_hoje_idx = hoje.month 
mes_atual_nome = meses_pt[mes_hoje_idx - 1] 

def to_br_currency(val):
    try:
        v = float(val)
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "R$ 0,00"

def parse_br_currency(val):
    try:
        if isinstance(val, (int, float)): return float(val)
        clean = re.sub(r'[^\d,-]', '', str(val)).replace(",", ".")
        return float(clean) if clean else 0.0
    except: return 0.0

# ==========================================
# 3. BASES DE DADOS INTELIGENTES (COM LUCRO)
# ==========================================
if 'db_produtos' not in st.session_state:
    st.session_state.db_produtos = pd.DataFrame([
        {"Item": "Boiler Aquecedor Solar 400L", "Custo (R$)": 2200.0, "Margem (%)": 72.7, "Lucro (R$)": 1600.0, "Venda (R$)": 3800, "Descrição": "Classe A INMETRO Aço 304\nIdeal para até 6 banhos/dia\nGarantia: 3 Anos de fábrica"},
        {"Item": "Placa Coletora Solar 1x1m", "Custo (R$)": 500.0, "Margem (%)": 70.0, "Lucro (R$)": 350.0, "Venda (R$)": 850, "Descrição": "Vidro temperado de alta eficiência térmica."},
        {"Item": "Trocador de Calor Piscina 40m3", "Custo (R$)": 6000.0, "Margem (%)": 58.3, "Lucro (R$)": 3500.0, "Venda (R$)": 9500, "Descrição": "Condensador em Titânio\nPainel digital inteligente\nGarantia: 1 Ano"},
        {"Item": "Bomba Pressurizadora 1/2 CV", "Custo (R$)": 700.0, "Margem (%)": 71.4, "Lucro (R$)": 500.0, "Venda (R$)": 1200, "Descrição": "Bomba silenciosa com fluxostato integrado."},
        {"Item": "Tubo a Vácuo (Unidade)", "Custo (R$)": 80.0, "Margem (%)": 87.5, "Lucro (R$)": 70.0, "Venda (R$)": 150, "Descrição": "Vidro borossilicato de altíssima resistência."}
    ])

if 'db_servicos' not in st.session_state:
    st.session_state.db_servicos = pd.DataFrame([
        {"Item": "Instalação Padrão Aquecedor Solar", "Custo (R$)": 600.0, "Margem (%)": 150.0, "Lucro (R$)": 900.0, "Venda (R$)": 1500, "Descrição": "Mão de obra especializada para instalação completa do sistema no telhado."},
        {"Item": "Manutenção Preventiva Sistema", "Custo (R$)": 150.0, "Margem (%)": 200.0, "Lucro (R$)": 300.0, "Venda (R$)": 450, "Descrição": "Troca de ânodo de sacrifício, limpeza de conectores e revisão hidráulica."}
    ])

if 'db_outros' not in st.session_state:
    st.session_state.db_outros = pd.DataFrame([
        {"Item": "Locação de Guindaste/Munck", "Custo (R$)": 600.0, "Margem (%)": 33.3, "Lucro (R$)": 200.0, "Venda (R$)": 800, "Descrição": "Diária de caminhão munck para içamento seguro do boiler."},
        {"Item": "Material Hidráulico Extra", "Custo (R$)": 300.0, "Margem (%)": 66.7, "Lucro (R$)": 200.0, "Venda (R$)": 500, "Descrição": "Tubos e conexões em CPVC Aquatherm para adaptação térmica."}
    ])

# ==========================================
# 4. FUNÇÕES FINANCEIRAS (MANTIDAS)
# ==========================================
def load_year_data(table_name, itens_padrao, ano_escolhido):
    try:
        res = supabase.table(table_name).select("*").eq("ano", ano_escolhido).execute()
        df_raw = pd.DataFrame(res.data)
        if df_raw.empty:
            df = pd.DataFrame(0, index=range(len(itens_padrao)), columns=meses_pt)
            df.insert(0, 'MESES', itens_padrao); return df
        df_pivot = df_raw.pivot(index='conta', columns='mes', values='valor').fillna(0)
        for m in meses_pt:
            if m not in df_pivot.columns: df_pivot[m] = 0
        df_pivot = df_pivot[meses_pt].reset_index()
        df_pivot.rename(columns={'conta': 'MESES'}, inplace=True)
        for item in itens_padrao:
            if item not in df_pivot['MESES'].values:
                nova_linha = {m: 0 for m in meses_pt}; nova_linha['MESES'] = item
                df_pivot = pd.concat([df_pivot, pd.DataFrame([nova_linha])], ignore_index=True)
        df_pivot.set_index('MESES', inplace=True); df_pivot = df_pivot.reindex(itens_padrao).reset_index()
        df_pivot[meses_pt] = df_pivot[meses_pt].astype(int)
        return df_pivot
    except:
        df = pd.DataFrame(0, index=range(len(itens_padrao)), columns=meses_pt)
        df.insert(0, 'MESES', itens_padrao); return df

def save_to_supabase(table_name, df_int, ano_escolhido):
    try:
        df_melted = df_int.melt(id_vars=['MESES'], var_name='mes', value_name='valor')
        df_melted['ano'] = ano_escolhido; df_melted.rename(columns={'MESES': 'conta'}, inplace=True)
        df_melted['valor'] = df_melted['valor'].astype(int)
        data = df_melted.to_dict(orient='records')
        supabase.table(table_name).delete().eq('ano', ano_escolhido).execute()
        supabase.table(table_name).insert(data).execute()
    except Exception as e: pass

def load_user_settings():
    try:
        res = supabase.table('configuracoes').select("*").eq('user_id', 'breno.lima').execute()
        if res.data: return res.data[0]['mes_inicio'], res.data[0]['mes_fim']
    except: pass
    return "JANEIRO", mes_atual_nome

def save_user_settings(inicio, fim):
    try:
        data = {"id": 1, "user_id": "breno.lima", "mes_inicio": inicio, "mes_fim": fim}
        supabase.table('configuracoes').upsert(data).execute()
    except: pass

# ==========================================
# 5. CSS GERAL E LOGIN
# ==========================================
st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem !important; padding-left: 1rem !important; padding-right: 1rem !important; max-width: 100% !important; }
    div.container-tabelas div[data-testid="stVerticalBlock"] { gap: 0px !important; padding: 0px !important; }
    [data-testid="stTable"] { overflow: hidden !important; }
    .dvn-scroller { overflow-y: hidden !important; }
    .stDataFrame table, .stDataEditor table { table-layout: fixed !important; width: 100% !important; }
    .stDataFrame td, .stDataFrame th, .stDataEditor td, .stDataEditor th { text-align: center !important; font-size: 0.85rem !important; }
    .financeiro section.main div[data-testid="stDataFrame"]:nth-of-type(1) thead, .financeiro section.main div[data-testid="stDataEditor"]:nth-of-type(2) thead, .financeiro section.main div[data-testid="stDataFrame"]:nth-of-type(2) thead, .financeiro section.main div[data-testid="stDataFrame"]:nth-of-type(3) thead { display: none !important; }
    </style>
""", unsafe_allow_html=True)

if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "pagina_atual" not in st.session_state: st.session_state.pagina_atual = "Página Inicial"

def login_screen():
    if os.path.exists("logo.png"):
        col_img1, col_img2, col_img3 = st.columns([1, 1, 1])
        with col_img2: st.image("logo.png", use_container_width=True)
    st.markdown("<br><h2 style='text-align: center;'>Acesso ao Sistema</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        user = st.text_input("Usuário")
        password = st.text_input("Senha", type="password")
        if st.button("Entrar", use_container_width=True):
            if user == "breno.lima" and password == "Ecoclim2026@":
                st.session_state.authenticated = True; st.rerun()
            else: st.error("Usuário ou senha incorretos")

# ==========================================
# 6. GERADOR DE PDF (COM DESCRIÇÕES)
# ==========================================
def gerar_pdf_orcamento(cliente, telefone, produto, df_equip, desc_serv, val_serv, desc_outros, val_outros, total, obs, mostrar_val_equip):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    
    if os.path.exists("logo.png"): pdf.image("logo.png", 10, 8, 40)
    
    pdf.cell(0, 10, "PROPOSTA COMERCIAL", ln=True, align="R")
    pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 5, f"Data: {datetime.datetime.now().strftime('%d/%m/%Y')}", ln=True, align="R")
    pdf.cell(0, 5, "Validade da proposta: 15 dias", ln=True, align="R")
    pdf.ln(10)
    
    pdf.set_font("helvetica", "B", 12)
    pdf.set_fill_color(230, 240, 255)
    pdf.cell(0, 8, " DADOS DO CLIENTE", border=1, ln=True, fill=True)
    pdf.set_font("helvetica", "", 11)
    pdf.cell(0, 8, f" Nome: {cliente}", border=1, ln=True)
    pdf.cell(0, 8, f" Telefone: {telefone}", border=1, ln=True)
    pdf.ln(5)

    img_urls = {
        "AQUECEDOR SOLAR TRADICIONAL": "https://dummyimage.com/600x200/004488/fff&text=Aquecedor+Solar+Tradicional",
        "AQUECEDOR SOLAR A VÁCUO ACOPLADO": "https://dummyimage.com/600x200/004488/fff&text=Tubos+a+Vacuo+Acoplado",
        "AQUECEDOR SOLAR MODULAR": "https://dummyimage.com/600x200/004488/fff&text=Aquecedor+Solar+Modular",
        "AQUECEDOR DE PISCINA - TRADICIONAL": "https://dummyimage.com/600x200/004488/fff&text=Aquecedor+de+Piscina",
        "AQUECEDOR DE PISCINA - TROCADOR DE CALOR": "https://dummyimage.com/600x200/004488/fff&text=Trocador+de+Calor",
        "SISTEMAS DE PRESSURIZAÇÃO": "https://dummyimage.com/600x200/004488/fff&text=Sistema+de+Pressurizacao"
    }
    
    try: pdf.image(img_urls.get(produto, img_urls["AQUECEDOR SOLAR TRADICIONAL"]), x=10, w=190)
    except: pdf.cell(0, 20, f"[IMAGEM DO PRODUTO: {produto}]", border=1, ln=True, align="C")
    pdf.ln(5)

    # 1. Equipamentos
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(0, 8, " 1. DESCRIÇÃO DE EQUIPAMENTOS", border=1, ln=True, fill=True)
    pdf.set_font("helvetica", "B", 10)
    
    if mostrar_val_equip:
        pdf.cell(100, 8, " Item", border=1)
        pdf.cell(30, 8, " Qtd", border=1, align="C")
        pdf.cell(60, 8, " Subtotal", border=1, ln=True, align="R")
    else:
        pdf.cell(160, 8, " Item", border=1)
        pdf.cell(30, 8, " Qtd", border=1, ln=True, align="C")
    
    for _, row in df_equip.iterrows():
        nome = row['Produto da Base'] if row['Produto da Base'] != "OUTRO (Digitar)" else row['Produto Manual']
        if nome.strip() != "":
            q = float(row['Quantidade'])
            v = float(row['Venda (R$)'])
            
            # Busca a descrição na base de dados (se existir)
            desc_texto = ""
            if nome in st.session_state.db_produtos['Item'].values:
                desc_texto = st.session_state.db_produtos.loc[st.session_state.db_produtos['Item'] == nome, 'Descrição'].values[0]
            
            # Linha Principal (Nome e Preços)
            pdf.set_font("helvetica", "B", 10)
            pdf.set_text_color(0, 0, 0)
            if mostrar_val_equip:
                pdf.cell(100, 8, f" {nome}", border=1)
                pdf.cell(30, 8, f" {int(q)}", border=1, align="C")
                pdf.cell(60, 8, f" {to_br_currency(q * v)}", border=1, ln=True, align="R")
            else:
                pdf.cell(160, 8, f" {nome}", border=1)
                pdf.cell(30, 8, f" {int(q)}", border=1, ln=True, align="C")
            
            # Linha Secundária (Descrição do Item Mesclada em Baixo)
            if desc_texto.strip() != "":
                pdf.set_font("helvetica", "I", 8)
                pdf.set_text_color(80, 80, 80) # Cinza para não brigar com o título
                pdf.multi_cell(0, 5, f"  Detalhes: {desc_texto}", border=1)

    # 2. Serviços
    pdf.set_text_color(0, 0, 0)
    pdf.ln(5)
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(0, 8, " 2. ORÇAMENTO DO SERVIÇO", border=1, ln=True, fill=True)
    pdf.set_font("helvetica", "", 10)
    pdf.multi_cell(0, 6, f"Descrição:\n{desc_serv}", border=1)
    if val_serv > 0:
        pdf.cell(130, 8, "Valor do Serviço:", border=1)
        pdf.cell(60, 8, f" {to_br_currency(val_serv)}", border=1, ln=True, align="R")

    # 3. Outros
    if val_outros > 0 or desc_outros.strip() != "":
        pdf.ln(5)
        pdf.set_font("helvetica", "B", 12)
        pdf.cell(0, 8, " 3. OUTROS SERVIÇOS / PRODUTOS", border=1, ln=True, fill=True)
        pdf.set_font("helvetica", "", 10)
        pdf.multi_cell(0, 6, f"Descrição:\n{desc_outros}", border=1)
        if val_outros > 0:
            pdf.cell(130, 8, "Valor Adicional:", border=1)
            pdf.cell(60, 8, f" {to_br_currency(val_outros)}", border=1, ln=True, align="R")

    # Total Geral
    pdf.ln(5)
    pdf.set_font("helvetica", "B", 14)
    pdf.set_fill_color(0, 68, 136)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(130, 10, " INVESTIMENTO TOTAL", border=1, fill=True)
    pdf.cell(60, 10, f" {to_br_currency(total)}", border=1, ln=True, align="R", fill=True)
    
    # Observações
    pdf.ln(10)
    pdf.set_text_color(200, 0, 0)
    pdf.set_font("helvetica", "B", 10)
    pdf.multi_cell(0, 6, f"OBSERVAÇÕES IMPORTANTES:\n{obs}", border=0)

    return bytes(pdf.output())

# ==========================================
# 7. TELAS E MÓDULOS
# ==========================================
def tela_inicial():
    st.markdown("## Página Inicial")
    st.write("Bem-vindo ao sistema de gestão, Breno. Selecione uma opção abaixo:")
    st.write("---")
    col1, col2 = st.columns(2); col3, col4 = st.columns(2)
    with col1:
        if st.button("📝\n\nFazer Orçamento", use_container_width=True): 
            st.session_state.pagina_atual = "Orçamentos"; st.rerun()
    with col2:
        if st.button("📊\n\nControle Financeiro", use_container_width=True):
            st.session_state.pagina_atual = "Controle Financeiro"; st.rerun()
    with col3:
        if st.button("⚙️\n\nConfigurações", use_container_width=True): 
            st.session_state.pagina_atual = "Configurações"; st.rerun()
    with col4:
        if st.button("🛠️\n\nServiços Ecoclim", use_container_width=True): st.info("Módulo em desenvolvimento.")

def render_db_config(db_name):
    df_old = st.session_state[db_name].copy()
    
    col_cfg = {
        "Item": st.column_config.TextColumn("Item", width="medium"),
        "Custo (R$)": st.column_config.NumberColumn("Custo (R$)", format="R$ %.2f", min_value=0.0),
        "Margem (%)": st.column_config.NumberColumn("Margem (%)", format="%.1f%%", step=1.0),
        "Lucro (R$)": st.column_config.NumberColumn("Lucro (R$)", format="R$ %.2f", disabled=True),
        "Venda (R$)": st.column_config.NumberColumn("Venda (R$)", format="R$ %d", disabled=True), # Sem centavos!
        "Descrição": st.column_config.TextColumn("Descrição (Aparece no PDF)", width="large")
    }
    
    df_edit = st.data_editor(st.session_state[db_name], num_rows="dynamic", column_config=col_cfg, use_container_width=True)
    
    # Motor de Cálculo (Arredonda o valor de venda e calcula o lucro real)
    df_edit['Venda (R$)'] = (df_edit['Custo (R$)'] * (1 + df_edit['Margem (%)'] / 100)).fillna(0).round().astype(int)
    df_edit['Lucro (R$)'] = df_edit['Venda (R$)'] - df_edit['Custo (R$)']
    
    if not df_edit.equals(df_old):
        st.session_state[db_name] = df_edit
        st.rerun()

def tela_configuracoes():
    st.markdown("## ⚙️ Configurações do Sistema")
    st.info("💡 **Como usar:** Edite o 'Custo' e a 'Margem (%)'. O sistema calculará o 'Lucro' e o 'Valor Venda' sozinho! O Valor de Venda é arredondado para não ter centavos.")
    
    tab1, tab2, tab3 = st.tabs(["🛒 Equipamentos", "🛠️ Serviços", "➕ Terceirizados"])
    
    with tab1:
        st.subheader("Base de Dados: Equipamentos")
        render_db_config('db_produtos')

    with tab2:
        st.subheader("Base de Dados: Serviços")
        render_db_config('db_servicos')

    with tab3:
        st.subheader("Base de Dados: Terceirizados / Outros")
        render_db_config('db_outros')

def tela_orcamentos():
    st.markdown("## 📝 Novo Orçamento Ecoclim")
    st.write("Preencha os dados abaixo para gerar a proposta comercial.")
    
    lista_produtos_db = st.session_state.db_produtos['Item'].tolist()
    lista_servicos_db = st.session_state.db_servicos['Item'].tolist()
    lista_outros_db = st.session_state.db_outros['Item'].tolist()
    
    with st.container(border=True):
        st.subheader("👤 1. Dados do Cliente")
        col1, col2 = st.columns(2)
        cliente = col1.text_input("Nome do Cliente", placeholder="Ex: João da Silva")
        telefone = col2.text_input("Telefone / WhatsApp", placeholder="(00) 00000-0000")
        produtos_lista = ["AQUECEDOR SOLAR TRADICIONAL", "AQUECEDOR SOLAR A VÁCUO ACOPLADO", "AQUECEDOR SOLAR MODULAR", "AQUECEDOR DE PISCINA - TRADICIONAL", "AQUECEDOR DE PISCINA - TROCADOR DE CALOR", "SISTEMAS DE PRESSURIZAÇÃO"]
        produto_selecionado = st.selectbox("Selecione a Imagem do Produto para a Capa", produtos_lista)

    with st.container(border=True):
        col_eq1, col_eq2 = st.columns([3, 1])
        with col_eq1: st.subheader("⚙️ 2. Descrição de Equipamentos")
        with col_eq2: mostrar_pdf = st.checkbox("Mostrar R$ no PDF?", value=True, help="Desmarque para ocultar os preços unitários no PDF.")
        
        opcoes_db_produtos = [""] + lista_produtos_db + ["OUTRO (Digitar)"]
        
        if 'df_equip' not in st.session_state:
            st.session_state.df_equip = pd.DataFrame([{"Produto da Base": "", "Produto Manual": "", "Quantidade": 1, "Venda (R$)": 0.0} for _ in range(5)])
        
        config_colunas = {
            "Produto da Base": st.column_config.SelectboxColumn("Selecionar Produto (Base)", options=opcoes_db_produtos, width="medium"),
            "Produto Manual": st.column_config.TextColumn("Se 'OUTRO', digite aqui:", width="medium"),
            "Quantidade": st.column_config.NumberColumn("Qtd", min_value=1, step=1, width="small"),
            "Venda (R$)": st.column_config.NumberColumn("Valor Un. (R$)", format="R$ %d", width="small")
        }

        df_equip_edit = st.data_editor(st.session_state.df_equip, column_config=config_colunas, num_rows="dynamic", use_container_width=True)
        
        mudou_algo = False
        for i in range(len(df_equip_edit)):
            prod_selecionado = df_equip_edit.at[i, 'Produto da Base']
            valor_atual = df_equip_edit.at[i, 'Venda (R$)']
            if prod_selecionado in lista_produtos_db and valor_atual == 0.0:
                valor_banco = st.session_state.db_produtos.loc[st.session_state.db_produtos['Item'] == prod_selecionado, 'Venda (R$)'].values[0]
                df_equip_edit.at[i, 'Venda (R$)'] = float(valor_banco)
                mudou_algo = True

        if mudou_algo:
            st.session_state.df_equip = df_equip_edit
            st.rerun()
        else:
            st.session_state.df_equip = df_equip_edit

        total_equip = sum([float(r['Quantidade']) * float(r['Venda (R$)']) for _, r in df_equip_edit.iterrows() if r['Produto da Base'] != ""])
        st.markdown(f"**Subtotal Equipamentos:** {to_br_currency(total_equip)}")

    with st.container(border=True):
        st.subheader("🛠️ 3. Orçamento do Serviço")
        opcoes_db_serv = ["Selecione da Base..."] + lista_servicos_db + ["Outro (Digitar manualmente)"]
        servico_selecionado = st.selectbox("Selecione um serviço cadastrado ou digite:", opcoes_db_serv)
        
        if servico_selecionado == "Outro (Digitar manualmente)":
            desc_servico = st.text_area("Descreva o serviço:")
            valor_servico = st.number_input("Valor do Serviço (R$)", min_value=0.0, step=100.0, format="%.2f")
        elif servico_selecionado != "Selecione da Base...":
            # Puxa o texto da descrição do banco também!
            desc_banco_serv = st.session_state.db_servicos.loc[st.session_state.db_servicos['Item'] == servico_selecionado, 'Descrição'].values[0]
            desc_servico = st.text_area("Descreva o serviço:", value=f"{servico_selecionado}\n{desc_banco_serv}")
            
            val_banco_serv = st.session_state.db_servicos.loc[st.session_state.db_servicos['Item'] == servico_selecionado, 'Venda (R$)'].values[0]
            valor_servico = st.number_input("Valor do Serviço (R$)", value=float(val_banco_serv), min_value=0.0, step=100.0, format="%.2f")
        else:
            desc_servico = ""; valor_servico = 0.0

    with st.container(border=True):
        st.subheader("➕ 4. Outros Serviços / Produtos (Terceirizados)")
        opcoes_db_outros = ["Selecione da Base..."] + lista_outros_db + ["Outro (Digitar manualmente)"]
        outros_selecionado = st.selectbox("Selecione um item extra cadastrado ou digite:", opcoes_db_outros)
        
        if outros_selecionado == "Outro (Digitar manualmente)":
            desc_outros = st.text_area("Descreva materiais ou serviços extras:")
            valor_outros = st.number_input("Valor Adicional (R$)", min_value=0.0, step=100.0, format="%.2f")
        elif outros_selecionado != "Selecione da Base...":
            desc_banco_outros = st.session_state.db_outros.loc[st.session_state.db_outros['Item'] == outros_selecionado, 'Descrição'].values[0]
            desc_outros = st.text_area("Descreva materiais ou serviços extras:", value=f"{outros_selecionado}\n{desc_banco_outros}")
            
            val_banco_outros = st.session_state.db_outros.loc[st.session_state.db_outros['Item'] == outros_selecionado, 'Venda (R$)'].values[0]
            valor_outros = st.number_input("Valor Adicional (R$)", value=float(val_banco_outros), min_value=0.0, step=100.0, format="%.2f")
        else:
            desc_outros = ""; valor_outros = 0.0

    with st.container(border=True):
        total_geral = total_equip + valor_servico + valor_outros
        st.markdown(f"<h3 style='color: #004488;'>💰 INVESTIMENTO TOTAL: {to_br_currency(total_geral)}</h3>", unsafe_allow_html=True)
        obs_padrao = "Material Hidráulico não inclusos na proposta\nValores válidos para pagamento conforme negociação."
        observacoes = st.text_area("Observações (Aparecerá em VERMELHO no PDF):", value=obs_padrao, height=100)
    
    col_btn1, col_btn2 = st.columns([1, 1])
    with col_btn1:
        if st.button("🚀 SALVAR E GERAR PDF", use_container_width=True, type="primary"):
            if cliente == "": st.warning("Preencha o nome do cliente!")
            else:
                try:
                    data_db = {"nome": cliente, "telefone": telefone, "produto_ref": produto_selecionado, "valor_total": total_geral, "status": "Em fase de orçamento", "data_entrada": datetime.datetime.now().strftime("%Y-%m-%d")}
                    supabase.table("clientes_orcamentos").insert(data_db).execute()
                    st.success("✅ Cliente salvo no sistema como 'Em fase de orçamento'!")
                except Exception as e:
                    st.toast("⚠️ Tabela 'clientes_orcamentos' não encontrada no banco. O PDF será gerado, mas os dados não foram salvos na nuvem.", icon="⚠️")
                
                pdf_bytes = gerar_pdf_orcamento(cliente, telefone, produto_selecionado, df_equip_edit, desc_servico, valor_servico, desc_outros, valor_outros, total_geral, observacoes, mostrar_pdf)
                st.download_button(label="📥 BAIXAR PDF DO ORÇAMENTO", data=pdf_bytes, file_name=f"Orcamento_{cliente.replace(' ', '_')}.pdf", mime="application/pdf", use_container_width=True)

def tela_financeira():
    st.markdown('<div class="financeiro">', unsafe_allow_html=True)
    st.subheader("📊 Controle Financeiro")
    
    with st.sidebar:
        ano_selecionado = st.selectbox("Ano Fiscal", options=[2025, 2026, 2027, 2028], index=1)
        st.write("---")
        st.markdown("### 👁️ Linha do Tempo")
        
        pref_inicio, pref_fim = load_user_settings()
        if pref_inicio not in meses_pt: pref_inicio = "JANEIRO"
        if pref_fim not in meses_pt: pref_fim = mes_atual_nome
            
        mes_inicio, mes_fim = st.select_slider("Período Visível:", options=meses_pt, value=(pref_inicio, pref_fim))
        if (mes_inicio != pref_inicio) or (mes_fim != pref_fim): save_user_settings(mes_inicio, mes_fim)
            
        idx_inicio = meses_pt.index(mes_inicio)
        idx_fim = meses_pt.index(mes_fim)
        colunas_visiveis = ["MESES"] + meses_pt[idx_inicio:idx_fim + 1]

        if st.button("🔄 Recarregar Dados"): st.session_state.pop('ano_dados_atual', None); st.rerun()

    contas_p = ['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS', 'IMÓVEIS', 'VEÍCULOS']
    contas_e = ['ECOCLIM', 'AIRNB', 'CONS INVESTIMENTOS', 'MAGGI CONSORCIOS']
    
    if 'ano_dados_atual' not in st.session_state or st.session_state.ano_dados_atual != ano_selecionado:
        st.session_state.df_p = load_year_data('patrimonio', contas_p, ano_selecionado)
        st.session_state.df_e = load_year_data('entradas', contas_e, ano_selecionado)
        st.session_state.ano_dados_atual = ano_selecionado

    col_cfg = {"MESES": st.column_config.TextColumn("MESES", width=220, disabled=True)}
    for m in meses_pt: col_cfg[m] = st.column_config.TextColumn(m, width=80) 

    st.markdown('<div class="container-tabelas">', unsafe_allow_html=True)
    
    # [PATRIMÔNIO]
    df_p_display = st.session_state.df_p[colunas_visiveis].copy()
    for m in [c for c in colunas_visiveis if c != "MESES"]: df_p_display[m] = df_p_display[m].apply(lambda x: to_br_currency(x).replace(",00", ""))
    styled_df_p = df_p_display.style.set_properties(subset=[mes_atual_nome] if mes_atual_nome in colunas_visiveis and ano_selecionado == ano_atual else [], **{'background-color': '#e0f0ff', 'font-weight': 'bold'})
    df_p_edit_str = st.data_editor(styled_df_p, hide_index=True, column_config=col_cfg, use_container_width=True, height=295)

    if not df_p_edit_str.equals(df_p_display):
        for m in [c for c in colunas_visiveis if c != "MESES"]: st.session_state.df_p.loc[:, m] = df_p_edit_str[m].apply(parse_br_currency)
        save_to_supabase('patrimonio', st.session_state.df_p, ano_selecionado); st.toast("💾 Salvo!", icon="✅"); st.rerun()

    df_n = st.session_state.df_p.set_index('MESES')
    pat_liq = df_n.loc[['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS']].sum()
    pat_tot = pat_liq + df_n.loc['IMÓVEIS'] + df_n.loc['VEÍCULOS']
    var_abs = pat_tot.diff().fillna(0); var_pct = (pat_tot.pct_change().fillna(0) * 100).round(2)

    for i, m in enumerate(meses_pt):
        if (ano_selecionado > ano_atual) or (ano_selecionado == ano_atual and i > mes_hoje_idx - 1):
            var_abs[m] = 0; var_pct[m] = 0

    df_res_p = pd.DataFrame({'MESES': ['PATRIMÔNIO LÍQUIDO', 'PATRIMÔNIO TOTAL', 'VARIAÇÃO MENSAL ($)', 'VARIAÇÃO MENSAL (%)']})
    for m in meses_pt: df_res_p[m] = [pat_liq[m], pat_tot[m], var_abs[m], f"{var_pct[m]:.2f}%"]
    styled_res_p = df_res_p[colunas_visiveis].style.apply(lambda row: [f'background-color: {"#FF9900" if row["MESES"] == "PATRIMÔNIO TOTAL" else "#FFF2CC" if "LÍQUIDO" in row["MESES"] else "white"}; font-weight: bold; border-left: {"3px solid #4A90E2" if col == mes_atual_nome and ano_selecionado == ano_atual else "none"}' for col in colunas_visiveis], axis=1)
    st.dataframe(styled_res_p.format(lambda x: to_br_currency(x).replace(",00","") if isinstance(x, (int, float, np.integer, np.floating)) else x), hide_index=True, column_config=col_cfg, use_container_width=True, height=175)

    # [ENTRADAS]
    df_e_display = st.session_state.df_e[colunas_visiveis].copy()
    for m in [c for c in colunas_visiveis if c != "MESES"]: df_e_display[m] = df_e_display[m].apply(lambda x: to_br_currency(x).replace(",00", ""))
    styled_df_e = df_e_display.style.set_properties(subset=[mes_atual_nome] if mes_atual_nome in colunas_visiveis and ano_selecionado == ano_atual else [], **{'background-color': '#e0f0ff', 'font-weight': 'bold'})
    df_e_edit_str = st.data_editor(styled_df_e, hide_index=True, column_config=col_cfg, use_container_width=True, height=190)

    if not df_e_edit_str.equals(df_e_display):
        for m in [c for c in colunas_visiveis if c != "MESES"]: st.session_state.df_e.loc[:, m] = df_e_edit_str[m].apply(parse_br_currency)
        save_to_supabase('entradas', st.session_state.df_e, ano_selecionado); st.toast("💾 Salvo!", icon="✅"); st.rerun()

    df_e_n = st.session_state.df_e.set_index('MESES'); tot_ent = df_e_n.sum()
    df_res_e = pd.DataFrame({'MESES': ['TOTAL RECEBIMENTOS:']})
    for m in meses_pt: df_res_e[m] = [tot_ent[m]]
    styled_res_e = df_res_e[colunas_visiveis].style.apply(lambda row: [f'background-color: #9BC2E6; font-weight: bold; border-left: {"3px solid #4A90E2" if col == mes_atual_nome and ano_selecionado == ano_atual else "none"}' for col in colunas_visiveis], axis=1)
    st.dataframe(styled_res_e.format(lambda x: to_br_currency(x).replace(",00","") if isinstance(x, (int, float, np.integer, np.floating)) else x), hide_index=True, column_config=col_cfg, use_container_width=True, height=75)

    # [RENDIMENTOS]
    st.markdown("#### 📈 Rendimento Mensal (Investimentos)")
    xp_val = df_n.loc['INVESTIMENTO XP']; inter_val = df_n.loc['CONTA INTER']
    xp_var = xp_val.diff().fillna(0); inter_var = inter_val.diff().fillna(0); rend_total = xp_var + inter_var; prev_bal = (xp_val + inter_val).shift(1).fillna(0)
    df_rend = pd.DataFrame({'MESES': ['VARIAÇÃO INVESTIMENTO XP', 'VARIAÇÃO CONTA INTER', 'RENDIMENTO TOTAL', '% RETORNO MÊS', 'SALÁRIO + RENDIMENTO MÊS']})
    for i, m in enumerate(meses_pt):
        if (ano_selecionado > ano_atual) or (ano_selecionado == ano_atual and i > mes_hoje_idx - 1): df_rend[m] = [0, 0, 0, "0,00%", 0]
        else:
            rt = rend_total[m]; pb = prev_bal[m]; pct_val = (rt / pb * 100) if pb > 0 else 0
            df_rend[m] = [xp_var[m], inter_var[m], rt, f"{pct_val:.2f}%".replace(".", ","), tot_ent[m] + rt]
    styled_rend = df_rend[colunas_visiveis].style.apply(lambda row: [f'background-color: {"#FF9900" if row["MESES"] == "RENDIMENTO TOTAL" else "#FFF2CC" if "%" in row["MESES"] else "#9BC2E6" if "SALÁRIO" in row["MESES"] else "white"}; font-weight: bold; border-left: {"3px solid #4A90E2" if col == mes_atual_nome and ano_selecionado == ano_atual else "none"}' for col in colunas_visiveis], axis=1)
    st.dataframe(styled_rend.format(lambda x: to_br_currency(x).replace(",00","") if isinstance(x, (int, float, np.integer, np.floating)) else x), hide_index=True, column_config=col_cfg, use_container_width=True, height=215)
    st.markdown('</div></div>', unsafe_allow_html=True)

    # [MÉTRICAS E GRÁFICOS]
    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    meses_calculo = meses_pt if ano_selecionado < ano_atual else meses_pt[:mes_hoje_idx]
    media_entradas = tot_ent[meses_calculo].mean(); media_rend_r = rend_total[meses_calculo].mean(); media_rend_p = (rend_total[meses_calculo] / prev_bal[meses_calculo].replace(0, np.nan)).mean() * 100
    idx_ref = 11 if ano_selecionado < ano_atual else (mes_hoje_idx - 1 if mes_hoje_idx > 0 else 0)

    c1.metric("💰 MÉDIA ENTRADAS FIXAS", to_br_currency(media_entradas))
    c2.metric("🎯 LIMITE DE GASTO (MÉDIA REND.)", to_br_currency(media_rend_r))
    c3.metric("📈 MÉDIA RETORNO (%)", f"{media_rend_p:.2f}%".replace(".", ","))
    c4.metric("🏛️ PATRIMÔNIO ATUAL", to_br_currency(pat_tot.iloc[idx_ref]))

    st.write("---")
    g1, g2 = st.columns(2)
    with g1:
        st.subheader("Aumento de Patrimônio Total"); st.line_chart(pat_tot[meses_pt])
        st.subheader("Rendimento Mensal (R$)"); st.bar_chart(rend_total[meses_pt])
    with g2:
        st.subheader("Salário + Rendimento Mensal"); st.area_chart(tot_ent[meses_pt] + rend_total[meses_pt])
        st.subheader("Faturamento Ecoclim"); st.line_chart(df_e_n.loc['ECOCLIM'][meses_pt])

# ==========================================
# 8. EXECUÇÃO PRINCIPAL
# ==========================================
if not st.session_state.authenticated:
    login_screen()
else:
    with st.sidebar:
        if os.path.exists("logo.png"): st.image("logo.png", use_container_width=True)
        st.write("### Menu Principal")
        opcoes_menu = ["Página Inicial", "Orçamentos", "Controle Financeiro", "Configurações"]
        idx_menu = opcoes_menu.index(st.session_state.pagina_atual) if st.session_state.pagina_atual in opcoes_menu else 0
        escolha = st.radio("Navegação:", opcoes_menu, index=idx_menu)
        
        if escolha != st.session_state.pagina_atual:
            st.session_state.pagina_atual = escolha; st.rerun()
            
        st.write("---")
        if st.button("🚪 Sair", use_container_width=True):
            st.session_state.authenticated = False; st.rerun()

    if st.session_state.pagina_atual == "Página Inicial": tela_inicial()
    elif st.session_state.pagina_atual == "Orçamentos": tela_orcamentos()
    elif st.session_state.pagina_atual == "Controle Financeiro": tela_financeira()
    elif st.session_state.pagina_atual == "Configurações": tela_configuracoes()
