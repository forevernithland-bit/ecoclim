"""Importar orçamento já enviado — arrasta o PDF, o ERP procura se já está salvo.

Fluxo (pedido do Breno, 2026-11-04):
  1. Arrasta o PDF que foi mandado ao cliente.
  2. O sistema lê o PDF e procura na memória (Supabase) se esse orçamento já
     existe: pelo nome do arquivo, pelo número da proposta e, por último, por
     cliente + valor.
  3. Já salvo -> mostra onde está (status) e oferece abrir pra editar ou mandar
     pra Serviços em Andamento.
  4. Não salvo -> pergunta: "importar e editar" (carrega na aba Orçamento
     Personalizado, sem gravar nada) ou "enviar direto pra Em Andamento".

O PDF é lido pelo texto (PyPDF2, que já está no deploy). Só o PDF padrão do
ERP (capa + 1. Equipamentos + 2. Serviços + 3. Outros) tem os itens lidos; PDFs
de outros formatos entram só com cliente, número e total, e a tela avisa.
"""
import datetime
import difflib
import io
import re
import unicodedata

import pandas as pd
import streamlit as st

import movimentacoes
import orcamento_personalizado as _op
import utils

CAPAS = [
    "Aquecedor Solar Tradicional",
    "Aquecedor Solar a Vácuo Acoplado",
    "Aquecedor Solar Modular",
    "Aquecedor de Piscina - Tradicional",
    "Aquecedor de Piscina - Trocador de Calor",
    "Sistema de Pressurização",
]
STATUS_PODE_ANDAMENTO = ("Rascunho", "Orçamento Enviado", "Orçamento Cancelado")

_RE_BRL = re.compile(r"R\$\s*([\d\.]+,\d{2})")
_RE_NUM = re.compile(r"^\d+(?:[.,]\d+)?$")
# Cabeçalho/rodapé que o gerador repete em toda página do PDF.
_RE_RUIDO = re.compile(
    r"^(PROPOSTA COMERCIAL|OR[ÇC]AMENTO\s+FECHADO|N[º°o]?\s*(ORC|RASC)-.*|Data:.*"
    r"|Ecoclim\s*[·•].*|P[áa]gina\s+\d+\s+de\s+\d+)$", re.I)
_CABECALHOS_TABELA = {"qtd", "item", "v. unit.", "subtotal", "qtd · valor", "qtd · v.unit · subtotal"}


def _n(texto):
    """MAIÚSCULA, sem acento, espaços colapsados — chave de comparação."""
    t = unicodedata.normalize("NFD", str(texto or "").upper())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t).strip()


def _brl(linha):
    m = _RE_BRL.search(linha or "")
    return float(m.group(1).replace(".", "").replace(",", ".")) if m else None


def _fmt_tel(tel):
    d = re.sub(r"\D", "", str(tel or ""))
    if len(d) in (12, 13) and d.startswith("55"):
        d = d[2:]
    if len(d) == 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    if len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    return str(tel or "").strip()


# ---------------------------------------------------------------------------
# Leitura do PDF
# ---------------------------------------------------------------------------
def _texto_pdf(conteudo):
    try:
        import PyPDF2 as _pdf
    except ImportError:  # ambiente só com pypdf
        import pypdf as _pdf
    leitor = _pdf.PdfReader(io.BytesIO(conteudo))
    return "\n".join((p.extract_text() or "") for p in leitor.pages)


def _depois(linhas, rotulo, ini=0):
    """Linha logo depois da primeira linha igual a `rotulo` (ou None)."""
    for i in range(ini, len(linhas) - 1):
        if _n(linhas[i]) == rotulo:
            return linhas[i + 1].strip()
    return None


def _indice(linhas, padrao, ini=0):
    rx = re.compile(padrao, re.I)
    for i in range(ini, len(linhas)):
        if rx.search(linhas[i]):
            return i
    return None


