export interface ComposeServiceIndex {
  services: Record<string, unknown>;
}

export function hasService(compose: ComposeServiceIndex, service: string): boolean {
  return Boolean(compose.services && Object.prototype.hasOwnProperty.call(compose.services, service));
}
