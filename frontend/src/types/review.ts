export interface PullRequestMetadata { repository: string; pull_request_title: string; pull_request_number: number; url?: string }
export interface ReviewFinding { severity: 'Critical'|'High'|'Medium'|'Low'|'Informational'; title: string; file: string; line: number|string; text: string; proof?: string; status?: string }
export interface ReviewResponse extends PullRequestMetadata { review_id?: string; findings: ReviewFinding[]; status?: string }
export interface ApiError { detail: string }
