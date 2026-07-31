// Standard 8-4-4-4-12 hex-group form -- matches what Python's uuid.UUID()
// accepts format-wise (any RFC 4122 version), which is what the backend's
// path converter (paper_id: uuid.UUID) ultimately parses.
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

export function isValidUuid(value: string | undefined): value is string {
  return typeof value === 'string' && UUID_PATTERN.test(value)
}
