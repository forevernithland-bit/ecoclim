import streamlit as st
import pandas as pd
import datetime
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_RIGHT, TA_LEFT
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

def obter_data_atual_br():
    """Retorna a data atual forçando o fuso horário de Brasília (GMT-3) de forma dinâmica."""
    tz_br = datetime.timezone(datetime.timedelta(hours=-3))
    return datetime.datetime.now(tz_br).date()

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

def get_supabase_client():
    """Tenta obter a conexão do Streamlit. Se falhar (API rodando no backend), cria uma nova."""
    try:
        return st.session_state.supabase
    except Exception:
        return init_connection()

def iniciar_conexao_consorbens():
    """Conexão de LEITURA com o Supabase do ERP CONSORBENS (projeto/banco
    diferente do Ecoclim) — usada para ler resultado_socios_mensal (linha
    'CONS INVESTIMENTOS' do Controle Financeiro). Usa os mesmos secrets já
    usados pelo próprio ERP Consorbens para ler/gravar suas tabelas
    (CONSORBENS_SUPABASE_URL / CONSORBENS_SUPABASE_KEY). Retorna None se não
    configurado — a integração fica desligada sem quebrar a tela."""
    try:
        from supabase import create_client
        url = st.secrets["CONSORBENS_SUPABASE_URL"]
        key = st.secrets["CONSORBENS_SUPABASE_KEY"]
        if not url or not key:
            return None
        return create_client(url, key)
    except Exception:
        return None

# ==========================================
# INTEGRAÇÃO GOOGLE DRIVE E CALENDAR (MOTOR VITALÍCIO)
# ==========================================
MAIN_DRIVE_FOLDER_ID = '1rdCO-d0CTF4UPQ1Vddxr0loCgqYaXE2l'
# Pastas específicas do Drive (IDs absolutos) onde os PDFs devem cair.
DRIVE_FOLDER_ORCAMENTOS = '1DySx6I2sMQ6OQNR74mwbTrAf2KuK2YI4'
DRIVE_FOLDER_CONTRATOS = '1s1pIqZ2MhlxKOQzjwNZwTU8SE3K5WnKb'

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
        file_id = uploaded_file.get('id')
        
        # ==========================================
        # CORREÇÃO: TORNAR O ARQUIVO PÚBLICO (QUALQUER PESSOA COM O LINK)
        # ==========================================
        try:
            permission = {'type': 'anyone', 'role': 'reader'}
            service.permissions().create(fileId=file_id, body=permission).execute()
        except Exception as e:
            pass # Se falhar a permissão, o arquivo já foi salvo pelo menos
            
        return True, file_id
    except Exception as e:
        return False, str(e)

def upload_to_drive_folder_id(file_buffer, filename, mimetype, folder_id):
    """Envia um arquivo direto para uma pasta específica do Drive (ID absoluto),
    sem aninhar sob MAIN_DRIVE_FOLDER_ID. Deixa acessível por link. Retorna
    (True, file_id) ou (False, erro)."""
    try:
        service = get_drive_service()
        if not service: return False, "Serviço do Google Drive indisponível."
        file_metadata = {'name': filename, 'parents': [folder_id]}
        buffer_puro = BytesIO(file_buffer.getvalue())
        media = MediaIoBaseUpload(buffer_puro, mimetype=mimetype, resumable=True)
        uploaded_file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        file_id = uploaded_file.get('id')
        try:
            service.permissions().create(fileId=file_id, body={'type': 'anyone', 'role': 'reader'}).execute()
        except Exception:
            pass
        return True, file_id
    except Exception as e:
        return False, str(e)

def drive_nome_existe(folder_id, filename):
    """True se já existe um arquivo com esse nome exato dentro da pasta.
    Usado para desambiguar (gerar _v2, _v3) quando se salva um novo a cada clique."""
    try:
        service = get_drive_service()
        if not service: return False
        safe = str(filename).replace("\\", "\\\\").replace("'", "\\'")
        q = f"'{folder_id}' in parents and name = '{safe}' and trashed = false"
        res = service.files().list(q=q, spaces='drive', fields='files(id)').execute()
        return len(res.get('files', [])) > 0
    except Exception:
        return False

