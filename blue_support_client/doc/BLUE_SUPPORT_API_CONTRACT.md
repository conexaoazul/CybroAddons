# Suporte Conexão Azul — integração do wizard (Odoo 19)

**Status:** código opt-in proposto, endpoint HTTP ainda **não homologado**.

O módulo técnico é `blue_support_client`, inclusive no overlay da imagem BlueApps19 DB Consultas. A PR legada CybroAddons#17 alterava `cybrosys_support_client` e não deve ser aplicada diretamente.

## Canais e segurança

- `blue_support.mode=gateway` (padrão): JSON-RPC ao Helpdesk central, com fallback SMTP; manter comportamento existente até revisão de idempotência do RPC.
- `blue_support.mode=local`: Helpdesk do banco local, com fallback SMTP.
- `blue_support.mode=api` (somente após QA): POST autenticado para endpoint HTTPS first-party, **sem fallback SMTP** após tentativa de POST, pois um timeout pode ocorrer depois da criação do ticket.
- Modo desconhecido: falha fechada.

Configurar `blue_support.endpoint_url` apenas em HTTPS sob `conexaoazul.com`, depois de homologar o contrato. Token preferencial no Docker secret apontado por `BLUE_SUPPORT_API_TOKEN_FILE=/run/secrets/blue_support_api_token`; montar no serviço Odoo com permissões adequadas. Se o caminho de secret for definido mas estiver ausente, **não** usar token de banco como fallback. O parâmetro legado `blue_support.api_token` fica disponível apenas para migração quando não houver secret mount.

`blue_support.tracking_url` é opcional e validado **antes** da tentativa de criação, evitando que uma URL inválida cause erro após um ticket remoto criado.

## Contrato HTTP proposto

```http
POST https://<dominio-first-party>/support/tickets
Authorization: Bearer <token-de-servico>
X-Idempotency-Key: <uuid-estavel-do-wizard>
X-Correlation-ID: <mesmo-uuid>
Accept: application/json
Content-Type: application/json
```

Payload atual mantém o envelope `{"params": {customer_name, email, phone, subject, description, support_type, category, priority, attachments}}`. A resposta síncrona confirmada exige `{"result":{"message":"success","ticket_id":"CA-123"}}`.

O cliente **não segue redirects**; falha em 401/403/429, resposta malformada e referência ausente, sem prometer sucesso. O receptor **deve deduplicar transacionalmente** por credencial/tenant + chave de idempotência e hash do payload, persistindo o mesmo receipt para retries. Caso uma chave seja reutilizada com payload diferente, retornar 409. Cabeçalhos não substituem deduplicação no servidor.

Limitar anexos (máx. 5 × 3 MiB binários no emissor), validar extensão/MIME/conteúdo no receptor, restringir tamanho do proxy (~20 MiB só de base64), aplicar rate limit e observabilidade sem guardar segredo ou base64 nos logs. Resolver tenant e fila Helpdesk pelo emissor autorizado, nunca pelo primeiro contato com e-mail igual entre clientes. Confirmar SLA e URL de acompanhamento somente com autorização por proprietário.

## Dependência n8n

O fluxo `gzczLBXgZqGeAZLt` (Criação de Tickets de Suporte v2) está ativo, mas `availableInMCP=false`; seu contrato real ainda não foi revisado. O webhook IA de `LUX7bo74Sq1eJUvE` não exige credenciais próprias: **não conectá-lo diretamente**.

Antes de habilitar `mode=api` em qualquer banco:

1. Inspecionar/homologar receptor dedicado, autenticação, deduplicação e permissão do usuário de serviço.
2. Testar sucesso → um ticket e referência canônica; duplo clique/timeout/retry → um ticket; mismatch de hash → 409.
3. Testar 401/403/429/5xx, redirect, timeouts, HTML, anexos, tenant A/B e traduções pt_BR.
4. Validar em QA com destino controlado, logs redigidos e fallback WhatsApp, depois GO explícito.
5. Publicar o overlay atualizado no BlueApps19; atualizar lock/digest e homologar imagem no azul2. Não usar OCI.

**Sem alteração de produção, n8n ou segredos por esta PR.**
