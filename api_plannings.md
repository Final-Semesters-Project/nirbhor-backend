4. **Render + NeonDB deployment** — set `FIREBASE_CREDENTIALS_JSON` as an
   env var on Render (paste the full JSON content, not the file path).
   Set `SCHEDULER_ENABLED=true` on only one Render worker instance to
   prevent duplicate job runs.