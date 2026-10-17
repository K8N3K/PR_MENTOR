# PR Mentor frontend

React + TypeScript frontend powered by Vite. All frontend source, configuration, and public assets live in this directory.

## Run locally

```bash
npm install
npm run dev
```

Copy `.env.example` to `.env.local` and set `VITE_API_BASE_URL` to the FastAPI service URL. Start the backend from `backend/` with `uvicorn app.main:app --reload --port 8000`.

Email and phone login use `POST /api/auth/otp/send` and `POST /api/auth/otp/verify`. Local development defaults to a clearly labeled demo code shown in the login screen. For actual delivery, set `PR_MENTOR_OTP_MODE=smtp` with SMTP settings or `PR_MENTOR_OTP_MODE=twilio` with Twilio SMS settings; see `backend/.env.example`. Never use demo OTP mode in production.

This starter keeps OTP challenges, send limits, and sessions in process memory. Use a shared store and persistent account/session handling before deploying multiple backend workers or using it for production accounts.

The review UI expects `POST /api/reviews/analyze` to accept `{ "url": "https://github.com/owner/repo/pull/42" }`. API calls are isolated in `src/services/api.ts`.

When the backend is unavailable, the review workspace and verification panels remain clearly labeled as sample data. No API credentials or database connection details belong in this frontend.
