import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '@/lib/api'
import { requiredQuestions, type SiteFacts } from '@/lib/advisor'

import { AdvisorPage } from './AdvisorPage'

// MKC-36.4, development agent: what AdvisorPage.test.tsx and advisor.test.ts leave open.

vi.mock('@/lib/api', () => ({ apiFetch: vi.fn() }))

afterEach(() => vi.resetAllMocks())

const OPERATORS = [{ id: 'stromnetz-berlin', label: 'Stromnetz Berlin' }]

const FACTS: SiteFacts = {
  operator_id: 'stromnetz-berlin',
  pv: { kwp: 10, feed_in: 'surplus', generation_metered: false },
  battery: null,
  sve: [],
  extra_households: 0,
  unknown: [],
  out_of_scope: [],
}

async function extract() {
  render(<AdvisorPage operators={OPERATORS} />)
  await userEvent.type(screen.getByLabelText(/site description/i), 'EFH mit PV')
  await userEvent.click(screen.getByRole('button', { name: /extract facts/i }))
}

describe('AdvisorPage details (MKC-36.4)', () => {
  it('uses the first operator by default', async () => {
    vi.mocked(apiFetch).mockResolvedValue(Response.json(FACTS))
    await extract()
    await screen.findByRole('button', { name: /confirm/i })
    const [, init] = vi.mocked(apiFetch).mock.calls[0]
    expect(JSON.parse(String(init?.body))).toMatchObject({ operator_id: 'stromnetz-berlin' })
  })

  it('says when no question is left', async () => {
    vi.mocked(apiFetch)
      .mockResolvedValueOnce(Response.json(FACTS))
      .mockResolvedValueOnce(Response.json([]))
    await extract()
    await userEvent.click(await screen.findByRole('button', { name: /confirm/i }))
    expect(await screen.findByText(/no further questions/i)).toBeInTheDocument()
  })

  it('shows the options of a question', async () => {
    const questions = [{ field: 'pv.feed_in', text: 'Surplus or full?', options: ['surplus', 'full'] }]
    vi.mocked(apiFetch)
      .mockResolvedValueOnce(Response.json(FACTS))
      .mockResolvedValueOnce(Response.json(questions))
    await extract()
    await userEvent.click(await screen.findByRole('button', { name: /confirm/i }))
    expect(await screen.findByText('Options: surplus, full')).toBeInTheDocument()
  })

  it('shows the status when the questions request fails', async () => {
    vi.mocked(apiFetch)
      .mockResolvedValueOnce(Response.json(FACTS))
      .mockResolvedValueOnce(new Response('', { status: 500 }))
    await extract()
    await userEvent.click(await screen.findByRole('button', { name: /confirm/i }))
    expect(await screen.findByText(/500/)).toBeInTheDocument()
  })

  it('disables the button while the extraction runs', async () => {
    vi.mocked(apiFetch).mockReturnValue(new Promise(() => {}))
    await extract()
    expect(screen.getByRole('button', { name: /extract facts/i })).toBeDisabled()
  })

  it('clears the questions and shows the new facts on a second extraction', async () => {
    const second: SiteFacts = { ...FACTS, pv: { kwp: 7, feed_in: 'full', generation_metered: false } }
    vi.mocked(apiFetch)
      .mockResolvedValueOnce(Response.json(FACTS))
      .mockResolvedValueOnce(Response.json([]))
      .mockResolvedValueOnce(Response.json(second))
    await extract()
    await userEvent.click(await screen.findByRole('button', { name: /confirm/i }))
    await screen.findByText(/no further questions/i)

    await userEvent.click(screen.getByRole('button', { name: /extract facts/i }))

    expect(await screen.findByText(/7 kWp/)).toBeInTheDocument()
    expect(screen.queryByText(/10 kWp/)).not.toBeInTheDocument()
    expect(screen.queryByText(/no further questions/i)).not.toBeInTheDocument()
  })

  it('shows an out-of-scope note and asks nothing', async () => {
    const outOfScope: SiteFacts = {
      ...FACTS,
      pv: null,
      out_of_scope: [{ reason: 'commercial', message: 'Commercial sites are not covered; clarify with the operator.' }],
    }
    vi.mocked(apiFetch).mockResolvedValue(Response.json(outOfScope))
    await extract()
    expect(await screen.findByText(/commercial sites are not covered/i)).toBeInTheDocument()
    expect(apiFetch).toHaveBeenCalledTimes(1)
  })
})

describe('requiredQuestions errors (MKC-36.4)', () => {
  it('throws with the backend status', async () => {
    vi.mocked(apiFetch).mockResolvedValue(new Response('', { status: 401 }))
    await expect(requiredQuestions(FACTS)).rejects.toThrow(/401/)
  })
})
