"""Backup e Lixeira do ERP Ecoclim — pra não perdermos nenhum dado.

1. BACKUP DIÁRIO AUTOMÁTICO
   Uma vez por dia (no primeiro acesso de um Admin), copia TODAS as tabelas do
   banco para um .zip (um JSON por tabela + um resumo) e guarda no Google
   Drive, pasta "Backups" dentro da pasta principal do ERP. Roda em segundo
   plano: não deixa o sistema mais lento. Mantém os 45 mais recentes (os mais
   velhos vão para a LIXEIRA do Drive, que ainda guarda por 30 dias).
   Também dá pra fazer na hora e baixar o .zip em Configurações → 🛡️ Backup.

2. LIXEIRA (excluir com cópia)
   Antes de excluir um cliente/serviço, boleto, empréstimo, lista, tarefa…,
   o registro inteiro é guardado em `fin_configuracoes` (chave
   "lixeira:<tabela>:<id>:<quando>"). Em Configurações → 🛡️ Backup dá pra ver
   e RESTAURAR com um clique. Nenhuma tabela nova foi criada (sem migração).

Nada aqui altera dados existentes: só lê, copia e (na restauração) devolve.
"""
import datetime
import io
import json
import threading
import zipfile

# Todas as tabelas do banco do Ecoclim (levantadas no código do ERP, do app do
# instalador, da API e dos scripts). Tabela que não existir é só pulada.
TABELAS = [
    "servicos_andamento", "boletos_fornecedores", "emprestimos", "agenda_visitas",
    "listas_materiais", "vendas_materiais", "compras_materiais", "estoque_movimentos",
    "materiais_padrao", "materiais_modelos", "materiais_sugeridos",
    "catalogo_produtos", "catalogo_servicos", "catalogo_outros", "catalogo_taxas",
    "config_kits_lote", "config_instaladores",
    "fin_patrimonio", "fin_entradas", "fin_configuracoes", "fin_aportes_itens", "fin_recebimentos_itens",
    "airnb_entradas", "airnb_saidas",
    "orcamento_versoes", "servico_midias", "movimentacoes", "lembretes", "notas_secretas",
    "adiantamentos_instalador", "adiantamento_baixas", "push_subscriptions", "usuarios_erp",
    "fit_alimentos", "fit_perfis",
]
PASTA_BACKUPS = ["Backups"]
MANTER = 45
CHAVE_ULTIMO = "backup_ultimo"
PREFIXO_LIXEIRA = "lixeira:"

_trava = threading.Lock()


def _agora_br():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-3)))


def _cliente_puro(sb):
    """Cliente sem o cache de leitura (backup tem que ler o banco de verdade)."""
    return getattr(sb, "_cliente", sb)


# ---------------------------------------------------------------------------
# Exportação
# ---------------------------------------------------------------------------
def ler_tabela(sb, tabela, lote=1000):
    linhas, ini = [], 0
    while True:
        r = sb.table(tabela).select("*").range(ini, ini + lote - 1).execute()
        dados = r.data or []
        linhas.extend(dados)
        if len(dados) < lote:
            return linhas
        ini += lote


def gerar_zip(sb):
    """Lê todas as tabelas e devolve (bytes_do_zip, resumo)."""
    sb = _cliente_puro(sb)
    quando = _agora_br()
    resumo = {"gerado_em": quando.isoformat(), "tabelas": {}, "erros": {}}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for t in TABELAS:
            try:
                linhas = ler_tabela(sb, t)
            except Exception as e:  # noqa: BLE001
                resumo["erros"][t] = str(e)[:200]
                continue
            z.writestr(f"{t}.json", json.dumps(linhas, ensure_ascii=False, default=str, indent=1))
            resumo["tabelas"][t] = len(linhas)
        resumo["total_linhas"] = sum(resumo["tabelas"].values())
        z.writestr("_resumo.json", json.dumps(resumo, ensure_ascii=False, indent=1))
    return buf.getvalue(), resumo


def nome_arquivo(quando=None):
    q = quando or _agora_br()
    return f"backup_erp_{q.strftime('%Y-%m-%d_%H%M')}.zip"


# ---------------------------------------------------------------------------
# Google Drive
# ---------------------------------------------------------------------------
def _pasta_backups(service, utils):
    return utils.get_or_create_nested_folder(service, utils.MAIN_DRIVE_FOLDER_ID, PASTA_BACKUPS)


