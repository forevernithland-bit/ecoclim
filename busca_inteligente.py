"""Busca "inteligente" de produtos/itens do sistema.

Diferente do filtro nativo das listas suspensas (que só acha o texto digitado
exatamente como está escrito, do começo, com acento), aqui:
  * as palavras podem vir em QUALQUER ordem ("316 15 tubos" acha
    "AQUECEDOR A VÁCUO ACOPLADO 15 TUBOS 316");
  * não importa acento nem maiúscula ("vacuo" = "VÁCUO");
  * começo de palavra basta ("aquece", "acopl", "16 tub");
  * singular/plural ("tubo" = "tubos");
  * erro de digitação leve ("aquesedor" -> "aquecedor");
  * "20t" / "20tb" = "20 tubos"; "mod" = módulo; "acop" = acoplado;
  * número só casa com o número inteiro ("15" não acha "150");
  * os melhores resultados vêm primeiro (frase exata e ordem original pesam mais);
  * se nenhum item tem TODAS as palavras, mostra os aproximados (que casam
    com a maioria), avisando que são aproximados.
Módulo sem dependência do banco; a caixa pronta para o Streamlit está em
`caixa_produto`.
"""
import difflib
import re
import unicodedata


# Abreviações comuns digitadas no dia a dia -> palavra do catálogo.
SINONIMOS = {"cx": "caixa", "reg": "registro", "tb": "tubo", "cond": "conector", "jlh": "joelho",
             "aquec": "aquecedor", "bba": "bomba", "pressuriz": "pressurizadora", "solen": "solenoide",
             "mod": "modulo", "acop": "acoplado"}
# Logo depois de um número, "t"/"tb"/"tbs" é sempre TUBOS: "20t" = "20 tubos"
# (acha os módulos e os aquecedores acoplados de 20 tubos).
_TUBOS_APOS_NUMERO = {"t", "tb", "tbs", "tub"}


