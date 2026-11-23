# Contrato de integração — Suporte Conexão Azul (Odoo 19 → API first-party)

**Status:** proposta técnica para homologação, não endpoint publicado.  
**Módulo emissor:** `cybrosys_support_client` (wizard interno `client.support`).  
**Destino:** API sob `conexaoazul.com`, com autenticação dedicada e registro efetivo de `helpdesk.ticket` ou outra entidade de atendimento canônica escolhida pelo time.

## Achados de integração em 23/11/2026

- O wizard já envia HTTP POST por HTTPS e só aceita domínio Conexão Azul; sem endpoint/token ele falha fechado e mantém o WhatsApp como alternativa.
- O workflow n8n **"Conexão Azul - Criação de Tickets de Suporte v2"** (`gzczLBXgZqGeAZLt`) consta **ativo**, porém os detalhes não foram disponibilizados ao conector (não autorizar um contrato inferido).
- O workflow n8n **"Conexão Azul - IA de Criação de Tickets de Suporte"** (`LUX7bo74Sq1eJUvE`) consta ativo e dispõe de ferramentas Odoo `helpdesk.ticket` para buscar/criar/atualizar. Sua entrada Webhook inspecionada **não exige autenticação própria**. **Não aponte o wizard diretamente para esse webhook.**
- Foi observada configuração sensível em parâmetro de nó de outro fluxo de notificação. Solicitar à operação rotação e migração para credencial gerenciada; nunca copiar valores para Git, logs ou tickets.
- A arquitetura `blue_chat_kanban_helpdesk` usa um bridge de eventos assinados e deduplica pela conversa. Essa é outra origem de tickets: evitar duplicar o mesmo chamado entre intake direto e bridge de conversa.

## Entrada HTTP proposta — versão 1

```http
POST https://<endpoint-first-party-confiavel>/support/tickets
Authorization: Bearer <token-de-servico>
X-Idempotency-Key: <uuid-persistido-no-wizard>
Accept: application/json
Content-Type: application/json
```

Payload atual (sem bytes reais no exemplo):

```json
{
  "params": {
    "customer_name": "Cliente",
    "email": "cliente@example.com",
    "phone": "+55...",
    "subject": "Problema com o Odoo",
    "description": "Descrição revisada",
    "support_type": "technical",
    "category": "Bug",
    "priority": "High",
    "attachments": [{"name": "evidencia.pdf", "data": "<base64>"}]
  }
}
```

**Atenção:** `category` e `priority` são rótulos de seleção no contrato legado, não códigos estáveis. O adapter deve validar/mapeá-los para os valores permitidos por `helpdesk.ticket`; evoluir para códigos em versão 2, sem mudar o wire format silenciosamente.

Resposta de sucesso **síncrona** obrigatória para a UI atual:

```json
{"result": {"message": "success", "ticket_id": "CA-12345"}}
```

Erros de negócio: `{"result":{"message":"unauthorized|rate_limited|too_many_files|file_too_large|file_type_not_allowed|invalid_payload"}}`. Códigos HTTP: 400/401/403/413/429/5xx conforme causa, sempre sem PII/segredos. Resposta malformada, redirecionamento, timeout ou 5xx = falha segura; não afirmar criação de ticket. Um `202` sem referência canônica não satisfaz a confirmação da UI.

## Requisitos do lado API/automação

1. **Entrada dedicada e autenticada**, hospedada em domínio first-party via proxy TLS. Não reutilizar diretamente os webhooks Chatwoot/IA antigos sem checagem de auth e schema. O bearer será armazenado em secret Docker/Portainer, montado no Odoo emissor em `/run/secrets/...`.
2. **Idempotência verdadeira no receptor:** chave única (`credential_id`, `X-Idempotency-Key`) + hash do payload; mesma chave e mesmo hash devolvem o mesmo ticket; mesma chave com payload diferente retorna conflito `409`, sem criar outro. Persistir o receipt de forma transacional com a criação. O cliente preserva a chave em retries.
3. **Identidade e multiempresa:** resolver empresa/cliente com regra explícita (e-mail/telefone + identificação da instalação confiável), sem escolher o primeiro `res.partner` ambíguo; usar equipe de suporte Conexão Azul configurada, não criar contatos/equipes indiscriminadamente. Testar isolamento de dois tenants.
4. **Armazenamento de anexos:** validar base64, tipo real/MIME e extensão, nomes saneados, antimalware e associação `res_model` + `res_id`; 5 × 3 MiB em binário geram aproximadamente **20 MiB de base64**, além do JSON — confirmar limites de n8n, reverse proxy e destino ou usar upload seguro separado. Não persistir base64 nos execution logs.
5. **Segurança operacional:** rate limit por credential/tenant, TTL/revogação de chave, IP/mTLS se viável, TLS válido, sem redirects, retenção/LGPD, logs somente com request-id/status, correlação e alarmes de repetição/falha. Nunca registrar bearer ou corpo.
6. **Roteamento e experiência:** aplicar prioridade (0–3), categoria, fila responsável e SLA; devolver o número real do ticket e URL de acompanhamento apenas se houver portal autorizado com ownership/token. Notificação ao time deve ocorrer **após** criação confirmada.
7. **Evitar duplicidade intercanal:** se um mesmo chamado também abrir conversa no Magic Chat, relacioná-lo ao ID do ticket/receipt e impedir criação paralela via bridge.

## Configuração do emissor após QA

- `blue_support.endpoint_url`: endereço HTTPS first-party **verificado**; não há valor default seguro.
- **Preferencial:** `BLUE_SUPPORT_API_TOKEN_FILE=/run/secrets/blue_support_api_token`, com Docker secret montado e legível pelo worker Odoo; falha do mount bloqueia o envio.
- **Legado:** `blue_support.api_token` em parâmetros do Odoo, usado só quando a variável de secret file não está definida.
- `blue_support.whatsapp_number=551151924469`: alternativa manual, não envia mensagem automaticamente.
- `blue_support.tracking_url`: somente depois de validar portal e autorização de acesso ao ticket.

**Não inserir um URL de exemplo em produção nem ativar a função com token de fluxo legado.**

## Critérios de aceite (QA isolada)

- [ ] Autenticação ausente/incorreta ⇒ 401 e nenhum ticket
- [ ] POST válido ⇒ exatamente um ticket com referência canônica; time, tipo e prioridade corretos
- [ ] Duplo clique, timeout e retry com a mesma chave ⇒ **um** ticket
- [ ] Mesma chave + payload diferente ⇒ 409 sem duplicar
- [ ] Tentativa de redirect/host externo ⇒ nenhum reenvio de body/Authorization
- [ ] Resposta sem JSON/`result` inválido ⇒ erro claro sem falso sucesso
- [ ] 400/413/429/5xx ⇒ UI pt-BR e WhatsApp alternativo, sem log de PII
- [ ] Testes de limites/anexos, MIME, scanner, multiempresa e retenção
- [ ] Observabilidade: receipt sem segredo, ID da conversa (se houver) e ID do ticket
- [ ] Smoke na QA permanente, backup/restauração, rollback e GO antes de produção

## Decisão de arquitetura pendente

Confirmar com o responsável do n8n/Odoo qual é o **system of record** do suporte (Helpdesk Odoo central x Magic Chat + bridge) e a equipe/inbox destino. O workflow v2 ativo é o primeiro candidato para análise de reuso, **mas não está homologado como endpoint do wizard**. Essa decisão não bloqueia o build do módulo; mantém **Submit fail-closed** até o contrato e os gates passarem.
