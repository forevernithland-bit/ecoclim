#!/usr/bin/env bash
# Liga a IA (Google Gemini) do app Evolua na API da Ecoclim — com trava de segurança.
# Uso (terminal da VPS):  bash <(curl -fsSL https://raw.githubusercontent.com/forevernithland-bit/ecoclim/main/instalar_fit.sh)
#
# O que faz:
#  1. Confere se há alterações locais no código do servidor — se houver, PARA sem mexer em nada.
#  2. Backup do .streamlit/secrets.toml e anota a versão atual do código.
#  3. Pede a chave do Gemini (não aparece na tela) e grava na 1ª linha do secrets.toml.
#  4. git pull (só avança, nunca mistura) e reinicia SÓ o serviço ecoclim-api.
#  5. Testa. Se a API não voltar, desfaz tudo (código + secrets) e reinicia como estava.
# Não toca em n8n, Evolution, crons, nginx nem em nenhum outro serviço.

set -u
PASTA=/root/ecoclim-bot/ecoclim
SEGREDOS="$PASTA/.streamlit/secrets.toml"
SERVICO=ecoclim-api

verde() { printf "\033[32m%s\033[0m\n" "$*"; }
vermelho() { printf "\033[31m%s\033[0m\n" "$*"; }

cd "$PASTA" 2>/dev/null || { vermelho "Pasta $PASTA não encontrada. Nada foi alterado."; exit 1; }

echo "1/5  Conferindo o servidor..."
MEXIDOS=$(git status --porcelain --untracked-files=no)
if [ -n "$MEXIDOS" ]; then
  vermelho "Há arquivos alterados direto no servidor:"
  echo "$MEXIDOS"
  vermelho "Parei por segurança — NADA foi alterado. Mande este print para o Claude."
  exit 1
fi
if ! systemctl is-active --quiet "$SERVICO"; then
  vermelho "O serviço $SERVICO já estava parado antes de começar. Parei — NADA foi alterado."
  exit 1
fi
ANTES=$(git rev-parse HEAD)
verde "     OK (versão atual: ${ANTES:0:7})"

echo "2/5  Fazendo backup..."
CARIMBO=$(date +%Y%m%d-%H%M%S)
mkdir -p "$PASTA/.streamlit"
[ -f "$SEGREDOS" ] && cp -p "$SEGREDOS" "$SEGREDOS.bak-$CARIMBO"
verde "     OK (backup: secrets.toml.bak-$CARIMBO)"

echo "3/5  Chave do Gemini"
read -rsp "     Cole a chave e aperte Enter (ela não aparece na tela): " CHAVE < /dev/tty
echo
CHAVE=$(printf "%s" "$CHAVE" | tr -d '[:space:]"')
if [ ${#CHAVE} -lt 20 ]; then
  vermelho "Chave vazia ou curta demais. Parei — NADA foi alterado."
  exit 1
fi
CHAVE="$CHAVE" python3 - "$SEGREDOS" <<'PY'
import os, sys
caminho = sys.argv[1]
linhas = open(caminho, encoding="utf-8").read().splitlines() if os.path.exists(caminho) else []
linhas = [l for l in linhas if not l.strip().startswith("GEMINI_API_KEY")]
linhas.insert(0, 'GEMINI_API_KEY = "%s"' % os.environ["CHAVE"])
open(caminho, "w", encoding="utf-8").write("\n".join(linhas) + "\n")
PY
unset CHAVE
verde "     OK (gravada na 1ª linha do secrets.toml)"

desfazer() {
  vermelho "Algo deu errado — desfazendo tudo..."
  git reset -q --hard "$ANTES"
  [ -f "$SEGREDOS.bak-$CARIMBO" ] && cp -p "$SEGREDOS.bak-$CARIMBO" "$SEGREDOS"
  systemctl restart "$SERVICO"; sleep 4
  if systemctl is-active --quiet "$SERVICO"; then
    verde "Servidor voltou exatamente como estava. Mande o print para o Claude."
  else
    vermelho "ATENÇÃO: o serviço não voltou. Mande o print para o Claude."
  fi
  exit 1
}

echo "4/5  Atualizando o código..."
if ! git pull -q --ff-only; then
  vermelho "Não foi possível atualizar o código (nada do código mudou)."
  [ -f "$SEGREDOS.bak-$CARIMBO" ] && cp -p "$SEGREDOS.bak-$CARIMBO" "$SEGREDOS"
  vermelho "Secrets restaurado. Mande o print para o Claude."
  exit 1
fi
verde "     OK ($(git rev-parse --short HEAD))"

echo "5/5  Reiniciando só a API da Ecoclim e testando..."
systemctl restart "$SERVICO"
sleep 5
systemctl is-active --quiet "$SERVICO" || desfazer
DOCS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/docs)
[ "$DOCS" = "200" ] || desfazer
SAUDE=$(curl -s http://127.0.0.1:8000/fit/saude)
verde "     API da Ecoclim no ar ✅"
echo "     App fitness: $SAUDE"
echo
verde "Pronto! Nada do que já funcionava foi alterado além da atualização do código."
