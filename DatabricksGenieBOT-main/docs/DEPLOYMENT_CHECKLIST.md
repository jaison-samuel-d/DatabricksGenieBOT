# Genie Bot – Deployment Checklist

Use this checklist to verify your Azure Web App and Bot are configured correctly.

---

## Web App (teams-genie-bot) – Application settings

| Name | Required | Value / Notes |
|------|----------|---------------|
| `APP_ID` | ✓ | Bot's Microsoft App ID (e.g. `f0c0e252-db28-4391-bafc-8577702c0767` for genie-bot-new) |
| `APP_PASSWORD` | ✓ | Bot's client secret (from App registration → Certificates & secrets) |
| `MICROSOFT_APP_TENANT_ID` | ✓ | Your tenant ID (e.g. `1c2be116-d207-42f3-952b-c66289745879`) – **required for single-tenant bots** to avoid AADSTS700016 |
| `DATABRICKS_HOST` | ✓ | `https://adb-xxxxx.xx.azuredatabricks.net` (no trailing slash) |
| `DATABRICKS_CLIENT_ID` | ✓ | Databricks service principal client ID |
| `DATABRICKS_CLIENT_SECRET` | ✓ | Databricks service principal client secret |
| `AUTH_METHOD` | ✓ | `service_principal` |
| `WEBSITES_PORT` | ✓ | `8000` |

---

## Web App – General settings

| Setting | Value |
|---------|--------|
| **Startup Command** | `gunicorn --bind 0.0.0.0:8000 --worker-class aiohttp.worker.GunicornWebWorker --timeout 1200 --chdir src app:app` |

---

## Bot (genie-bot-new) – Configuration

| Setting | Value |
|---------|--------|
| **Messaging endpoint** | `https://teams-genie-bot-fyejdmdjf6bgerff.southindia-01.azurewebsites.net/api/messages` |
| **Microsoft App ID** | Must match `APP_ID` in Web App |
| **Bot Type** | Single Tenant |
| **App Tenant ID** | Same as `MICROSOFT_APP_TENANT_ID` in Web App |

---

## Common errors and fixes

| Error | Fix |
|-------|-----|
| **AADSTS700016: Application not found in directory 'Bot Framework'** | Add `MICROSOFT_APP_TENANT_ID` to Web App Application settings (your tenant ID). |
| **Taking longer than usual to connect** | Check `APP_ID`/`APP_PASSWORD` match the bot, and `WEBSITES_PORT` = 8000. |
| **404 on site URL** | Add health endpoint and redeploy, or ensure `WEBSITES_PORT` = 8000. |
| **"Bot misconfigured: Databricks credentials..."** | Add `DATABRICKS_CLIENT_ID` and `DATABRICKS_CLIENT_SECRET` to Web App. |
| **"Send failed. Retry."** in Web Chat | Messaging endpoint wrong or unreachable. Verify URL exactly, no typos. Check Web App has no Access restrictions blocking Bot Framework. |

---

## After changes

1. **Save** Application settings.
2. **Restart** the Web App (Overview → Restart).
3. Wait 2–3 minutes.
4. Test in Web Chat (Start over → send a message).
