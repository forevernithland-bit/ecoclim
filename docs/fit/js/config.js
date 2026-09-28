// Mesmo Supabase do ERP Ecoclim (decisão do Breno: app pessoal, reaproveita a
// infraestrutura). Tudo deste app usa o prefixo "fit_" nas tabelas e o bucket
// "fit-fotos" — facilita separar num projeto próprio no futuro.
// A anon key é pública por natureza (vai no navegador); a service_role NUNCA entra aqui.
export const SUPABASE_URL = "https://ldoxfmdajhamdfrksyby.supabase.co";
export const SUPABASE_ANON_KEY = "sb_publishable_dWLIIeBa7Yj68FP4W4uq2A_ljsHb6W2";
export const BUCKET_FOTOS = "fit-fotos";

// Backend próprio (VPS da Ecoclim): rotas da IA ficam em /fit/*. A chave da
// Anthropic mora só no servidor.
export const API_BASE = "https://api.ecoclim.com.br";

// Troque para false se quiser usar o app 100% local (sem nuvem).
export const SYNC_ATIVO = true;
