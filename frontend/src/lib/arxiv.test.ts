import { describe, expect, it } from 'vitest'

import { arxivAbstractUrl, arxivPdfUrl } from '@/lib/arxiv'

describe('arxivAbstractUrl', () => {
  it('builds the correct arXiv abstract-page URL from a valid arxiv_id', () => {
    expect(arxivAbstractUrl('1601.01507')).toBe('https://arxiv.org/abs/1601.01507')
  })

  it('accepts a versioned arxiv_id', () => {
    expect(arxivAbstractUrl('2607.24651v2')).toBe('https://arxiv.org/abs/2607.24651v2')
  })

  it('returns null for a null arxiv_id', () => {
    expect(arxivAbstractUrl(null)).toBeNull()
  })

  it('returns null for a malformed arxiv_id, never a fabricated link', () => {
    expect(arxivAbstractUrl('not-an-id')).toBeNull()
    expect(arxivAbstractUrl('')).toBeNull()
    expect(arxivAbstractUrl('12345.678')).toBeNull()
  })
})

describe('arxivPdfUrl', () => {
  it('builds the correct arXiv PDF URL from a valid arxiv_id', () => {
    expect(arxivPdfUrl('1601.01507')).toBe('https://arxiv.org/pdf/1601.01507')
  })

  it('accepts a versioned arxiv_id', () => {
    expect(arxivPdfUrl('2607.24651v2')).toBe('https://arxiv.org/pdf/2607.24651v2')
  })

  it('returns null for a null arxiv_id -- never fabricates a PDF link when one is unavailable', () => {
    expect(arxivPdfUrl(null)).toBeNull()
  })

  it('returns null for a malformed arxiv_id', () => {
    expect(arxivPdfUrl('not-an-id')).toBeNull()
    expect(arxivPdfUrl('')).toBeNull()
  })

  it('uses the same validation as arxivAbstractUrl, so PDF and abstract links are never inconsistent', () => {
    const samples = ['1601.01507', 'not-an-id', '', null, '2607.24727v1']
    for (const id of samples) {
      expect(arxivPdfUrl(id) !== null).toBe(arxivAbstractUrl(id) !== null)
    }
  })
})
