#!/usr/bin/env bash
#
# Cola Dong — update script
#
# Pulls the latest code, applies new migrations, and restarts the gunicorn
# service. Safe to run repeatedly; it is a no-op if there is nothing new.
#
# Usage:
#   bash deploy/update.sh
#
# The Django admin "Update now" button runs this same script, so the manual
# and the one-click paths stay in lockstep.
#
# The service runs as the deploying user (no root/sudo needed). After the
# code is updated the gunicorn master is signalled via its pidfile and
# systemd's Restart=always brings it back up.
#
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
APP_DIR="${REPO_DIR}/ColaDong"
VENV_PY="${REPO_DIR}/.venv/bin/python"
SERVICE="coladong"
LOG_DIR="/var/log/coladong"
PID_FILE="${LOG_DIR}/gunicorn.pid"

if [[ -t 1 ]]; then
    C_GRN=$'\033[0;32m'; C_YLW=$'\033[0;33m'; C_RED=$'\033[0;31m'; C_RST=$'\033[0m'
else
    C_GRN=""; C_YLW=""; C_RED=""; C_RST=""
fi
info() { printf '%s[%s]%s %s\n' "${C_GRN}"  "ok"   "${C_RST}" "$*"; }
step() { printf '\n%s==> %s%s\n' "${C_GRN}" "$*" "${C_RST}"; }
warn() { printf '%s[%s]%s %s\n' "${C_YLW}"  "warn" "${C_RST}" "$*"; }
err()  { printf '%s[%s]%s %s\n' "${C_RED}"  "err"  "${C_RST}" "$*" >&2; }
die()  { err "$*"; exit 1; }
ok()   { printf '%s[%s]%s %s\n' "${C_GRN}" "ok" "${C_RST}" "$*"; }

on_err() {
    local line="$1"
    err "Command failed at line ${line}: ${BASH_COMMAND}"
    die "Update aborted. The service was not restarted; check the output above."
}
trap 'on_err "$LINENO"' ERR

command -v git >/dev/null 2>&1 || die "git is not installed."

step "Pull latest changes"
cd "${REPO_DIR}"
BEFORE="$(git rev-parse HEAD)"
git pull --ff-only
AFTER="$(git rev-parse HEAD)"
if [[ "${BEFORE}" == "${AFTER}" ]]; then
    info "Already up to date (${AFTER:0:7})"
else
    info "Updated ${BEFORE:0:7} -> ${AFTER:0:7}"
fi

step "Refresh Python dependencies"
(cd "${REPO_DIR}" && uv sync --frozen) || (cd "${REPO_DIR}" && uv sync)

step "Apply database migrations"
(cd "${APP_DIR}" && "${VENV_PY}" manage.py migrate --noinput)

step "Re-collect static files"
(cd "${APP_DIR}" && "${VENV_PY}" manage.py collectstatic --noinput)

step "Restart ${SERVICE}"
if systemctl list-unit-files | grep -q "^${SERVICE}\.service"; then
    if [[ -f "${PID_FILE}" ]]; then
        local pid
        pid="$(cat "${PID_FILE}")"
        if kill -0 "${pid}" 2>/dev/null; then
            kill -TERM "${pid}"
            # Wait for graceful shutdown (gunicorn timeout is 60s, but usually <5s)
            local i
            for i in $(seq 1 15); do
                kill -0 "${pid}" 2>/dev/null || break
                sleep 1
            done
            if kill -0 "${pid}" 2>/dev/null; then
                warn "Graceful shutdown took longer than expected; sending SIGKILL"
                kill -9 "${pid}" 2>/dev/null || true
            fi
            ok "Gunicorn master (pid ${pid}) stopped; systemd will restart it."
        else
            warn "Pidfile exists but pid ${pid} is not running; sending SIGHUP for reload."
            systemctl reload "${SERVICE}" 2>/dev/null || systemctl start "${SERVICE}"
        fi
    else
        warn "No pidfile found at ${PID_FILE}; using systemctl restart."
        systemctl restart "${SERVICE}"
    fi
    sleep 2
    if systemctl is-active --quiet "${SERVICE}"; then
        ok "Service restarted and active."
    else
        err "Service failed after restart. Last log lines:"
        tail -n 20 "${LOG_DIR}/gunicorn.err.log" 2>/dev/null || true
        die "Service is not active after update."
    fi
else
    warn "${SERVICE}.service not found — skipping restart (run deploy/install.sh first)."
fi

ok "Update complete."
