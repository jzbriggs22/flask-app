terraform {
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = ">= 2.25.0"
    }
  }
}

# Configure the Kubernetes provider with your cluster credentials.
provider "kubernetes" {
  host                   = var.cluster_host
  client_certificate     = base64decode(var.client_certificate)
  client_key             = base64decode(var.client_key)
  cluster_ca_certificate = base64decode(var.cluster_ca_certificate)
}

locals {
  app_labels = {
    app = "task-registry"
  }

  env = {
    DATABASE_URL                = var.database_url
    API_AUTH_ENABLED            = "true"
    RATE_LIMIT_BACKEND          = var.rate_limit_backend
    RATE_LIMIT_REDIS_URL        = var.rate_limit_redis_url
    METRICS_KEY                 = var.metrics_key
    METRICS_CACHE_SECONDS       = tostring(var.metrics_cache_seconds)
    METRICS_CACHE_BYPASS_QUERY  = "refresh"
    METRICS_CACHE_OVERRIDES     = jsonencode({ "/metrics" = var.metrics_cache_seconds })
    VAULT_ENABLED               = tostring(var.vault_enabled)
    VAULT_ADDR                  = var.vault_addr
    VAULT_TOKEN                 = var.vault_token
    VAULT_MOUNT_POINT           = var.vault_mount_point
    VAULT_PATH_PREFIX           = var.vault_path_prefix
    VAULT_VERIFY_WRITES         = tostring(var.vault_verify_writes)
    VAULT_TRANSIT_KEY           = var.vault_transit_key
    AUDIT_LOG_ENABLED           = "true"
    AUDIT_QUEUE_ENABLED         = tostring(var.audit_queue_enabled)
    AUDIT_QUEUE_BACKEND         = var.audit_queue_backend
    AUDIT_QUEUE_KAFKA_BOOTSTRAP = var.audit_queue_kafka_bootstrap
    AUDIT_QUEUE_KAFKA_TOPIC     = var.audit_queue_kafka_topic
  }
}

resource "kubernetes_config_map" "task_registry_env" {
  metadata {
    name      = "task-registry-env"
    namespace = var.namespace
    labels    = local.app_labels
  }

  data = local.env
}

resource "kubernetes_secret" "task_registry_secrets" {
  metadata {
    name      = "task-registry-secrets"
    namespace = var.namespace
    labels    = local.app_labels
  }

  string_data = {
    metrics_key = var.metrics_key
    vault_token = var.vault_token
  }
}

resource "kubernetes_deployment" "task_registry" {
  metadata {
    name      = "task-registry"
    namespace = var.namespace
    labels    = local.app_labels
  }

  spec {
    replicas = var.replicas

    selector {
      match_labels = local.app_labels
    }

    template {
      metadata {
        labels = local.app_labels
      }

      spec {
        container {
          name  = "task-registry"
          image = var.image

          port {
            name           = "http"
            container_port = 8000
          }

          env_from {
            config_map_ref {
              name = kubernetes_config_map.task_registry_env.metadata[0].name
            }
          }

          env_from {
            secret_ref {
              name = kubernetes_secret.task_registry_secrets.metadata[0].name
            }
          }

          resources {
            limits = {
              cpu    = "500m"
              memory = "512Mi"
            }
            requests = {
              cpu    = "250m"
              memory = "256Mi"
            }
          }

          args = [
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000"
          ]
        }
      }
    }
  }
}

variable "namespace" {
  type = string
}

variable "image" {
  type    = string
  default = "ghcr.io/example/task-registry:latest"
}

variable "replicas" {
  type    = number
  default = 2
}

variable "database_url" {
  type = string
}

variable "rate_limit_backend" {
  type    = string
  default = "redis"
}

variable "rate_limit_redis_url" {
  type    = string
  default = "redis://task-registry-redis:6379/0"
}

variable "metrics_key" {
  type = string
}

variable "metrics_cache_seconds" {
  type    = number
  default = 15
}

variable "vault_enabled" {
  type    = bool
  default = false
}

variable "vault_addr" {
  type    = string
  default = "http://vault.vault.svc:8200"
}

variable "vault_token" {
  type      = string
  default   = ""
  sensitive = true
}

variable "vault_mount_point" {
  type    = string
  default = "secret"
}

variable "vault_path_prefix" {
  type    = string
  default = "task-registry/api-keys"
}

variable "vault_verify_writes" {
  type    = bool
  default = true
}

variable "vault_transit_key" {
  type    = string
  default = ""
}

variable "audit_queue_enabled" {
  type    = bool
  default = false
}

variable "audit_queue_backend" {
  type    = string
  default = "memory"
}

variable "audit_queue_kafka_bootstrap" {
  type    = string
  default = ""
}

variable "audit_queue_kafka_topic" {
  type    = string
  default = ""
}

variable "cluster_host" {
  type = string
}

variable "client_certificate" {
  type      = string
  sensitive = true
}

variable "client_key" {
  type      = string
  sensitive = true
}

variable "cluster_ca_certificate" {
  type      = string
  sensitive = true
}
