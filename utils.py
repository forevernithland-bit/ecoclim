import streamlit as st
import pandas as pd
import datetime
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER
import urllib.request
import json
import re

try:
    import PyPDF2
except ImportError:
    pass

# IMPORTAÇÕES OAUTH (LOGIN VITALÍCIO)
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# ==========================================
# FUNÇÕES DE SEGURANÇA E DATA
# ==========================================
def safe_float(val):
    try:
        if pd.isna(val) or val is None or str(val).strip() == '': 
            return 0.0
        return float(val)
    except:
        return 0.0

hoje = datetime.date.today()
ano_atual = hoje.year
meses_pt = ['JANEIRO', 'FEVEREIRO', 'MARÇO', 'ABRIL', 'MAIO', 'JUNHO', 'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO']
mes_hoje_idx = hoje.month
mes_atual_nome = meses_pt[mes_hoje_idx - 1]

def init_connection():
    from supabase import create_client
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

# ==========================================
# INTEGRAÇÃO GOOGLE DRIVE E CALENDAR (MOTOR VITALÍCIO)
# ==========================================
MAIN_DRIVE_FOLDER_ID = '1rdCO-d0CTF4UPQ1Vddxr0loCgqYaXE2l'

def get_drive_service():
    """Autentica no Drive usando o seu login definitivo (OAuth)"""
    try:
        oauth_info = st.secrets["google_oauth"]
        creds = Credentials(
            token=None,
            refresh_token=oauth_info["refresh_token"],
            client_id=oauth_info["client_id"],
            client_secret=oauth_info["client_secret"],
            token_uri="https://oauth2.googleapis.com/token"
        )
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"Erro na conexão do Drive: {e}")
        return None

def get_calendar_service():
    """Autentica no Calendar usando o seu login definitivo (OAuth)"""
    try:
        oauth_info = st.secrets["google_oauth"]
        creds = Credentials(
            token=None,
            refresh_token=oauth_info["refresh_token"],
            client_id=oauth_info["client_id"],
            client_secret=oauth_info["client_secret"],
            token_uri="https://oauth2.googleapis.com/token"
        )
        return build('calendar', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"Erro na conexão do Calendário: {e}")
        return None

def get_or_create_nested_folder(service, parent_id, path_list):
    current_id = parent_id
    for folder_name in path_list:
        query = f"'{current_id}' in parents and name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        response = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        files = response.get('files', [])
        if files:
            current_id = files[0].get('id')
        else:
            folder_metadata = {'name': folder_name, 'parents': [current_id], 'mimeType': 'application/vnd.google-apps.folder'}
            folder = service.files().create(body=folder_metadata, fields='id').execute()
            current_id = folder.get('id')
    return current_id

def upload_to_drive(file_buffer, filename, mimetype, folder_path):
    try:
        service = get_drive_service()
        if not service: return False, "Serviço do Google Drive indisponível."
        if isinstance(folder_path, str): folder_path = [folder_path]
        subfolder_id = get_or_create_nested_folder(service, MAIN_DRIVE_FOLDER_ID, folder_path)
        
        file_metadata = {'name': filename, 'parents': [subfolder_id]}
        buffer_puro = BytesIO(file_buffer.getvalue())
        media = MediaIoBaseUpload(buffer_puro, mimetype=mimetype, resumable=True)
        
        uploaded_file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return True, uploaded_file.get('id')
    except Exception as e:
        return False, str(e)

def list_drive_files(folder_path):
    try:
        service = get_drive_service()
        if not service: return []
        if isinstance(folder_path, str): folder_path = [folder_path]
        subfolder_id = get_or_create_nested_folder(service, MAIN_DRIVE_FOLDER_ID, folder_path)
        
        query = f"'{subfolder_id}' in parents and trashed=false and mimeType != 'application/vnd.google-apps.folder'"
        response = service.files().list(q=query, spaces='drive', fields='files(id, name, size, createdTime, webViewLink)').execute()
        return response.get('files', [])
    except:
        return []

