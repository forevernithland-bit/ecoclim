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
EVOLUTION_API_KEY = "EcoclimBot2026!"
INSTANCE_NAME = "ECOCLIM_01"

# ==========================================
# ESTRUTURA DOS DADOS QUE O ROBÔ VAI MANDAR
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
        
    endpoint = f"{EVOLUTION_BASE_URL}/media/sendMedia/{INSTANCE_NAME}"
    
    headers = {
        "apikey": EVOLUTION_API_KEY,
        "Content-Type": "application/json"
    }
    
    # Payload configurado para enviar documento via URL pública do Google Drive
    payload = {
        "number": num_limpo,
        "mediaMessage": {
            "mediatype": "document",
            "media": url_pdf,
            "fileName": nome_arquivo,
            "caption": f"Olá, {nome_cliente}! Conforme conversamos, segue em anexo a sua proposta comercial detalhada da Ecoclim. Qualquer dúvida estou à disposição!"
        },
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
# ROTA DE GERAÇÃO E ENVIO DE ORÇAMENTO
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