def limpar_orcamentos_antigos(dias=183):
    """Manda para a LIXEIRA do Drive os PDFs de ORÇAMENTO com mais de `dias`
    dias (padrão ~6 meses), pela data de criação. Vai para a lixeira (reversível
    por ~30 dias), não é exclusão permanente. NUNCA mexe em contratos.
    Retorna o nº de arquivos movidos para a lixeira."""
    try:
        service = get_drive_service()
        if not service: return 0
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=dias)
        q = (f"'{DRIVE_FOLDER_ORCAMENTOS}' in parents and "
             "mimeType != 'application/vnd.google-apps.folder' and trashed = false")
        res = service.files().list(q=q, spaces='drive',
                                   fields='files(id, name, createdTime)', pageSize=1000).execute()
        movidos = 0
        for f in res.get('files', []):
            ct = f.get('createdTime')
            if not ct:
                continue
            try:
                dt = datetime.datetime.fromisoformat(str(ct).replace('Z', '+00:00'))
            except ValueError:
                continue
            if dt < cutoff:
                try:
                    service.files().update(fileId=f['id'], body={'trashed': True}).execute()
                    movidos += 1
                except Exception:
                    pass
        return movidos
    except Exception:
        return 0

def criar_atalho_drive(file_id, pasta_destino_id, nome_atalho):
    """Cria um ATALHO (não uma cópia) do arquivo file_id dentro de pasta_destino_id.
    O arquivo original continua na pasta onde já estava (Orçamentos/Contratos) —
    o atalho é só um ponteiro, então não duplica armazenamento nem fica
    desatualizado. Retorna (True, id_do_atalho) ou (False, erro)."""
    try:
        service = get_drive_service()
        if not service: return False, "Serviço do Google Drive indisponível."
        metadata = {
            'name': nome_atalho,
            'mimeType': 'application/vnd.google-apps.shortcut',
            'parents': [pasta_destino_id],
            'shortcutDetails': {'targetId': file_id},
        }
        atalho = service.files().create(body=metadata, fields='id').execute()
        return True, atalho.get('id')
    except Exception as e:
        return False, str(e)

def _buscar_arquivo_por_prefixo(folder_id, prefixo):
    """Procura, dentro de folder_id, o arquivo cujo nome comece com `prefixo`
    (usado para achar o PDF do orçamento já salvo, pelo número da proposta).
    Retorna {'id', 'name'} ou None."""
    if not prefixo:
        return None
    try:
        service = get_drive_service()
        if not service: return None
        safe = str(prefixo).replace("'", "\\'")
        q = f"'{folder_id}' in parents and name contains '{safe}' and trashed = false"
        res = service.files().list(q=q, spaces='drive', fields='files(id, name)').execute()
        arquivos = res.get('files', [])
        arquivos = [a for a in arquivos if a['name'].startswith(prefixo)]
        arquivos.sort(key=lambda a: a['name'])
        return arquivos[0] if arquivos else None
    except Exception:
        return None