def delete_drive_file(file_id):
    try:
        service = get_drive_service()
        if not service: return False
        service.files().delete(fileId=file_id).execute()
        return True
    except:
        return False

# ==========================================
# FUNÇÕES FINANCEIRAS E CATÁLOGOS (MANTIDAS 100%)
# ==========================================
def load_year_data(nome_tabela, contas_padrao, ano):
    supabase = st.session_state.supabase
    try:
        res = supabase.table(nome_tabela).select("*").eq("ano", ano).execute()
        df_banco = pd.DataFrame(res.data)
        if df_banco.empty:
            df_novo = pd.DataFrame({"MESES": contas_padrao})
            for mes in meses_pt: df_novo[mes] = 0.0
            return df_novo
        df_banco.columns = df_banco.columns.str.upper()
        colunas_ordenadas = ["MESES"] + meses_pt
        for col in colunas_ordenadas:
            if col not in df_banco.columns: df_banco[col] = 0.0 if col != "MESES" else ""
        return df_banco[colunas_ordenadas]
    except:
        return pd.DataFrame({"MESES": contas_padrao, **{m: 0.0 for m in meses_pt}})

def save_to_supabase(nome_tabela, df, ano):
    supabase = st.session_state.supabase
    dados_finais = []
    for _, linha in df.iterrows():
        registro = {"ano": ano, "MESES": linha["MESES"]}
        for mes_coluna in meses_pt: registro[mes_coluna] = float(linha[mes_coluna]) if pd.notna(linha[mes_coluna]) else 0.0
        dados_finais.append(registro)
    try:
        supabase.table(nome_tabela).delete().eq("ano", ano).execute()
        supabase.table(nome_tabela).insert(dados_finais).execute()
    except Exception as e: st.error(f"Erro ao salvar: {e}")

def load_catalog(nome_tabela):
    supabase = st.session_state.supabase
    colunas_corretas = ["Item", "Descrição", "Custo (R$)", "Margem (%)", "Lucro (R$)", "Venda (R$)"]
    try:
        res = supabase.table(nome_tabela).select("*").order("item").execute()
        df = pd.DataFrame(res.data)
        mapeamento = {"item": "Item", "descricao": "Descrição", "custo": "Custo (R$)", "margem": "Margem (%)", "lucro": "Lucro (R$)", "venda": "Venda (R$)"}
        if df.empty: return pd.DataFrame(columns=colunas_corretas)
        df = df.rename(columns={k: v for k, v in mapeamento.items() if k in df.columns})
        for coluna in colunas_corretas:
            if coluna not in df.columns:
                df[coluna] = "" if "Desc" in coluna or "Item" in coluna else 0.0
        return df[colunas_corretas]
    except:
        return pd.DataFrame(columns=colunas_corretas)

def save_catalog(nome_tabela, df):
    supabase = st.session_state.supabase
    lista_dados = []
    for _, linha in df.iterrows():
        if linha.get('Item') and str(linha['Item']).strip() != "":
            lista_dados.append({
                "item": linha['Item'], "descricao": str(linha.get('Descrição', '')),
                "custo": float(linha.get('Custo (R$)', 0.0)), "margem": float(linha.get('Margem (%)', 0.0)),
                "lucro": float(linha.get('Lucro (R$)', 0.0)), "venda": float(linha.get('Venda (R$)', 0.0))
            })
    try:
        supabase.table(nome_tabela).delete().neq("item", "___VAZIO___").execute()
        if lista_dados: supabase.table(nome_tabela).insert(lista_dados).execute()
    except Exception as e: st.error(f"Erro ao salvar catálogo: {e}")

def to_br_currency(valor, incluir_simbolo=True):
    try: valor_float = float(valor)
    except: valor_float = 0.0
    res = f"{valor_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {res}" if incluir_simbolo else res

def parse_br_currency(texto_valor):
    if isinstance(texto_valor, (int, float)): return float(texto_valor)
    s = str(texto_valor).replace("R$", "").strip().replace(".", "").replace(",", ".")
    try: return float(s)
    except: return 0.0

