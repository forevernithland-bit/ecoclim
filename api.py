from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import pandas as pd
import datetime
import requests
import utils

# Inicia a API
app = FastAPI(title="Ecoclim API - V2", description="API para integração com n8n, ERP e envio automático de PDF via Evolution API")

# Conecta no seu Supabase
supabase = utils.init_connection()

# CONFIGURAÇÕES CRÍTICAS DA EVOLUTION API (Com base na sua infraestrutura)
EVOLUTION_BASE_URL = "http://187.127.21.127:8080"
EVOLUTION_API_KEY = "E76FE78F42C9-411F-A6E5-EE8432420A65"
INSTANCE_NAME = "ERP"

# ==========================================
# ESTRUTURA DOS DADOS QUE O ROBÔ VAI MANDAR (MANUAL)
# ==========================================
class ItemOrcamento(BaseModel):
    produto: str
    quantidade: int
    preco_unidade: float
    descricao: Optional[str] = ""

class OrcamentoRequest(BaseModel):
    nome_cliente: str
    telefone: str
    itens: List[ItemOrcamento]
    com_instalacao: bool
    valor_instalacao: float = 0.0
    descricao_instalacao: Optional[str] = ""
    observacoes: Optional[str] = "Material hidráulico não incluso nesta proposta."

# ==========================================
# ESTRUTURA PARA O NOVO ORÇAMENTO VIA IA (KITS INTELIGENTES)
# ==========================================
class OrcamentoKitRequest(BaseModel):
    nome_cliente: str
    telefone: str
    nome_do_kit: str
    com_instalacao: bool
    observacoes: Optional[str] = "Material hidráulico não incluso nesta proposta."

# ==========================================
# FUNÇÃO AUXILIAR PARA DISPARAR O PDF VIA WHATSAPP
# ==========================================
def enviar_pdf_via_whatsapp(telefone_cliente: str, url_pdf: str, nome_arquivo: str, nome_cliente: str):
    """
    Envia o arquivo PDF gerado diretamente para o WhatsApp do cliente
    utilizando a sua instância conectada na Evolution API.
    """
    # Limpa o número de telefone para garantir o formato correto (apenas números)
    num_limpo = "".join(filter(str.isdigit, telefone_cliente))
    
    # Adiciona o código do país caso não exista
    if not num_limpo.startswith("55"):
        num_limpo = f"55{num_limpo}"
        
    endpoint = f"{EVOLUTION_BASE_URL}/message/sendMedia/{INSTANCE_NAME}"
    
    headers = {
        "apikey": EVOLUTION_API_KEY,
        "Content-Type": "application/json"
    }
    
    # Payload configurado para enviar documento via URL pública do Google Drive
    payload = {
        "number": num_limpo,
        "mediatype": "document",
        "mimetype": "application/pdf",
        "media": url_pdf,
        "fileName": nome_arquivo,
        "caption": f"Olá, {nome_cliente}! Conforme conversamos, segue em anexo a sua proposta comercial detalhada da Ecoclim. Qualquer dúvida estou à disposição!",
        "options": {
            "delay": 1200, # Delay sutil humano de 1.2 segundos
            "presence": "composing" # Mostra "digitando..." ou "enviando arquivo..." no zap
        }
    }
    
    try:
        response = requests.post(endpoint, json=payload, headers=headers)
        return response.status_code in [200, 201], response.json()
    except Exception as e:
        return False, str(e)

