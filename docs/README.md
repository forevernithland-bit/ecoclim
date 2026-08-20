# Ecoclim Instalador (PWA) — Fase 1

App instalável (sem loja de app) pro instalador ver as próprias instalações,
mesmo sem sinal — o que ele preencher em obra sincroniza sozinho quando
voltar a internet. Sem build (HTML/CSS/JS puro), grátis pra hospedar.

## O que já funciona nesta fase

- Login (usuário/senha, direto na tabela `usuarios_erp`).
- Sessão local: depois do primeiro login, abre offline sem pedir senha de novo.
- Lista "Minhas Instalações" (Em Aberto / Concluídas) — só as do instalador logado.
- Detalhe: cliente, telefone, endereço, produtos (sem preço), **Valor da
  Instalação em texto, não editável**.
- Campo de **Observação** (editável) e botão **"Marcar Instalação Concluída"**
  (grava a data do momento do clique, mesmo offline).
- Fila de sincronização: o que for feito sem sinal fica pendente e é enviado
  sozinho quando a internet voltar (evento `online` + verificação a cada 30s).

## Antes de usar — 2 passos obrigatórios

### 1. Rodar o SQL no Supabase (mesmo projeto do ERP)

```sql
alter table usuarios_erp add column instalador_vinculado text;
alter table servicos_andamento add column observacao_instalador text;
alter table servicos_andamento add column instalacao_concluida_instalador boolean default false;
alter table servicos_andamento add column data_conclusao_instalador date;
```

### 2. Preencher `js/config.js`

Pegue no Supabase → **Project Settings → API**:
- **Project URL** → `SUPABASE_URL`
- **anon public** (a chave pública, NÃO a `service_role`) → `SUPABASE_ANON_KEY`

### 3. Criar o login de um instalador de teste

Direto na tabela `usuarios_erp` do Supabase, insira uma linha:

| usuario | senha | nome_completo | perfil | ativo | instalador_vinculado |
|---|---|---|---|---|---|
| valdimar | (uma senha) | Valdimar Souza | Instalador | true | VALDIMAR *(exatamente igual ao nome usado em `config_instaladores` / no campo "Instalador" de Serviços em Andamento)* |

O campo `instalador_vinculado` **precisa bater exatamente** com o texto do
campo `instalador` em `servicos_andamento` — é assim que o app decide quais
instalações mostrar.

## Rodar localmente pra testar

Não precisa de Node — qualquer servidor estático simples serve, por exemplo:

```bash
python -m http.server 8765
```

Depois abra `http://localhost:8765` no navegador do celular (mesma rede) ou
no computador.

## Publicar de graça (GitHub Pages)

1. Crie um repositório novo no GitHub (ex. `ecoclim-instalador`), via GitHub
   Desktop, igual você já faz com o `github_ecoclim/ecoclim`.
2. Copie todo o conteúdo desta pasta pra dentro do repositório e publique
   (commit + push).
3. No GitHub, vá em **Settings → Pages**, escolha a branch `main` (pasta
   raiz) e salve. Em alguns minutos o app fica disponível em
   `https://SEU-USUARIO.github.io/ecoclim-instalador/`.
4. Esse link é o que o instalador abre no celular e escolhe **"Adicionar à
   tela de início"** (Android/Chrome) ou **"Adicionar à Tela de Início"**
   (iPhone/Safari) — vira um ícone de app normal.

## O que ainda falta (combinado, nesta ordem)

1. Fotos/vídeos da instalação + pasta automática por cliente no Drive.
2. Agenda de visitas (orçamento/manutenção), lista de materiais, financeiro
   do instalador (a receber x recebido).
3. Por último: segurança de verdade — Supabase Auth, RLS no banco, senha
   com hash, tela de criação de acesso (hoje é manual, direto no Supabase).
