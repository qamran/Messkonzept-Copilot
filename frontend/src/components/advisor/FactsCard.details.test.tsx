import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { SiteFacts } from '@/lib/advisor'

import { FactsCard } from './FactsCard'

// MKC-36.4, development agent: what FactsCard.test.tsx leaves open.

const EMPTY: SiteFacts = {
  operator_id: 'x',
  pv: null,
  battery: null,
  sve: [],
  extra_households: null,
  unknown: [],
  out_of_scope: [],
}

const GAPS: SiteFacts = {
  ...EMPTY,
  pv: { kwp: null, feed_in: null, generation_metered: true },
  battery: { present: true, inverter: null },
  sve: [
    { type: 'wallbox', modul14a: null },
    { type: 'heat_pump', modul14a: 1 },
  ],
  extra_households: 1,
}

describe('FactsCard details (MKC-36.4)', () => {
  it('says what the site does not have', () => {
    render(<FactsCard facts={EMPTY} onConfirm={vi.fn()} />)
    expect(screen.getByText('PV: none')).toBeInTheDocument()
    expect(screen.getByText('Battery: none')).toBeInTheDocument()
    expect(screen.getByText('Controllable consumers (§14a): none')).toBeInTheDocument()
    expect(screen.getByText('Further households: not stated')).toBeInTheDocument()
  })

  it('marks missing values as not stated', () => {
    render(<FactsCard facts={GAPS} onConfirm={vi.fn()} />)
    expect(screen.getByText('PV: size not stated, feed-in not stated, own generation meter')).toBeInTheDocument()
    expect(screen.getByText('Battery: inverter not stated')).toBeInTheDocument()
    expect(screen.getByText('Wallbox: §14a module not stated')).toBeInTheDocument()
    expect(screen.getByText('Heat pump: §14a Modul 1')).toBeInTheDocument()
    expect(screen.getByText('Further households: 1')).toBeInTheDocument()
  })

  it('names a site without its own generation meter and other consumers', () => {
    const facts: SiteFacts = {
      ...EMPTY,
      pv: { kwp: 4, feed_in: 'full', generation_metered: false },
      sve: [{ type: 'other', modul14a: 2 }],
    }
    render(<FactsCard facts={facts} onConfirm={vi.fn()} />)
    expect(screen.getByText('PV: 4 kWp, full feed-in, no own generation meter')).toBeInTheDocument()
    expect(screen.getByText('Other consumer: §14a Modul 2')).toBeInTheDocument()
  })

  it('marks an unstated generation meter', () => {
    const facts: SiteFacts = { ...EMPTY, pv: { kwp: 4, feed_in: 'full', generation_metered: null } }
    render(<FactsCard facts={facts} onConfirm={vi.fn()} />)
    expect(screen.getByText('PV: 4 kWp, full feed-in, generation meter not stated')).toBeInTheDocument()
  })

  it('shows no edit fields for parts the site does not have', async () => {
    const onConfirm = vi.fn()
    render(<FactsCard facts={EMPTY} onConfirm={onConfirm} />)

    await userEvent.click(screen.getByRole('button', { name: /edit/i }))

    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /confirm/i }))
    expect(onConfirm).toHaveBeenCalledWith(EMPTY)
  })

  it('keeps a value not stated and sets a second module on its own', async () => {
    const onConfirm = vi.fn()
    render(<FactsCard facts={GAPS} onConfirm={onConfirm} />)

    await userEvent.click(screen.getByRole('button', { name: /edit/i }))
    expect(screen.queryByRole('button', { name: /edit/i })).not.toBeInTheDocument()
    const modules = screen.getAllByLabelText(/§14a module/i)
    expect(modules).toHaveLength(2)
    await userEvent.selectOptions(modules[1], '2')
    await userEvent.selectOptions(screen.getByLabelText(/PV feed-in/i), '')
    await userEvent.click(screen.getByRole('button', { name: /confirm/i }))

    const confirmed = onConfirm.mock.calls[0][0] as SiteFacts
    expect(confirmed.pv).toEqual(GAPS.pv)
    expect(confirmed.battery).toEqual(GAPS.battery)
    expect(confirmed.sve).toEqual([
      { type: 'wallbox', modul14a: null },
      { type: 'heat_pump', modul14a: 2 },
    ])
  })

  it('offers no inverter choice when there is no battery', async () => {
    const facts: SiteFacts = { ...GAPS, battery: { present: false, inverter: null } }
    render(<FactsCard facts={facts} onConfirm={vi.fn()} />)

    expect(screen.getByText('Battery: none')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /edit/i }))
    expect(screen.queryByLabelText(/Battery inverter/i)).not.toBeInTheDocument()
  })
})
