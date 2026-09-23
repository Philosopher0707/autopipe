import { describe, expect, it } from 'vitest'
import { WebSocketClient, parseWSMessage } from '../websocket'

describe('WebSocketClient.tokenUrl', () => {
  it('appends token to a bare URL', () => {
    expect(WebSocketClient.tokenUrl('ws://h/api/v1/ws/runs/42', 'abc')).toBe(
      'ws://h/api/v1/ws/runs/42?token=abc'
    )
  })

  it('appends token when the URL already has a query string', () => {
    expect(WebSocketClient.tokenUrl('ws://h/ws?foo=1', 'abc')).toBe('ws://h/ws?foo=1&token=abc')
  })

  it('does not double-attach a token that is already present', () => {
    expect(WebSocketClient.tokenUrl('ws://h/ws?token=old', 'abc')).toBe('ws://h/ws?token=old')
  })

  it('leaves the URL untouched when there is no token', () => {
    expect(WebSocketClient.tokenUrl('ws://h/ws', null)).toBe('ws://h/ws')
    expect(WebSocketClient.tokenUrl('ws://h/ws', '')).toBe('ws://h/ws')
  })

  it('encodes the token so JWT dots/specials survive the query string', () => {
    const url = WebSocketClient.tokenUrl('ws://h/ws', 'a.b c')
    expect(url).toBe('ws://h/ws?token=a.b%20c')
  })

  it('covers the RunDetail case: run-scoped URL now carries a token', () => {
    // Regression: RunDetail used to pass an explicit URL and never got a
    // token attached, so the server closed the handshake with 1008.
    const runUrl = 'ws://localhost/api/v1/ws/runs/run-123'
    expect(WebSocketClient.tokenUrl(runUrl, 'jwt-token')).toContain('token=jwt-token')
  })
})

describe('parseWSMessage (contract guard)', () => {
  it('accepts the canonical envelope and exposes data for handlers', () => {
    const msg = parseWSMessage(
      JSON.stringify({
        type: 'run.log',
        data: { run_id: 'r1', step_id: 'a', level: 'ERROR', message: 'boom' },
        timestamp: '2026-01-01T00:00:00+00:00',
      })
    )
    expect(msg?.type).toBe('run.log')
    expect(msg?.data.message).toBe('boom')
  })

  it('defaults missing data to {} so handlers never see undefined', () => {
    const msg = parseWSMessage(JSON.stringify({ type: 'run.status', timestamp: 't' }))
    expect(msg?.data).toEqual({})
  })

  it('rejects malformed frames instead of dispatching them', () => {
    expect(parseWSMessage('not-json')).toBeNull()
    expect(parseWSMessage('null')).toBeNull()
    expect(parseWSMessage('[1,2,3]')).toBeNull()
    expect(parseWSMessage('{"no_type": true}')).toBeNull()
    expect(parseWSMessage('{"type": ""}')).toBeNull()
  })
})
