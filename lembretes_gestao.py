"""Editar / encerrar recorrência / remover um lembrete de pagamento pendente
(tabela boletos_fornecedores). Usado pelo card da Página Inicial (app.py) e pela
aba Boletos de Documentos (tela_documentos.py).

Regra da recorrência do sistema: ao PAGAR um lembrete recorrente nasce o do
mês seguinte, copiando valor/categoria do pago. Logo:
  * editar o valor aqui já vale para os próximos meses;
  * "encerrar recorrência" só desmarca is_recorrente (este lembrete continua,
    mas ao pagar não nasce o próximo);
  * remover apaga este lembrete pendente (como nenhum outro nasce sozinho,
    a recorrência também acaba). Os já pagos ficam como histórico.
"""
import datetime

import streamlit as st

import utils

CATEGORIAS = ["Casa Airnb", "Ecoclim", "Consorbens", "Pessoal", "Outros"]


def _depois():
    utils.sincronizar_boletos_com_calendar()
    try:
        st.cache_data.clear()
    except Exception:  # noqa: BLE001
        pass
    st.rerun()


def formulario(sb, b, kp):
    """Desenha o formulário de gestão dentro do container atual (popover/expander)."""
    bid = b["id"]
    k = f"{kp}_{bid}"
    nome = st.text_input("Descrição", value=str(b.get("cliente") or "").strip(), key=f"{k}_nome")
    c1, c2 = st.columns(2)
    valor = c1.number_input("Valor (R$)", min_value=min(0.0, float(b.get("valor") or 0)), value=float(b.get("valor") or 0), step=10.0, format="%.2f", key=f"{k}_val")
    try:
        venc0 = datetime.datetime.strptime(str(b["vencimento"]), "%Y-%m-%d").date()
    except Exception:  # noqa: BLE001
        venc0 = datetime.date.today()
    venc = c2.date_input("Vencimento", value=venc0, format="DD/MM/YYYY", key=f"{k}_venc")
    cat_atual = b.get("categoria") if b.get("categoria") in CATEGORIAS else "Outros"
    cat = st.selectbox("Categoria", CATEGORIAS, index=CATEGORIAS.index(cat_atual), key=f"{k}_cat")
    rec = st.checkbox("🔄 Recorrente (gera o próximo ao pagar)", value=bool(b.get("is_recorrente")), key=f"{k}_rec")

    if st.button("💾 Salvar alterações", type="primary", use_container_width=True, key=f"{k}_salvar"):
        if not nome.strip():
            st.error("Informe a descrição.")
        else:
            sb.table("boletos_fornecedores").update({
                "cliente": nome.strip(), "valor": valor, "vencimento": venc.strftime("%Y-%m-%d"),
                "categoria": cat, "is_recorrente": bool(rec),
            }).eq("id", bid).execute()
            _depois()

    if b.get("is_recorrente"):
        if st.button("🔕 Encerrar recorrência (não gerar o próximo)", use_container_width=True, key=f"{k}_enc"):
            sb.table("boletos_fornecedores").update({"is_recorrente": False}).eq("id", bid).execute()
            _depois()

    st.divider()
    ok = st.checkbox("Confirmo remover este lembrete", key=f"{k}_okdel")
    if st.button("🗑️ Remover este lembrete", use_container_width=True, disabled=not ok, key=f"{k}_del"):
        import backup_dados as _bk
        _bk.excluir_com_copia(sb, "boletos_fornecedores", bid, f"Conta: {b.get('cliente', '')}")
        _depois()
