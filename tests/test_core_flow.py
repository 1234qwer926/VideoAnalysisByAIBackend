def _register_and_login_admin(client, email="admin@test.com", password="secret123"):
  client.post("/api/admin/auth/register", json={"email": email, "password": password})
  res = client.post("/api/admin/auth/login", json={"email": email, "password": password})
  assert res.status_code == 200, res.text
  token = res.json()["access_token"]
  return {"Authorization": f"Bearer {token}"}


def test_admin_login_and_forms_access(client):
  headers = _register_and_login_admin(client)
  res = client.get("/api/admin/forms/", headers=headers)
  assert res.status_code == 200
  assert isinstance(res.json(), list)


def test_candidate_assignment_and_exam_submit_flow(client):
  headers = _register_and_login_admin(client)

  form_res = client.post(
    "/api/admin/forms/",
    headers=headers,
    json={
      "title": "Test Form",
      "description": "desc",
      "questions": [
        {
          "type": "short_text",
          "title": "Q1",
          "description": "",
          "required": True,
          "order": 0,
          "points": 5,
          "config": {},
        }
      ],
    },
  )
  assert form_res.status_code == 200, form_res.text
  form_id = form_res.json()["id"]

  assignment_res = client.post(
    "/api/admin/assignments/",
    headers=headers,
    json={"title": "A1", "description": "d", "form_id": form_id},
  )
  assert assignment_res.status_code == 200, assignment_res.text
  assignment_id = assignment_res.json()["id"]

  user_res = client.post(
    f"/api/admin/assignments/{assignment_id}/users",
    headers=headers,
    json={"email": "candidate@test.com"},
  )
  assert user_res.status_code == 200, user_res.text
  exam_token = user_res.json()["token"]

  login_res = client.post("/api/candidate/auth/login", json={"email": "candidate@test.com"})
  assert login_res.status_code == 200, login_res.text

  save_res = client.post(
    f"/api/exam/save?token={exam_token}",
    json={"answers": {"1": "draft"}, "current_question_index": 0},
  )
  assert save_res.status_code == 200, save_res.text
  assert save_res.json()["status"] == "saved"

  submit_res = client.post(
    "/api/exam/submit",
    json={
      "assignment_user_token": exam_token,
      "responses": [{"question_id": 1, "answer": "final"}],
      "is_auto_submitted": False,
    },
  )
  assert submit_res.status_code == 200, submit_res.text
  submission_id = submit_res.json()["id"]

  detail_res = client.get(f"/api/admin/results/submission/{submission_id}", headers=headers)
  assert detail_res.status_code == 200, detail_res.text

  review_res = client.put(
    f"/api/admin/results/{submission_id}",
    headers=headers,
    json={"score": 88, "feedback": "Good"},
  )
  assert review_res.status_code == 200, review_res.text