def enviar_para_drive(conteudo, nome, service=None):
    """Sobe o .zip para Drive/Backups. Devolve (ok, id_ou_erro)."""
    import utils
    from googleapiclient.http import MediaIoBaseUpload
    try:
        service = service or utils.get_drive_service()
        if not service:
            return False, "Google Drive indisponível"
        pasta = _pasta_backups(service, utils)
        media = MediaIoBaseUpload(io.BytesIO(conteudo), mimetype="application/zip", resumable=True)
        arq = service.files().create(body={"name": nome, "parents": [pasta]}, media_body=media, fields="id").execute()
        return True, arq.get("id")
    except Exception as e:  # noqa: BLE001
        return False, str(e)[:300]


def listar_backups(service=None, limite=60):
    import utils
    try:
        service = service or utils.get_drive_service()
        pasta = _pasta_backups(service, utils)
        r = service.files().list(
            q=f"'{pasta}' in parents and name contains 'backup_erp_' and trashed = false",
            orderBy="createdTime desc", pageSize=limite, fields="files(id,name,createdTime,size)").execute()
        return r.get("files", [])
    except Exception:
        return []


def limpar_antigos(service=None, manter=MANTER):
    """Manda para a lixeira do Drive (reversível por 30 dias) os backups além dos `manter` mais novos."""
    import utils
    try:
        service = service or utils.get_drive_service()
        arquivos = listar_backups(service, limite=500)
        for f in arquivos[manter:]:
            service.files().update(fileId=f["id"], body={"trashed": True}).execute()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Registro do último backup (fin_configuracoes)
# ---------------------------------------------------------------------------
def ler_ultimo(sb):
    try:
        r = _cliente_puro(sb).table("fin_configuracoes").select("*").eq("chave", CHAVE_ULTIMO).execute().data
        if r:
            info = {}
            try:
                info = json.loads(r[0].get("valor2") or "{}")
            except Exception:
                info = {}
            info["quando"] = r[0].get("valor1")
            return info
    except Exception:
        pass
    return None


def _gravar_ultimo(sb, quando_iso, info):
    sb = _cliente_puro(sb)
    payload = {"chave": CHAVE_ULTIMO, "valor1": quando_iso, "valor2": json.dumps(info, ensure_ascii=False)}
    existe = sb.table("fin_configuracoes").select("id").eq("chave", CHAVE_ULTIMO).execute().data
    if existe:
        sb.table("fin_configuracoes").update(payload).eq("id", existe[0]["id"]).execute()
    else:
        sb.table("fin_configuracoes").insert(payload).execute()


def fazer_backup(sb, service=None, enviar=True):
    """Backup completo agora. Devolve dict com o resultado."""
    conteudo, resumo = gerar_zip(sb)
    nome = nome_arquivo()
    resultado = {"arquivo": nome, "tamanho_kb": round(len(conteudo) / 1024, 1),
                 "linhas": resumo.get("total_linhas", 0), "tabelas": len(resumo["tabelas"]),
                 "erros": resumo["erros"], "drive": None}
    if enviar:
        ok, ref = enviar_para_drive(conteudo, nome, service)
        resultado["drive"] = ref if ok else None
        resultado["drive_erro"] = None if ok else ref
        if ok:
            limpar_antigos(service)
    _gravar_ultimo(sb, _agora_br().isoformat(), resultado)
    return resultado, conteudo


def backup_diario_se_preciso(sb):
    """Chamado pelo app.py no acesso de um Admin. Se ainda não houve backup
    hoje, dispara um em SEGUNDO PLANO (não trava a tela). Nunca levanta erro."""
    try:
        hoje = _agora_br().date().isoformat()
        ult = ler_ultimo(sb)
        if ult and str(ult.get("quando") or "")[:10] == hoje:
            return False
        if not _trava.acquire(blocking=False):
            return False
        cliente = _cliente_puro(sb)
        import utils
        service = utils.get_drive_service()  # criado aqui (thread principal), usado lá
        # marca já, pra outra sessão aberta ao mesmo tempo não disparar outro
        _gravar_ultimo(cliente, _agora_br().isoformat(), {"status": "em andamento"})

        def _rodar():
            try:
                fazer_backup(cliente, service=service, enviar=True)
            except Exception as e:  # noqa: BLE001
                try:
                    _gravar_ultimo(cliente, _agora_br().isoformat(), {"status": "erro", "erro": str(e)[:300]})
                except Exception:
                    pass
            finally:
                _trava.release()

        threading.Thread(target=_rodar, name="backup-diario-erp", daemon=True).start()
        return True
    except Exception:
        try:
            _trava.release()
        except Exception:
            pass
        return False