# ==========================================
# ROTA ORIGINAL: GERAÇÃO E ENVIO DE ORÇAMENTO MANUAL
# ==========================================
@app.post("/gerar-orcamento")
async def criar_orcamento_bot(req: OrcamentoRequest):
    try:
        # 1. Montar a tabela de itens para o PDF
        linhas_pdf = []
        total_equipamentos = 0.0
        
        for item in req.itens:
            v_tot = item.quantidade * item.preco_unidade
            total_equipamentos += v_tot
            
            linhas_pdf.append({
                "Produto da Base": item.produto,
                "Produto Manual": "",
                "Descrição": item.descricao,
                "Quantidade": item.quantidade,
                "Custo (R$)": 0.0,  # Oculto para segurança comercial
                "Venda (R$)": item.preco_unidade,
                "Custo Total": 0.0,
                "Venda Total": v_tot
            })
            
        df_itens = pd.DataFrame(linhas_pdf)
        
        # 2. Configurar Serviços e Instalação
        val_serv = req.valor_instalacao if req.com_instalacao else 0.0
        desc_serv = req.descricao_instalacao if req.com_instalacao else ""
        total_geral = total_equipamentos + val_serv
        
        # 3. Gerar o arquivo PDF usando o seu utils.py original
        pdf_buffer = utils.gerar_pdf_orcamento(
            nome=req.nome_cliente,
            tel=req.telefone,
            capa="Aquecedor Solar Tradicional", 
            df_items=df_itens,
            d_s=desc_serv,
            v_s=val_serv,
            d_o="",
            v_o=0.0,
            total=total_geral,
            obs=req.observacoes,
            mostrar_un=True
        )
        
        # 4. Salvar os dados no seu Supabase para aparecer no Painel do ERP
        string_data = datetime.datetime.now().strftime('%y%m%d-%H%M')
        numero_orc = f"ORC-BOT-{string_data}"
        
        snapshot_itens = []
        for item in req.itens:
            snapshot_itens.append({
                "Item": item.produto,
                "Qtd": item.quantidade,
                "Venda Un.": item.preco_unidade,
                "Descrição": item.descricao
            })
            
        payload = {
            "numero_orcamento": numero_orc,
            "nome_cliente": req.nome_cliente,
            "telefone_cliente": req.telefone,
            "valor_venda_total": total_geral,
            "status_projeto": "Orçamento Enviado",
            "detalhamento_itens": snapshot_itens,
            "data_conclusao": datetime.date.today().strftime('%Y-%m-%d'),
            "notas_internas": "Gerado automaticamente via Bot WhatsApp"
        }
        
        supabase.table("servicos_andamento").insert(payload).execute()
        
        # 5. Fazer upload do PDF para o Google Drive
        mes_atual = utils.mes_atual_nome
        nome_arquivo = f"ORC_{req.nome_cliente.replace(' ', '_')}_{string_data}.pdf"
        
        sucesso_drive, drive_id_ou_erro = utils.upload_to_drive(
            file_buffer=pdf_buffer,
            filename=nome_arquivo,
            mimetype="application/pdf",
            folder_path=["Orçamentos", mes_atual]
        )
        
        if not sucesso_drive:
            return {"sucesso": False, "erro": f"Erro ao salvar no Drive: {drive_id_ou_erro}"}

        # 6. Criar Link de Download Direto para a Evolution API consumir
        link_drive = f"https://drive.google.com/uc?export=download&id={drive_id_ou_erro}"
        
        # 7. ENVIAR DIRETAMENTE VIA WHATSAPP (Mágica da Automação)
        sucesso_whatsapp, retorno_whatsapp = enviar_pdf_via_whatsapp(
            telefone_cliente=req.telefone,
            url_pdf=link_drive,
            nome_arquivo=nome_arquivo,
            nome_cliente=req.nome_cliente
        )
        
        # 8. Devolver a resposta consolidada para o n8n/robô
        return {
            "sucesso": True,
            "mensagem": "Orçamento gerado, registrado no ERP e enviado ao WhatsApp!",
            "link_pdf_download": link_drive,
            "numero_orcamento": numero_orc,
            "valor_total_reais": total_geral,
            "whatsapp_enviado": sucesso_whatsapp,
            "detalhes_whatsapp": retorno_whatsapp
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# NOVA ROTA: GERAÇÃO DE ORÇAMENTO INTELIGENTE POR KIT (USADA PELO N8N)
# ==========================================
@app.post("/gerar-orcamento-kit")
async def gerar_orcamento_kit_bot(req: OrcamentoKitRequest):
    try:
        # 1. Buscar o Kit configurado no Supabase
        res_kit = supabase.table('config_kits_lote').select('*').eq('nome_kit', req.nome_do_kit).execute()
        
        if not res_kit.data:
            raise HTTPException(status_code=404, detail=f"O Kit '{req.nome_do_kit}' não foi encontrado na base de dados.")
            
        kit = res_kit.data[0]

        # 2. Carregar catálogos atualizados para puxar os preços de hoje
        db_produtos = utils.load_catalog('catalogo_produtos')
        db_servicos = utils.load_catalog('catalogo_servicos')

        # 3. Processar os itens do Kit e calcular valores
        linhas_pdf = []
        total_equipamentos = 0.0
        snapshot_itens = []
        
        itens_do_kit = kit.get('itens', [])
        
        for ik in itens_do_kit:
            p_nome = str(ik.get('Produto', '')).strip()
            p_qtd = int(ik.get('Quantidade', 1))
            
            p_preco = 0.0
            p_desc = ""
            
            # Cruzamento: Busca o preço e a descrição atualizada do produto
            match_p = db_produtos[db_produtos['Item'].astype(str).str.strip().str.upper() == p_nome.upper()]
            if not match_p.empty:
                try: 
                    p_preco = float(match_p['Venda (R$)'].values[0])
                except: 
                    pass
                p_desc = str(match_p['Descrição'].values[0])
                if p_desc.lower() == 'nan': 
                    p_desc = ""
                    
            subtotal_item = p_preco * p_qtd
            total_equipamentos += subtotal_item
            
            # Prepara a linha para a geração do PDF
            linhas_pdf.append({
                "Produto da Base": p_nome,
                "Produto Manual": "",
                "Descrição": p_desc,
                "Quantidade": p_qtd,
                "Custo (R$)": 0.0,
                "Venda (R$)": p_preco,
                "Custo Total": 0.0,
                "Venda Total": subtotal_item
            })
            
            # Prepara a linha para salvar no histórico do ERP
            snapshot_itens.append({
                "Item": p_nome,
                "Qtd": p_qtd,
                "Venda Un.": p_preco,
                "Descrição": p_desc
            })
            
        df_itens = pd.DataFrame(linhas_pdf)

        # 4. Processar Serviço e Instalação (se solicitado pela IA)
        val_serv = 0.0
        desc_serv = ""
        
        if req.com_instalacao:
            servico_nome = str(kit.get('servico_base', '')).strip()
            if servico_nome:
                match_s = db_servicos[db_servicos['Item'].astype(str).str.strip().str.upper() == servico_nome.upper()]
                if not match_s.empty:
                    try: 
                        val_serv = float(match_s['Venda (R$)'].values[0])
                    except: 
                        pass
                    nome_real_serv = str(match_s['Item'].values[0])
                    desc_real_serv = str(match_s['Descrição'].values[0])
                    
                    desc_serv = f"{nome_real_serv}\n{desc_real_serv}"
                    if desc_serv.endswith('\nnan') or desc_serv.endswith('\n'): 
                        desc_serv = nome_real_serv

        total_geral = total_equipamentos + val_serv
        capa_modelo = str(kit.get('modelo_capa', 'Aquecedor Solar Tradicional'))

        # 5. Gerar o arquivo PDF
        pdf_buffer = utils.gerar_pdf_orcamento(
            nome=req.nome_cliente,
            tel=req.telefone,
            capa=capa_modelo,
            df_items=df_itens,
            d_s=desc_serv,
            v_s=val_serv,
            d_o="",
            v_o=0.0,
            total=total_geral,
            obs=req.observacoes,
            mostrar_un=True 
        )

        # 6. Salvar Rastro no ERP (Painel de Serviços em Andamento)
        string_data = datetime.datetime.now().strftime('%y%m%d-%H%M')
        numero_orc = f"ORC-IA-{string_data}"
        
        payload_erp = {
            "numero_orcamento": numero_orc,
            "nome_cliente": req.nome_cliente,
            "telefone_cliente": req.telefone,
            "valor_venda_total": total_geral,
            "status_projeto": "Orçamento Enviado",
            "detalhamento_itens": snapshot_itens,
            "data_conclusao": datetime.date.today().strftime('%Y-%m-%d'),
            "notas_internas": f"Gerado automaticamente pelo Agente IA via WhatsApp. (Kit Utilizado: {req.nome_do_kit})"
        }
        
        supabase.table("servicos_andamento").insert(payload_erp).execute()

        # 7. Upload para o Google Drive
        mes_atual = utils.mes_atual_nome
        nome_arquivo = f"ORC_{req.nome_cliente.replace(' ', '_')}_{string_data}.pdf"
        
        sucesso_drive, drive_id_ou_erro = utils.upload_to_drive(
            file_buffer=pdf_buffer,
            filename=nome_arquivo,
            mimetype="application/pdf",
            folder_path=["Orçamentos", mes_atual]
        )
        
        if not sucesso_drive:
            return {"sucesso": False, "erro": f"Erro ao salvar no Drive: {drive_id_ou_erro}"}

        # 8. Link Público e Envio via WhatsApp
        link_drive = f"https://drive.google.com/uc?export=download&id={drive_id_ou_erro}"
        
        sucesso_whatsapp, retorno_whatsapp = enviar_pdf_via_whatsapp(
            telefone_cliente=req.telefone,
            url_pdf=link_drive,
            nome_arquivo=nome_arquivo,
            nome_cliente=req.nome_cliente
        )
        
        return {
            "sucesso": True,
            "mensagem": f"Orçamento gerado pelo Kit '{req.nome_do_kit}' e enviado ao cliente!",
            "numero_orcamento": numero_orc,
            "link_pdf_download": link_drive,
            "valor_total_reais": total_geral,
            "whatsapp_enviado": sucesso_whatsapp,
            "detalhes_whatsapp": retorno_whatsapp
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
