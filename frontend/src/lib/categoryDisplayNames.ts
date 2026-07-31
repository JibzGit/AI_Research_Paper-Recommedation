/**
 * Fallback readable names for well-known arXiv category codes. The
 * backend's own `display_name` is always the primary source -- but in the
 * live API this field currently just echoes `code` back verbatim (e.g.
 * `{code: "cs.CV", display_name: "cs.CV"}`), which is not actually a
 * readable name. This map is used whenever the backend value is missing,
 * blank, or identical to the raw code; the canonical `code` is always
 * preserved and shown alongside the name regardless.
 */
const KNOWN_ARXIV_CATEGORIES: Record<string, string> = {
  'cs.AI': 'Artificial Intelligence',
  'cs.CL': 'Computation and Language',
  'cs.CV': 'Computer Vision and Pattern Recognition',
  'cs.LG': 'Machine Learning',
  'cs.IR': 'Information Retrieval',
  'cs.NE': 'Neural and Evolutionary Computing',
  'cs.RO': 'Robotics',
  'cs.SE': 'Software Engineering',
  'cs.DC': 'Distributed, Parallel, and Cluster Computing',
  'cs.CR': 'Cryptography and Security',
  'cs.HC': 'Human-Computer Interaction',
  'cs.DB': 'Databases',
  'cs.SI': 'Social and Information Networks',
  'stat.ML': 'Machine Learning (Statistics)',
  'math.OC': 'Optimization and Control',
  'math.ST': 'Statistics Theory',
  'eess.IV': 'Image and Video Processing',
  'eess.AS': 'Audio and Speech Processing',
}

export function getCategoryDisplayName(code: string, backendDisplayName: string | undefined | null): string {
  const trimmed = backendDisplayName?.trim()
  if (trimmed && trimmed !== code) return trimmed
  return KNOWN_ARXIV_CATEGORIES[code] ?? code
}
