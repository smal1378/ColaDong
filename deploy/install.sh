#!/usr/bin/env bash
#
# Cola Dong — Ubuntu 22.04 installer
#
# Installs the Django app onto this server, wires up a gunicorn process under
# systemd, and prints an nginx site config you can drop into place.
#
# Usage:
#   sudo bash deploy/install.sh          # install (or reinstall)
#   sudo bash deploy/install.sh uninstall# remove the service + generated files
#
# The script operates on the repository checkout that contains it, so put the
# repo on the server first (git clone / copy) and then run this.
#
set -Eeuo pipefail

# ---------------------------------------------------------------------------
# Locations (derived from where this script lives)
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"      # git root (pyproject.toml, .venv)
APP_DIR="${REPO_DIR}/ColaDong"                   # manage.py, db.sqlite3, Django pkg
VENV_PY="${REPO_DIR}/.venv/bin/python"
VENV_GUNICORN="${REPO_DIR}/.venv/bin/gunicorn"
ENV_FILE="/etc/coladong/coladong.env"
SERVICE_FILE="/etc/systemd/system/coladong.service"
LOG_DIR="/var/log/coladong"
STATIC_ROOT="${APP_DIR}/staticfiles"
NGINX_CONF="${REPO_DIR}/coladong-nginx.conf"
GUNICORN_BIND="${GUNICORN_BIND:-127.0.0.1:8000}"
GUNICORN_WORKERS="${GUNICORN_WORKERS:-3}"
PID_FILE="${LOG_DIR}/gunicorn.pid"

# User the service runs as: whoever invoked sudo, else the current user.
RUN_USER="${SUDO_USER:-$(id -un)}"

# ---------------------------------------------------------------------------
# Small output helpers
# ---------------------------------------------------------------------------
if [[ -t 1 ]]; then
    C_RED=$'\033[0;31m'; C_GRN=$'\033[0;32m'; C_YLW=$'\033[0;33m'; C_BLU=$'\033[0;34m'; C_RST=$'\033[0m'
else
    C_RED=""; C_GRN=""; C_YLW=""; C_BLU=""; C_RST=""
fi
info()  { printf '%s[%s]%s %s\n' "${C_BLU}" "info" "${C_RST}" "$*"; }
ok()    { printf '%s[%s]%s %s\n' "${C_GRN}" "ok"   "${C_RST}" "$*"; }
warn()  { printf '%s[%s]%s %s\n' "${C_YLW}" "warn" "${C_RST}" "$*"; }
err()   { printf '%s[%s]%s %s\n' "${C_RED}" "err"  "${C_RST}" "$*" >&2; }
die()   { err "$*"; exit 1; }
step()  { printf '\n%s==> %s%s\n' "${C_GRN}" "$*" "${C_RST}"; }

on_err() {
    local line="$1"
    err "Command failed at line ${line}:"
    err "  ${BASH_COMMAND}"
    die "Aborting. Re-run the script to retry (it is idempotent)."
}
trap 'on_err "$LINENO"' ERR

require_root() {
    if [[ "${EUID}" -ne 0 ]]; then
        die "This script must be run as root. Try: sudo bash deploy/install.sh"
    fi
}

# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------
do_uninstall() {
    require_root
    step "Uninstalling Cola Dong"

    if systemctl list-unit-files | grep -q '^coladong\.service'; then
        info "Stopping and disabling coladong.service"
        systemctl disable --now coladong.service 2>/dev/null || true
        rm -f "${SERVICE_FILE}"
        systemctl daemon-reload
        ok "Service removed"
    else
        info "coladong.service not found — nothing to stop"
    fi

    rm -f "${ENV_FILE}"
    rm -f "${NGINX_CONF}"
    rm -rf "${LOG_DIR}"
    rmdir /etc/coladong 2>/dev/null || true

    # Leave the checkout, .venv and database in place (your data).
    warn "Left ${REPO_DIR} (code + ${APP_DIR}/db.sqlite3) untouched."
    warn "If you want a full wipe, delete that directory manually."
    ok "Uninstall complete."
    warn "You may still need to remove the nginx site config and reload nginx."
}