def _indice_catalogo(cat_produtos):
    """nome normalizado -> (nome, custo, venda, descrição) do catálogo."""
    idx = {}
    if cat_produtos is None or getattr(cat_produtos, "empty", True):
        return idx
    for _, r in cat_produtos.iterrows():
        nome = str(r.get("Item", "")).strip()
        if not nome:
            continue
        achado = (nome, utils.safe_float(r.get("Custo (R$)")),
                  utils.safe_float(r.get("Venda (R$)")), str(r.get("Descrição", "") or ""))
        # o PDF mostra o nome SEM a marca (utils.remover_marca_equipamento)
        for chave in (_n(nome), _n(utils.remover_marca_equipamento(nome))):
            idx.setdefault(chave, achado)
    return idx


def _resolver_item(linhas, idx):
    """Nome pode quebrar em mais de uma linha no PDF: tenta de 4 linhas até 1
    contra o catálogo (a mais longa primeiro) — o resto vira descrição."""
    for k in range(min(4, len(linhas)), 0, -1):
        achou = idx.get(_n(" ".join(linhas[:k])))
        if achou:
            return achou[0], "\n".join(linhas[k:]), achou, True
    return linhas[0], "\n".join(linhas[1:]), None, False


def _ajustar_precos(itens, alvo):
    """Faz Σ qtd × venda = alvo. Item sem preço conhecido (fora do catálogo)
    absorve a diferença; sem nenhum, reescala os do catálogo na proporção."""
    conhecidos = [i for i in itens if i["venda_un"] > 0]
    desconhecidos = [i for i in itens if i["venda_un"] <= 0]
    soma = sum(i["qtd"] * i["venda_un"] for i in conhecidos)
    if desconhecidos and conhecidos and alvo - soma > 0:
        qtd_desc = sum(i["qtd"] for i in desconhecidos) or 1
        for i in desconhecidos:
            i["venda_un"] = round((alvo - soma) / qtd_desc, 2)
    elif soma > 0:
        fator = alvo / soma
        for i in conhecidos:
            i["venda_un"] = round(i["venda_un"] * fator, 2)
    else:
        qtd_total = sum(i["qtd"] for i in itens) or 1
        for i in itens:
            i["venda_un"] = round(alvo / qtd_total, 2)
    resto = round(alvo - sum(i["qtd"] * i["venda_un"] for i in itens), 2)
    if itens and abs(resto) >= 0.01:
        ult = itens[-1]
        ult["venda_un"] = round(ult["venda_un"] + resto / (ult["qtd"] or 1), 2)


