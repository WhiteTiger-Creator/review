export interface CandidateExceptionReview {
  exception_id: string;
  review_round: number;
  status: string;
  service: string;
  compose_file: string;
  rule_code: string;
  expires_on: string;
  approver: string;
  evidence_ref: string;
  mount_target: string;
  secret_readonly: number;
  environment: string;
}
