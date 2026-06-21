# Terraform configuration for WW Bridge deployment
# Addresses NEW-V6-I1#2 (Captain Raj Kumar)

terraform {
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

variable "image_tag" {
  description = "Docker image tag"
  default     = "latest"
}

variable "host_port" {
  description = "Host port mapping"
  default     = 8080
}

provider "docker" {}

resource "docker_image" "ww_bridge" {
  name         = "ww-bridge:${var.image_tag}"
  build {
    path       = "../.."
    dockerfile = "deploy/Dockerfile"
  }
}

resource "docker_container" "ww_bridge" {
  image = docker_image.ww_bridge.name
  name  = "ww-bridge"
  
  ports {
    internal = 8080
    external = var.host_port
  }

  volumes {
    volume_name    = "ww_data"
    container_path = "/app/.ww"
  }

  env = [
    "WW_CONFIG=/app/config.yaml",
    "WW_WORKSPACE=/app",
  ]

  restart = "unless-stopped"

  healthcheck {
    test         = ["CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8080/api/v1/health', timeout=5)"]
    interval     = "30s"
    timeout      = "10s"
    retries      = 3
    start_period = "10s"
  }

  memory = 512
  memory_swap = 1024
}

resource "docker_volume" "ww_data" {
  name = "ww_data"
}

output "container_id" {
  value = docker_container.ww_bridge.id
}

output "health_url" {
  value = "http://localhost:${var.host_port}/api/v1/health"
}
