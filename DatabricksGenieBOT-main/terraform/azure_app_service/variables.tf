variable "prefix" {
  description = "Prefix for all resources"
  type        = string
  default     = "databricks-chatx"
}

variable "bot_name" {
  description = "Name of the bot"
  type        = string
  default     = "Databricks ChatX"
}

variable "location" {
  description = "Location for all resources"
  type        = string
}

variable "subscription_id" {
  description = "Subscription ID for the Azure subscription"
  type        = string
}

variable "tenant_id" {
  description = "Tenant ID for the Azure Active Directory"
  type        = string
}

variable "databricks_host" {
  description = "Databricks host URL"
  type        = string
}

variable "databricks_profile" {
  description = "Databricks profile for authentication. This must be at account-level profile"
  type        = string
}

variable "auth_method" {
  description = "Auth method to use. oauth: for user authorization and data access, service-principal: for spn based data access"
  type        = string
  default     = "oauth"
  validation {
    condition     = contains(["oauth", "service-principal"], var.auth_method)
    error_message = "The auth_method value must be either 'oauth' or 'service-principal'."
  }
}

variable "databricks_spn_client_id" {
  description = "Databricks Service Principal Client ID (required when auth_method is set to 'service-principal')"
  type        = string
  default     = ""
}

variable "databricks_spn_client_secret" {
  description = "Databricks Service Principal Client secret (required when auth_method is set to 'service-principal')"
  type        = string
  default     = ""
}
