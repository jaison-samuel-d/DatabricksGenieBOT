# Setting up Genie Bot with OAuth

## Motivation

While using a PAT token or Service Principal are straightforward, most enterprises will need some sort of user-level authentication. This enables useful things like user-based auditing and user-based access control.

## Enter OAuth

Azure Bot Framework has some great support for OAuth, whether you're using Entra ID as your Identity Provider, or other IdPs that follow industry standard protocols like OAuth 2.0.

Because not everyone uses Entra, this sample will focus on using **Databricks** as the OAuth identity provider.

## Setting Up

1. Set up a new custom OAuth application in Databricks, following the [step-by-step instructions](https://docs.databricks.com/aws/en/integrations/enable-disable-oauth#enable-custom-app-ui).
   1. For the `redirect URL` field, enter `https://token.botframework.com/.auth/web/redirect`
      1. If you have any specific requirements on the redirect URL, Azure Bot Framework also provides [a few alternatives](https://learn.microsoft.com/en-us/azure/bot-service/ref-oauth-redirect-urls?view=azure-bot-service-4.0)
   1. Remember to generate a client secret.
   1. Take note of the `Client ID` and `Client Secret`, which you will need when configuring your Oauth connection for the Azure Bot.

1. Configure OAuth Connection for your Azure Bot
   1. In the Azure Bot that you created following the [instructions in this repo](../README.md), go to `Configuration`, under `Settings`.
   1. Click on `Add OAuth Connection Settings`
   1. Give your connection a name (in this example we'll call it `databricks`)
   1. For `Service Provider`, select `Generic OAuth 2`
   1. For the remaining fields:
      * Client Id: `<client_id_from_databricks_custom_oauth>`
      * Client Secret: `<client_secret_from_databricks_custom_oauth>`
      * Authorization URL: `https://<databricks-instance>/oidc/v1/authorize` OR `https://accounts.cloud.databricks.com/oidc/accounts/<my-account-id>/v1/authorize`
      * Token URL: `https://<databricks-instance>/oidc/v1/token` or `https://accounts.cloud.databricks.com/oidc/accounts/<my-account-id>/v1/token`
      * Refresh URL: Same as `Token URL`
      * Scopes: `openid, email, profile, offline_access, all-apis`
   1. Finish creating and test your OAuth connection.
