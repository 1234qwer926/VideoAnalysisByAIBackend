#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@example.com}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin123}"
CANDIDATE_EMAIL="${CANDIDATE_EMAIL:-candidate@example.com}"

echo "==> API smoke test against ${BASE_URL}"

json_get() {
  local json="$1"
  local key="$2"
  python3 - "$json" "$key" <<'PY'
import json, sys
obj = json.loads(sys.argv[1])
key = sys.argv[2]
print(obj.get(key, ""))
PY
}

echo "==> Admin register (idempotent)"
curl -sS -X POST "${BASE_URL}/api/admin/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${ADMIN_EMAIL}\",\"password\":\"${ADMIN_PASSWORD}\"}" >/dev/null || true

echo "==> Admin login"
ADMIN_LOGIN_JSON="$(curl -sS -X POST "${BASE_URL}/api/admin/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${ADMIN_EMAIL}\",\"password\":\"${ADMIN_PASSWORD}\"}")"
ADMIN_TOKEN="$(json_get "$ADMIN_LOGIN_JSON" "access_token")"
if [[ -z "${ADMIN_TOKEN}" ]]; then
  echo "Admin login failed: ${ADMIN_LOGIN_JSON}"
  exit 1
fi

echo "==> Create form"
FORM_JSON="$(curl -sS -X POST "${BASE_URL}/api/admin/forms/" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"title":"Smoke Test Form","description":"API smoke flow","questions":[{"type":"short_text","title":"Tell me about yourself","description":"","required":true,"order":0,"points":10,"config":{}}]}')"
FORM_ID="$(json_get "$FORM_JSON" "id")"
if [[ -z "${FORM_ID}" ]]; then
  echo "Form create failed: ${FORM_JSON}"
  exit 1
fi

echo "==> Create assignment"
ASSIGN_JSON="$(curl -sS -X POST "${BASE_URL}/api/admin/assignments/" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"title\":\"Smoke Assignment\",\"description\":\"Flow test\",\"form_id\":${FORM_ID}}")"
ASSIGN_ID="$(json_get "$ASSIGN_JSON" "id")"
if [[ -z "${ASSIGN_ID}" ]]; then
  echo "Assignment create failed: ${ASSIGN_JSON}"
  exit 1
fi

echo "==> Add candidate user"
USER_JSON="$(curl -sS -X POST "${BASE_URL}/api/admin/assignments/${ASSIGN_ID}/users" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${CANDIDATE_EMAIL}\"}")"
EXAM_TOKEN="$(json_get "$USER_JSON" "token")"
if [[ -z "${EXAM_TOKEN}" ]]; then
  echo "Candidate add failed: ${USER_JSON}"
  exit 1
fi

echo "==> Candidate login"
CAND_LOGIN_JSON="$(curl -sS -X POST "${BASE_URL}/api/candidate/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${CANDIDATE_EMAIL}\",\"password\":\"dummy\"}")"
CAND_TOKEN="$(json_get "$CAND_LOGIN_JSON" "access_token")"
if [[ -z "${CAND_TOKEN}" ]]; then
  echo "Candidate login failed: ${CAND_LOGIN_JSON}"
  exit 1
fi

echo "==> Save progress"
curl -sS -X POST "${BASE_URL}/api/exam/save?token=${EXAM_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"answers":{"1":"draft answer"},"current_question_index":0}' >/dev/null

echo "==> Submit exam"
SUBMIT_JSON="$(curl -sS -X POST "${BASE_URL}/api/exam/submit" \
  -H "Content-Type: application/json" \
  -d "{\"assignment_user_token\":\"${EXAM_TOKEN}\",\"responses\":[{\"question_id\":1,\"answer\":\"final answer\"}],\"is_auto_submitted\":false}")"
SUBMISSION_ID="$(json_get "$SUBMIT_JSON" "id")"
if [[ -z "${SUBMISSION_ID}" ]]; then
  echo "Submit failed: ${SUBMIT_JSON}"
  exit 1
fi

echo "==> Admin review update"
REVIEW_JSON="$(curl -sS -X PUT "${BASE_URL}/api/admin/results/${SUBMISSION_ID}" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"score":82,"feedback":"Good attempt"}')"
REVIEW_ID="$(json_get "$REVIEW_JSON" "id")"
if [[ -z "${REVIEW_ID}" ]]; then
  echo "Review update failed: ${REVIEW_JSON}"
  exit 1
fi

echo "==> Candidate result fetch"
curl -sS -X GET "${BASE_URL}/api/candidate/results/${SUBMISSION_ID}" \
  -H "Authorization: Bearer ${CAND_TOKEN}" >/dev/null

echo "PASS: smoke flow completed (submission_id=${SUBMISSION_ID})"