def load_taxas():
    try:
        res = st.session_state.supabase.table('catalogo_taxas').select("*").execute()
        df = pd.DataFrame(res.data)
        if df.empty: return pd.DataFrame(columns=["Item", "Taxa (%)"])
        return df.rename(columns={"item": "Item", "taxa_percentual": "Taxa (%)"})
    except: return pd.DataFrame(columns=["Item", "Taxa (%)"])

def save_taxas(df):
    dados = [{"item": r['Item'], "taxa_percentual": float(r.get('Taxa (%)', 0.0))} for _, r in df.iterrows() if r.get('Item')]
    st.session_state.supabase.table('catalogo_taxas').delete().neq("item", "___").execute()
    if dados: st.session_state.supabase.table('catalogo_taxas').insert(dados).execute()

def buscar_cep(cep):
    cep = str(cep).replace('-', '').replace('.', '').strip()
    if len(cep) != 8: return None
    try:
        url = f"https://viacep.com.br/ws/{cep}/json/"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            dados = json.loads(response.read().decode('utf-8'))
            if "erro" not in dados: return dados
    except: pass
    return None

# ==========================================
# GERAÇÃO DE PDF (ORÇAMENTO)
# ==========================================
def gerar_pdf_orcamento(nome, tel, capa, df_items, d_s, v_s, d_o, v_o, total, obs, mostrar_un):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    largura, altura = A4
    
    try: p.drawImage("logo.png", 2*cm, altura - 3.5*cm, width=4*cm, preserveAspectRatio=True, mask='auto')
    except: p.setFont("Helvetica-Bold", 16); p.drawString(2*cm, altura - 2.5*cm, "ECOCLIM")
    
    p.setFont("Helvetica-Bold", 14); p.drawString(largura - 9*cm, altura - 1.5*cm, "PROPOSTA COMERCIAL")
    p.setFont("Helvetica", 8); p.setFillColor(colors.grey)
    p.drawString(largura - 9*cm, altura - 2.1*cm, "WWW.ECOCLIM.COM.BR"); p.drawString(largura - 9*cm, altura - 2.5*cm, "COMERCIAL@ECOCLIM.COM.BR")
    
    p.setFillColor(colors.black); p.setFont("Helvetica", 9)
    p.drawString(largura - 9*cm, altura - 3.5*cm, f"Data: {datetime.date.today().strftime('%d/%m/%Y')}")
    p.drawString(largura - 9*cm, altura - 4.0*cm, "Validade da Proposta: 15 dias")
    
    y = altura - 5.5*cm
    p.setFillColor(colors.HexColor("#f0f0f0")); p.rect(2*cm, y - 1.5*cm, largura - 4*cm, 2*cm, fill=1, stroke=0)
    p.setFillColor(colors.black); p.setFont("Helvetica-Bold", 10); p.drawString(2.3*cm, y, "DADOS DO CLIENTE")
    p.setFont("Helvetica", 10); p.drawString(2.3*cm, y - 0.5*cm, f"Nome: {nome}"); p.drawString(2.3*cm, y - 1*cm, f"WhatsApp: {tel}")
    
    y -= 2.2*cm
    img_map = {
        "Aquecedor Solar Tradicional": "aquecedor_tradicional.jpg", "Aquecedor Solar a Vácuo Acoplado": "vacuo_acoplado.jpg",
        "Aquecedor Solar Modular": "modular.jpg", "Aquecedor de Piscina - Tradicional": "piscina_tradicional.jpg",
        "Aquecedor de Piscina - Trocador de Calor": "piscina_trocador.jpg", "Sistema de Pressurização": "pressurizacao.jpg"
    }
    try: p.drawImage(img_map.get(capa, ""), 2*cm, y - 5.5*cm, width=largura-4*cm, height=5.5*cm, preserveAspectRatio=True)
    except: pass
    
    y -= 6.5*cm
    p.setFillColor(colors.HexColor("#004488")); p.rect(2*cm, y, largura - 4*cm, 0.7*cm, fill=1, stroke=0)
    p.setFillColor(colors.white); p.setFont("Helvetica-Bold", 11); p.drawString(2.3*cm, y + 0.2*cm, "1. EQUIPAMENTOS")
    
    y -= 0.6*cm; p.setFillColor(colors.black); p.setFont("Helvetica-Bold", 9)
    p.drawString(2.3*cm, y - 0.3*cm, "Item")
    p.drawString(12.5*cm, y - 0.3*cm, "Qtd")
    
    if mostrar_un:
        p.drawRightString(largura - 4.5*cm, y - 0.3*cm, "V. Un.")
        p.drawRightString(largura - 2.3*cm, y - 0.3*cm, "Subtotal")
        
    y -= 0.8*cm
    
    total_equipamentos = 0.0
    
    for _, row in df_items.iterrows():
        if row.get('Quantidade', 0) > 0:
            p_base = str(row.get('Produto da Base', '')).strip()
            if p_base.upper() in ['', 'NONE', 'NAN', 'OUTRO']:
                item = str(row.get('Produto Manual', '')).strip()
            else:
                item = p_base
                
            if not item: 
                item = str(row.get('Item', '')).strip()
            
            p.setFont("Helvetica-Bold", 9); p.drawString(2.3*cm, y, str(item)[:60])
            p.setFont("Helvetica", 9); p.drawString(12.8*cm, y, str(int(row.get('Quantidade', 0))))
            
            v_total_item = safe_float(row.get('Venda Total', 0))
            total_equipamentos += v_total_item
            
            if mostrar_un:
                v_un = row.get('Venda (R$)', row.get('Venda Un.', 0))
                p.drawRightString(largura - 4.5*cm, y, to_br_currency(v_un))
                p.drawRightString(largura - 2.3*cm, y, to_br_currency(v_total_item))
                
            y -= 0.4*cm
            desc = str(row.get('Descrição', ""))
            if desc and desc.lower() != "nan":
                p.setFont("Helvetica", 8); p.setFillColor(colors.grey)
                for l in desc.split('\n'): p.drawString(2.3*cm, y, l.strip()); y -= 0.35*cm
                p.setFillColor(colors.black)
            y -= 0.2*cm
            
    y -= 0.2*cm
    p.setFont("Helvetica-Bold", 10)
    p.drawRightString(largura - 6.0*cm, y, "Subtotal de Equipamentos:")
    p.drawRightString(largura - 2.3*cm, y, to_br_currency(total_equipamentos))
    
    y -= 1.0*cm 
    p.setFillColor(colors.HexColor("#004488")); p.rect(2*cm, y, largura - 4*cm, 0.7*cm, fill=1, stroke=0)
    p.setFillColor(colors.white); p.setFont("Helvetica-Bold", 11); p.drawString(2.3*cm, y + 0.2*cm, "2. SERVIÇOS")
    y -= 0.8*cm; p.setFillColor(colors.black); p.setFont("Helvetica", 10)
    
    if d_s:
        p.drawRightString(largura - 2.3*cm, y, to_br_currency(v_s))
            
        for l in d_s.split('\n'): p.drawString(2.3*cm, y, l); y -= 0.45*cm
    else:
        p.drawString(2.3*cm, y, "Nenhum serviço selecionado."); y -= 0.45*cm
        
    y -= 0.5*cm 
    p.setFillColor(colors.HexColor("#004488")); p.rect(2*cm, y, largura - 4*cm, 0.7*cm, fill=1, stroke=0)
    p.setFillColor(colors.white); p.setFont("Helvetica-Bold", 11); p.drawString(2.3*cm, y + 0.2*cm, "3. OUTROS / TERCEIROS")
    y -= 0.8*cm; p.setFillColor(colors.black); p.setFont("Helvetica", 10)
    
    if d_o:
        p.drawRightString(largura - 2.3*cm, y, to_br_currency(v_o))
            
        for l in d_o.split('\n'): p.drawString(2.3*cm, y, l); y -= 0.45*cm
    else:
        p.drawString(2.3*cm, y, "Nenhum item adicional selecionado."); y -= 0.45*cm
        
    y -= 1.0*cm; p.setFillColor(colors.HexColor("#f0f0f0")); p.rect(2*cm, y - 0.2*cm, largura - 4*cm, 1.2*cm, fill=1, stroke=0)
    p.setFillColor(colors.black); p.setFont("Helvetica-Bold", 12); p.drawString(2.3*cm, y + 0.2*cm, "INVESTIMENTO TOTAL"); p.drawRightString(largura - 2.3*cm, y + 0.2*cm, to_br_currency(total))
    
    y -= 1.8*cm; p.setFillColor(colors.red); p.setFont("Helvetica-Bold", 10); p.drawString(2*cm, y, "OBSERVAÇÕES:"); p.setFont("Helvetica", 9); p.setFillColor(colors.black); p.drawString(2*cm, y - 0.5*cm, str(obs)[:100])
    
    p.save()
    buffer.seek(0)
    return buffer