def garantir_pasta_drive_cliente(servico):
    """Garante uma pasta no Drive ("Clientes/{numero}_{nome}", dentro da pasta
    raiz do sistema) para este serviço, criando-a na primeira vez que o status
    vira 'Em Andamento' (ou além) e tentando linkar por atalho o orçamento já
    enviado. Orçamento/Rascunho ainda não geram pasta. Idempotente: se já
    existe `drive_pasta_id`, só devolve ele. Retorna (pasta_id, erro) — erro
    vem preenchido (string) sempre que algo falhou, pra dar pra mostrar na
    tela em vez de falhar em silêncio."""
    status = str(servico.get('status_projeto', ''))
    if status in ('', 'Orçamento Enviado', 'Orçamento Cancelado', 'Rascunho', 'Rascunho Rápido'):
        return None, None
    pasta_existente = servico.get('drive_pasta_id')
    # `servico` costuma ser uma linha de pandas DataFrame — quando a coluna
    # tem uma mistura de valores reais e vazios entre os projetos, o pandas
    # troca o vazio por NaN (float) em vez de None. `pd.notna` pega os dois
    # casos; sem isso, `NaN` virava string "nan" e era usado como se fosse
    # um ID de pasta de verdade (daí o link quebrado pra .../folders/nan).
    if pd.notna(pasta_existente) and str(pasta_existente).strip():
        return pasta_existente, None
    try:
        service = get_drive_service()
        if not service: return None, "Serviço do Drive indisponível (verifique os secrets do Google OAuth)."
        # Mesmo cuidado do drive_pasta_id acima: `or` não pega NaN (é
        # "verdadeiro" pro Python), só None/"" — sem o pd.notna, um
        # numero_orcamento vazio virava a string literal "nan" e a busca do
        # atalho do orçamento falhava calada (procurava por um arquivo
        # chamado "nan", nunca achava, e não avisava ninguém).
        _numero_raw = servico.get('numero_orcamento')
        numero = str(_numero_raw).strip() if pd.notna(_numero_raw) else ''
        _nome_raw = servico.get('nome_cliente')
        nome_cliente = str(_nome_raw).strip() if pd.notna(_nome_raw) and str(_nome_raw).strip() else 'cliente'
        nome_pasta = f"{numero}_{nome_cliente}" if numero else nome_cliente
        pasta_id = get_or_create_nested_folder(service, MAIN_DRIVE_FOLDER_ID, ["Clientes", nome_pasta])

        prefixo_num = re.sub(r'^(ORC|VENDA|RASC)-', '', numero)
        if prefixo_num:
            arq = _buscar_arquivo_por_prefixo(DRIVE_FOLDER_ORCAMENTOS, prefixo_num)
            if arq:
                criar_atalho_drive(arq['id'], pasta_id, arq['name'])

        st.session_state.supabase.table('servicos_andamento').update(
            {'drive_pasta_id': pasta_id}).eq('id', servico['id']).execute()
        return pasta_id, None
    except Exception as e:
        return None, str(e)

def sincronizar_midias_pendentes_drive(servico_id, pasta_id):
    """Copia para a pasta do cliente no Drive as fotos/vídeos que o instalador
    já enviou pro Supabase Storage e ainda não foram sincronizados
    (servico_midias.sincronizado_drive = false). Marca cada um como
    sincronizado ao concluir. Retorna (enviados, erro) — erro só vem
    preenchido se algo impediu de tentar de verdade (ex.: Drive fora do ar);
    falha em um arquivo isolado não é reportada aqui, só pula pro próximo."""
    if not pasta_id:
        return 0, None
    try:
        sb = st.session_state.supabase
        res = sb.table('servico_midias').select('*').eq('servico_id', servico_id).eq('sincronizado_drive', False).execute()
        pendentes = res.data or []
        if not pendentes:
            return 0, None
        service = get_drive_service()
        if not service: return 0, "Serviço do Drive indisponível."
        url_base = st.secrets["SUPABASE_URL"].rstrip('/')
        enviados = 0
        ultimo_erro = None
        for m in pendentes:
            try:
                url_arquivo = f"{url_base}/storage/v1/object/public/instalacao-midias/{m['storage_path']}"
                with urllib.request.urlopen(url_arquivo, timeout=30) as resp:
                    conteudo = resp.read()
                if m.get('tipo') == 'video':
                    mimetype = 'video/mp4'
                elif m.get('tipo') == 'audio':
                    mimetype = 'audio/webm'
                else:
                    mimetype = 'image/jpeg'
                media = MediaIoBaseUpload(BytesIO(conteudo), mimetype=mimetype, resumable=True)
                metadata = {'name': m.get('nome_arquivo') or m['storage_path'], 'parents': [pasta_id]}
                service.files().create(body=metadata, media_body=media, fields='id').execute()
                sb.table('servico_midias').update({'sincronizado_drive': True}).eq('id', m['id']).execute()
                enviados += 1
            except Exception as e:
                ultimo_erro = str(e)
                continue
        return enviados, (None if enviados > 0 else ultimo_erro)
    except Exception as e:
        return 0, str(e)

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
# FUNÇÕES FINANCEIRAS E CATÁLOGOS
# ==========================================
def load_year_data(nome_tabela, contas_padrao, ano):
    supabase = get_supabase_client()
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
    supabase = get_supabase_client()
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
    supabase = get_supabase_client()
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
    supabase = get_supabase_client()
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

