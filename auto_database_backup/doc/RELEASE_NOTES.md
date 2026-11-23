## Module <auto_database_backup>

#### 19.09.2025
#### Version 19.0.1.0.0
#### ADD

- Initial commit for Automatic Database Backup To Local Server, Remote Server, Google Drive, Dropbox, Onedrive, Nextcloud and Amazon S3 Odoo19.

#### 25.05.2026
#### Version 19.0.1.0.1
#### UPDT

- Added option to submit support ticket.

#### 20.07.2026
#### Version 19.0.2.0.2
#### IMP

- Code Refactored
- New Features added


#### 12.08.2026
#### Version 19.0.2.0.3
#### UPDT

- Added blue_support_client as a dependency module




#### 23.11.2026 — Conexão Azul fork
#### Version 19.0.2.0.4
#### SECURITY / BRANDING / BUGFIX
- Routes WhatsApp support to Conexão Azul Digital (+55 11 5192-4469) via blue_support.whatsapp_number.
- Submit fails closed until a first-party HTTPS endpoint and bearer token (blue_support.endpoint_url / blue_support.api_token) are configured; legacy Cybrosys endpoint removed from runtime.
- Controller: download of fresh .dump no longer crashes with io.UnsupportedOperation (non-seekable pg_dump pipe handled).
- Landing page and docs rebranded; LGPL-3 attribution preserved.