# ==========================================
# GERAÇÃO DE PDF (CONTRATO INTELIGENTE)
# ==========================================
def gerar_pdf_contrato(nome, doc, tipo_cliente, endereco, objeto, df_items, mat_inclusos, forma_pagamento, obs_pagamento, data_termino, val_base, val_inst, val_hidr, val_outros, desc_outros):
    buffer = BytesIO()
    doc_pdf = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    
    style_normal = ParagraphStyle('Normal_J', parent=styles['Normal'], alignment=TA_JUSTIFY, spaceAfter=8, fontSize=10, leading=14)
    style_title = ParagraphStyle('Title_C', parent=styles['Heading2'], alignment=TA_CENTER, spaceAfter=15, textColor=colors.HexColor("#004488"))
    style_h3 = ParagraphStyle('H3', parent=styles['Heading3'], spaceBefore=12, spaceAfter=6, fontSize=11, textColor=colors.black)
    style_bullet = ParagraphStyle('Bullet', parent=style_normal, leftIndent=15, bulletIndent=5)

    story = []

    try: 
        img = RLImage("logo.png", width=4.5*cm, height=2.2*cm)
        img.hAlign = 'CENTER'
        story.append(img)
        story.append(Spacer(1, 0.5*cm))
    except: 
        story.append(Paragraph("<b>ECOCLIM</b>", style_title))

    story.append(Paragraph("<b>CONTRATO DE FORNECIMENTO E PRESTAÇÃO DE SERVIÇOS</b>", style_title))
    
    story.append(Paragraph("Pelo presente instrumento particular, as parties abaixo qualificadas firmam o presente CONTRATO:", style_normal))
    story.append(Paragraph("A <b>ECOCLIM</b> com sede na cidade de Santa Luzia, MG, Av. Brasília, 2731 - Duquesa I, no CNPJ 40.111.279/0001-03, endereço eletrônico: comercial@ecoclim.com.br, doravante designada <b>CONTRATADA</b> e de outro lado;", style_normal))
    
    doc_tipo = "inscrito sob o CPF" if tipo_cliente == "Pessoa Física" else "inscrita sob o CNPJ"
    story.append(Paragraph(f"<b>{nome}</b>, {tipo_cliente.lower()}, {doc_tipo} {doc}, situada na {endereco}, doravante designado(a) <b>CONTRATANTE</b>.", style_normal))

    if objeto.strip():
        story.append(Paragraph("<b>1. OBJETO DO CONTRATO</b>", style_h3))
        story.append(Paragraph(objeto.strip(), style_normal))

    story.append(Paragraph("<b>2. EQUIPAMENTOS E SERVIÇOS FORNECIDOS</b>", style_h3))
    for _, row in df_items.iterrows():
        qtd = safe_float(row.get('Qtd', 0))
        if qtd > 0:
            item_nome = row.get('Item', '')
            desc = str(row.get('Descrição', '')).replace('\n', ', ')
            texto_item = f"<b>{int(qtd)}x {item_nome}</b>"
            if desc and desc != 'nan': texto_item += f" - {desc}"
            story.append(Paragraph(f"• {texto_item}", style_bullet))
            
    mat_txt = "Materiais hidráulicos inclusos na proposta." if mat_inclusos == "Sim" else "Materiais hidráulicos não inclusos na proposta."
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(f"<i>{mat_txt}</i>", style_normal))

    story.append(Paragraph("<b>3. VALOR DO CONTRATO</b>", style_h3))
    total_contrato = val_base + val_inst + val_hidr + val_outros
    
    story.append(Paragraph("Abaixo a discriminação dos valores presentes neste contrato:", style_normal))
    story.append(Paragraph(f"• Equipamentos / Valor Base: <b>{to_br_currency(val_base)}</b>", style_bullet))
    
    if val_inst > 0: story.append(Paragraph(f"• Instalação: <b>{to_br_currency(val_inst)}</b>", style_bullet))
    if val_hidr > 0: story.append(Paragraph(f"• Materiais Hidráulicos: <b>{to_br_currency(val_hidr)}</b>", style_bullet))
    if val_outros > 0:
        desc_text = f" ({desc_outros})" if desc_outros else ""
        story.append(Paragraph(f"• Outros Serviços{desc_text}: <b>{to_br_currency(val_outros)}</b>", style_bullet))
        
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(f"O valor total do presente contrato é de <b>{to_br_currency(total_contrato)}</b>.", style_normal))
    story.append(Paragraph(f"Forma de pagamento acordada: <b>{forma_pagamento}</b>.", style_normal))
    if obs_pagamento: story.append(Paragraph(f"Observações do Pagamento: {obs_pagamento}", style_normal))
    story.append(Paragraph("Nosso PIX é o CNPJ: <b>40.111.279/0001-03</b>", style_normal))

    story.append(Paragraph("<b>4. EXECUÇÃO DE SERVIÇOS E GARANTIA</b>", style_h3))
    for _, row in df_items.iterrows():
        qtd = safe_float(row.get('Qtd', 0))
        if qtd > 0:
            item_nome = row.get('Item', '')
            desc = str(row.get('Descrição', '')).replace('\n', ' ')
            if desc and desc != 'nan' and ('garantia' in desc.lower() or 'anos' in desc.lower()):
                story.append(Paragraph(f"• <b>{item_nome}:</b> {desc}.", style_bullet))
    
    dt_term_str = data_termino.strftime('%d/%m/%Y') if data_termino else "conclusão da obra"
    story.append(Paragraph(f"• <b>Serviço de instalação:</b> Garantia de 90 dias a contar da data de término da instalação ({dt_term_str}).", style_bullet))

    story.append(Paragraph("<b>CLÁUSULA 5 – DAS OBRIGAÇÕES E RESPONSABILIDADES DO CONTRATANTE</b>", style_h3))
    story.append(Paragraph("Para a viabilização da instalação e o bom funcionamento do sistema, o CONTRATANTE compromete-se a:", style_normal))
    obs_list = [
        "<b>Acompanhamento Técnico:</b> Manter no local da obra, durante o período de execução, um representante capaz, com autorização para fornecer instruções e dar aceite ao final do serviço.",
        "<b>Infraestrutura Elétrica e Hidráulica:</b> Disponibilizar, sob sua exclusiva responsabilidade e custo, os pontos de energia para o sistema de pressurização e resistência de apoio.",
        "<b>Autorizações e Condomínios:</b> Providenciar todas as autorizações junto à administração do condomínio.",
        "<b>Logística de Materiais:</b> Informar e disponibilizar espaço adequado para o içamento de materiais e equipamentos.",
        "<b>Descarte de Resíduos:</b> Providenciar caçamba ou local adequado para descarte de embalagens.",
        "<b>Reposição de Telhas:</b> Disponibilizar telhas de reserva para substituição em caso de trincas.",
        "<b>Testes e Entrega:</b> Realizar o teste final de funcionamento em conjunto com a equipe técnica da CONTRATADA."
    ]
    for obs in obs_list: story.append(Paragraph(f"• {obs}", style_bullet))

    story.append(Paragraph("<b>CLÁUSULA 6 – DOS PAGAMENTOS E PENALIDADES</b>", style_h3))
    story.append(Paragraph("<b>Mora e Multa:</b> O atraso em qualquer das parcelas pactuadas de pagamento sujeitará o CONTRATANTE ao pagamento de multa moratória de 2% (dois por cento) sobre o valor da parcela vencida, acrescida de juros de mora de 1% (um por cento) ao mês e correção monetária pelo índice IGPM.", style_bullet))

    story.append(Paragraph("<b>CLÁUSULA 7 – DA GARANTIA E LIMITAÇÃO DE RESPONSABILIDADE</b>", style_h3))
    g_list = [
        "<b>Garantia dos Equipamentos:</b> A garantia dos produtos é de responsabilidade exclusiva do fabricante, conforme manuais disponíveis. Validade condicionada à instalação correta.",
        "<b>Garantia de Instalação:</b> A CONTRATADA oferece o prazo de 90 dias de garantia sobre os serviços de mão de obra de instalação a ser contada da data de término da instalação.",
        "<b>Exclusões de Garantia:</b> Mau uso, negligência, intervenções não autorizadas, fenômenos naturais extraordinários (granizo, ventos, raios), ou pressão fora dos padrões.",
        "<b>Vazamentos e Consumo:</b> Em caso de suspeita de vazamento, o CONTRATANTE deve fechar imediatamente os registros e comunicar a CONTRATADA. Não nos responsabilizamos por aumento de contas ou danos secundários.",
        "<b>Riscos Inerentes ao Telhado:</b> O cliente declara estar ciente que a instalação exige trânsito sobre o telhado, existindo risco inerente de quebra de telhas. A CONTRATADA limita-se a substituir as telhas quebradas fornecidas pelo cliente."
    ]
    for g in g_list: story.append(Paragraph(f"• {g}", style_bullet))

    story.append(Paragraph("<b>CLÁUSULA 8 – DO FORO</b>", style_h3))
    story.append(Paragraph("Fica eleito o foro da Comarca de Santa Luzia/MG para dirimir quaisquer controvérsias oriundas deste contrato, com renúncia expressa a qualquer outro, por mais privilegiado que seja.", style_normal))

    story.append(Spacer(1, 1.0*cm))
    story.append(Paragraph(f"Santa Luzia, MG, {datetime.date.today().strftime('%d de %B de %Y').lower()}.", style_normal))
    story.append(Spacer(1, 1.5*cm))
    
    try:
        img_ass = RLImage("assinatura.png", width=6.0*cm, height=3.3*cm)
        img_ass.hAlign = 'CENTER'
    except:
        img_ass = "______________________________________________\nCONTRATADA\nECOCLIM SOLUÇÕES SUSTENTÁVEIS"
        
    t_data = [
        ["______________________________________________", img_ass],
        [f"CONTRATANTE\n{nome}", ""]
    ]
    t = Table(t_data, colWidths=[8.5*cm, 8.5*cm])
    t.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
    ]))
    story.append(t)

    doc_pdf.build(story)
    buffer.seek(0)
    return buffer

