import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query'

import { api, authFetch, type Schemas } from '@/lib/api/client'
import { ApiError, unwrap } from '@/lib/api/errors'

export type LogbookEntry = Schemas['LogbookEntryOut']
export type Pin = Schemas['PinOut']
export type Dataset = Schemas['DatasetOut']
export type DatasetInput = Schemas['DatasetIn']
export type Attachment = Schemas['AttachmentOut']

const path = (projectId: string) => ({ params: { path: { project_id: projectId } } })

export const logbookQueryOptions = (projectId: string) =>
  queryOptions({
    queryKey: ['projects', projectId, 'logbook'] as const,
    queryFn: async () => unwrap(await api.GET('/api/v1/projects/{project_id}/logbook', path(projectId))),
  })

export const pinsQueryOptions = (projectId: string) =>
  queryOptions({
    queryKey: ['projects', projectId, 'pins'] as const,
    queryFn: async () => unwrap(await api.GET('/api/v1/projects/{project_id}/pins', path(projectId))),
  })

export const datasetsQueryOptions = (projectId: string) =>
  queryOptions({
    queryKey: ['projects', projectId, 'datasets'] as const,
    queryFn: async () =>
      unwrap(await api.GET('/api/v1/projects/{project_id}/datasets', path(projectId))),
  })

export function useAddLogbookEntry(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (text: string) =>
      unwrap(
        await api.POST('/api/v1/projects/{project_id}/logbook', { ...path(projectId), body: { text } }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: logbookQueryOptions(projectId).queryKey }),
  })
}

export function useDeleteLogbookEntry(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (entryId: string) =>
      unwrap(await api.DELETE('/api/v1/logbook/{entry_id}', { params: { path: { entry_id: entryId } } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: logbookQueryOptions(projectId).queryKey }),
  })
}

export function usePinBlock(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: Schemas['PinIn']) =>
      unwrap(await api.POST('/api/v1/projects/{project_id}/pins', { ...path(projectId), body })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: pinsQueryOptions(projectId).queryKey }),
  })
}

export function useUnpin(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (pinId: string) =>
      unwrap(await api.DELETE('/api/v1/pins/{pin_id}', { params: { path: { pin_id: pinId } } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: pinsQueryOptions(projectId).queryKey }),
  })
}

export function useSaveDataset(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, data }: { id: string | null; data: DatasetInput }) =>
      id
        ? unwrap(
            await api.PUT('/api/v1/datasets/{dataset_id}', {
              params: { path: { dataset_id: id } },
              body: data,
            }),
          )
        : unwrap(
            await api.POST('/api/v1/projects/{project_id}/datasets', { ...path(projectId), body: data }),
          ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: datasetsQueryOptions(projectId).queryKey }),
  })
}

/** Uploads a photo. Sent as a form, which the typed JSON client does not do. */
export async function uploadPhoto(projectId: string, file: File): Promise<Attachment> {
  const form = new FormData()
  form.append('file', file)
  const response = await authFetch(
    new Request(new URL(`/api/v1/projects/${projectId}/attachments`, window.location.origin), {
      method: 'POST',
      credentials: 'same-origin',
      body: form,
    }),
  )
  const body = (await response.json().catch(() => null)) as
    | (Attachment & { detail?: string; code?: string })
    | null
  if (!response.ok || !body) {
    throw new ApiError(
      typeof body?.detail === 'string' ? body.detail : "That photo couldn't be uploaded.",
      body?.code ?? 'error',
      response.status,
    )
  }
  return body
}
