import { describe, expect, it } from 'vitest'

import { getCategoryDisplayName } from '@/lib/categoryDisplayNames'

describe('getCategoryDisplayName', () => {
  it('prefers a real backend display name when it differs from the code', () => {
    expect(getCategoryDisplayName('cs.CV', 'Computer Vision and Pattern Recognition')).toBe('Computer Vision and Pattern Recognition')
  })

  it('falls back to the known-category map when the backend just echoes the code back', () => {
    expect(getCategoryDisplayName('cs.CV', 'cs.CV')).toBe('Computer Vision and Pattern Recognition')
  })

  it('falls back to the known-category map when the backend name is blank or missing', () => {
    expect(getCategoryDisplayName('cs.IR', '')).toBe('Information Retrieval')
    expect(getCategoryDisplayName('cs.IR', null)).toBe('Information Retrieval')
    expect(getCategoryDisplayName('cs.IR', undefined)).toBe('Information Retrieval')
  })

  it('falls back to the raw code as a last resort for an unknown category', () => {
    expect(getCategoryDisplayName('q-bio.XX', 'q-bio.XX')).toBe('q-bio.XX')
  })
})