# ==========================================
# EXTRAÇÃO INTELIGENTE DE BOLETOS
# ==========================================
def extrair_dados_boleto(file_buffer):
    """Lê o PDF e tenta encontrar a data de vencimento e valor do documento."""
    try:
        file_buffer.seek(0)
        reader = PyPDF2.PdfReader(file_buffer)
        texto = ""
        for page in reader.pages:
            texto += page.extract_text() + "\n"

        data_venc = None
        match_data = re.search(r'Vencimento\s*(\d{2}/\d{2}/\d{4})', texto, re.IGNORECASE)
        if not match_data:
            match_data = re.search(r'\b(\d{2}/\d{2}/\d{4})\b', texto)
        if match_data:
            data_venc = match_data.group(1)

        valor_float = 0.0
        match_valor = re.search(r'Valor do Documento.*?(\d{1,3}(?:\.\d{3})*,\d{2})', texto, re.IGNORECASE | re.DOTALL)
        if not match_valor:
            match_valor = re.search(r'R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})', texto)
        
        if match_valor:
            valor_str = match_valor.group(1).replace('.', '').replace(',', '.')
            valor_float = float(valor_str)

        file_buffer.seek(0) 
        return data_venc, valor_float
    except Exception as e:
        file_buffer.seek(0)
        return None, 0.0