# ---------------------------------------------------------------------------
# Lixeira
# ---------------------------------------------------------------------------
def guardar_na_lixeira(sb, tabela, registro, descricao=""):
    """Guarda uma cópia completa do registro antes de excluir. Devolve True/False."""
    try:
        q = _agora_br()
        chave = f"{PREFIXO_LIXEIRA}{tabela}:{registro.get('id', '')}:{q.strftime('%Y%m%d%H%M%S%f')}"
        info = {"tabela": tabela, "quando": q.isoformat(), "descricao": descricao or "", "registro": registro}
        _cliente_puro(sb).table("fin_configuracoes").insert(
            {"chave": chave, "valor1": json.dumps(info, ensure_ascii=False, default=str),
             "valor2": (descricao or "")[:250]}).execute()
        return True
    except Exception:
        return False


# Tabelas "filhas" de um cliente/serviço (apontam para ele por servico_id).
FILHAS_SERVICO = ["listas_materiais", "vendas_materiais", "boletos_fornecedores", "orcamento_versoes", "servico_midias"]


def _filhos_do_servico(cliente, sid):
    filhos = {}
    for t in FILHAS_SERVICO:
        try:
            filhos[t] = cliente.table(t).select("*").eq("servico_id", sid).execute().data or []
        except Exception:
            filhos[t] = []
    return filhos


def excluir_com_copia(sb, tabela, id_registro, descricao=""):
    """Lê o registro, guarda na Lixeira e só então exclui. Se a cópia falhar,
    NÃO exclui e levanta erro (prefere não apagar a arriscar perder).
    Para cliente/serviço, guarda junto as listas de materiais, vendas, boletos,
    versões de orçamento e mídias ligadas a ele (se o banco apagar em cascata,
    a restauração devolve tudo)."""
    cliente = _cliente_puro(sb)
    linhas = cliente.table(tabela).select("*").eq("id", id_registro).execute().data or []
    for reg in linhas:
        copia = dict(reg)
        if tabela == "servicos_andamento":
            copia["__filhos__"] = _filhos_do_servico(cliente, id_registro)
        if not guardar_na_lixeira(sb, tabela, copia, descricao):
            raise RuntimeError("Não consegui guardar a cópia de segurança na Lixeira — nada foi excluído. Tente de novo.")
    sb.table(tabela).delete().eq("id", id_registro).execute()
    return len(linhas)


def listar_lixeira(sb, limite=300):
    try:
        r = (_cliente_puro(sb).table("fin_configuracoes").select("*")
             .like("chave", f"{PREFIXO_LIXEIRA}%").order("id", desc=True).limit(limite).execute().data or [])
    except Exception:
        return []
    itens = []
    for x in r:
        try:
            info = json.loads(x.get("valor1") or "{}")
        except Exception:
            continue
        info["_id_lixeira"] = x["id"]
        itens.append(info)
    return itens


def _inserir(sb, tabela, reg):
    """Insere mantendo o id original quando o banco deixa; senão, com id novo.
    Devolve o id com que ficou."""
    try:
        r = sb.table(tabela).insert(reg).execute().data or [reg]
    except Exception:
        sem_id = {k: v for k, v in reg.items() if k != "id"}
        r = sb.table(tabela).insert(sem_id).execute().data or [sem_id]
    return r[0].get("id")


def restaurar(sb, item):
    """Devolve o registro à tabela de origem (com o mesmo id quando o banco
    permite; se não, com id novo) e tira da Lixeira. Para cliente/serviço,
    religa/devolve as listas, vendas, boletos, versões e mídias dele."""
    tabela = item["tabela"]
    reg = dict(item["registro"])
    filhos = reg.pop("__filhos__", None) or {}
    id_antigo = reg.get("id")
    id_novo = _inserir(sb, tabela, reg)
    if tabela == "servicos_andamento" and id_novo is not None:
        cliente = _cliente_puro(sb)
        for t, linhas in filhos.items():
            for f in linhas:
                try:
                    existe = cliente.table(t).select("id").eq("id", f.get("id")).execute().data if f.get("id") is not None else []
                    if existe:
                        if id_novo != id_antigo:
                            cliente.table(t).update({"servico_id": id_novo}).eq("id", f["id"]).execute()
                    else:
                        f2 = dict(f)
                        f2["servico_id"] = id_novo
                        _inserir(cliente, t, f2)
                except Exception:
                    pass
        if id_novo != id_antigo:
            try:
                cliente.table("movimentacoes").update({"referencia_id": id_novo}).eq("tipo", "servico").eq("referencia_id", id_antigo).execute()
            except Exception:
                pass
    _cliente_puro(sb).table("fin_configuracoes").delete().eq("id", item["_id_lixeira"]).execute()
    try:
        sb.limpar_cache()
    except Exception:
        pass
    return id_novo


def apagar_da_lixeira(sb, item):
    _cliente_puro(sb).table("fin_configuracoes").delete().eq("id", item["_id_lixeira"]).execute()
