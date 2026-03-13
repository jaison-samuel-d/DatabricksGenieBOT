terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.37.0"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 3.4.0"
    }
    databricks = {
      source  = "databricks/databricks"
      version = "~> 1.85.0"
    }
  }
}
