# Terraform Infrastructure Overview

This Terraform configuration sets up a complete Azure-based infrastructure for deploying a chatbot that integrates with Databricks. The infrastructure includes:

## Core Azure Resources

- **Resource Group**: Creates an Azure resource group with configurable location and name prefix
- **App Service**: Provisions a Linux B1 service plan and web app configured to run a Python application
- **Bot Service**: Deploys an Azure Bot Service with Microsoft Teams channel integration

## Authentication & Security

- **Azure AD Integration**: Creates an Azure AD application for the bot with multi-tenant authentication
- **Databricks OAuth**: Sets up a Databricks custom app integration with OAuth scopes and token policies
- **Bot Connections**: Configures OAuth connection between the bot and Databricks

## Deployment Artifacts

- **Deployment Script**: Generates a deployment script based on the provisioned resources
- **Teams Manifest**: Creates a Teams app manifest file for easier distribution

## Configuration

- Uses variables for customization including prefix, location, and Databricks settings
- Configures Azure, Azure AD, and Databricks providers with appropriate versions

This infrastructure enables a secure chatbot application that can authenticate with Databricks and be deployed to Teams.
