import os
import tempfile
import json
import time

from google import genai
from google.genai import types

from app.core.config import settings
from app.db.database import SessionLocal
from app.models.submission import Submission, QuestionResponse
from app.models.assignment import AssignmentUser, Assignment
from app.models.form import Form, Question
from app.models.review import Review
from app.services.s3 import download_file


def _build_eval_prompt(q, knowledge_base: str, ai_prompt: str) -> str:
    max_pts = q.points or 10
    is_video = q.type in ("video", "audio")

    prompt = ""
    if knowledge_base:
        prompt += f"=== KNOWLEDGE BASE ===\n{knowledge_base}\n\n"
    if ai_prompt:
        prompt += f"=== EVALUATOR INSTRUCTIONS ===\n{ai_prompt}\n\n"

    prompt += (
        f"=== QUESTION ===\n"
        f"Type: {q.type}\n"
        f"Title: {q.title}\n"
        f"Prompt: {q.description or q.title}\n\n"
    )

    if is_video:
        prompt += (
            "=== EVALUATION TASK ===\n"
            "Carefully watch/listen to the candidate's video/audio response.\n"
            "Evaluate the following metrics on a scale of 0–10 each:\n"
            "  1. content_accuracy   – How accurately does the answer address the question based on the knowledge base?\n"
            "  2. confidence         – How confident and assured is the candidate's delivery?\n"
            "  3. communication      – Clarity, fluency, and articulation.\n"
            "  4. facial_expressions – Eye contact, engagement, positive body language (video only).\n"
            "  5. overall_presentation – Overall professionalism and impression.\n\n"
        )
    else:
        prompt += (
            "=== EVALUATION TASK ===\n"
            "Carefully read the candidate's written answer.\n"
            "Evaluate the following metrics on a scale of 0–10 each:\n"
            "  1. content_accuracy  – Accuracy and completeness based on the knowledge base.\n"
            "  2. clarity           – How clearly and logically is the answer structured?\n"
            "  3. depth             – Depth of understanding demonstrated.\n\n"
        )

    prompt += (
        f"Give a final score out of {max_pts} based on the above metrics.\n\n"
        "Respond in STRICT JSON — no markdown, no extra text. Format:\n"
    )

    if is_video:
        prompt += (
            '{"score": <float>, '
            '"metrics": {"content_accuracy": <0-10>, "confidence": <0-10>, '
            '"communication": <0-10>, "facial_expressions": <0-10>, '
            '"overall_presentation": <0-10>}, '
            '"feedback": "<detailed feedback string>"}'
        )
    else:
        prompt += (
            '{"score": <float>, '
            '"metrics": {"content_accuracy": <0-10>, "clarity": <0-10>, "depth": <0-10>}, '
            '"feedback": "<detailed feedback string>"}'
        )

    return prompt


def _parse_response_text(text: str) -> dict:
    """Strip markdown fences and parse JSON."""
    t = text.strip()
    if "```json" in t:
        t = t.split("```json")[1].split("```")[0]
    elif "```" in t:
        t = t.split("```")[1].split("```")[0]
    return json.loads(t.strip())


