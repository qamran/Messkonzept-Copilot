import { apiFetch } from '@/lib/api'

// MKC-36: the advisor API's JSON (backend `mkc.advisor.facts` and `mkc.advisor.questions`).

export type FactKey =
  | 'pv.kwp'
  | 'pv.feed_in'
  | 'pv.generation_metered'
  | 'battery.present'
  | 'battery.inverter'
  | 'sve.modul14a'
  | 'extra_households'

export type FeedIn = 'surplus' | 'full'
export type Inverter = 'shared' | 'separate'
export type SveType = 'heat_pump' | 'wallbox' | 'other'
/** §14a Modul 3 is out of scope (design section 7). */
export type Modul14a = 1 | 2

export interface Pv {
  kwp: number | null
  feed_in: FeedIn | null
  generation_metered: boolean | null
}

export interface Battery {
  present: boolean
  inverter: Inverter | null
}

export interface Sve {
  type: SveType
  modul14a: Modul14a | null
}

export interface ScopeNote {
  reason: 'modul3' | 'plug_in_pv' | 'commercial' | 'medium_voltage' | 'off_topic'
  message: string
}

export interface SiteFacts {
  operator_id: string
  pv: Pv | null
  battery: Battery | null
  sve: Sve[]
  extra_households: number | null
  unknown: FactKey[]
  out_of_scope: ScopeNote[]
}

export interface Question {
  field: FactKey
  text: string
  options: string[]
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await apiFetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    throw new Error(`The advisor request failed with status ${response.status}`)
  }
  return (await response.json()) as T
}

/** Free text and an operator become site facts (one model call in the backend). */
export function extractFacts(text: string, operatorId: string): Promise<SiteFacts> {
  return postJson<SiteFacts>('/api/advisor/facts', { text, operator_id: operatorId })
}

/** The follow-up questions for confirmed facts (plain code in the backend). */
export function requiredQuestions(facts: SiteFacts): Promise<Question[]> {
  return postJson<Question[]>('/api/advisor/questions', facts)
}
