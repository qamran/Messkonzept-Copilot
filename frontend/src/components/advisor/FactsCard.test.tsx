import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { SiteFacts } from '@/lib/advisor'

import { FactsCard } from './FactsCard'

const FACTS: SiteFacts = {
  operator_id: 'stromnetz-berlin',
  pv: { kwp: 10, feed_in: 'surplus', generation_metered: null },
  battery: { present: true, inverter: 'shared' },
  sve: [{ type: 'heat_pump', modul14a: 2 }],
  extra_households: 0,
  unknown: [],
  out_of_scope: [],
}

describe('FactsCard (MKC-36: confirm or edit the facts)', () => {
  it('shows the extracted facts', () => {
    render(<FactsCard facts={FACTS} onConfirm={vi.fn()} />)
    expect(screen.getByText(/10 kWp/)).toBeInTheDocument()
    expect(screen.getByText(/surplus/i)).toBeInTheDocument()
    expect(screen.getByText(/shared/i)).toBeInTheDocument()
    expect(screen.getByText(/Modul 2/)).toBeInTheDocument()
  })

  it('confirms the facts unchanged', async () => {
    const onConfirm = vi.fn()
    render(<FactsCard facts={FACTS} onConfirm={onConfirm} />)

    await userEvent.click(screen.getByRole('button', { name: /confirm/i }))

    expect(onConfirm).toHaveBeenCalledWith(FACTS)
  })

  it('confirms the edited facts after an edit', async () => {
    const onConfirm = vi.fn()
    render(<FactsCard facts={FACTS} onConfirm={onConfirm} />)

    await userEvent.click(screen.getByRole('button', { name: /edit/i }))
    await userEvent.selectOptions(screen.getByLabelText(/PV feed-in/i), 'full')
    await userEvent.selectOptions(screen.getByLabelText(/Battery inverter/i), 'separate')
    await userEvent.selectOptions(screen.getAllByLabelText(/§14a module/i)[0], '1')
    await userEvent.click(screen.getByRole('button', { name: /confirm/i }))

    expect(onConfirm).toHaveBeenCalledTimes(1)
    const confirmed = onConfirm.mock.calls[0][0] as SiteFacts
    expect(confirmed.pv?.feed_in).toBe('full')
    expect(confirmed.battery?.inverter).toBe('separate')
    expect(confirmed.sve[0].modul14a).toBe(1)
    expect(confirmed.operator_id).toBe('stromnetz-berlin')
  })

  it('offers only Modul 1 and 2 for §14a', async () => {
    render(<FactsCard facts={FACTS} onConfirm={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: /edit/i }))

    const select = screen.getAllByLabelText(/§14a module/i)[0]
    const values = Array.from(select.querySelectorAll('option')).map((o) => o.value)
    expect(values).toContain('1')
    expect(values).toContain('2')
    expect(values).not.toContain('3')
  })

  it('answers an out-of-scope site as not covered, with nothing to confirm', () => {
    const outOfScope: SiteFacts = {
      ...FACTS,
      pv: null,
      battery: null,
      sve: [],
      extra_households: null,
      out_of_scope: [
        { reason: 'modul3', message: '§14a Modul 3 is not covered; clarify with the operator.' },
      ],
    }
    render(<FactsCard facts={outOfScope} onConfirm={vi.fn()} />)

    expect(screen.getByText(/clarify with the operator/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /confirm/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /edit/i })).not.toBeInTheDocument()
  })
})