def ler_orcamento_pdf(conteudo, nome_arquivo, cat_produtos):
    """Lê o PDF e devolve um dict com cliente, número, itens, serviço, total...

    Nunca levanta por formato diferente: o que não foi entendido vira aviso.
    """
    texto = _texto_pdf(conteudo)
    todas = [l.strip() for l in texto.splitlines() if l.strip()]
    linhas = [l for l in todas if not _RE_RUIDO.match(l)]
    avisos = []

    m = re.search(r"\b(?:ORC|RASC)-(\d{6}-\d{4})", texto)
    m_arq = re.search(r"(\d{6}-\d{4})", nome_arquivo or "")
    dados = {
        "numero": m.group(1) if m else None,               # aammdd-HHMM do texto do PDF
        "numero_arquivo": m_arq.group(1) if m_arq else None,
        "cliente": _depois(linhas, "CLIENTE") or "",
        "telefone": _fmt_tel(_depois(linhas, "WHATSAPP") or ""),
        "capa": "", "itens": [], "subtotal_eq": None,
        "servico_txt": "", "servico_val": 0.0, "outros_txt": "", "outros_val": 0.0,
        "total": None, "obs": "", "padrao": False, "confere": False,
    }

    # capa = linha logo antes de "SELECIONADO"
    for i, l in enumerate(linhas):
        if _n(l) == "SELECIONADO" and i > 0:
            dados["capa"] = linhas[i - 1].strip()
            break

    # total: 1º "R$" depois de "INVESTIMENTO TOTAL" (o rótulo pode quebrar em 2 linhas)
    i_tot = _indice(linhas, r"^INVESTIMENTO\s+TOTAL")
    if i_tot is not None:
        for l in linhas[i_tot:i_tot + 4]:
            v = _brl(l)
            if v is not None:
                dados["total"] = v
                break

    i_eq = _indice(linhas, r"^\d\s*\.\s*EQUIPAMENTO")
    i_sub = _indice(linhas, r"^Subtotal de Equipamentos", i_eq or 0) if i_eq is not None else None
    i_serv = _indice(linhas, r"^\d\s*\.\s*SERVI[ÇC]OS")
    i_out = _indice(linhas, r"^\d\s*\.\s*OUTROS")
    dados["padrao"] = None not in (i_eq, i_sub, i_serv, i_out, i_tot)

    if dados["padrao"]:
        # --- equipamentos: blocos "nome + descrição ... quantidade [R$ ...]"
        idx = _indice_catalogo(cat_produtos)
        reg = [l for l in linhas[i_eq + 1:i_sub] if l.strip().lower() not in _CABECALHOS_TABELA]
        buf, brutos, k = [], [], 0
        while k < len(reg):
            if _RE_NUM.match(reg[k]) and buf:
                qtd, vals = float(reg[k].replace(",", ".")), []
                while k + 1 < len(reg) and reg[k + 1].startswith("R$"):
                    vals.append(_brl(reg[k + 1]))
                    k += 1
                brutos.append({"linhas": buf, "qtd": qtd, "vals": vals})
                buf = []
            else:
                buf.append(reg[k])
            k += 1
        dados["subtotal_eq"] = _brl(linhas[i_sub]) if _brl(linhas[i_sub]) is not None else (
            _brl(linhas[i_sub + 1]) if i_sub + 1 < len(linhas) else None)

        for b in brutos:
            nome, desc, achou, no_cat = _resolver_item(b["linhas"], idx)
            vals = [v for v in b["vals"] if v is not None]
            venda_un = None
            if len(vals) >= 2:
                venda_un = vals[0]
            elif len(vals) == 1 and b["qtd"]:
                venda_un = vals[0] / b["qtd"]
            dados["itens"].append({
                "nome": nome, "desc": desc, "qtd": b["qtd"],
                "custo_un": achou[1] if achou else 0.0,
                "venda_un": venda_un if venda_un is not None else (achou[2] if achou else 0.0),
                "preco_do_pdf": venda_un is not None, "no_catalogo": no_cat,
            })
        fora_catalogo = [i["nome"] for i in dados["itens"] if not i["no_catalogo"]]
        if fora_catalogo:
            avisos.append("Itens que não achei no catálogo atual (entram com custo R$ 0,00, então o lucro estimado "
                          "fica maior que o real até o custo ser ajustado): " + "; ".join(fora_catalogo) + ".")

        # preços: o PDF padrão só traz o subtotal; reescala o catálogo pra fechar com ele
        sem_preco = [i for i in dados["itens"] if not i["preco_do_pdf"]]
        if sem_preco and dados["subtotal_eq"] is not None:
            fixo = sum(i["qtd"] * i["venda_un"] for i in dados["itens"] if i["preco_do_pdf"])
            antes = sum(i["qtd"] * i["venda_un"] for i in sem_preco)
            _ajustar_precos(sem_preco, round(dados["subtotal_eq"] - fixo, 2))
            if abs(fixo + antes - dados["subtotal_eq"]) > 0.05:
                avisos.append("O PDF não mostra o preço de cada item, só o subtotal, e os preços atuais do catálogo "
                              "não fecham com ele. Ajustei os valores unitários pra bater com o subtotal do PDF "
                              f"({utils.to_br_currency(dados['subtotal_eq'])}) — confira a tabela acima.")

        # --- serviço
        fim_serv = i_out if i_out > i_serv else i_tot
        reg_s = [l for l in linhas[i_serv + 1:fim_serv] if _n(l) != "INSTALACAO"]
        vals_s = [_brl(l) for l in reg_s if _brl(l) is not None]
        dados["servico_val"] = vals_s[-1] if vals_s else 0.0
        dados["servico_txt"] = "\n".join(l for l in reg_s if _brl(l) is None)

        # --- outros / terceiros
        fim_out = next((j for j in range(i_out + 1, len(linhas))
                        if re.match(r"^(INVESTIMENTO TOTAL|SUBTOTAL|MATERIAL HIDR|OBSERVA)", _n(linhas[j]))), len(linhas))
        reg_o = [l for l in linhas[i_out + 1:fim_out] if _n(l) != "ADICIONAIS"]
        vals_o = [_brl(l) for l in reg_o if _brl(l) is not None]
        dados["outros_val"] = vals_o[-1] if vals_o else 0.0
        txt_o = "\n".join(l for l in reg_o if _brl(l) is None)
        dados["outros_txt"] = "" if "nenhum item adicional" in txt_o.lower() else txt_o

        # --- observações
        i_obs = _indice(linhas, r"^OBSERVA[ÇC][ÕO]ES")
        if i_obs is not None:
            fim = next((j for j in range(i_obs + 1, len(linhas))
                        if re.match(r"^(PRAZO DE EXECU|VALIDADE DA PROPOSTA|GARANTIA$)", _n(linhas[j]))), len(linhas))
            dados["obs"] = "\n".join(linhas[i_obs + 1:fim])

        if _indice(linhas, r"^\d\s*\.\s*MATERIAL HIDR"):
            avisos.append("Este PDF tem uma seção de material hidráulico — ela não foi importada como itens.")
        soma = (dados["subtotal_eq"] or 0.0) + dados["servico_val"] + dados["outros_val"]
        dados["confere"] = dados["total"] is not None and abs(soma - dados["total"]) < 0.05
        if not dados["confere"]:
            avisos.append("A conta do PDF não fechou (equipamentos + serviço + outros ≠ total). "
                          "Confira os valores antes de usar.")
    else:
        avisos.append("Este PDF não é do formato padrão do ERP (capa + equipamentos + serviços + outros): "
                      "li só o cliente, o número e o total, sem os itens.")
    # modelos antigos (antes do gerador atual): "Nome: ...", "WhatsApp: ...", "VALOR TOTAL: R$ ..."
    if not dados["cliente"]:
        mc = re.search(r"^Nome:\s*(.+)$", texto, re.M)
        dados["cliente"] = mc.group(1).strip() if mc else ""
    if not dados["telefone"]:
        mt = re.search(r"^WhatsApp:\s*(.+)$", texto, re.M | re.I)
        dados["telefone"] = _fmt_tel(mt.group(1)) if mt else ""
    if dados["total"] is None:
        mv = re.search(r"VALOR\s+TOTAL[^\n]*?R\$\s*([\d\.]+,\d{2})", texto)
        if mv:
            dados["total"] = float(mv.group(1).replace(".", "").replace(",", "."))
    if not dados["cliente"]:
        avisos.append("Não achei o nome do cliente no PDF.")
    if dados["total"] is None:
        avisos.append("Não achei o valor total no PDF.")
    dados["avisos"] = avisos
    return dados


