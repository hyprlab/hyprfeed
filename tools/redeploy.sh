#!/usr/bin/env bash
# Rebuild the local container from the working tree and restart it, so a
# change can be tried in the running app. This is the test loop after every
# change; it publishes nothing.
#
#   tools/redeploy.sh
set -euo pipefail
cd "$(dirname "$0")/.."

docker compose up -d --build
port=$(docker compose port hyprfeed 8000 | cut -d: -f2)
# Hyprfeed has no health route; the sign-in page answering (or the setup
# redirect on an empty instance) means the app is serving.
for _ in $(seq 1 30); do
    code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$port/login" || true)
    if [ "$code" = 200 ] || [ "$code" = 302 ]; then
        version=$(docker compose exec -T hyprfeed python -c 'import hyprfeed; print(hyprfeed.__version__)' 2>/dev/null || echo "?")
        echo "Up: http://localhost:$port (version $version)"
        exit 0
    fi
    sleep 1
done
echo "The container did not come up. Logs:" >&2
docker compose logs --tail 40 >&2
exit 1
