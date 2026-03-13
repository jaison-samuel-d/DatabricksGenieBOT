resource "databricks_custom_app_integration" "this" {
  count         = var.auth_method == "oauth" ? 1 : 0
  name          = "Genie Chatbot"
  confidential  = true
  redirect_urls = ["https://token.botframework.com/.auth/web/redirect"]
  scopes        = ["all-apis"]
  token_access_policy {
    access_token_ttl_in_minutes  = 60
    refresh_token_ttl_in_minutes = 10080
  }
}