# ---------------------------------------------------------------------------
# Busca na memória (Supabase)
# ---------------------------------------------------------------------------
_COLS = "id, numero_orcamento, nome_cliente, telefone_cliente, valor_venda_total, status_projeto, data_conclusao"


def _mesmo_cliente(nome_pdf, tel_pdf, linha):
    a, b = _n(nome_pdf), _n(linha.get("nome_cliente"))
    if a and b and (a == b or a in b or b in a or difflib.SequenceMatcher(None, a, b).ratio() >= 0.85):
        return True
    d1 = re.sub(r"\D", "", str(tel_pdf or ""))[-8:]
    d2 = re.sub(r"\D", "", str(linha.get("telefone_cliente") or ""))[-8:]
    return len(d1) == 8 and d1 == d2


def procurar_salvo(supabase, dados, nome_arquivo):
    """-> {"salvo": linha|None, "motivo": str, "parecidos": [linhas]}"""
    nomes = {nome_arquivo, re.sub(r"\s*\(\d+\)(?=\.pdf$)", "", nome_arquivo or "", flags=re.I)}
    nums = {n for n in (dados.get("numero"), dados.get("numero_arquivo")) if n}
    formas = {f"{p}{n}" for n in nums for p in ("", "ORC-", "RASC-")}

    def _por_ids(ids):
        ids = sorted({i for i in ids if i})
        if not ids:
            return []
        return supabase.table("servicos_andamento").select(_COLS).in_("id", ids).execute().data or []

    try:
        v = supabase.table("orcamento_versoes").select("servico_id, nome_arquivo").in_(
            "nome_arquivo", sorted(n for n in nomes if n)).execute().data or []
        achou = _por_ids([x["servico_id"] for x in v])
        if achou:
            return {"salvo": achou[0], "motivo": "o arquivo com esse nome já foi gerado por este ERP", "parecidos": []}

        if nums:
            v = supabase.table("orcamento_versoes").select("servico_id").in_(
                "numero_orcamento", sorted(nums)).execute().data or []
            achou = _por_ids([x["servico_id"] for x in v])
            if not achou:
                achou = supabase.table("servicos_andamento").select(_COLS).in_(
                    "numero_orcamento", sorted(formas)).execute().data or []
            if achou:
                return {"salvo": achou[0], "motivo": "pelo número da proposta", "parecidos": []}

        todos = supabase.table("servicos_andamento").select(_COLS).order("id", desc=True).limit(3000).execute().data or []
    except Exception as e:
        return {"salvo": None, "motivo": "", "parecidos": [], "erro": str(e)}

    mesmos = [r for r in todos if _mesmo_cliente(dados.get("cliente"), dados.get("telefone"), r)]
    total = dados.get("total")
    iguais = [r for r in mesmos if total is not None and abs(utils.safe_float(r.get("valor_venda_total")) - total) <= 0.5]
    if iguais:
        return {"salvo": iguais[0], "motivo": "mesmo cliente e mesmo valor", "parecidos": []}
    return {"salvo": None, "motivo": "", "parecidos": mesmos[:6]}


