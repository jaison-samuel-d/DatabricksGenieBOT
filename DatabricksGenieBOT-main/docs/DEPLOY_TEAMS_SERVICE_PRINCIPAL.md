# Deploy Genie Bot to Teams (Service Principal)

This guide uses **service principal** auth for Databricks (no user OAuth).  
Resources used: **Web App** `teams-genie-bot`, **Bot** `teams-genie`.

---

## 1. Resources summary

| Resource   | Value |
|-----------|--------|
| **Web App** | `teams-genie-bot` |
| **URL**     | `https://teams-genie-bot-fyejdmdjf6bgerff.southindia-01.azurewebsites.net` |
| **Bot**     | `teams-genie` (recommended) — App ID: `5800c88d-33dd-4e88-9c61-9c32505a37f2` |
| **Messaging endpoint** | `https://teams-genie-bot-fyejdmdjf6bgerff.southindia-01.azurewebsites.net/api/messages` |

**Bot choice:** Use **one** bot. `teams-genie` is recommended (simpler name). Both bots in your subscription point to the same web app; ensure the web app’s `APP_ID` and `APP_PASSWORD` match the bot you use.

---

## 2. Databricks service principal

1. In Databricks: **Settings** → **Developer** → **Service principals** (or create via OAuth M2M / account console).
2. Create a service principal and generate a **secret** (client secret).
3. Grant the SP access to the workspace and to the Genie space (e.g. allow “Genie user” or equivalent).
4. Note **Client ID** and **Client secret** for step 4.

---

## 3. Azure Bot secret

1. Azure Portal → **Bot** `teams-genie` (or the bot you chose) → **Configuration**.
2. Under **Microsoft App ID**, click **Manage** (opens App registration).
3. **Certificates & secrets** → **New client secret** → copy the **Value** (this is `APP_PASSWORD`; store it once).
4. **Application (client) ID** = `APP_ID` (e.g. `5800c88d-33dd-4e88-9c61-9c32505a37f2` for `teams-genie`).

---

## 4. Web App configuration

In Azure Portal → **Web App** `teams-genie-bot` → **Configuration** → **Application settings**, add or set:

| Name | Value | Notes |
|------|--------|------|
| `DATABRICKS_HOST` | `https://adb-2376768479807879.19.azuredatabricks.net` | No trailing slash |
| `DATABRICKS_CLIENT_ID` | \<your Databricks SP client id\> | Required for Genie (service principal) |
| `DATABRICKS_CLIENT_SECRET` | \<your Databricks SP client secret\> | Required for Genie (service principal) |
| `APP_ID` or `MICROSOFT_APP_ID` | Bot’s Microsoft App ID | See below |
| `APP_PASSWORD` or `MICROSOFT_APP_PASSWORD` | Bot’s client secret | From the same app as APP_ID |

The app reads bot credentials from **either** `APP_ID`/`APP_PASSWORD` **or** `MICROSOFT_APP_ID`/`MICROSOFT_APP_PASSWORD` (Azure often uses the latter).

**Which bot are you using?**
- **teams-genie** (recommended): use `APP_ID` / `MICROSOFT_APP_ID` = `5800c88d-33dd-4e88-9c61-9c32505a37f2` and that app’s client secret.
- **databricks-genie-teams**: use `APP_ID` / `MICROSOFT_APP_ID` = `c227e509-5774-44e1-b76b-12669d5914fc` and that app’s client secret.

The Web App’s App ID and password **must** match the Bot whose “Messaging endpoint” points to this Web App. Genie spaces are read from `spaces.json` in the repo (not from `GENIE_SPACE_ID` env).

**Startup command** (in **Configuration** → **General settings**):

```bash
gunicorn --bind 0.0.0.0:8000 --worker-class aiohttp.worker.GunicornWebWorker --timeout 1200 --chdir src app:app
```

> Ensure this matches `WEBSITES_PORT` (8000).

**Optional:** Set `SCM_DO_BUILD_DURING_DEPLOYMENT` to `true` so dependencies install on deploy.

**Python version:** App is currently **3.10**. The repo recommends **3.12**; you can change **General settings** → **Stack settings** to **Python 3.12** and redeploy if desired.

Save configuration and restart the web app if needed.

---

## 5. Bot ↔ Web App

1. **Bot** `teams-genie` → **Configuration**.
2. **Messaging endpoint** must be:  
   `https://teams-genie-bot-fyejdmdjf6bgerff.southindia-01.azurewebsites.net/api/messages`
3. **Channels:** Ensure **Microsoft Teams** (and optionally Web Chat) are enabled.

---

## 6. Genie space

The repo is set to use one Genie space:

- **Space ID:** `01f08d9c974b134d9ebee73a06bd896e`
- **Name in bot:** `@default` (users can type `@default` or “switch to @default”; with a single space it’s used by default).

Spaces are defined in `src/chatx/spaces.json`. To add more, add entries and redeploy.

---

## 7. Deploy code

From the project root (where `requirements.txt` and `src/` are):

```bash
# Azure CLI login
az login

# Deploy (replace with your resource group / app name if different)
az webapp up --name teams-genie-bot --resource-group Metadata_Framework1 --runtime "PYTHON:3.10"
```

Or use your existing CI/CD / ZIP deploy so that the **startup command** and **application settings** above are unchanged.

---

## 8. Test

1. **Web Chat:** Bot resource → **Test in Web Chat** — send a message (e.g. “What tables are there?”). With service principal, no sign-in is required.
2. **Teams:** **Channels** → **Microsoft Teams** → **Open in Teams**. In Teams, open the bot and send the same message.

If you see 401/502, check `APP_ID`/`APP_PASSWORD` and that the bot’s messaging endpoint URL is exactly as above. If Genie returns errors, check `DATABRICKS_HOST`, `DATABRICKS_CLIENT_ID`, and `DATABRICKS_CLIENT_SECRET` and that the service principal has access to the Genie space.

---

## 9. Changes not reflected after push

If you pushed code but the bot still shows old behavior:

1. **Push to `main`** — The GitHub Action deploys only on push to the `main` branch. Pushing to another branch will not trigger deployment.

2. **Check GitHub Actions** — Repo → **Actions** tab. Confirm the deploy workflow ran and completed successfully after your push.

3. **Restart the Web App** — Azure Portal → Web App `teams-genie-bot` → **Overview** → **Restart**.

4. **Start a new conversation** — Teams may cache old cards. Delete the chat with the bot and start a new one, or use "Start over" in Web Chat.

5. **Manual deploy** — If GitHub Actions is not set up or failing:
   ```bash
   az login
   az webapp up --name teams-genie-bot --resource-group Metadata_Framework1 --runtime "PYTHON:3.10"
   ```
   Run from the project root (where `requirements.txt` and `src/` are).