def contar_notificacoes_instalador(supabase):
    """Conta quantas novidades do instalador o admin ainda não viu — comentário
    ou mídia numa tarefa de Agenda, instalação concluída, ou foto/áudio anexado
    direto num cliente. Usada no aviso da barra lateral (app.py), que aparece
    em qualquer tela do sistema, não só em Serviços em Andamento."""
    total = 0
    try:
        r1 = supabase.table('agenda_visitas').select('id', count='exact', head=True).eq('visto_pelo_admin', False).execute()
        total += r1.count or 0
    except Exception:
        pass
    try:
        r2 = supabase.table('servicos_andamento').select('id', count='exact', head=True).eq('conclusao_vista_pelo_admin', False).execute()
        total += r2.count or 0
    except Exception:
        pass
    try:
        r3 = supabase.table('servico_midias').select('id', count='exact', head=True).eq('visto_pelo_admin', False).not_.is_('servico_id', 'null').execute()
        total += r3.count or 0
    except Exception:
        pass
    return total

def to_br_currency(valor, incluir_simbolo=True):
    try: valor_float = float(valor)
    except: valor_float = 0.0
    res = f"{valor_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {res}" if incluir_simbolo else res

def to_br_currency_md(valor):
    # Igual a to_br_currency, mas com o '$' escapado — usar dentro de
    # st.markdown/st.caption/st.warning/st.success quando o texto tem 2+
    # valores em R$: sem o escape, o Streamlit lê tudo entre o 1º e o 2º '$'
    # como LaTeX e renderiza estranho (foi o que aconteceu na Meta de Patrimônio).
    return to_br_currency(valor).replace("$", "\\$")

def parse_br_currency(texto_valor):
    if isinstance(texto_valor, (int, float)): return float(texto_valor)
    s = str(texto_valor).replace("R$", "").strip().replace(".", "").replace(",", ".")
    try: return float(s)
    except: return 0.0

def load_taxas():
    supabase = get_supabase_client()
    try:
        res = supabase.table('catalogo_taxas').select("*").execute()
        df = pd.DataFrame(res.data)
        if df.empty: return pd.DataFrame(columns=["Item", "Taxa (%)"])
        return df.rename(columns={"item": "Item", "taxa_percentual": "Taxa (%)"})
    except: return pd.DataFrame(columns=["Item", "Taxa (%)"])

