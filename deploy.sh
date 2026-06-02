#!/usr/bin/env bash

set -euo pipefail

IMAGE_NAME="${IMAGE_NAME:-maxbot}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
FULL_IMAGE_NAME="${FULL_IMAGE_NAME:-$IMAGE_NAME:$IMAGE_TAG}"

echo "Building image ${FULL_IMAGE_NAME}..."
docker build -t "${FULL_IMAGE_NAME}" .

echo "Image built successfully."
echo "Run locally with:"
echo "  docker compose up -d --build"

if [[ "${PUSH_IMAGE:-false}" == "true" ]]; then
  if [[ -z "${REGISTRY_IMAGE:-}" ]]; then
    echo "REGISTRY_IMAGE is required when PUSH_IMAGE=true"
    exit 1
  fi

  docker tag "${FULL_IMAGE_NAME}" "${REGISTRY_IMAGE}"
  docker push "${REGISTRY_IMAGE}"
  echo "Pushed ${REGISTRY_IMAGE}"
fi