do_install() {
    require_root

    # -- 1. Ask for the host name ------------------------------------------------
    step "Configuration"
    if [[ -n "${COLADONG_DOMAIN:-}" ]]; then
        DOMAIN="${COLADONG_DOMAIN}"
        info "Using COLADONG_DOMAIN=${DOMAIN} (env override)"
    else
        read -rp "$(printf '%s' "Domain or IP (e.g. coladong.example.com or 192.168.1.10): ")" DOMAIN
    fi
    DOMAIN="${DOMAIN//\//}"   # nginx server_name cannot contain '/'
    DOMAIN="${DOMAIN//[:space:]/}"
    [[ -n "${DOMAIN}" ]] || die "A domain or IP is required."
    ok "Host: ${DOMAIN}   (user: ${RUN_USER}, deploy: ${REPO_DIR})"

    # -- 2. uv -------------------------------------------------------------------
    step "Package manager (uv)"
    if ! command -v uv >/dev/null 2>&1; then
        info "uv not found — installing via the official installer"
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="${HOME}/.local/bin:${PATH}"
        command -v uv >/dev/null 2>&1 || die "uv install failed."
    fi
    ok "uv $(uv --version 2>/dev/null | awk '{print $2}')"

    # -- 3. Python environment ---------------------------------------------------
    step "Python environment (uv sync)"
    [[ -f "${APP_DIR}/manage.py" ]] || die "manage.py not found under ${APP_DIR} — wrong repo layout?"
    (cd "${REPO_DIR}" && uv sync)
    ok "venv ready at ${REPO_DIR}/.venv"

    # -- 4. Secrets / env file ---------------------------------------------------
    step "Environment file"
    local secret_key
    if [[ -f "${ENV_FILE}" ]] && grep -q '^DJANGO_SECRET_KEY=' "${ENV_FILE}"; then
        secret_key="$(sed -n 's/^DJANGO_SECRET_KEY=//p' "${ENV_FILE}")"
        info "Reusing existing secret key from ${ENV_FILE}"
    else
        secret_key="$(openssl rand -base64 48)"
        info "Generated a new secret key"
    fi
    mkdir -p /etc/coladong
    cat > "${ENV_FILE}" <<EOF
DJANGO_SECRET_KEY=${secret_key}
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=${DOMAIN},localhost
DJANGO_STATIC_ROOT=${STATIC_ROOT}
EOF
    chmod 600 "${ENV_FILE}"
    chown "${RUN_USER}:${RUN_USER}" "${ENV_FILE}"
    ok "Wrote ${ENV_FILE} (mode 600)"

    # -- 5. Migrations + static --------------------------------------------------
    step "Database migrations"
    (cd "${APP_DIR}" && "${VENV_PY}" manage.py migrate --noinput)
    ok "Migrations applied"

    step "Collecting static files"
    mkdir -p "${STATIC_ROOT}"
    (cd "${APP_DIR}" && "${VENV_PY}" manage.py collectstatic --noinput)
    chown -R "${RUN_USER}:${RUN_USER}" "${REPO_DIR}" || warn "chown of ${REPO_DIR} failed (continuing)"
    ok "Static files collected to ${STATIC_ROOT}"

    # -- 6. systemd unit ---------------------------------------------------------
    step "systemd service"
    mkdir -p "${LOG_DIR}"
    chown "${RUN_USER}:${RUN_USER}" "${LOG_DIR}"
    cat > "${SERVICE_FILE}" <<EOF
[Unit]
Description=Cola Dong (Django via gunicorn)
After=network.target

[Service]
Type=simple
User=${RUN_USER}
Group=${RUN_USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${VENV_GUNICORN} ColaDong.wsgi:application \
    --bind ${GUNICORN_BIND} \
    --workers ${GUNICORN_WORKERS} \
    --timeout 60 \
    --pid ${PID_FILE}
Restart=always
RestartSec=3
StandardOutput=append:${LOG_DIR}/gunicorn.log
StandardError=append:${LOG_DIR}/gunicorn.err.log

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable --now coladong.service
    sleep 1
    if systemctl is-active --quiet coladong.service; then
        ok "coladong.service is running"
    else
        err "coladong.service failed to start. Last log lines:"
        tail -n 20 "${LOG_DIR}/gunicorn.err.log" 2>/dev/null || true
        die "Service is not active. Check ${LOG_DIR}/gunicorn.err.log"
    fi

    # -- 7. nginx example --------------------------------------------------------
    step "nginx configuration"
    generate_nginx_conf "${DOMAIN}"
    ok "Wrote example nginx config to ${NGINX_CONF}"

    # -- 8. Summary --------------------------------------------------------------
    step "Done — next steps"
    cat <<EOF

  1) Put the nginx config in place (you handle nginx):
       sudo cp ${NGINX_CONF} /etc/nginx/sites-available/coladong.conf
       sudo ln -s /etc/nginx/sites-available/coladong.conf /etc/nginx/sites-enabled/
       sudo nginx -t && sudo systemctl reload nginx
     (remove the default site if it conflicts on port 80)

  2) Create an admin account:
       cd ${APP_DIR}
       ${VENV_PY} manage.py createsuperuser

  3) Point your DNS / firewall at this host, then visit http://${DOMAIN}/

  Useful commands:
       systemctl status coladong
       journalctl -u coladong -f
       bash ${SCRIPT_DIR}/update.sh      # pull + migrate + restart

EOF
    ok "Installation complete."
}

generate_nginx_conf() {
    local domain="$1"
    cat > "${NGINX_CONF}" <<EOF
# Cola Dong — nginx site config (generated by deploy/install.sh)
#
# Install:
#   sudo cp ${NGINX_CONF} /etc/nginx/sites-available/coladong.conf
#   sudo ln -s /etc/nginx/sites-available/coladong.conf /etc/nginx/sites-enabled/
#   sudo nginx -t && sudo systemctl reload nginx
#
# gunicorn listens on ${GUNICORN_BIND} (see coladong.service).

server {
    listen 80;
    listen [::]:80;
    server_name ${domain};

    # Static files collected by Django (manage.py collectstatic)
    location /static/ {
        alias ${STATIC_ROOT}/;
    }

    location / {
        proxy_pass http://${GUNICORN_BIND};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}

# --- HTTPS (optional) -----------------------------------------------------
# Get certificates with Let's Encrypt:
#   sudo certbot --nginx -d ${domain}
# certbot rewrites the port-80 block to redirect to HTTPS and adds a 443
# block for you. Or, add your own 443 server block mirroring the one above
# with ssl_certificate / ssl_certificate_key and
#   proxy_set_header X-Forwarded-Proto https;
#
# Note: with SSL behind nginx, the app already trusts X-Forwarded-Proto
# (see SECURE_PROXY_SSL_HEADER in settings.py).
EOF
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
case "${1:-install}" in
    install)   do_install ;;
    uninstall) do_uninstall ;;
    *) die "Unknown command '${1}'. Use: install | uninstall" ;;
esac
