.. image:: https://img.shields.io/badge/license-LGPL--3-green.svg
    :target: https://www.gnu.org/licenses/lgpl-3.0-standalone.html
    :alt: License: LGPL-3

Conexão Azul Support Assistant
=============================
Contact Conexão Azul Digital from your Odoo 19 backend.

Overview
========
Adds a "Suporte Conexão Azul" tool to the Odoo backend. A headphones icon
appears in the systray (and an entry in the user menu); clicking it — or
pressing ``Alt+Shift+H`` — opens a wizard where any internal user can raise a
support request without leaving Odoo.

The wizard collects the customer name, email, phone, subject, description,
support type, category and priority, and lets the user attach files. A live
"Show what will be sent" preview displays the exact JSON payload (with
attachment bytes redacted) before submitting.

Two ways to send:

* **Submit** – disabled until an HTTPS endpoint and bearer token under a
  Conexão Azul-owned domain are configured. On success, a sticky notification
  shows the ticket reference returned by that endpoint.
* **WhatsApp** – opens a WhatsApp chat with Conexão Azul, with the request
  details pre-filled for user review before sending.

No request is sent to the former Cybrosys support server. The legacy endpoint
parameter is intentionally ignored, even when an older database retains it.

Features
========
* Systray icon + user-menu entry, with an ``Alt+Shift+H`` keyboard shortcut.
* Transient wizard (``client.support``) – no data stored locally.
* Support type, category and priority selection.
* Multiple file attachments (sent inline, base64-encoded).
* Payload preview before sending.
* WhatsApp fallback channel.
* Robust, user-friendly error handling on submission.

Data privacy
============
When a first-party endpoint has been configured, **Submit** sends the details
entered — name, email, phone, subject, description and attachments — to that
Conexão Azul endpoint over HTTPS. Without it, the operation fails closed.

* Nothing leaves your database unless a user explicitly clicks **Submit**
  after configuration, or opens **WhatsApp** and sends a message. The module
  does not automatically transmit data in the background.
* Only authenticated internal users can open the support wizard.
* Use the **Show what will be sent** preview to review the exact data before
  submitting.
* The destination must use HTTPS on ``conexaoazul.com`` or its subdomains.
  No first-party ticket API is enabled by default.

Configuration
=============
Configuration is intentionally opt-in for automated ticket submission:

* **Settings → Technical → System Parameters**
* ``blue_support.whatsapp_number`` – default ``551151924469``
* ``blue_support.endpoint_url`` – required first-party HTTPS API URL for Submit
* ``blue_support.api_token`` – required bearer token stored outside Git
* ``blue_support.tracking_url`` – optional first-party ticket tracking URL

Do not configure an endpoint or token before the Conexão Azul backend is
validated and the security/QA gate is approved. A pre-existing
``cybrosys_support_client.endpoint_url`` is ignored for privacy.

If the parameter is missing or blank, the module falls back to the default
above.

License
=======
GNU LESSER GENERAL PUBLIC LICENSE v3.0 (LGPL v3)
(https://www.gnu.org/licenses/lgpl-3.0-standalone.html)

Support provider
----------------
* `Conexão Azul Digital <https://www.conexaoazul.com/>`__

Contacts
--------
* Email: suporte@conexaoazul.com
* WhatsApp: https://wa.me/551151924469
* Website: https://www.conexaoazul.com

Bug Tracker
-----------
Bugs are tracked on GitHub Issues. In case of trouble, please check there if your issue has already been reported.

Attribution and maintenance
===========================
Original module and copyright: Cybrosys Techno Solutions, licensed LGPL-3.
Conexão Azul Digital maintains this fork's support routing, branding and
privacy changes. Original license and source attribution are preserved.

Further information
===================
HTML Description: `<static/description/index.html>`__