def save_taxas(df):
    supabase = get_supabase_client()
    dados = [{"item": r['Item'], "taxa_percentual": float(r.get('Taxa (%)', 0.0))} for _, r in df.iterrows() if r.get('Item')]
    supabase.table('catalogo_taxas').delete().neq("item", "___").execute()
    if dados: supabase.table('catalogo_taxas').insert(dados).execute()

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
# GERAÇÃO DE PDF (ORÇAMENTO) — layout profissional "bulletproof" via Platypus
# ==========================================
class _CanvasNumerado(canvas.Canvas):
    """Canvas que imprime 'Página X de Y' (conta o total no fechamento)."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._estados = []

    def showPage(self):
        self._estados.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._estados)
        for estado in self._estados:
            self.__dict__.update(estado)
            self.setFont("Helvetica", 7.5)
            self.setFillColor(colors.HexColor("#6a7180"))
            self.drawRightString(A4[0] - 2*cm, 1.15*cm, f"Página {self._pageNumber} de {total}")
            super().showPage()
        super().save()


def gerar_pdf_orcamento(nome, tel, capa, df_items, d_s, v_s, d_o, v_o, total, obs, mostrar_un):
    # Paleta aprovada no mockup: grafite + dourado (sol), verde como detalhe.
    GRAFITE = colors.HexColor("#2b3440")
    GRAFITE_DEEP = colors.HexColor("#171c24")
    GOLD = colors.HexColor("#E4A100")
    GOLD_SOFT = colors.HexColor("#fbf1d6")
    GOLD_DEEP = colors.HexColor("#a9760a")
    GREEN = colors.HexColor("#7FB01E")
    INK = colors.HexColor("#1e2530")
    MUTED = colors.HexColor("#6a7180")
    HAIR = colors.HexColor("#e6e8ec")
    PANEL = colors.HexColor("#f6f7f9")
    ZEBRA = colors.HexColor("#fafbfc")

    numero = f"ORC-{datetime.datetime.now().strftime('%y%m%d-%H%M')}"
    data_str = obter_data_atual_br().strftime('%d/%m/%Y')

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm, topMargin=3.05*cm, bottomMargin=1.75*cm,
        title=f"Orçamento - {nome}",
    )
    LU = doc.width  # largura interna útil (frame)

    styles = getSampleStyleSheet()
    def _st(name, **kw):
        return ParagraphStyle(name, parent=styles['Normal'], **kw)

    s_item   = _st('it', fontName='Helvetica-Bold', fontSize=10, leading=12.5, textColor=INK)
    s_desc   = _st('de', fontName='Helvetica', fontSize=8.5, leading=11, textColor=MUTED)
    s_body   = _st('bo', fontName='Helvetica', fontSize=9.5, leading=13.5, textColor=INK)
    s_val    = _st('va', fontName='Helvetica-Bold', fontSize=11, leading=13, textColor=GRAFITE, alignment=TA_RIGHT)
    s_num    = _st('nu', fontName='Helvetica', fontSize=9.5, leading=12, textColor=INK, alignment=TA_CENTER)
    s_numr   = _st('nr', fontName='Helvetica', fontSize=9.5, leading=12, textColor=INK, alignment=TA_RIGHT)
    s_tag    = _st('tg', fontName='Helvetica-Bold', fontSize=9.5, leading=13, textColor=MUTED, alignment=TA_CENTER)
    s_obs_t  = _st('obt', fontName='Helvetica-Bold', fontSize=9, leading=12, textColor=GOLD_DEEP)
    s_obs    = _st('ob', fontName='Helvetica', fontSize=9, leading=13, textColor=colors.HexColor("#5a4212"))
    s_cli_k  = _st('ck', fontName='Helvetica', fontSize=7.5, leading=9, textColor=MUTED)
    s_cli_v  = _st('cv', fontName='Helvetica-Bold', fontSize=10, leading=12, textColor=INK)
    s_stat_n = _st('sn', fontName='Helvetica-Bold', fontSize=15, leading=17, textColor=GOLD, alignment=TA_CENTER)
    s_stat_l = _st('sl', fontName='Helvetica', fontSize=7, leading=8.5, textColor=colors.white, alignment=TA_CENTER)
    s_secbar = _st('sb', fontName='Helvetica-Bold', fontSize=10.5, leading=13, textColor=colors.white)
    s_secbarR= _st('sbr', fontName='Helvetica', fontSize=8.5, leading=12, textColor=colors.HexColor("#c9cdd4"), alignment=TA_RIGHT)
    s_th     = _st('th', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=MUTED)
    s_thc    = _st('thc', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=MUTED, alignment=TA_CENTER)
    s_thr    = _st('thr', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=MUTED, alignment=TA_RIGHT)
    s_sub    = _st('su', fontName='Helvetica-Bold', fontSize=9.5, leading=12, textColor=GRAFITE_DEEP)
    s_subr   = _st('sur', fontName='Helvetica-Bold', fontSize=9.5, leading=12, textColor=GRAFITE_DEEP, alignment=TA_RIGHT)
    s_cond_k = _st('cok', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=MUTED)
    s_cond_v = _st('cov', fontName='Helvetica', fontSize=9, leading=12, textColor=INK)

    def _limpo(txt):
        s = str(txt or "").strip()
        return s if s.lower() != 'nan' else ""

    story = []

    # ---------- Faixa de impacto ----------
    def _stat(n, l):
        return [Paragraph(n, s_stat_n), Paragraph(l, s_stat_l)]
    impacto = Table([[_stat("10+", "ANOS DE EXPERIÊNCIA"), _stat("+4 mil", "CLIENTES SATISFEITOS"),
                      _stat("Até 60%", "DE ECONOMIA"), _stat("100%", "SATISFAÇÃO")]],
                    colWidths=[LU / 4.0] * 4)
    impacto.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), GRAFITE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LINEAFTER', (0, 0), (-2, -1), 0.5, colors.HexColor("#454e5b")),
    ]))
    story.append(impacto)
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph("Mais conforto, mais economia, <b>mais sustentabilidade</b>", s_tag))
    story.append(Spacer(1, 0.4*cm))

    # ---------- Imagem do produto (conforme a capa) ----------
    img_map = {
        "Aquecedor Solar Tradicional": "aquecedor_tradicional.jpg",
        "Aquecedor Solar a Vácuo Acoplado": "vacuo_acoplado.jpg",
        "Aquecedor Solar Modular": "modular.jpg",
        "Aquecedor de Piscina - Tradicional": "piscina_tradicional.jpg",
        "Aquecedor de Piscina - Trocador de Calor": "piscina_trocador.jpg",
        "Sistema de Pressurização": "pressurizacao.jpg",
    }
    caminho_img = img_map.get(capa, "")
    if caminho_img:
        try:
            img = RLImage(caminho_img)
            # Preserva o aspecto original (não estica): ajusta pela largura e,
            # se passar da altura máxima, reduz a largura proporcionalmente.
            ratio = float(img.drawHeight) / float(img.drawWidth) if float(img.drawWidth) else 0.5
            larg_img = LU
            alt_img = larg_img * ratio
            if alt_img > 4.0 * cm:
                alt_img = 4.0 * cm
                larg_img = alt_img / ratio
            img.drawWidth = larg_img
            img.drawHeight = alt_img
            img.hAlign = 'CENTER'
            legenda = Table([[Paragraph(f"<b>{capa}</b>", _st('cap', fontName='Helvetica-Bold', fontSize=11, textColor=colors.white)),
                              Paragraph("SELECIONADO", _st('capr', fontName='Helvetica-Bold', fontSize=7.5, textColor=GRAFITE_DEEP, alignment=TA_RIGHT))]],
                            colWidths=[larg_img*0.68, larg_img*0.32])
            legenda.hAlign = 'CENTER'
            legenda.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), GRAFITE),
                ('BACKGROUND', (1, 0), (1, -1), GOLD),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 10), ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ]))
            story.append(KeepTogether([img, legenda]))
            story.append(Spacer(1, 0.2*cm))
        except Exception:
            pass

    # ---------- Dados do cliente ----------
    def _cli(k, v):
        return [Paragraph(k, s_cli_k), Paragraph(_limpo(v) or "—", s_cli_v)]
    cliente = Table([[_cli("CLIENTE", nome), _cli("WHATSAPP", tel), _cli("DATA", data_str), _cli("Nº PROPOSTA", numero)]],
                    colWidths=[LU*0.34, LU*0.22, LU*0.17, LU*0.27])
    cliente.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.6, HAIR),
        ('LINEAFTER', (0, 0), (-2, -1), 0.6, HAIR),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 10), ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(cliente)
    story.append(Spacer(1, 0.22*cm))

    # ---------- barra de seção ----------
    def barra(titulo, direita=""):
        t = Table([[Paragraph(titulo, s_secbar), Paragraph(direita, s_secbarR)]], colWidths=[LU*0.6, LU*0.4])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), GRAFITE),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 10), ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        return t

    # ---------- 1. Equipamentos ----------
    if mostrar_un:
        cab = [Paragraph("Item", s_th), Paragraph("Qtd", s_thc), Paragraph("V. Unit.", s_thr), Paragraph("Subtotal", s_thr)]
        col_w = [LU*0.55, LU*0.10, LU*0.16, LU*0.19]
    else:
        cab = [Paragraph("Item", s_th), Paragraph("Qtd", s_thc), Paragraph("Subtotal", s_thr)]
        col_w = [LU*0.66, LU*0.14, LU*0.20]
    linhas = [cab]

    subtotal_eq = 0.0
    for _, row in df_items.iterrows():
        qtd = safe_float(row.get('Quantidade', row.get('Qtd', 0)))
        if qtd <= 0:
            continue
        p_base = str(row.get('Produto da Base', '')).strip()
        if p_base.upper() in ['', 'NONE', 'NAN', 'OUTRO']:
            item_nome = _limpo(row.get('Produto Manual', '')) or _limpo(row.get('Item', ''))
        else:
            item_nome = p_base
        v_un = safe_float(row.get('Venda (R$)', row.get('Venda Un.', 0)))
        v_tot = safe_float(row.get('Venda Total', qtd * v_un))
        subtotal_eq += v_tot
        cel = [Paragraph(item_nome or "Item", s_item)]
        desc = _limpo(row.get('Descrição', ''))
        if desc:
            cel.append(Paragraph(desc.replace('\n', '<br/>'), s_desc))
        if mostrar_un:
            linhas.append([cel, Paragraph(str(int(qtd)), s_num), Paragraph(to_br_currency(v_un), s_numr), Paragraph(to_br_currency(v_tot), s_numr)])
        else:
            linhas.append([cel, Paragraph(str(int(qtd)), s_num), Paragraph(to_br_currency(v_tot), s_numr)])

    if len(linhas) == 1:  # nenhum equipamento
        vazio = ["", "", ""] if not mostrar_un else ["", "", "", ""]
        vazio[0] = Paragraph("Nenhum equipamento nesta proposta.", s_body)
        linhas.append(vazio)

    # linha de subtotal
    if mostrar_un:
        linhas.append([Paragraph("Subtotal de Equipamentos", s_sub), "", "", Paragraph(to_br_currency(subtotal_eq), s_subr)])
    else:
        linhas.append([Paragraph("Subtotal de Equipamentos", s_sub), "", Paragraph(to_br_currency(subtotal_eq), s_subr)])

    n_last = len(linhas) - 1
    tbl = Table(linhas, colWidths=col_w, repeatRows=1)
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PANEL),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, HAIR),
        ('BOX', (0, 0), (-1, -1), 0.6, HAIR),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 10), ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('ROWBACKGROUNDS', (0, 1), (-1, n_last - 1), [colors.white, ZEBRA]),
        ('BACKGROUND', (0, n_last), (-1, n_last), colors.HexColor("#eef1f5")),
        ('SPAN', (0, n_last), (-2, n_last)),
    ]))
    story.append(barra("1.  EQUIPAMENTOS", "Qtd · Valor"))
    story.append(tbl)
    story.append(Spacer(1, 0.22*cm))

    # ---------- bloco descritivo (Serviços / Outros) ----------
    estilo_bloco = TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.6, HAIR),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 10), ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 7), ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ])

    def bloco_desc(texto, valor, vazio_msg):
        t = _limpo(texto)
        conteudo = Paragraph(t.replace('\n', '<br/>'), s_body) if t else Paragraph(vazio_msg, s_body)
        tab = Table([[conteudo, Paragraph(to_br_currency(valor or 0), s_val)]], colWidths=[LU*0.78, LU*0.22])
        tab.setStyle(estilo_bloco)
        return tab

    # ---------- 2. Serviços ----------
    story.append(barra("2.  SERVIÇOS", "Instalação"))
    story.append(bloco_desc(d_s, v_s, "Nenhum serviço incluído nesta proposta."))
    story.append(Spacer(1, 0.22*cm))

    # ---------- 3. Outros / Terceiros ----------
    story.append(barra("3.  OUTROS / TERCEIROS", "Adicionais"))
    story.append(bloco_desc(d_o, v_o, "Nenhum item adicional nesta proposta."))
    story.append(Spacer(1, 0.22*cm))

    # ---------- Investimento total ----------
    total_tbl = Table([[Paragraph("INVESTIMENTO TOTAL", _st('tl', fontName='Helvetica-Bold', fontSize=12, textColor=colors.white)),
                        Paragraph(to_br_currency(total), _st('tv', fontName='Helvetica-Bold', fontSize=17, textColor=colors.white, alignment=TA_RIGHT))]],
                      colWidths=[LU*0.5, LU*0.5])
    total_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), GRAFITE_DEEP),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 14), ('RIGHTPADDING', (0, 0), (-1, -1), 14),
        ('TOPPADDING', (0, 0), (-1, -1), 10), ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LINEBEFORE', (1, 0), (1, 0), 3, GOLD),
    ]))
    story.append(total_tbl)

    # ---------- Observações ----------
    obs_txt = _limpo(obs)
    if obs_txt:
        story.append(Spacer(1, 0.22*cm))
        obs_tbl = Table([[[Paragraph("OBSERVAÇÕES", s_obs_t), Spacer(1, 0.15*cm), Paragraph(obs_txt.replace('\n', '<br/>'), s_obs)]]],
                        colWidths=[LU])
        obs_tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), GOLD_SOFT),
            ('LINEBEFORE', (0, 0), (0, -1), 3, GOLD),
            ('LEFTPADDING', (0, 0), (-1, -1), 12), ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 10), ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        story.append(obs_tbl)

    # ---------- Condições ----------
    story.append(Spacer(1, 0.22*cm))
    def _cond(k, v):
        return [Paragraph(k, s_cond_k), Spacer(1, 0.08*cm), Paragraph(v, s_cond_v)]
    cond = Table([[_cond("PRAZO DE EXECUÇÃO", "A combinar."),
                   _cond("VALIDADE DA PROPOSTA", "15 dias corridos."),
                   _cond("GARANTIA", "Conforme certificado do fabricante.")]],
                 colWidths=[LU/3.0]*3)
    cond.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.6, HAIR), ('INNERGRID', (0, 0), (-1, -1), 0.6, HAIR),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 10), ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(cond)

    # ---------- Barra de contato ----------
    story.append(Spacer(1, 0.22*cm))
    contato = Table([[Paragraph("<b>ECOCLIM</b>  ·  Especialistas em energia solar e sustentabilidade",
                                _st('c1', fontName='Helvetica', fontSize=9, textColor=colors.white)),
                      Paragraph("(31) 99867-7808  ·  WWW.ECOCLIM.COM.BR",
                                _st('c2', fontName='Helvetica-Bold', fontSize=9, textColor=colors.white, alignment=TA_RIGHT))]],
                    colWidths=[LU*0.6, LU*0.4])
    contato.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), GRAFITE_DEEP),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 14), ('RIGHTPADDING', (0, 0), (-1, -1), 14),
        ('TOPPADDING', (0, 0), (-1, -1), 7), ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ]))
    story.append(contato)

    # ---------- Cabeçalho/rodapé repetidos em cada página ----------
    def _moldura(canv, _doc):
        w, h = A4
        try:
            canv.drawImage("logo.png", 2*cm, h - 2.55*cm, width=4.3*cm, height=1.7*cm, preserveAspectRatio=True, mask='auto')
        except Exception:
            canv.setFillColor(GRAFITE); canv.setFont("Helvetica-Bold", 18); canv.drawString(2*cm, h - 2.1*cm, "ECOCLIM")
        canv.setFillColor(GRAFITE); canv.setFont("Helvetica-Bold", 13)
        canv.drawRightString(w - 2*cm, h - 1.55*cm, "PROPOSTA COMERCIAL")
        canv.setFillColor(MUTED); canv.setFont("Helvetica", 8.5)
        canv.drawRightString(w - 2*cm, h - 2.0*cm, f"Nº {numero}")
        canv.drawRightString(w - 2*cm, h - 2.4*cm, f"Data: {data_str}    Validade: 15 dias")
        rw = w - 4*cm; ry = h - 2.78*cm
        canv.setFillColor(GRAFITE); canv.rect(2*cm, ry, rw*0.55, 0.09*cm, fill=1, stroke=0)
        canv.setFillColor(GREEN);  canv.rect(2*cm + rw*0.55, ry, rw*0.15, 0.09*cm, fill=1, stroke=0)
        canv.setFillColor(GOLD);   canv.rect(2*cm + rw*0.70, ry, rw*0.30, 0.09*cm, fill=1, stroke=0)
        canv.setStrokeColor(HAIR); canv.setLineWidth(0.5); canv.line(2*cm, 1.5*cm, w - 2*cm, 1.5*cm)
        canv.setFillColor(MUTED); canv.setFont("Helvetica", 7.5)
        canv.drawString(2*cm, 1.15*cm, "Ecoclim · Aquecimento Solar · (31) 99867-7808 · comercial@ecoclim.com.br")

    doc.build(story, onFirstPage=_moldura, onLaterPages=_moldura, canvasmaker=_CanvasNumerado)
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
        story.append(Spacer(1, 0.22*cm))
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
    story.append(Paragraph(f"Santa Luzia, MG, {obter_data_atual_br().strftime('%d de %B de %Y').lower()}.", style_normal))
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
        supabase = get_supabase_client()
        res = supabase.table('boletos_fornecedores').select('*').execute()
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

        hoje_dt = obter_data_atual_br()

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