# ---------------------------------------------------------------------------
# Ações
# ---------------------------------------------------------------------------
def _snapshot(dados):
    return [{"Item": i["nome"], "Qtd": i["qtd"], "Venda Un.": i["venda_un"],
             "Custo Un.": i["custo_un"], "Descrição": i["desc"]} for i in dados["itens"]]


def _carregar_na_tela(snapshot, *, cliente, telefone, endereco, serv_txt, serv_val, out_txt, out_val,
                      obs, capa, rascunho_id, num_proposta, lista_nomes_produtos, cat_produtos, limpar_func):
    """Joga o orçamento na aba Orçamento Personalizado. Mesmo mapeamento do botão
    "Carregar" de rascunhos; sem gravar nada no banco."""
    linhas = []
    for it in snapshot:
        nome = str(it.get("Item", "") or "")
        manual, custo = "", utils.safe_float(it.get("Custo Un."))
        if nome and nome not in lista_nomes_produtos and nome != "OUTRO":
            manual, nome = nome, "OUTRO"
        elif nome and cat_produtos is not None and not cat_produtos.empty:
            m = cat_produtos[cat_produtos["Item"].astype(str).str.strip() == nome]
            if not m.empty:
                custo = utils.safe_float(m["Custo (R$)"].values[0])
        qtd, venda = utils.safe_float(it.get("Qtd")), utils.safe_float(it.get("Venda Un."))
        linhas.append({"Produto da Base": nome, "Produto Manual": manual, "Descrição": it.get("Descrição", "") or "",
                       "Quantidade": qtd, "Custo (R$)": custo, "Venda (R$)": venda,
                       "Custo Total": qtd * custo, "Venda Total": qtd * venda})
    while len(linhas) < 5:
        linhas.append({"Produto da Base": "", "Produto Manual": "", "Descrição": "", "Quantidade": 0,
                       "Custo (R$)": 0.0, "Venda (R$)": 0.0, "Custo Total": 0.0, "Venda Total": 0.0})
    df = pd.DataFrame(linhas)

    limpar_func()
    ss = st.session_state
    if rascunho_id:
        ss.rascunho_id = rascunho_id
    ss.input_nome_cliente, ss.input_whatsapp, ss.input_endereco_cliente = cliente, telefone, endereco or ""
    ss.txt_servico, ss.val_servico = serv_txt or "", float(serv_val or 0.0)
    ss.txt_outros, ss.val_outros = out_txt or "", float(out_val or 0.0)
    ss.input_obs_pdf = obs or "Material Hidráulico não incluído na proposta"
    ss.df_orc, ss.df_orc_prev = df, df.copy()
    ss.pop("editor_orc_base", None)
    capa = capa if capa in CAPAS else _op.detectar_capa_por_produtos(df)
    if capa in CAPAS:
        ss.input_modelo_capa = capa
        ss.capa_anterior_piscina = capa
    # Sem isto a automação da aba Personalizado enxerga "equipamentos mudaram" e
    # sobrescreve o serviço/valor importados com o do catálogo.
    ss.auto_equip_assinatura = _op._assinatura_produtos(df)
    ss.sel_servico_base = ss.servico_selecionado_anterior = "Manual"
    ss.sel_outros_base = ss.outros_selecionado_anterior = "Manual"
    if num_proposta:
        ss.num_proposta_atual = num_proposta


