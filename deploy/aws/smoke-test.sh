#!/bin/bash
# Smoke test through the Nginx gateway. Usage: bash deploy/aws/smoke-test.sh http://<elastic-ip>
set -uo pipefail
BASE="${1:-http://127.0.0.1}"
FAILED=0

check() {
    local name="$1" url="$2" expected="$3"
    local code
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 15 "$url")
    if [ "$code" = "$expected" ]; then
        echo "OK   $name ($code)"
    else
        echo "FAIL $name: expected $expected, got $code ($url)"
        FAILED=1
    fi
}

for attempt in $(seq 1 30); do
    curl -fs --max-time 5 "$BASE/gateway/health" >/dev/null && break
    echo "waiting for the gateway... ($attempt)"
    sleep 5
done

check "gateway"            "$BASE/gateway/health"               200
check "django home"        "$BASE/"                             200
check "django status page" "$BASE/estado/"                      200
check "plan-service v2"    "$BASE/api/v2/plans/"                200
check "strangled v1 route" "$BASE/api/v1/plans/"                200
check "public summary"     "$BASE/api/v2/public/summary/"       200
check "exchange rates"     "$BASE/api/v2/rates/?symbols=COP"    200
check "notifications"      "$BASE/api/v2/notifications/"        200

BODY='{"company_description":"Somos una empresa de software en Medellin que desarrolla una plataforma para pequenas tiendas y necesita su equipo inicial."}'
CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 30 -H "Content-Type: application/json" -d "$BODY" "$BASE/api/v2/plans/")
if [ "$CODE" = "201" ]; then echo "OK   create plan (201)"; else echo "FAIL create plan: $CODE"; FAILED=1; fi

exit $FAILED