# ==========================================
# SINCRONIZAÇÃO INTELIGENTE COM GOOGLE CALENDAR
# ==========================================
def sincronizar_boletos_com_calendar():
    """Sincroniza todos os lembretes do banco com o Google Calendar usando o motor vitalício"""
    service = get_calendar_service()
    if not service:
        return

    try:
        res = st.session_state.supabase.table('boletos_fornecedores').select('*').execute()
        boletos_db = res.data if res.data else []
        db_ids = {b['id'] for b in boletos_db}

        events_result = service.events().list(calendarId='primary', q='[Ecoclim ID:', singleEvents=True).execute()
        events_calendar = events_result.get('items', [])
        
        calendar_map = {}
        for ev in events_calendar:
            desc = ev.get('description', '')
            match = re.search(r'\[Ecoclim ID:\s*(\d+)\]', desc)
            if match:
                ev_id_db = int(match.group(1))
                calendar_map[ev_id_db] = ev['id']

        hoje_dt = datetime.date.today()

        for b in boletos_db:
            id_db = b['id']
            cliente = b['cliente']
            try:
                valor = float(b['valor'])
            except:
                valor = 0.0
                
            status = b['status']
            
            try:
                venc_dt = datetime.datetime.strptime(b['vencimento'], "%Y-%m-%d").date()
            except:
                continue
            
            description = f"Identificador interno do ERP Ecoclim: [Ecoclim ID: {id_db}]"
            valor_formatado = f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

            if status == 'Pago':
                start_date = venc_dt
                end_date = venc_dt + datetime.timedelta(days=1)
                summary = f"✅ [PAGO] Boleto: {cliente} - {valor_formatado}"
                color_id = '10' # Verde (Basil)
            else:
                diff_days = (venc_dt - hoje_dt).days
                
                if diff_days > 1:
                    start_date = venc_dt
                    end_date = venc_dt + datetime.timedelta(days=1)
                    summary = f"📅 [PENDENTE] Boleto: {cliente} - {valor_formatado}"
                    color_id = '1' # Azul (Lavender)
                elif diff_days == 1:
                    start_date = venc_dt
                    end_date = venc_dt + datetime.timedelta(days=1)
                    summary = f"⏳ [VENCE AMANHÃ] Boleto: {cliente} - {valor_formatado}"
                    color_id = '5' # Amarelo (Banana)
                elif diff_days == 0:
                    start_date = hoje_dt
                    end_date = hoje_dt + datetime.timedelta(days=1)
                    summary = f"⚠️ [VENCE HOJE] Boleto: {cliente} - {valor_formatado}"
                    color_id = '6' # Laranja (Tangerine)
                else:
                    start_date = hoje_dt
                    end_date = hoje_dt + datetime.timedelta(days=1)
                    summary = f"🚨 [ATRASADO] Boleto: {cliente} - {valor_formatado} (Venceu em {venc_dt.strftime('%d/%m')})"
                    color_id = '11' # Vermelho (Tomato)

            event_body = {
                'summary': summary,
                'description': description,
                'start': {'date': start_date.strftime('%Y-%m-%d')},
                'end': {'date': end_date.strftime('%Y-%m-%d')},
                'colorId': color_id
            }

            if id_db in calendar_map:
                service.events().update(calendarId='primary', eventId=calendar_map[id_db], body=event_body).execute()
            else:
                service.events().insert(calendarId='primary', body=event_body).execute()

        for ev_id_db, ev_cal_id in calendar_map.items():
            if ev_id_db not in db_ids:
                service.events().delete(calendarId='primary', eventId=ev_cal_id).execute()

    except Exception as e:
        pass
