import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  cn,
  formatDuration,
  formatBytes,
  formatDate,
  formatRelativeTime,
  getStatusColor,
  getStatusBgColor,
} from '../helpers'

describe('cn', () => {
  it('merges class names', () => {
    expect(cn('px-2', 'py-1')).toBe('px-2 py-1')
  })

  it('resolves tailwind conflicts', () => {
    expect(cn('px-2', 'px-4')).toBe('px-4')
  })
})

describe('formatDuration', () => {
  it('returns -- for null/undefined/0', () => {
    expect(formatDuration(null)).toBe('--')
    expect(formatDuration(undefined)).toBe('--')
    expect(formatDuration(0)).toBe('--')
  })

  it('formats seconds only', () => {
    expect(formatDuration(45)).toBe('45s')
  })

  it('formats minutes and seconds', () => {
    expect(formatDuration(125)).toBe('2m 5s')
  })

  it('formats hours, minutes, and seconds', () => {
    expect(formatDuration(3723)).toBe('1h 2m 3s')
  })
})

describe('formatBytes', () => {
  it('returns -- for null/undefined', () => {
    expect(formatBytes(null)).toBe('--')
    expect(formatBytes(undefined)).toBe('--')
  })

  it('formats 0 bytes as --', () => {
    expect(formatBytes(0)).toBe('--')
  })

  it('formats small values in bytes', () => {
    expect(formatBytes(500)).toBe('500 B')
  })

  it('formats kilobytes', () => {
    expect(formatBytes(1024)).toBe('1.00 KB')
  })

  it('formats megabytes', () => {
    expect(formatBytes(1048576)).toBe('1.00 MB')
  })
})

describe('formatDate', () => {
  it('returns -- for null/undefined', () => {
    expect(formatDate(null)).toBe('--')
    expect(formatDate(undefined)).toBe('--')
  })

  it('formats a date string', () => {
    const result = formatDate('2024-01-15T10:30:00Z')
    expect(result).toContain('Jan')
    expect(result).toContain('2024')
  })
})

describe('formatRelativeTime', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2024-06-15T12:00:00Z'))
  })

  it('returns -- for null/undefined', () => {
    expect(formatRelativeTime(null)).toBe('--')
    expect(formatRelativeTime(undefined)).toBe('--')
  })

  it('returns "just now" for sub-second times', () => {
    expect(formatRelativeTime('2024-06-15T11:59:59.999Z')).toBe('just now')
  })

  it('returns minutes ago', () => {
    expect(formatRelativeTime('2024-06-15T11:55:00Z')).toBe('5 minutes ago')
  })

  it('returns singular for 1 unit', () => {
    expect(formatRelativeTime('2024-06-15T11:59:00Z')).toBe('1 minute ago')
  })

  it('returns hours ago', () => {
    expect(formatRelativeTime('2024-06-15T09:00:00Z')).toBe('3 hours ago')
  })

  it('returns days ago', () => {
    expect(formatRelativeTime('2024-06-13T12:00:00Z')).toBe('2 days ago')
  })

  afterEach(() => {
    vi.useRealTimers()
  })
})

describe('getStatusColor', () => {
  it('returns correct colors for known statuses', () => {
    expect(getStatusColor('pending')).toBe('bg-amber-500')
    expect(getStatusColor('running')).toBe('bg-blue-500')
    expect(getStatusColor('success')).toBe('bg-green-500')
    expect(getStatusColor('failed')).toBe('bg-red-500')
    expect(getStatusColor('cancelled')).toBe('bg-gray-500')
  })

  it('is case insensitive', () => {
    expect(getStatusColor('Running')).toBe('bg-blue-500')
  })

  it('returns default for unknown status', () => {
    expect(getStatusColor('unknown')).toBe('bg-gray-400')
  })
})

describe('getStatusBgColor', () => {
  it('returns correct bg+text classes for known statuses', () => {
    expect(getStatusBgColor('pending')).toContain('amber')
    expect(getStatusBgColor('success')).toContain('green')
  })
})