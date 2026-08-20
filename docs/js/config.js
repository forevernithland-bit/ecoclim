// Configuração do projeto Supabase — mesma base que o ERP (Streamlit) já usa.
// A "anon key" é feita para ser pública (vai dentro do app, no navegador de
// qualquer instalador) — não é a mesma coisa que a service_role key, que
// NUNCA deve entrar aqui. Pegue os dois valores em: Supabase → Project
// Settings → API → "Project URL" e "anon public".
export const SUPABASE_URL = "https://ldoxfmdajhamdfrksyby.supabase.co";
export const SUPABASE_ANON_KEY = "sb_publishable_dWLIIeBa7Yj68FP4W4uq2A_ljsHb6W2";
