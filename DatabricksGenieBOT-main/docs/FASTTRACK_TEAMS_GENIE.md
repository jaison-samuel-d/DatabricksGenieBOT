# Fast-track: Genie + Microsoft Teams (match video)

This guide gets you to **“Integrating Genie with Microsoft Teams: Seamless Text-to-SQL Access”** as quickly as possible.  
Flow: **Teams user → types "login" → OAuth (identity) → Bot → Web App → Genie API** so queries run under the user’s identity and Unity Catalog permissions apply.

---

## Checklist (in order)

### 1. Databricks

- [ ] **Genie space** with tables attached, connected to a **SQL warehouse** (Unity Catalog).
- [ ] **OAuth app** for the bot (so users sign in and get a token for Databricks):
  - In Databricks: create a **custom OAuth application** (or use Entra ID if your workspace uses it).
  - Redirect URL: `https://token.botframework.com/.auth/web/redirect`
  - Note **Client ID** and **Client secret** for step 3.
- [ ] Users who will use the bot must exist in Databricks and have access to the Genie space and underlying tables.

### 2. Azure Web App (`teams-genie-bot`)

- [ ] **Runtime:** Python 3.10 or 3.12.
- [ ] **Startup command:**
  ```bash
  gunicorn --bind 0.0.0.0 --worker-class aiohttp.worker.GunicornWebWorker --timeout 1200 --chdir src app:app
  ```
- [ ] **Application settings** (Configuration → Environment variables):

  | Name | Value |
  |------|--------|
  | `DATABRICKS_HOST` | `https://adb-2376768479807879.19.azuredatabricks.net` |
  | `APP_ID` or `MICROSOFT_APP_ID` | Your **Azure Bot** Microsoft App ID (e.g. `5800c88d-33dd-4e88-9c61-9c32505a37f2` for **teams-genie**) |
  | `APP_PASSWORD` or `MICROSOFT_APP_PASSWORD` | Azure Bot’s **client secret** (from the app registration) |
  | `OAUTH_CONNECTION_NAME` | Name you give the OAuth connection in the Bot (e.g. `databricks`) |
| `AUTH_METHOD` | `oauth` (for video flow; user signs in). Omit or set to `service_principal` for app-only auth. |

  For **OAuth (user identity)** you do **not** need `DATABRICKS_CLIENT_ID` / `DATABRICKS_CLIENT_SECRET` in the Web App; the user’s token is used.  
  For **service principal** (no user login), set `AUTH_METHOD=service_principal` in code and add `DATABRICKS_CLIENT_ID` and `DATABRICKS_CLIENT_SECRET` here.

- [ ] Deploy this repo to the Web App (e.g. `az webapp up`, or your CI/CD). Ensure `spaces.json` contains your Genie space ID (see `src/chatx/spaces.json`).

### 3. Azure Bot (e.g. **teams-genie**)

- [ ] **Configuration:**
  - **Messaging endpoint:** `https://teams-genie-bot-fyejdmdjf6bgerff.southindia-01.azurewebsites.net/api/messages` (your Web App URL + `/api/messages`).
  - **Microsoft App ID:** Same as the app registration used for the bot (e.g. `5800c88d-33dd-4e88-9c61-9c32505a37f2`).
  - Create the **client secret** in the app registration (Certificates & secrets) and use it as `APP_PASSWORD` / `MICROSOFT_APP_PASSWORD` in the Web App.
- [ ] **OAuth (to match the video – user signs in):**
  - In the Bot: **Configuration** → **Add OAuth Connection Settings**.
  - **Name:** e.g. `databricks` (must match `OAUTH_CONNECTION_NAME` in the Web App).
  - **Service provider:**  
    - **Databricks:** use **Generic OAuth 2** and set Authorization URL, Token URL, Scopes as in [databricks_oauth.md](./databricks_oauth.md).  
    - **Entra ID (Azure AD):** use **Azure AD v2** (or “Microsoft Entra ID”), same tenant as Teams, and the **same app registration** as the Bot (or a separate one with correct redirect and permissions).  
  - Scopes / permissions must allow getting a token that Databricks accepts (e.g. for Databricks OAuth: `openid, email, profile, offline_access, all-apis`; for Entra, ensure the app can get tokens for Databricks if your workspace uses Entra).
