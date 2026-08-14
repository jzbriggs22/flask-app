#!/bin/bash
# End-to-end smoke test of the takeoff/estimating API
#
# Exercises the full takeoff -> estimating flow against a running API:
# routing, structured errors, calibration, quantity derivation, uom
# validation, cross-reference rejection, versioning, staleness, recompute,
# soft deletes, and audit events. Requires: curl, jq, psql.
# Usage: API_URL=http://host:port PSQL_ARGS="-h host -p port -U user -d db" ./scripts/api-smoke.sh
set -u
API=${API_URL:-http://127.0.0.1:3000}/api
PSQL="psql -q ${PSQL_ARGS:--h localhost -p 5432 -U openbuild -d openbuild} -tA"
PASS=0; FAIL=0
check() { # check <desc> <actual> <expected>
  if [ "$2" = "$3" ]; then PASS=$((PASS+1)); echo "ok   $1"
  else FAIL=$((FAIL+1)); echo "FAIL $1: got '$2' want '$3'"; fi
}

NIL=00000000-0000-0000-0000-000000000000

# --- routing + errors ---
P=$(curl -s -X POST $API/projects -H 'content-type: application/json' -d '{"name":"Smoke","number":"S-1"}')
PID=$(jq -r .id <<<"$P")
check "create project" "$(jq -r .name <<<"$P")" "Smoke"
check "GET by id routes (:param fix)" "$(curl -s $API/projects/$PID | jq -r .id)" "$PID"
MISSING=$(curl -s -w '|%{http_code}' $API/projects/11111111-1111-1111-1111-111111111111)
check "404 structured error" "$(cut -d'|' -f2 <<<"$MISSING")|$(cut -d'|' -f1 <<<"$MISSING" | jq -r .code)" "404|NOT_FOUND"

# --- drawing set, layer, sheet, revision ---
DS=$(curl -s -X POST $API/projects/$PID/drawing-sets -H 'content-type: application/json' -d '{"name":"Set A"}' | jq -r .id)
LAYER=$(curl -s -X POST $API/drawing-sets/$DS/layers -H 'content-type: application/json' -d '{"name":"Concrete","color":"#3b82f6"}' | jq -r .id)
check "layer has created_by" "$($PSQL -c "SELECT created_by FROM takeoff_layers WHERE id='$LAYER'")" "$NIL"
SHEET=$($PSQL -c "INSERT INTO drawing_sheets (drawing_set_id, sheet_number, title, page_index, created_by) VALUES ('$DS','A-1','Plan',0,'$NIL') RETURNING id")
REV=$($PSQL -c "INSERT INTO drawing_sheet_revisions (sheet_id, drawing_set_id, revision_number, page_index, uploaded_by, page_width_pt, page_height_pt) VALUES ('$SHEET','$DS',1,0,'$NIL',2592,1728) RETURNING id")

# --- calibration: 720 pt = 10 ft ---
CAL=$(curl -s -X POST $API/sheet-revisions/$REV/calibration -H 'content-type: application/json' \
  -d '{"sheet_revision_id":"'$REV'","unit_system":"imperial","display_unit":"ft","point1_x":0,"point1_y":0,"point2_x":720,"point2_y":0,"real_distance":10}')
CALID=$(jq -r .id <<<"$CAL")
check "calibration scale_factor" "$(jq -r .scale_factor <<<"$CAL" | cut -c1-6)" "0.0138"

# --- measurement: 720 pt line, calibrated -> 10 ft ---
M=$(curl -s -X POST $API/layers/$LAYER/measurements -H 'content-type: application/json' \
  -d '{"sheet_id":"'$SHEET'","sheet_revision_id":"'$REV'","measurement_type":"linear","points":[{"x":0,"y":0},{"x":720,"y":0}],"uom":"ft","cost_code":"03","calibration_id":"'$CALID'"}')
MID=$(jq -r .id <<<"$M")
check "quantity_real derived (10 ft)" "$(jq -r .quantity_real <<<"$M")" "10.0"
check "version 1 recorded" "$($PSQL -c "SELECT count(*) FROM measurement_versions WHERE measurement_id='$MID'")" "1"

# --- uom mismatch rejected ---
BAD=$(curl -s -X POST $API/layers/$LAYER/measurements -H 'content-type: application/json' \
  -d '{"sheet_id":"'$SHEET'","sheet_revision_id":"'$REV'","measurement_type":"linear","points":[{"x":0,"y":0},{"x":720,"y":0}],"uom":"m","calibration_id":"'$CALID'"}')
check "uom mismatch -> 422" "$(jq -r .code <<<"$BAD")" "UOM_MISMATCH"

# --- cross-project revision rejected ---
P2=$(curl -s -X POST $API/projects -H 'content-type: application/json' -d '{"name":"Other","number":"S-2"}' | jq -r .id)
DS2=$(curl -s -X POST $API/projects/$P2/drawing-sets -H 'content-type: application/json' -d '{"name":"Set B"}' | jq -r .id)
L2=$(curl -s -X POST $API/drawing-sets/$DS2/layers -H 'content-type: application/json' -d '{"name":"X","color":"#000"}' | jq -r .id)
XREF=$(curl -s -X POST $API/layers/$L2/measurements -H 'content-type: application/json' \
  -d '{"sheet_id":"'$SHEET'","sheet_revision_id":"'$REV'","measurement_type":"count","points":[{"x":1,"y":1}],"uom":"ea"}')
check "foreign revision -> CROSS_REFERENCE" "$(jq -r .code <<<"$XREF")" "CROSS_REFERENCE"

# --- count without calibration works ---
CNT=$(curl -s -X POST $API/layers/$LAYER/measurements -H 'content-type: application/json' \
  -d '{"sheet_id":"'$SHEET'","sheet_revision_id":"'$REV'","measurement_type":"count","points":[{"x":1,"y":1},{"x":2,"y":2},{"x":3,"y":3}],"uom":"ea"}')
check "uncalibrated count -> 3 ea" "$(jq -r .quantity_real <<<"$CNT")" "3.0"

# --- estimate + driven line item: quantity derived, client value ignored ---
EST=$(curl -s -X POST $API/projects/$PID/estimates -H 'content-type: application/json' -d '{"name":"Est 1"}' | jq -r .id)
LI=$(curl -s -X POST $API/estimates/$EST/line-items -H 'content-type: application/json' \
  -d '{"cost_code":"03","description":"Wall","quantity":9999,"unit":"bogus","unit_cost_cents":500,"source_type":"driven","measurement_ids":["'$MID'"]}')
LIID=$(jq -r .id <<<"$LI")
check "driven qty derived, not client 9999" "$(jq -r .quantity <<<"$LI")" "10.0"
check "driven unit derived from measurement" "$(jq -r .unit <<<"$LI")" "ft"
check "snapshot recorded" "$(jq -r .quantity_snapshot <<<"$LI")" "10.0"

# --- driven quantity immutable via PUT ---
IMM=$(curl -s -X PUT $API/line-items/$LIID -H 'content-type: application/json' -d '{"quantity":5}')
check "driven qty PUT -> 422" "$(jq -r .code <<<"$IMM")" "DRIVEN_QUANTITY_IMMUTABLE"

# --- edit measurement geometry -> quantity recomputed + item goes stale ---
UPD=$(curl -s -X PUT $API/measurements/$MID -H 'content-type: application/json' \
  -d '{"points":[{"x":0,"y":0},{"x":1440,"y":0}]}')
check "edited quantity_real (20 ft)" "$(jq -r .quantity_real <<<"$UPD")" "20.0"
check "version bumped to 2" "$(jq -r .version <<<"$UPD")" "2"
check "line item marked stale" "$(curl -s $API/estimates/$EST/line-items | jq -r '.[0].is_stale')" "true"

# --- recompute pulls new quantity, clears stale ---
RC=$(curl -s -X POST $API/line-items/$LIID/recompute)
check "recompute -> 20" "$(jq -r .quantity <<<"$RC")" "20.0"
check "recompute clears stale" "$(jq -r .is_stale <<<"$RC")" "false"

# --- recalibration: events + staleness ---
curl -s -X POST $API/sheet-revisions/$REV/calibration -H 'content-type: application/json' \
  -d '{"sheet_revision_id":"'$REV'","unit_system":"imperial","display_unit":"ft","point1_x":0,"point1_y":0,"point2_x":720,"point2_y":0,"real_distance":20}' > /dev/null
EVENTS=$(curl -s $API/projects/$PID/takeoff-events)
check "CALIBRATION_SET events" "$(jq '[.[] | select(.event_type=="CalibrationSet")] | length' <<<"$EVENTS")" "2"
check "CALIBRATION_INVALIDATED event" "$(jq '[.[] | select(.event_type=="CalibrationInvalidated")] | length' <<<"$EVENTS")" "1"
check "recalibration re-stales item" "$(curl -s $API/estimates/$EST/line-items | jq -r '.[0].is_stale')" "true"

# --- delete source measurement -> stale; then soft-delete line item ---
curl -s -X DELETE $API/measurements/$MID > /dev/null
check "measurement soft-deleted" "$($PSQL -c "SELECT deleted_at IS NOT NULL FROM measurements WHERE id='$MID'")" "t"
RC2=$(curl -s -X POST $API/line-items/$LIID/recompute)
check "recompute w/ no live sources -> 422" "$(jq -r .code <<<"$RC2")" "NO_LIVE_SOURCES"
curl -s -X DELETE $API/line-items/$LIID > /dev/null
check "line item soft-deleted (row kept)" "$($PSQL -c "SELECT deleted_at IS NOT NULL FROM estimate_line_items WHERE id='$LIID'")" "t"
check "sources rows survive delete" "$($PSQL -c "SELECT count(*) FROM estimate_line_item_sources WHERE line_item_id='$LIID'")" "1"
check "deleted item excluded from list" "$(curl -s $API/estimates/$EST/line-items | jq length)" "0"

echo "----------------------------------------"
echo "PASS=$PASS FAIL=$FAIL"
[ $FAIL -eq 0 ]