def normalizar(texto):
    t = unicodedata.normalize("NFD", str(texto or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    # número colado em letra vira palavra separada: "20tubos" -> "20 tubos",
    # "2m" -> "2 m", "28x22" -> "28 x 22", "250w" -> "250 w"
    t = re.sub(r"(?<=\d)(?=[a-z])|(?<=[a-z])(?=\d)", " ", t)
    t = re.sub(r"[^a-z0-9]+", " ", t).strip()
    saida = []
    for p in t.split():
        if p in _TUBOS_APOS_NUMERO and saida and saida[-1].isdigit():
            saida.append("tubos")
        else:
            saida.append(SINONIMOS.get(p, p))
    return " ".join(saida)


def _singular(p):
    return p[:-1] if len(p) > 3 and p.endswith("s") and not p.endswith("ss") else p


def _tokens(texto):
    return [_singular(p) for p in normalizar(texto).split()]


def _pontos_token(tok, palavras):
    """Melhor pontuação de um termo digitado contra as palavras do item (0 = não casa)."""
    melhor = 0.0
    eh_num = tok.isdigit()
    for p in palavras:
        if p == tok:
            melhor = max(melhor, 3.0)
        elif eh_num:
            # número casa com o número inteiro ou com número+unidade ("250" -> "250w",
            # "20" -> "20mm"), mas nunca com outro número ("15" não acha "150")
            if p.startswith(tok) and not p[len(tok)].isdigit():
                melhor = max(melhor, 2.5)
            continue
        elif p.startswith(tok):
            melhor = max(melhor, 2.5 if len(tok) >= 2 else 1.0)
        elif len(tok) >= 3 and tok in p:
            melhor = max(melhor, 1.5)
        elif len(tok) >= 4 and len(p) >= 4 and difflib.SequenceMatcher(None, tok, p).ratio() >= 0.8:
            melhor = max(melhor, 1.0)
    return melhor


def _pontuar(termo, item):
    """(pontos, tokens_casados, total_tokens)."""
    tk = _tokens(termo)
    if not tk:
        return 0.0, 0, 0
    palavras = _tokens(item)
    pts, casados = 0.0, 0
    for t in tk:
        s = _pontos_token(t, palavras)
        if s > 0:
            casados += 1
            pts += s
    if casados == len(tk):
        item_norm = " ".join(palavras)
        if " ".join(tk) in item_norm:
            pts += 4.0  # frase inteira, na ordem
        # termos aparecem na mesma ordem do item?
        pos, ordem = -1, True
        for t in tk:
            achou = next((i for i, p in enumerate(palavras) if i > pos and (p == t or p.startswith(t))), None)
            if achou is None:
                ordem = False
                break
            pos = achou
        if ordem:
            pts += 2.0
        if palavras and palavras[0].startswith(tk[0]):
            pts += 1.5  # o nome COMEÇA pelo que foi digitado
        pts -= 0.02 * len(palavras)  # entre empates, o nome mais enxuto vem antes
    return pts, casados, len(tk)


def buscar(termo, itens, limite=10):
    """Devolve (lista_de_itens_ordenada, aproximado: bool)."""
    if not normalizar(termo):
        return [], False
    pont = []
    itens = list(dict.fromkeys(itens))  # mesmo nome de fornecedores diferentes aparece uma vez só
    for it in itens:
        s, c, n = _pontuar(termo, it)
        if n and c:
            pont.append((s, c, n, it))
    completos = sorted((x for x in pont if x[1] == x[2]), key=lambda x: (-x[0], str(x[3])))
    if completos:
        return [x[3] for x in completos[:limite]], False
    n_tok = len(_tokens(termo))
    if n_tok >= 2:  # nenhum tem tudo: mostra os que casam com a maioria das palavras
        parciais = sorted((x for x in pont if x[1] >= max(1, n_tok - 1)), key=lambda x: (-x[1], -x[0], str(x[3])))
        return [x[3] for x in parciais[:limite]], True
    return [], False


def termo_bate(termo, *campos):
    """Para filtros de tabela: True se TODAS as palavras do termo casam em algum
    dos campos (qualquer ordem, sem acento, início de palavra, erro leve)."""
    tk = _tokens(termo)
    if not tk:
        return True
    palavras = []
    for c in campos:
        palavras.extend(_tokens(c))
    return all(_pontos_token(t, palavras) > 0 for t in tk)


# ----------------------------------------------------------------------------
# Streamlit
# ----------------------------------------------------------------------------
def _escolher(key, nome):
    import streamlit as st
    st.session_state[f"{key}_pick"] = nome
    st.session_state[f"{key}_q"] = ""  # limpa a caixa (callback roda antes do widget ser recriado)


def caixa_produto(itens, key, rotulo="🔎 Buscar produto (digite partes do nome, em qualquer ordem)", maximo=8):
    """Mostra a caixa de busca + resultados clicáveis. Chame `retirar_escolha(key)`
    ANTES de desenhar a grade para saber se o usuário clicou em algum resultado."""
    import streamlit as st
    termo = st.text_input(rotulo, key=f"{key}_q", placeholder="ex.: 20t · mod 20t · acop 15t 316 · bomba pressurizadora")
    if not termo.strip():
        return
    achados, aprox = buscar(termo, [str(i) for i in itens if str(i).strip()], limite=maximo)
    if not achados:
        st.caption("Nenhum produto encontrado. Tente menos palavras ou só o começo delas.")
        return
    if aprox:
        st.caption("Nenhum item tem todas as palavras — resultados aproximados:")
    for i, nome in enumerate(achados):
        st.button(f"➕ {nome}", key=f"{key}_b{i}", use_container_width=True, on_click=_escolher, args=(key, nome))


def retirar_escolha(key):
    """Devolve (e esquece) o produto clicado na caixa de busca, ou None."""
    import streamlit as st
    return st.session_state.pop(f"{key}_pick", None)


def _vazio(v):
    return str(v).strip().lower() in ("", "nan", "none", "nat")


def adicionar_na_grade(df, col_produto, nome, valores, col_manual=None):
    """Põe `nome` (e `valores`: {coluna: valor}) na primeira linha vazia da grade
    (sem produto nem nome manual); se não houver, acrescenta uma linha no fim."""
    import pandas as pd
    df = df.copy().reset_index(drop=True)
    alvo = None
    for i in range(len(df)):
        if _vazio(df.at[i, col_produto]) and (col_manual is None or _vazio(df.at[i, col_manual])):
            alvo = i
            break
    if alvo is None:
        nova = {c: ("" if df[c].dtype == object else 0.0) for c in df.columns}
        df = pd.concat([df, pd.DataFrame([nova])], ignore_index=True)
        alvo = len(df) - 1
    df.at[alvo, col_produto] = nome
    for c, v in valores.items():
        if c in df.columns:
            df.at[alvo, c] = v
    return df