- [ ] **Channels:** Enable **Microsoft Teams** (and optionally Web Chat for testing).

### 4. OAuth vs service principal

- [ ] To match the **video (user login):**  
  In the Web App’s Application settings, add **`AUTH_METHOD`** = **`oauth`**, and set **`OAUTH_CONNECTION_NAME`** to the same name as the OAuth connection in the Bot (e.g. `databricks`). No code change needed.
- [ ] For **service principal** (no user login), set **`AUTH_METHOD`** = **`service_principal`** (or leave unset) and add **`DATABRICKS_CLIENT_ID`** and **`DATABRICKS_CLIENT_SECRET`** in the Web App.

### 5. Teams app (add bot to Teams)

- [ ] Use the **Manifest** in this repo: [../Manifest/](../Manifest/).
- [ ] In `Manifest/manifest.json`, ensure `id` and `bots[].botId` (and `webApplicationInfo.id` if present) are your **Azure Bot’s Microsoft App ID** (e.g. `5800c88d-33dd-4e88-9c61-9c32505a37f2` for **teams-genie**).
- [ ] Add icon files to the Manifest folder if required: `outline.png` (32×32), `color.png` (192×192). Update the `icons` section in the manifest if you use different names.
- [ ] Zip the contents of the `Manifest` folder (manifest.json + icons) as `teams-genie.zip`.
- [ ] In **Microsoft Teams:** **Apps** → **Manage your apps** → **Upload an app** → **Upload a custom app** → select `teams-genie.zip`. (You must be a Teams admin to upload.)
- [ ] Install the app for yourself or your team.

### 6. Test

1. Open the Genie bot in Teams.
2. Send **hi** → you should see: “Please type **login** to sign in and use Genie.”
3. Send **login** → OAuth sign-in (browser or inline) → after success you should see a success message.
4. Ask a natural-language question (e.g. “Describe the data” or “Show me count of product by distribution city”) → the bot calls Genie and returns the answer; in the Genie space the request appears under your user.

---

## Quick reference

| Item | Example / value |
|------|------------------|
| Web App URL | `https://teams-genie-bot-fyejdmdjf6bgerff.southindia-01.azurewebsites.net` |
| Messaging endpoint | `https://teams-genie-bot-fyejdmdjf6bgerff.southindia-01.azurewebsites.net/api/messages` |
| Bot (teams-genie) App ID | `5800c88d-33dd-4e88-9c61-9c32505a37f2` |
| Genie space (in code) | `src/chatx/spaces.json` (e.g. `"default": "01f08d9c974b134d9ebee73a06bd896e"`) |

---

## Troubleshooting

- **“Please type login”** → User has not signed in; type **login** and complete OAuth.
- **401 / 500 on messages** → Check Web App’s `APP_ID` / `APP_PASSWORD` match the Bot’s app registration; check messaging endpoint URL.
- **Genie errors** → Check `DATABRICKS_HOST`; for OAuth ensure the token from the Bot is valid for Databricks (correct OAuth connection and scopes).
- **No OAuth card in Teams** → Ensure OAuth connection name in Bot matches `OAUTH_CONNECTION_NAME` in the Web App; check Bot channel is Teams and the app is installed.

For OAuth with **Databricks** as provider, see [databricks_oauth.md](./databricks_oauth.md).  
For **service principal** only (no user login), see [DEPLOY_TEAMS_SERVICE_PRINCIPAL.md](./DEPLOY_TEAMS_SERVICE_PRINCIPAL.md).