def _abrir_existente(supabase, linha, lista_nomes_produtos, cat_produtos, limpar_func):
    r = supabase.table("servicos_andamento").select("*").eq("id", linha["id"]).execute().data[0]
    dc = r.get("dados_contrato") or {}
    num = re.sub(r"^(ORC|RASC)-", "", str(r.get("numero_orcamento") or ""))
    _carregar_na_tela(
        r.get("detalhamento_itens") or [], cliente=r.get("nome_cliente", ""), telefone=r.get("telefone_cliente", "") or "",
        endereco=r.get("endereco_cliente", ""), serv_txt=r.get("servicos_adquiridos", "") or dc.get("txt_servico", ""),
        serv_val=utils.safe_float(dc.get("val_servico")), out_txt=dc.get("txt_outros", ""),
        out_val=utils.safe_float(dc.get("val_outros")), obs=dc.get("obs_pdf", ""), capa="",
        rascunho_id=r["id"], num_proposta=num if re.fullmatch(r"\d{6}-\d{4}", num) else None,
        lista_nomes_produtos=lista_nomes_produtos, cat_produtos=cat_produtos, limpar_func=limpar_func)


def _mover_para_andamento(supabase, linha):
    antes = linha.get("status_projeto")
    upd = {"status_projeto": "Em Andamento"}
    num = str(linha.get("numero_orcamento") or "")
    if num.startswith("RASC-"):  # deixou de ser rascunho: o número oficial é o ORC- do PDF enviado
        upd["numero_orcamento"] = "ORC-" + num[len("RASC-"):]
    supabase.table("servicos_andamento").update(upd).eq("id", linha["id"]).execute()
    movimentacoes.registrar(supabase, "servico", linha["id"], "status", de=antes, para="Em Andamento",
                            detalhe=linha.get("nome_cliente"))


