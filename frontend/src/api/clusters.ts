import { apiGet } from '@/api/client'
import type { ClusterPapersParams, NoisePapersParams } from '@/api/queryKeys'
import type { ClusterDetail, ClusterListResponse, ClusterPapersResponse, NoisePapersResponse } from '@/api/types'

export function getClusters(): Promise<ClusterListResponse> {
  return apiGet<ClusterListResponse>('/api/v1/clusters')
}

export function getClusterDetail(clusterId: number): Promise<ClusterDetail> {
  return apiGet<ClusterDetail>(`/api/v1/clusters/${clusterId}`)
}

export function getClusterPapers(clusterId: number, params: ClusterPapersParams): Promise<ClusterPapersResponse> {
  return apiGet<ClusterPapersResponse>(`/api/v1/clusters/${clusterId}/papers`, {
    limit: params.limit,
    offset: params.offset,
    category: params.category,
    min_membership_probability: params.minMembershipProbability,
  })
}

export function getNoisePapers(params: NoisePapersParams): Promise<NoisePapersResponse> {
  return apiGet<NoisePapersResponse>('/api/v1/clusters/noise', {
    limit: params.limit,
    offset: params.offset,
    category: params.category,
  })
}
