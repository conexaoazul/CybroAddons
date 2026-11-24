## Module <blue_support_client>

#### 13.06.2024
#### Version 19.0.1.0.0
#### ADD
- Initial commit

#### 12.08.2026
#### Version 19.0.1.0.1
#### UPDT
- Updated CSS to ensure consistent UI styling and flexibility across both light and dark modes.
#### 11.11.2026
#### Version 19.0.1.1.0
#### UPDT
- Requests to the support server now carry the module's API key (required by the server from cybrosys_support_server 19.0.2.1.0).
- Attachments are limited to images, PDF and Word documents, at most 5 files of 3 MB each, checked before sending.
- Clear messages for rejected requests (rate limit, file type or size, outdated module).

#### 23.11.2026 — Conexão Azul fork
#### Version 19.0.1.1.1
#### SECURITY / BRANDING
- Routes manual WhatsApp support to Conexão Azul Digital (+55 11 5192-4469).
- Removes the legacy Cybrosys ticket endpoint and static authentication token from runtime use.
- Ticket submission fails closed until a first-party HTTPS endpoint and bearer token are explicitly configured.
- Keeps legacy Odoo technical identifiers and original LGPL-3 attribution for compatibility.

#### 23.11.2026 — Brazilian Portuguese localization
#### Version 19.0.1.1.2
#### I18N
- Adds pt_BR translations for the support wizard, field labels, categories, priorities, errors and user notices.
- Keeps technical IDs, access control, WhatsApp destination, and fail-closed ticket submission unchanged.
- Requires module upgrade and pt_BR user language to display translated fields in Odoo 19.
