import { useId, useState, type FormEvent } from 'react'

import { FactsCard } from '@/components/advisor/FactsCard'
import { Button } from '@/components/ui/button'
import { MAX_TEXT_CHARS, extractFacts, requiredQuestions, type Question, type SiteFacts } from '@/lib/advisor'

// MKC-36: describe a site, confirm the extracted facts, see the follow-up questions.

export interface Operator {
  id: string
  label: string
}

function message(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

export function AdvisorPage({ operators }: { operators: Operator[] }) {
  const textId = useId()
  const operatorId = useId()
  const [text, setText] = useState('')
  const [operator, setOperator] = useState(operators[0]?.id ?? '')
  const [facts, setFacts] = useState<SiteFacts | null>(null)
  const [questions, setQuestions] = useState<Question[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function onExtract(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    // Unmounts the card, so a new extraction starts a fresh draft.
    setFacts(null)
    setQuestions(null)
    try {
      setFacts(await extractFacts(text, operator))
    } catch (caught) {
      setError(message(caught))
    } finally {
      setBusy(false)
    }
  }

  async function onConfirm(confirmed: SiteFacts) {
    setError(null)
    setQuestions(null)
    try {
      setQuestions(await requiredQuestions(confirmed))
    } catch (caught) {
      setError(message(caught))
    }
  }

  return (
    <section className="space-y-6">
      <h1 className="font-heading text-2xl font-semibold">Site advisor</h1>
      <form onSubmit={onExtract} className="space-y-3">
        <div className="space-y-1">
          <label htmlFor={textId} className="block font-medium">
            Site description
          </label>
          <textarea
            id={textId}
            value={text}
            onChange={(event) => setText(event.target.value)}
            rows={4}
            maxLength={MAX_TEXT_CHARS}
            className="w-full rounded-md border bg-background px-2 py-1"
          />
        </div>
        <div className="space-y-1">
          <label htmlFor={operatorId} className="block font-medium">
            Operator
          </label>
          <select
            id={operatorId}
            value={operator}
            onChange={(event) => setOperator(event.target.value)}
            className="rounded-md border bg-background px-2 py-1"
          >
            {operators.map((item) => (
              <option key={item.id} value={item.id}>
                {item.label}
              </option>
            ))}
          </select>
        </div>
        <Button type="submit" disabled={busy || !text.trim() || !operator}>
          Extract facts
        </Button>
      </form>
      {error !== null && (
        <p role="alert" className="text-destructive">
          {error}
        </p>
      )}
      {facts !== null && <FactsCard facts={facts} onConfirm={onConfirm} />}
      {questions !== null &&
        (questions.length === 0 ? (
          <p>No further questions: the facts are complete.</p>
        ) : (
          <ul className="space-y-2">
            {questions.map((question) => (
              <li key={question.field}>
                <p>{question.text}</p>
                {question.options.length > 0 && (
                  <p className="text-muted-foreground">Options: {question.options.join(', ')}</p>
                )}
              </li>
            ))}
          </ul>
        ))}
    </section>
  )
}
