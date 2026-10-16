import type { ApiError, ReviewResponse } from '../types/review';

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000').replace(/\/$/, '');

export interface OtpChallenge { challenge_id: string; expires_in: number; delivery: 'demo'|'email'|'sms'; demo_otp?: string }
export interface AuthSession { access_token: string; token_type: string; identity: string }

async function authPost<T>(path: string, payload: object): Promise<T> {
  const response = await fetch(`${API_BASE}/api/auth/${path}`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload) });
  const data = await response.json().catch(() => ({})) as {detail?:string};
  if (!response.ok) throw new Error(data.detail ?? `Login service returned ${response.status}`);
  return data as T;
}

export function sendLoginOtp(method:'email'|'phone', identifier:string) {
  return authPost<OtpChallenge>('otp/send', { method, identifier });
}
export function verifyLoginOtp(challenge_id:string, code:string) {
  return authPost<AuthSession>('otp/verify', { challenge_id, code });
}

export async function analyzePullRequest(url: string): Promise<ReviewResponse> {
  const response = await fetch(`${API_BASE}/api/reviews/analyze`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url }),
  });
  if (!response.ok) {
    let error: ApiError = { detail: `Review service returned ${response.status}` };
    try { error = await response.json() as ApiError; } catch { /* Keep the useful status message. */ }
    throw new Error(error.detail);
  }
  return await response.json() as ReviewResponse;
}

export async function getReview(reviewId: string): Promise<ReviewResponse> {
  const response = await fetch(`${API_BASE}/api/reviews/${encodeURIComponent(reviewId)}`);
  if (!response.ok) throw new Error(`Could not load review (${response.status})`);
  return await response.json() as ReviewResponse;
}

export async function getReviewHistory(): Promise<ReviewResponse[]> {
  const response = await fetch(`${API_BASE}/api/reviews/history`);
  if (!response.ok) throw new Error(`Could not load review history (${response.status})`);
  return await response.json() as ReviewResponse[];
}