def evaluate_submission_background(submission_id: int):
    if not settings.GEMINI_API_KEY:
        print("GEMINI_API_KEY not set. Skipping AI evaluation.")
        return

    db = SessionLocal()
    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        model_id = "gemini-2.5-flash"

        sub = db.query(Submission).filter(Submission.id == submission_id).first()
        if not sub:
            return

        assignment_user = db.query(AssignmentUser).filter(
            AssignmentUser.id == sub.assignment_user_id
        ).first()
        assignment = db.query(Assignment).filter(
            Assignment.id == assignment_user.assignment_id
        ).first()
        form = db.query(Form).filter(Form.id == assignment.form_id).first()

        responses = db.query(QuestionResponse).filter(
            QuestionResponse.submission_id == submission_id
        ).all()
        questions = {
            q.id: q
            for q in db.query(Question).filter(Question.form_id == form.id).all()
        }

        # Create / reset review record
        review = db.query(Review).filter(Review.submission_id == sub.id).first()
        if not review:
            review = Review(submission_id=sub.id)
            db.add(review)
            db.commit()
            db.refresh(review)

        total_score = 0.0
        max_score = 0.0
        overall_feedback_lines = []

        knowledge_base = assignment.knowledge_base or ""
        ai_prompt = assignment.ai_prompt or "Act as a professional interviewer and evaluator."

        for r in responses:
            q = questions.get(r.question_id)
            if not q or q.type == "instruction":
                continue

            max_score += float(q.points or 10)
            prompt_text = _build_eval_prompt(q, knowledge_base, ai_prompt)

            contents = [prompt_text]
            gemini_file = None
            temp_path = None

            try:
                # ---- Handle video/audio file ----
                if r.s3_key:
                    ext = os.path.splitext(r.s3_key)[1] or ".webm"
                    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                        temp_path = tmp.name

                    downloaded = False
                    if settings.AWS_ACCESS_KEY_ID:
                        try:
                            download_file(r.s3_key, temp_path)
                            downloaded = True
                        except Exception as dl_err:
                            print(f"Warning: Could not download {r.s3_key}: {dl_err}")
                            contents.append(
                                "NOTE: The candidate's video file is missing or was not "
                                "uploaded. Evaluate assuming a non-response."
                            )

                    if downloaded and os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
                        # Upload to Gemini File API
                        gemini_file = client.files.upload(file=temp_path)
                        # Poll until ready
                        while gemini_file.state.name == "PROCESSING":
                            time.sleep(2)
                            gemini_file = client.files.get(name=gemini_file.name)

                        if gemini_file.state.name == "FAILED":
                            print(f"Gemini file processing failed for {r.s3_key}")
                            contents.append("NOTE: Video processing failed. Evaluate as non-response.")
                        else:
                            contents.append(gemini_file)

                elif r.answer:
                    contents.append(f"=== CANDIDATE ANSWER ===\n{json.dumps(r.answer, ensure_ascii=False)}")

                # ---- Call Gemini ----
                response = client.models.generate_content(
                    model=model_id,
                    contents=contents,
                )

                result = _parse_response_text(response.text)
                q_score = float(result.get("score", 0))
                metrics = result.get("metrics", {})
                feedback = result.get("feedback", "")

                r.score = q_score
                # Store structured metrics alongside the answer JSON
                if r.answer and isinstance(r.answer, dict):
                    r.answer = {**r.answer, "ai_metrics": metrics, "ai_feedback": feedback}
                else:
                    r.answer = {"ai_metrics": metrics, "ai_feedback": feedback}

                total_score += q_score
                metrics_str = ", ".join(f"{k}: {v}/10" for k, v in metrics.items())
                overall_feedback_lines.append(
                    f"Q{q.order or 1}: {q.title}\n"
                    f"  Score: {q_score}/{q.points or 10}\n"
                    f"  Metrics: {metrics_str}\n"
                    f"  Feedback: {feedback}"
                )

            except Exception as q_err:
                print(f"Error evaluating question {r.question_id}: {q_err}")
                r.score = 0
                overall_feedback_lines.append(
                    f"Q{q.order or 1}: {q.title}\n"
                    f"  Score: 0/{q.points or 10}\n"
                    f"  Feedback: Evaluation failed — {q_err}"
                )

            finally:
                if gemini_file:
                    try:
                        client.files.delete(name=gemini_file.name)
                    except Exception:
                        pass
                if temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)

        final_percentage = round((total_score / max_score * 100), 2) if max_score > 0 else 0.0
        review.ai_score = final_percentage
        review.final_score = final_percentage
        review.comments = "\n\n".join(overall_feedback_lines)

        assignment_user.status = "evaluated"
        db.commit()

        print(f"Submission {submission_id} evaluated: {final_percentage}%")

    except Exception as e:
        import traceback
        print(f"Error evaluating submission {submission_id}: {e}")
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()
