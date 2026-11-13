#!/usr/bin/env bash
# Deploys one image tag on the AWS server, tests it, and goes back to the last good tag if the test fails.
#
#   bash scripts/deploy.sh main            newest build of main
#   bash scripts/deploy.sh sha-1a2b3c4     one specific build (also how you roll back by hand)
#   SIMULATE_FAILURE=true bash scripts/deploy.sh sha-1a2b3c4
#                                          rollback drill: the new tag "fails" on purpose, the last good tag returns
#
# Run by .github/workflows/deploy.yml on the self-hosted runner, from the checked-out repository.
# It expects: docker already logged in to ghcr.io, and ~/flood-payout/.env containing DOMAIN=<name>.
# Files it keeps in ~/flood-payout (APP_DIR): docker-compose.yml, Caddyfile, .env (IMAGE_TAG is written here),
# and .last_good_tag (the tag that passed the smoke test most recently).
set -euo pipefail

REQUESTED="${1:?usage: deploy.sh <image tag>}"
APP_DIR="${APP_DIR:-$HOME/flood-payout}"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export IMAGE_REPO="${IMAGE_REPO:-ghcr.io/alpha-beta-gamma-delta-chaky/flood-payout-calculator}"
ENV_FILE="$APP_DIR/.env"

die() { echo "::error::$*"; exit 1; }

[[ "$REQUESTED" =~ ^[A-Za-z0-9_.-]+$ ]] || die "Strange image tag: $REQUESTED"
[ -f "$ENV_FILE" ] || die "Missing $ENV_FILE. Create it with:  mkdir -p $APP_DIR && echo DOMAIN=<your name>.duckdns.org > $ENV_FILE"
DOMAIN="$(grep -E '^DOMAIN=' "$ENV_FILE" | tail -n 1 | cut -d= -f2- | tr -d "\"' " || true)"
{ [ -n "$DOMAIN" ] && [ "$DOMAIN" != ":80" ]; } || die "Set DOMAIN=<your name>.duckdns.org in $ENV_FILE"

compose() { docker compose -f "$APP_DIR/docker-compose.yml" --env-file "$ENV_FILE" "$@"; }

set_tag() {   # write IMAGE_TAG into .env (replace the line, or add it)
    if grep -q '^IMAGE_TAG=' "$ENV_FILE"; then
        sed -i "s|^IMAGE_TAG=.*|IMAGE_TAG=$1|" "$ENV_FILE"
    else
        printf '\nIMAGE_TAG=%s\n' "$1" >> "$ENV_FILE"
    fi
}

wait_healthy() {   # the app container's own health check (Dockerfile HEALTHCHECK) must turn "healthy"
    local cid status
    for _ in $(seq 1 60); do
        cid="$(compose ps -q app)"
        status="$(docker inspect --format '{{.State.Health.Status}}' "$cid" 2>/dev/null || echo none)"
        [ "$status" = healthy ] && return 0
        sleep 2
    done
    echo "App container did not become healthy (last status: $status)"
    return 1
}

start_and_test() {   # $1 = tag. Returns 1 on any failure. (Explicit "|| return 1": set -e is off inside "if f".)
    echo "--- Starting $IMAGE_REPO:$1"
    set_tag "$1"
    compose pull app || return 1
    compose up -d --remove-orphans || return 1
    wait_healthy || return 1
    # Pick up a changed Caddyfile. Harmless when nothing changed; ignore errors (Caddy may be starting).
    compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile >/dev/null 2>&1 || true
    echo "--- Smoke test on https://$DOMAIN"
    python3 "$SRC_DIR/scripts/smoke_test.py" "https://$DOMAIN" --wait 120 || return 1
    # Rollback drill: report a failure for the new tag only, never for the rollback (see deploy.yml).
    if [ "${SIMULATE_FAILURE:-false}" = "true" ] && [ "$1" = "$TAG" ]; then
        echo "::warning::Rollback drill: the smoke test passed, but this run reports a failure on purpose."
        return 1
    fi
}

# 1. Work out the exact build. "main" moves with every push, so find the sha-... tag of the image behind it.
echo "--- Looking up $IMAGE_REPO:$REQUESTED"
docker pull "$IMAGE_REPO:$REQUESTED" >/dev/null || die "Cannot pull $IMAGE_REPO:$REQUESTED (wrong tag, or no access to the package)"
REVISION="$(docker image inspect "$IMAGE_REPO:$REQUESTED" --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}')"
[[ "$REVISION" =~ ^[0-9a-f]{7,40}$ ]] || die "The image has no usable revision label ('$REVISION'), so its build cannot be identified"
TAG="sha-${REVISION:0:7}"

# 2. Put the compose file and Caddyfile in place. cp (not mv) keeps the file Caddy has mounted.
mkdir -p "$APP_DIR"
cp "$SRC_DIR/docker-compose.prod.yml" "$APP_DIR/docker-compose.yml"
cp "$SRC_DIR/Caddyfile" "$APP_DIR/Caddyfile"

PREVIOUS=""
[ -f "$APP_DIR/.last_good_tag" ] && PREVIOUS="$(cat "$APP_DIR/.last_good_tag")"
echo "--- Deploying $TAG (requested: $REQUESTED, last good: ${PREVIOUS:-none})"

# 3. Deploy; on failure go back to the last good tag.
if start_and_test "$TAG"; then
    echo "$TAG" > "$APP_DIR/.last_good_tag"
    docker image prune -f >/dev/null || true       # only untagged leftovers; tagged builds stay for quick rollback
    echo "Deployed $TAG to https://$DOMAIN"
    exit 0
fi

echo "::error::Deploy of $TAG failed. Recent logs:"
compose logs --tail 40 app caddy || true
if [ -n "$PREVIOUS" ] && [ "$PREVIOUS" != "$TAG" ]; then
    echo "--- Rolling back to $PREVIOUS"
    if start_and_test "$PREVIOUS"; then
        echo "::error::Rolled back: $PREVIOUS is running and passes the smoke test. $TAG did not."
    else
        echo "::error::Rollback to $PREVIOUS failed too. The site may be down: check the server."
    fi
else
    echo "::error::Nothing to roll back to (this was the first deploy, or the last good tag is the one that failed)."
fi
exit 1