def _enviar_direto(supabase, dados, nome_arquivo):
    snap = _snapshot(dados)
    custo_prod = sum(utils.safe_float(i["Qtd"]) * utils.safe_float(i["Custo Un."]) for i in snap)
    numero = f"ORC-{dados['numero']}" if dados.get("numero") else f"ORC-{datetime.datetime.now().strftime('%y%m%d-%H%M')}"
    payload = {
        "numero_orcamento": numero, "nome_cliente": dados["cliente"], "telefone_cliente": dados["telefone"],
        "endereco_cliente": "",
        "produtos_adquiridos": ", ".join(f"{int(i['Qtd'])}x {i['Item']}" for i in snap),
        "servicos_adquiridos": dados["servico_txt"], "valor_venda_total": dados["total"],
        "lucro_estimado": dados["total"] - custo_prod,
        "status_projeto": "Em Andamento", "detalhamento_itens": snap,
        "data_conclusao": datetime.date.today().strftime("%Y-%m-%d"),
        "dados_contrato": {
            "val_servico": dados["servico_val"], "txt_servico": dados["servico_txt"],
            "txt_outros": dados["outros_txt"], "val_outros": dados["outros_val"], "obs_pdf": dados["obs"],
            "importado_pdf": {"arquivo": nome_arquivo, "conferiu": bool(dados["confere"]),
                              "em": datetime.datetime.now().isoformat(timespec="seconds")},
        },
    }
    novo = supabase.table("servicos_andamento").insert(payload).execute().data[0]
    movimentacoes.registrar(supabase, "servico", novo["id"], "criou", para="Em Andamento",
                            detalhe=f"{dados['cliente']} (importado do PDF {nome_arquivo})")
    return novo["id"]


# ---------------------------------------------------------------------------
# Tela
# ---------------------------------------------------------------------------
def _resumo(dados):
    c1, c2, c3 = st.columns([2, 1, 1])
    c1.markdown(f"**{dados['cliente'] or '—'}**  \n{dados['telefone'] or ''}")
    c2.metric("Nº da proposta", f"ORC-{dados['numero']}" if dados.get("numero") else "—")
    c3.metric("Total", utils.to_br_currency(dados["total"]) if dados["total"] is not None else "—")
    if dados["itens"]:
        st.dataframe(pd.DataFrame([{
            "Item": i["nome"], "Qtd": i["qtd"], "Venda un.": utils.to_br_currency(i["venda_un"]),
            "Subtotal": utils.to_br_currency(i["qtd"] * i["venda_un"])} for i in dados["itens"]]),
            hide_index=True, use_container_width=True)
    if dados["servico_val"] or dados["servico_txt"]:
        st.caption(f"🛠️ Serviço: {dados['servico_txt'].splitlines()[0] if dados['servico_txt'] else '—'} — "
                   f"{utils.to_br_currency(dados['servico_val'])}")
    if dados["outros_val"]:
        st.caption(f"🤝 Outros: {utils.to_br_currency(dados['outros_val'])}")
    for a in dados["avisos"]:
        st.warning(a)


def _rotulo(r):
    return (f"{r.get('nome_cliente', '')} — {utils.to_br_currency(utils.safe_float(r.get('valor_venda_total')))}"
            f" — {r.get('status_projeto', '')} — {r.get('numero_orcamento') or 'sem nº'} (ID {r['id']})")


