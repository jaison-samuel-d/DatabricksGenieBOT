resource "random_uuid" "bot_id" {}

data "azuread_client_config" "current" {}

resource "azuread_application" "bot" {
  display_name     = "${var.prefix}-bot-sp"
  sign_in_audience = "AzureADandPersonalMicrosoftAccount"
  identifier_uris  = ["api://botid-${random_uuid.bot_id.result}"]
  owners           = [data.azuread_client_config.current.object_id]
  api {
    requested_access_token_version = 2
  }
}

resource "azurerm_bot_service_azure_bot" "genie_bot" {
  endpoint            = "https://${azurerm_linux_web_app.genie_app.default_hostname}/api/messages"
  location            = "global"
  microsoft_app_id    = azuread_application.bot.client_id
  microsoft_app_type  = "MultiTenant"
  display_name        = var.bot_name
  name                = "${var.prefix}-bot"
  resource_group_name = azurerm_resource_group.genie_rg.name
  sku                 = "F0"
}

resource "azurerm_bot_connection" "bot_aad" {
  count                 = var.auth_method == "oauth" ? 1 : 0
  name                  = "databricks"
  bot_name              = azurerm_bot_service_azure_bot.genie_bot.name
  location              = azurerm_bot_service_azure_bot.genie_bot.location
  resource_group_name   = azurerm_resource_group.genie_rg.name
  service_provider_name = "oauth2" # Generic Oauth 2
  client_id             = var.auth_method == "oauth" ? databricks_custom_app_integration.this[0].client_id : ""
  client_secret         = var.auth_method == "oauth" ? databricks_custom_app_integration.this[0].client_secret : ""
  parameters = {
    "authorizationUrl" : "${var.databricks_host}/oidc/v1/authorize",
    "tokenUrl" : "${var.databricks_host}/oidc/v1/token",
    "refreshUrl" : "${var.databricks_host}/oidc/v1/token"
  }
  scopes = "all-apis"
}

resource "azurerm_bot_channel_ms_teams" "teams" {
  bot_name            = azurerm_bot_service_azure_bot.genie_bot.name
  location            = azurerm_bot_service_azure_bot.genie_bot.location
  resource_group_name = azurerm_resource_group.genie_rg.name
}

locals {
  identifier_uri = tolist(azuread_application.bot.identifier_uris)[0]
}

resource "local_file" "manifest" {
  content = templatefile("${path.module}/manifest.json.tftpl", {
    bot_id = azurerm_bot_service_azure_bot.genie_bot.microsoft_app_id
    api_id = local.identifier_uri
  })
  filename = "${path.module}/../../appManifest/manifest.json"
}

resource "azuread_application_password" "bot" {
  application_id = azuread_application.bot.id
}
