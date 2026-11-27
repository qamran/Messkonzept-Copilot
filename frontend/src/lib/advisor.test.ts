import { afterEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '@/lib/api'

import { extractFacts, requiredQuestions, type SiteFacts } from './advisor'

vi.mock('@/lib/api', () => ({ apiFetch: vi.fn() }))

afterEach(() => vi.resetAllMocks())

const FACTS: SiteFacts = {
  operator_id: 'stromnetz-berlin',
  pv: { kwp: 10, feed_in: 'surplus', generation_metered: null },
  battery: { present: true, inverter: null },
  sve: [{ type: 'heat_pump', modul14a: 2 }],
  extra_households: 0,
  unknown: ['battery.inverter'],
  out_of_scope: [],
}

function sent(): { path: string; init: RequestInit } {
  const [path, init] = vi.mocked(apiFetch).mock.calls[0]
  return { path, init: init ?? {} }
}

describe('extractFacts (MKC-36)', () => {
  it('posts the text and operator to /api/advisor/facts as JSON', async () => {
    vi.mocked(apiFetch).mockResolvedValue(Response.json(FACTS))

    const facts = await extractFacts('EFH, 10 kWp PV', 'stromnetz-berlin')

    const { path, init } = sent()
    expect(path).toBe('/api/advisor/facts')
    expect(init.method).toBe('POST')
    expect(new Headers(init.headers).get('Content-Type')).toBe('application/json')
    expect(JSON.parse(String(init.body))).toEqual({
      text: 'EFH, 10 kWp PV',
      operator_id: 'stromnetz-berlin',
    })
    expect(facts).toEqual(FACTS)
  })

  it('throws with the backend status when the call fails', async () => {
    vi.mocked(apiFetch).mockResolvedValue(new Response('', { status: 422 }))
    await expect(extractFacts(' ', 'x')).rejects.toThrow(/422/)
  })
})

describe('requiredQuestions (MKC-36)', () => {
  it('posts the facts to /api/advisor/questions', async () => {
    const questions = [{ field: 'battery.inverter', text: 'Shared inverter?', options: ['shared', 'separate'] }]
    vi.mocked(apiFetch).mockResolvedValue(Response.json(questions))

    const result = await requiredQuestions(FACTS)

    const { path, init } = sent()
    expect(path).toBe('/api/advisor/questions')
    expect(init.method).toBe('POST')
    expect(JSON.parse(String(init.body))).toEqual(FACTS)
    expect(result).toEqual(questions)
  })
})
