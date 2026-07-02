#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/DjangoPeng/agentic-ai"
REPO_DIR="${HOME}/projects/agentic-ai"
PROJECT_ROOT="${HOME}/projects/xhs-auto-publisher"

echo "[setup] step 1/3 - clone or update repo"
if [ -d "${REPO_DIR}/.git" ]; then
  git -C "${REPO_DIR}" pull
else
  mkdir -p "${HOME}/projects"
  git clone "${REPO_URL}" "${REPO_DIR}"
fi

echo "[setup] step 2/3 - link xhs-auto-publisher"
if [ -d "${PROJECT_ROOT}" ] && [ ! -L "${PROJECT_ROOT}" ]; then
  echo "[setup] removing old copy, replacing with symlink"
  rm -rf "${PROJECT_ROOT}"
fi
ln -sfn "${REPO_DIR}/xhs-auto-publisher" "${PROJECT_ROOT}"

echo "[setup] writing .env (MODE=draft)"
cp "${PROJECT_ROOT}/deploy/env.example" "${PROJECT_ROOT}/.env"
sed -i 's/^MODE=.*/MODE=draft/' "${PROJECT_ROOT}/.env"

echo "[setup] step 3/3 - install system dependencies and init project"
bash "${PROJECT_ROOT}/deploy/install_system_ubuntu.sh"
bash "${PROJECT_ROOT}/deploy/bootstrap_project.sh"

echo "[setup] done - project ready at ${PROJECT_ROOT}"
echo "[setup] code lives in ${REPO_DIR}/xhs-auto-publisher"
echo "[setup] to update: git -C ${REPO_DIR} pull"
echo "[setup] run with: bash ${PROJECT_ROOT}/deploy/run_with_xvfb.sh"
