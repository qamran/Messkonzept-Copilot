import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '@/lib/api'
import type { SiteFacts } from '@/lib/advisor'

import { AdvisorPage } from './AdvisorPage'

vi.mock('@/lib/api', () => ({ apiFetch: vi.fn() }))

afterEach(() => vi.resetAllMocks())

const OPERATORS = [
  { id: 'stromnetz-berlin', label: 'Stromnetz Berlin' },
  { id: 'sachsennetze', label: 'SachsenNetze' },
]

const FACTS: SiteFacts = {
  operator_id: 'sachsennetze',
  pv: { kwp: 10, feed_in: 'surplus', generation_metered: null },
  battery: { present: true, inverter: null },
  sve: [{ type: 'heat_pump', modul14a: 2 }],
  extra_households: 0,
  unknown: ['battery.inverter'],
  out_of_scope: [],
}

const QUESTIONS = [
  {
    field: 'battery.inverter',
    text: 'Is the battery on the PV inverter or on its own inverter?',
    options: ['shared', 'separate'],
  },
]

async function describeSite(text: string) {
  await userEvent.type(screen.getByLabelText(/site description/i), text)
  await userEvent.selectOptions(screen.getByLabelText(/operator/i), 'sachsennetze')
  await userEvent.click(screen.getByRole('button', { name: /extract facts/i }))
}

describe('AdvisorPage (MKC-36)', () => {
  it('sends the description and operator and shows the facts card', async () => {
    vi.mocked(apiFetch).mockResolvedValue(Response.json(FACTS))
    render(<AdvisorPage operators={OPERATORS} />)

    await describeSite('EFH, 10 kWp PV, Batterie, WP Modul 2')

    expect(await screen.findByText(/10 kWp/)).toBeInTheDocument()
    const [path, init] = vi.mocked(apiFetch).mock.calls[0]
    expect(path).toBe('/api/advisor/facts')
    expect(JSON.parse(String(init?.body))).toEqual({
      text: 'EFH, 10 kWp PV, Batterie, WP Modul 2',
      operator_id: 'sachsennetze',
    })
  })

  it('asks the follow-up questions after the facts are confirmed', async () => {
    vi.mocked(apiFetch)
      .mockResolvedValueOnce(Response.json(FACTS))
      .mockResolvedValueOnce(Response.json(QUESTIONS))
    render(<AdvisorPage operators={OPERATORS} />)

    await describeSite('EFH, 10 kWp PV, Batterie, WP Modul 2')
    await userEvent.click(await screen.findByRole('button', { name: /confirm/i }))

    expect(await screen.findByText(QUESTIONS[0].text)).toBeInTheDocument()
    const [path, init] = vi.mocked(apiFetch).mock.calls[1]
    expect(path).toBe('/api/advisor/questions')
    expect(JSON.parse(String(init?.body))).toEqual(FACTS)
  })

  it('does not send an empty description', async () => {
    render(<AdvisorPage operators={OPERATORS} />)
    await userEvent.type(screen.getByLabelText(/site description/i), '   ')

    expect(screen.getByRole('button', { name: /extract facts/i })).toBeDisabled()
    expect(apiFetch).not.toHaveBeenCalled()
  })

  it('shows the backend status when the extraction fails', async () => {
    vi.mocked(apiFetch).mockResolvedValue(new Response('', { status: 503 }))
    render(<AdvisorPage operators={OPERATORS} />)

    await describeSite('EFH mit PV')

    expect(await screen.findByText(/503/)).toBeInTheDocument()
  })
})
