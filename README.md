# ZEUS IA — reconstrução

Nova interface de projeção para captura no TikTok LIVE Studio, com servidor Node, eventos TikTok via conexão direta, respostas com OpenAI e voz neural.

## Render
Frontend estático publica `public`. Backend Node executa `npm install` e `npm start`.

## Variáveis do backend
- `TIKTOK_USERNAME`: usuário da LIVE sem @.
- `OPENAI_API_KEY`: necessária para respostas IA e voz neural.
- `OPENAI_MODEL` (opcional; padrão gpt-4.1-mini).
- `OPENAI_TTS_MODEL` e `OPENAI_TTS_VOICE` (opcionais).

A conexão TikTok depende de uma LIVE pública ativa e da compatibilidade do conector. Voz e respostas não funcionam sem a chave OpenAI. Nunca coloque credenciais no código.
