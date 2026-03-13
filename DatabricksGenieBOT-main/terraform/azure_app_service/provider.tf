provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

provider "azuread" {
  tenant_id = var.tenant_id
}

provider "databricks" {
  profile = var.databricks_profile
}
