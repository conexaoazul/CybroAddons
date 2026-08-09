# Análise de ROI — Módulos CybroAddons candidatos (IA / Social / WhatsApp)

**Contexto:** Este é um fork legítimo de [CybroOdoo/CybroAddons](https://github.com/CybroOdoo/CybroAddons), mantido pela Conexão Azul Digital como catálogo complementar de módulos Odoo 19. Já operamos módulos próprios relacionados neste domínio no repositório [BlueApps19](https://github.com/conexaoazul/BlueApps19): `blue_social`, `blue_social_api`, `blue_magica_ai_provider_openai`.

**Objetivo deste documento:** servir de briefing para um agente (Claude Code / Codex) analisar, em sessão dedicada, o valor real aplicado de cada módulo abaixo às nossas operações — não uma instalação cega de tudo. A meta é identificar o que agrega valor real de curto/médio prazo e onde escalar para maior ROI, evitando redundância com o que já existe.

## O que já temos (base existente, não duplicar)

| Módulo (BlueApps19) | Papel atual |
|---|---|
| `blue_social` | Núcleo de gestão social/mídia da Conexão Azul |
| `blue_social_api` | Camada de API do blue_social |
| `blue_magica_ai_provider_openai` | Provider OpenAI já integrado ao ecossistema Magica AI |

Qualquer módulo abaixo que sobreponha função com esses três precisa de justificativa clara pra ser adotado em vez de estender o que já existe.

## Os 19 módulos candidatos (dados reais extraídos dos `__manifest__.py`)

### Cluster OpenAI / Geração de conteúdo

| Módulo | Summary (real) | Depends |
|---|---|---|
| `openai_odoo_base` | Seamlessly integrates OpenAI capabilities into the Odoo. | base, base_setup |
| `openai_product_images` | Generate images for products using OpenAI. | base, product, openai_odoo_base |
| `openai_product_tag_descrption` | Automatically generate product tags and descriptions using OpenAI. | product, openai_odoo_base |
| `openai_website_product_media` | AI-generated product media images for eCommerce. | base, product, website_sale, openai_odoo_base, openai_product_images |
| `odoo_chatgpt_connector` | Connect Odoo with ChatGPT. | website, mail, web |
| `generative_ai` | Integrate AI tools in website snippet creation. | base, website, html_builder |
| `easy_chatgpt_access` | Access ChatGPT from systray. | html_editor |
| `pivot_ai_summary` | Instant summaries de pivot tables + queries em linguagem natural. | web, iap |

**Pergunta central pro analista:** `openai_odoo_base` compete ou complementa `blue_magica_ai_provider_openai`? Se competir, qual tem melhor arquitetura pra evoluir (multi-provider, custo por chamada, etc)?

### Cluster Ora-AI (assistente de voz)

| Módulo | Summary (real) | Depends |
|---|---|---|
| `ora_ai_base` | Base module p/ configurar o voice assistant. | base, bus, mail, website_sale |
| `ora_ai_call` | Permite pedidos via assistente por chamada. | ora_ai_base, sale |
| `ora_ai_website` | Pedidos via voice assistant direto no website. | ora_ai_base, website_sale |

**Relevância possível:** cruza com o projeto MagicaVoice (SIP/FusionPBX) já em andamento — ver memória `project_magicavoice_platform`. Avaliar se complementa ou é redundante.

### Cluster WhatsApp

| Módulo | Summary (real) | Depends |
|---|---|---|
| `whatsapp_mail_messaging` | Odoo WhatsApp Connector genérico. | sale, account, website, sale_management |
| `whatsapp_product_inquiry` | Cliente pergunta sobre produto do site via WhatsApp. | website_sale |
| `survey_whatsapp_integration` | Envia link de survey via WhatsApp. | base, survey |
| `website_floating_whatsapp_icon` | Ícone flutuante WhatsApp no site. | base, website |
| `whatsapp_chat_layout` | Redesenha o Discuss no layout WhatsApp. | base, mail, base_setup, web |
| `pos_receipt_invoice_send_whatsapp` | Envia recibo/fatura do PDV via WhatsApp. | point_of_sale, account |

**Contexto crítico:** já temos stack próprio de WhatsApp em produção (Evolution API, WA Cloud API BlueConnect, WAHA multi-provider — ver skill `waha-multi-provider-ops`). Esses módulos CybroAddons usam integração nativa Odoo (provavelmente `wa.io`/API oficial Meta via Odoo), que é uma abordagem DIFERENTE da nossa (proxy externo). Avaliar se algum aqui resolve uma lacuna real (ex: `pos_receipt_invoice_send_whatsapp` pra clientes com PDV) ou se é redundante/conflitante com o pipeline já validado.

### Outros

| Módulo | Summary (real) | Depends |
|---|---|---|
| `product_recommendation_ai` | Recomendações de produto com IA, múltiplas opções de performance. | website, website_sale, sale, sale_management |
| `chat_favourites_in_systray` | Acesso rápido a chats favoritos no systray. | mail |
| `website_extra_social_media` | Snippet de links extra de redes sociais no site. | website |

## O que pedimos pro agente que assumir esta análise

1. **Ler o código real de cada módulo** (não só o manifest) — arquitetura, qualidade, dependências ocultas, licença (CybroAddons é LGPL-3 geralmente, confirmar por módulo).
2. **Cruzar com blue_social / blue_social_api / blue_magica_ai_provider_openai** — mapear sobreposição real, não suposição.
3. **Para cada módulo, responder:**
   - Resolve uma dor real que já temos hoje (nomear o cliente/caso interno)?
   - Custo de portar/manter (LOC, dependências, risco de conflito com nosso fork 19.0-mod)?
   - ROI esperado: curto prazo (uso interno imediato) vs médio prazo (produto vendável a clientes)?
   - Escala: isso serve 1 cliente ou vira produto/feature de catálogo (ver `project_catalogo_produtos_skills`)?
4. **Produzir um ranking priorizado** (não instalar tudo) com recomendação de sim/não/talvez por módulo e por quê.
5. **Não instalar nada em produção sem QA + aprovação do Diego** — seguir o fluxo já validado em `odoo-consultas-module-deploy` / `odoo-dev-efficient`.

## Não-objetivos desta análise

- Não é pra portar os 19 de uma vez.
- Não é pra competir/substituir o stack WhatsApp já em produção sem justificativa forte.
- Não é pra duplicar `blue_magica_ai_provider_openai` sem entender por que o nosso foi feito do jeito que foi.

---
*Gerado em 2026-08-09 pela sessão Claude Code (Planner Agent) a pedido do Diego, como briefing para sessão dedicada futura de análise de ROI.*
