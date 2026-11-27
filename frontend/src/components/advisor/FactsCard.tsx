import { useId, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import type { Battery, FeedIn, Inverter, Modul14a, Pv, SiteFacts, Sve, SveType } from '@/lib/advisor'

// MKC-36: the extracted facts, to confirm as they are or after an edit (feature 52).

const SVE_LABELS: Record<SveType, string> = {
  heat_pump: 'Heat pump',
  wallbox: 'Wallbox',
  other: 'Other consumer',
}

const NOT_STATED = 'not stated'

function pvLine(pv: Pv | null): string {
  if (pv === null) return 'PV: none'
  const size = pv.kwp === null ? `size ${NOT_STATED}` : `${pv.kwp} kWp`
  const feedIn = pv.feed_in === null ? `feed-in ${NOT_STATED}` : `${pv.feed_in} feed-in`
  const meter =
    pv.generation_metered === null
      ? `generation meter ${NOT_STATED}`
      : pv.generation_metered
        ? 'own generation meter'
        : 'no own generation meter'
  return `PV: ${size}, ${feedIn}, ${meter}`
}

function batteryLine(battery: Battery | null): string {
  if (battery === null || !battery.present) return 'Battery: none'
  return battery.inverter === null ? `Battery: inverter ${NOT_STATED}` : `Battery: ${battery.inverter} inverter`
}

function sveLine(sve: Sve): string {
  const module = sve.modul14a === null ? `§14a module ${NOT_STATED}` : `§14a Modul ${sve.modul14a}`
  return `${SVE_LABELS[sve.type]}: ${module}`
}

function FactsView({ facts }: { facts: SiteFacts }) {
  return (
    <ul className="space-y-1">
      <li>{pvLine(facts.pv)}</li>
      <li>{batteryLine(facts.battery)}</li>
      {facts.sve.length === 0 ? (
        <li>Controllable consumers (§14a): none</li>
      ) : (
        facts.sve.map((sve, index) => <li key={index}>{sveLine(sve)}</li>)
      )}
      <li>Further households: {facts.extra_households ?? NOT_STATED}</li>
    </ul>
  )
}

interface ChoiceProps {
  label: string
  value: string
  options: string[]
  onChange: (value: string) => void
}

/** A native select: an empty value means "not stated". */
function Choice({ label, value, options, onChange }: ChoiceProps) {
  const id = useId()
  return (
    <div className="flex items-center gap-2">
      <label htmlFor={id} className="w-48">
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="rounded-md border bg-background px-2 py-1"
      >
        <option value="">{NOT_STATED}</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </div>
  )
}

function FactsEdit({ facts, onChange }: { facts: SiteFacts; onChange: (facts: SiteFacts) => void }) {
  const { pv, battery } = facts
  return (
    <div className="space-y-2">
      {pv !== null && (
        <Choice
          label="PV feed-in"
          value={pv.feed_in ?? ''}
          options={['surplus', 'full']}
          onChange={(value) => onChange({ ...facts, pv: { ...pv, feed_in: (value || null) as FeedIn | null } })}
        />
      )}
      {battery !== null && battery.present && (
        <Choice
          label="Battery inverter"
          value={battery.inverter ?? ''}
          options={['shared', 'separate']}
          onChange={(value) =>
            onChange({ ...facts, battery: { ...battery, inverter: (value || null) as Inverter | null } })
          }
        />
      )}
      {facts.sve.map((sve, index) => (
        <Choice
          key={index}
          label={`§14a module (${SVE_LABELS[sve.type]})`}
          value={sve.modul14a === null ? '' : String(sve.modul14a)}
          options={['1', '2']}
          onChange={(value) =>
            onChange({
              ...facts,
              sve: facts.sve.map((item, i) =>
                i === index ? { ...item, modul14a: value ? (Number(value) as Modul14a) : null } : item,
              ),
            })
          }
        />
      ))}
    </div>
  )
}

interface FactsCardProps {
  facts: SiteFacts
  onConfirm: (facts: SiteFacts) => void
}

/** The facts as extracted; an out-of-scope site shows its notes and nothing to confirm. */
export function FactsCard({ facts, onConfirm }: FactsCardProps) {
  const [draft, setDraft] = useState(facts)
  const [editing, setEditing] = useState(false)

  if (facts.out_of_scope.length > 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Not covered</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-1">
            {facts.out_of_scope.map((note) => (
              <li key={note.reason}>{note.message}</li>
            ))}
          </ul>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Site facts</CardTitle>
      </CardHeader>
      <CardContent>{editing ? <FactsEdit facts={draft} onChange={setDraft} /> : <FactsView facts={draft} />}</CardContent>
      <CardFooter className="gap-2">
        {!editing && (
          <Button variant="outline" onClick={() => setEditing(true)}>
            Edit
          </Button>
        )}
        <Button onClick={() => onConfirm(draft)}>Confirm</Button>
      </CardFooter>
    </Card>
  )
}
