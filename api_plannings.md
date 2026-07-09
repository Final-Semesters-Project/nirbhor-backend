4. **Render + NeonDB deployment** — set `FIREBASE_CREDENTIALS_JSON` as an
   env var on Render (paste the full JSON content, not the file path).
   Set `SCHEDULER_ENABLED=true` on only one Render worker instance to
   prevent duplicate job runs.

5. **AI review summarization** — the weekly cron job that batches reviews
   and calls an AI model to generate `ai_review_summary_en/bn` on
   `provider_profiles`. This is a nice-to-have for the capstone demo.