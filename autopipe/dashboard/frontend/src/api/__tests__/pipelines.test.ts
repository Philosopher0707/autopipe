import { describe, it, expect, vi, beforeEach } from 'vitest'
import { pipelinesApi } from '../endpoints/pipelines'

// Mock the apiClient module
vi.mock('../client', () => {
  const mockClient = {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    patch: vi.fn(),
  }
  return { apiClient: mockClient }
})

import { apiClient } from '../client'
const mockedClient = vi.mocked(apiClient)

describe('pipelinesApi', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('list calls GET /pipelines with default params', async () => {
    const mockResponse = { items: [], total: 0, page: 1, page_size: 20 }
    mockedClient.get.mockResolvedValue(mockResponse)

    const result = await pipelinesApi.list()

    expect(mockedClient.get).toHaveBeenCalledWith('/pipelines', {
      params: {
        search: undefined,
        status: undefined,
        tag: undefined,
        skip: 0,
        limit: 20,
        sort_by: 'created_at',
        sort_order: 'desc',
      },
    })
    expect(result).toEqual(mockResponse)
  })

  it('list passes search and filter params', async () => {
    mockedClient.get.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 })

    await pipelinesApi.list({ search: 'test', status: 'running', limit: 50 })

    expect(mockedClient.get).toHaveBeenCalledWith('/pipelines', {
      params: expect.objectContaining({
        search: 'test',
        status: 'running',
        limit: 50,
      }),
    })
  })

  it('getById calls GET /pipelines/:id', async () => {
    const mockPipeline = { id: '123', name: 'test' }
    mockedClient.get.mockResolvedValue(mockPipeline)

    const result = await pipelinesApi.getById('123')

    expect(mockedClient.get).toHaveBeenCalledWith('/pipelines/123')
    expect(result).toEqual(mockPipeline)
  })

  it('create calls POST /pipelines with data', async () => {
    const newPipeline = { name: 'new pipeline' }
    const mockResponse = { id: '456', name: 'new pipeline' }
    mockedClient.post.mockResolvedValue(mockResponse)

    const result = await pipelinesApi.create(newPipeline)

    expect(mockedClient.post).toHaveBeenCalledWith('/pipelines', newPipeline)
    expect(result).toEqual(mockResponse)
  })

  it('delete calls DELETE /pipelines/:id', async () => {
    mockedClient.delete.mockResolvedValue(undefined)

    await pipelinesApi.delete('789')

    expect(mockedClient.delete).toHaveBeenCalledWith('/pipelines/789')
  })

  it('triggerRun calls POST /pipelines/:id/runs', async () => {
    const mockRun = { id: 'run1', status: 'pending' }
    mockedClient.post.mockResolvedValue(mockRun)

    const result = await pipelinesApi.triggerRun('123', { key: 'value' })

    expect(mockedClient.post).toHaveBeenCalledWith('/pipelines/123/runs', { key: 'value' })
    expect(result).toEqual(mockRun)
  })
})