${header}

I build Odoo modules at [Binhex](https://github.com/BinhexTeam) and send the reusable ones upstream to the [OCA](https://github.com/OCA). Mostly the parts where Odoo has to talk to something else: online stores, chat apps, mailboxes, webhooks. If I were an Odoo module, this would be my manifest:

```python
# oliverg09/__manifest__.py
{
    "name": "Oliver García",
    "summary": "Connects Odoo to the rest of the world",
    "version": "19.0.1.0.0",
    "author": "Binhex, Odoo Community Association (OCA)",
    "website": "https://github.com/oliverg09",
    "location": "Spain",
    "depends": ["python", "javascript", "postgresql", "owl", "connector", "queue_job"],
    "data": ["shopify.xml", "whatsapp.xml", "email.xml"],
    "external_dependencies": {"bin": ["coffee"]},
    "development_status": "Production/Stable",
    "maintainers": ["oliverg09"],
    "license": "AGPL-3",
}
```

## 🔌 Plugged into Odoo

<table>
<tr>
<td width="33%" valign="top">

**🛒 Shopify ⇄ Odoo**<br>
<sub>[OCA/connector-shopify](https://github.com/OCA/connector-shopify)</sub>

Took the connector and its accounting, POS and eCommerce modules to Odoo 18, added Dev Dashboard sign-in, and made token renewal safe when two workers race for it.

</td>
<td width="33%" valign="top">

**💬 Any inbox → Odoo**<br>
<sub>[OCA/social](https://github.com/OCA/social)</sub>

`mail_message_import`: one inbox for whatever a company receives, whatever the channel. Email and WhatsApp plug into it as their own modules.

</td>
<td width="33%" valign="top">

**📋 Requirements → Projects**<br>
<sub>[OCA/business-requirement](https://github.com/OCA/business-requirement)</sub>

When a business requirement is approved, its deliverables turn into project tasks, with the time already allocated.

</td>
</tr>
</table>

## 🌊 Where my pull requests go

${flow}

## ⏳ Waiting for review

${in_review}

## ✅ Recently merged

${merged}

<sub>Before Odoo: [NurseCare](https://github.com/oliverg09/Patient-Nurse-Call-System), a patient–nurse call system in FastAPI, my final project for the DAM degree.</sub><br>
<sub>Synced on ${synced}. A GitHub Action redraws this page every morning with plain Python ([`profile/`](profile)).</sub>