def renderizar(lista_nomes_produtos, cat_produtos, limpar_func):
    ss = st.session_state
    supabase = ss.supabase
    ss.setdefault("imp_orc_n", 0)

    with st.container(border=True):
        st.markdown("##### 📥 Importar orçamento já enviado")
        st.caption("Arraste aqui o PDF que você mandou ao cliente. O sistema procura se ele já está salvo; "
                   "se não estiver, você escolhe entre importar para editar ou enviar direto para Serviços em Andamento.")
        if ss.get("imp_orc_msg"):
            st.success(ss.pop("imp_orc_msg"))

        arq = st.file_uploader("PDF do orçamento enviado", type=["pdf"], key=f"imp_orc_up_{ss.imp_orc_n}",
                               label_visibility="collapsed")
        if arq is None:
            ss.pop("imp_orc_cache", None)
            return

        conteudo = arq.getvalue()
        sig = (arq.name, len(conteudo))
        cache = ss.get("imp_orc_cache")
        if not cache or cache["sig"] != sig:
            try:
                dados = ler_orcamento_pdf(conteudo, arq.name, cat_produtos)
                busca = procurar_salvo(supabase, dados, arq.name)
            except Exception as e:
                st.error(f"Não consegui ler esse PDF: {e}")
                return
            cache = {"sig": sig, "dados": dados, "busca": busca}
            ss["imp_orc_cache"] = cache
        dados, busca = cache["dados"], cache["busca"]
        chave = f"{ss.imp_orc_n}"

        _resumo(dados)
        if busca.get("erro"):
            st.error(f"Não consegui consultar o banco agora ({busca['erro']}). Tente de novo.")
            return

        def _concluir(msg):
            ss["imp_orc_msg"] = msg
            ss.imp_orc_n += 1
            ss.pop("imp_orc_cache", None)
            st.rerun()

        salvo = busca["salvo"]
        if not salvo and busca["parecidos"]:
            st.info("Não achei esse orçamento pelo número nem pelo valor, mas há registros do mesmo cliente:")
            opcoes = {_rotulo(r): r for r in busca["parecidos"]}
            nenhum = "Nenhum destes — é um orçamento novo"
            esc = st.selectbox("É algum destes?", [nenhum] + list(opcoes), key=f"imp_orc_sel_{chave}")
            if esc != nenhum:
                salvo = opcoes[esc]
                busca = {**busca, "motivo": "você escolheu este registro"}

        if salvo:
            st.success(f"✅ Já está salvo ({busca['motivo']}): **{_rotulo(salvo)}**")
            status = salvo.get("status_projeto")
            if status in STATUS_PODE_ANDAMENTO:
                b1, b2 = st.columns(2)
                if b1.button("✏️ Abrir para editar", use_container_width=True, key=f"imp_orc_ed_{chave}"):
                    _abrir_existente(supabase, salvo, lista_nomes_produtos, cat_produtos, limpar_func)
                    _concluir("Orçamento aberto na aba 📝 Orçamento Personalizado, logo abaixo.")
                if b2.button("🚀 Enviar para Em Andamento", type="primary", use_container_width=True,
                             key=f"imp_orc_mv_{chave}"):
                    _mover_para_andamento(supabase, salvo)
                    _concluir(f"🚀 {salvo['nome_cliente']} agora está em Serviços → Em Andamento.")
            else:
                st.caption(f"Esse orçamento já está em **{status}** — nada a fazer por aqui.")
            return

        st.info("🔎 Não encontrei esse orçamento salvo no sistema. O que você quer fazer?")
        pode_direto = bool(dados["cliente"]) and dados["total"] is not None
        b1, b2 = st.columns(2)
        if b1.button("📝 Importar e editar", use_container_width=True, key=f"imp_orc_im_{chave}"):
            _carregar_na_tela(
                _snapshot(dados), cliente=dados["cliente"], telefone=dados["telefone"], endereco="",
                serv_txt=dados["servico_txt"], serv_val=dados["servico_val"], out_txt=dados["outros_txt"],
                out_val=dados["outros_val"], obs=dados["obs"], capa=dados["capa"], rascunho_id=None,
                num_proposta=dados.get("numero"), lista_nomes_produtos=lista_nomes_produtos,
                cat_produtos=cat_produtos, limpar_func=limpar_func)
            _concluir("Orçamento importado na aba 📝 Orçamento Personalizado, logo abaixo — "
                      "ainda não foi gravado; ajuste e use Salvar Rascunho ou Salvar no Sistema.")
        if b2.button("🚀 Enviar direto para Em Andamento", type="primary", use_container_width=True,
                     disabled=not pode_direto, key=f"imp_orc_dir_{chave}"):
            try:
                novo_id = _enviar_direto(supabase, dados, arq.name)
            except Exception as e:
                st.error(f"Erro ao criar o serviço: {e}")
            else:
                _concluir(f"🚀 {dados['cliente']} foi criado em Serviços → Em Andamento (ID {novo_id}). "
                          "Falta definir instalador e custos por lá.")
        if not pode_direto:
            st.caption("Para enviar direto preciso do nome do cliente e do total — não consegui ler um deles.")
