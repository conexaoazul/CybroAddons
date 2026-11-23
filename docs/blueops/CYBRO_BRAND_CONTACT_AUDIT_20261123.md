# CybroAddons 19.0 — auditoria de marca e canais (23/11/2026)

Snapshot: `conexaoazul/CybroAddons` `feat/blue-brand-whatsapp-p2-19.0`,
commit `8a776ed5b6d956b621f0b12e6dad4c4bd5a3dc89`.

## Entregas encadeadas, ainda sem merge/deploy

- PR #11: integração de 169 commits de CybroOdoo 19.0 em branch de revisão,
  mantendo 9 commits locais; sem conflito textual no merge-tree, QA pendente.
- PR #12: suporte transacional (P0), com endpoint explícito e falha segura.
- PR #13: 24 CTAs (WhatsApp, e-mail e central de ajuda) em 8 módulos prioritários.
- PR #14: logo oficial da Conexão Azul e crédito original da Cybrosys nessas
  8 páginas; sem alteração dos remetentes de mensagens dos clientes.

## Nova pesquisa no catálogo

Foram verificadas **842** páginas de apresentação (`static/description/index.html`)
dos módulos do fork, com categorias sobrepostas:

| Evidência | Páginas |
| --- | ---: |
| `wa.me/919074270811` (WhatsApp anterior) | 744 |
| `href="mailto:"` vazio | 679 |
| `href="skype:"` vazio | 660 |
| Logo Cybrosys (`Cybrosys.png` ou `Cybrosys R.png`) | 794 |

Além dos HTMLs de marketing, a varredura incluiu cerca de **16,3 mil** arquivos
operacionais Python/XML/JavaScript/CSS/SCSS. Excluídos os testes e
`static/description`, não restaram referências ao telefone anterior
`919074270811` nem ao endpoint `support.cybrosys.com`.

**Exceções que não devem ser automaticamente transferidas para a Conexão Azul:**

- `theme_buildcraft/views/contact_template.xml` usa `wa.me/971551234567`
  como exemplo de contato de uma empresa cliente.
- `theme_og_store/views/header.xml` contém `mailto:` vazio,
  `info@example.com` e telefone de exemplo.

Esses templates precisam utilizar telefone/e-mail configurados na empresa ou
website do cliente e devem ser testados em Odoo 19, não receber o contato
institucional da Conexão Azul indiscriminadamente.

## Controle e execução por lotes

`python3 scripts/cybro_brand_contact_audit.py --strict` verifica as oito páginas
prioritárias e sinaliza regressões; `--json` exporta o inventário em stdout.
O script é somente leitura e não modifica páginas nem dados.

1. P3a: decidir quais módulos efetivamente serão publicados e/ou instalados.
2. P3b: migrar CTAs dos módulos de maior valor comercial, preferindo um overlay
   de apresentação para reduzir conflitos com atualizações da origem.
3. P3c: substituir logos de catálogo apenas com crédito original de autoria,
   verificação de licença e imagem oficial válida.
4. P3d: corrigir os contatos de exemplo em temas usando configuração por site.

**Divergência em fonte primária:** o site institucional exibe
`+55 11 95192-4469`, enquanto o botão da própria central de ajuda aponta para
`https://wa.me/551151924469`. O número canônico ainda precisa de confirmação
operacional antes de um rollout amplo, mesmo quando os links coincidam com o
botão público atual.

### Gates para merge e deploy

Nenhuma destas PRs autoriza produção. Necessários: revisão de licenças e
copyright, CI, teste estático e visual, homologação Odoo 19 em base não
descartável, backup/restore, smoke e GO explícito.
