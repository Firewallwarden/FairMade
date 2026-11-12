import { useCallback, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { WorkspaceLayout } from '../components/WorkspaceLayout'
import { ErrorNotice, SignInPrompt } from '../components/Feedback'
import { EvidenceDetails } from '../components/EvidenceDetails'
import { TextArea } from '../components/FormFields'
import { useSession } from '../services/session'
import { useAction } from '../hooks/useAction'
import { useResource } from '../hooks/useResource'
import { createConversation, deleteConversation, getConversation, getConversations, getTurns, sendTurn } from '../services/assistants'
import { getAnalyses, getProduct } from '../services/seller'
import { getCatalogListing } from '../services/commerce'
import type { ConversationScope } from '../services/assistant-contract'
import { fieldValue } from '../utils/form'

export function AssistantPage({ id, source }: { id?: string; source?: { role: 'buyer' | 'seller'; id: string } }) {
  const session = useSession()
  return <WorkspaceLayout title="A little more understanding." intro="Ask FairMade about selected evidence. Backend calculations stay authoritative; AI explanations are not independent verification.">
    {!session ? <SignInPrompt /> : id ? <ConversationView id={id} /> :
      source ? source.role === 'seller' && !session.account.roles.includes('seller') ? <p>Seller access is required.</p> : <StartConversation source={source} /> : <ConversationList />}
  </WorkspaceLayout>
}

function StartConversation({ source }: { source: { role: 'buyer' | 'seller'; id: string } }) {
  const resource = useResource(useCallback(async (signal) => {
    if (source.role === 'buyer') {
      const listing = await getCatalogListing(source.id, signal)
      return { title: listing.payload.product.title, analyses: [] }
    }
    const [product, analyses] = await Promise.all([getProduct(source.id, signal), getAnalyses(source.id, signal)])
    return { title: product.name, analyses: analyses.items }
  }, [source.role, source.id]))
  const action = useAction()
  const retry = useRef<{ signature: string; id: string } | null>(null)
  function start(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const fields = new FormData(event.currentTarget)
    void action.run(async () => {
      const analysis = fieldValue(fields, 'assistant-analysis')
      const scope: ConversationScope = source.role === 'buyer' ? { role: 'buyer', listing_ids: [source.id] } : {
        role: 'seller', product_id: source.id, ...(analysis && { analysis_id: analysis }), include_recipe_inputs: fields.has('assistant-recipe'),
      }
      const signature = JSON.stringify(scope)
      if (retry.current?.signature !== signature) retry.current = { signature, id: crypto.randomUUID() }
      const conversation = await createConversation(scope, retry.current.id)
      window.location.hash = `/assistant/conversations/${conversation.id}`
    })
  }
  return <section className="workspace-panel"><h2>{resource.data?.title ?? 'Select your evidence'}</h2>
    <ErrorNotice error={resource.error || action.error} />
    {resource.loading && <p role="status">Checking access to current sources…</p>}
    {resource.data && <form onSubmit={start}><fieldset className="calculator-form" disabled={action.busy}><legend className="sr-only">Start assistant conversation</legend>
      {source.role === 'seller' ? <>
        <label className="calculator-field">Saved pricing source<select name="assistant-analysis"><option value="">Use the backend’s current selection</option>{resource.data.analyses.map((item) => <option key={item.id} value={item.id}>{new Date(item.created_at).toLocaleString()} · {item.id.slice(0, 8)}</option>)}</select></label>
        <label className="workspace-check"><input type="checkbox" name="assistant-recipe" />Include my private recipe inputs in this seller-only conversation.</label>
        <p>Private seller evidence is sent only to the configured local model. It is never added to a buyer’s conversation.</p>
      </> : <p>This conversation uses this listing’s currently approved public disclosures. Hidden costs and unpublished seller records remain private.</p>}
      <p>Saved conversation history is private to your account. It expires after 30 days of inactivity and can be deleted. Sign in again after a browser reload to reopen it.</p>
      <div className="workspace-actions"><button className="button-primary" type="submit">Start saved conversation</button><a href="#/assistant">Your conversations</a></div>
    </fieldset></form>}
  </section>
}

function ConversationList() {
  const [offset, setOffset] = useState(0)
  const resource = useResource(useCallback((signal) => getConversations(offset, signal), [offset]))
  return <>
    <p>Start a new conversation from a product in your seller workspace or a buyer’s listing page.</p>
    <ErrorNotice error={resource.error} />
    {resource.loading && <p role="status">Loading saved conversations…</p>}
    {resource.data && <>
      {!resource.data.items.length && <div className="workspace-empty"><h2>What would you like to understand?</h2><p>No conversations on this page.</p><a href="#/market">Explore the market</a></div>}
      <div className="workspace-grid">{resource.data.items.map((item) => <article className="workspace-panel" key={item.id}>
        <p className="workspace-status">{item.role} · {item.revision} saved turns</p><h2>A conversation about your selected evidence</h2>
        <p>Updated {new Date(item.updated_at).toLocaleString()}.</p><a href={`#/assistant/conversations/${item.id}`}>Reopen conversation {item.id.slice(0, 8)}</a>
      </article>)}</div>
      <div className="workspace-actions"><button className="calculator-secondary" disabled={!offset} onClick={() => setOffset(offset - 20)}>Previous</button><button className="calculator-secondary" disabled={resource.data.items.length < 20} onClick={() => setOffset(offset + 20)}>Next</button></div>
    </>}
    <button className="calculator-secondary" onClick={resource.reload}>Refresh conversations</button>
  </>
}

function ConversationView({ id }: { id: string }) {
  const [offset, setOffset] = useState(0)
  const resource = useResource(useCallback(async (signal) => {
    const [conversation, turns] = await Promise.all([getConversation(id, signal), getTurns(id, offset, signal)])
    return { conversation, turns }
  }, [id, offset]))
  const action = useAction()
  const [attempt, setAttempt] = useState<{ request_id: string; question: string; expected_revision: number } | null>(null)
  function ask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const question = fieldValue(new FormData(form), 'assistant-question')
    const conversation = resource.data?.conversation
    if (!conversation) return
    const request = attempt ?? { request_id: crypto.randomUUID(), question, expected_revision: conversation.revision }
    setAttempt(request)
    void action.run(async () => {
      const saved = await sendTurn(id, request)
      setAttempt(null)
      form.reset()
      setOffset(Math.floor((saved.revision - 1) / 20) * 20)
      resource.reload()
    }, 'Answer saved. Facts and source access are rechecked when you reopen the conversation.')
  }
  return <>
    <a href="#/assistant">← All conversations</a>
    <ErrorNotice error={resource.error || action.error} />
    {resource.loading && <p role="status">Refreshing conversation evidence…</p>}
    {action.notice && <p role="status" className="calculator-notice">{action.notice}</p>}
    {resource.data && <>
      <p>{resource.data.conversation.role} conversation · {resource.data.conversation.revision}/40 turns · Expires {new Date(resource.data.conversation.expires_at).toLocaleString()}</p>
      <div className="workspace-actions">
        <button className="calculator-secondary" disabled={action.busy} onClick={() => { setAttempt(null); resource.reload() }}>Reload history & current source access</button>
        <button className="calculator-secondary" disabled={offset === 0 || action.busy} onClick={() => setOffset(offset - 20)}>Earlier turns</button>
        <button className="calculator-secondary" disabled={resource.data.turns.items.length < 20 || action.busy} onClick={() => setOffset(offset + 20)}>Later turns</button>
      </div>
      {!resource.data.turns.items.length && <p>No saved turns on this page. Ask your first question below.</p>}
      {resource.data.turns.items.map((turn) => <article className="workspace-panel assistant-turn" key={turn.id}>
        <p className="eyebrow">Your question · turn {turn.revision}</p><h2>{turn.question}</h2>
        {!turn.answer ? <p className="calculator-notice">The source evidence changed. This old answer is withheld; ask again using current evidence.</p> : <>
          <h3>Exact backend facts</h3>{turn.answer.facts.map((fact, index) => <p key={index}>{fact.text} <small>[{fact.evidence_keys.join(', ')}]</small></p>)}
          <h3>AI explanation · local Qwen3</h3>{turn.answer.paragraphs.map((paragraph, index) => <p key={index}>{paragraph.text} <small>[{paragraph.evidence_keys.join(', ')}]</small></p>)}
          <details><summary>Evidence and limitations</summary>{turn.answer.evidence.map((item) => <details key={item.key}><summary>{item.key} · {item.title}</summary><p>Basis: {item.basis.replaceAll('_', ' ')}</p><EvidenceDetails value={item.data} /></details>)}<ul>{turn.answer.notices.map((notice, index) => <li key={index}>{notice}</li>)}</ul></details>
        </>}
      </article>)}
      <section className="workspace-panel"><form onSubmit={ask}><fieldset disabled={action.busy || resource.data.conversation.revision >= 40} className="calculator-form"><legend className="sr-only">Ask FairMade</legend>
        <TextArea title="Your question" name="assistant-question" required maxLength={2000} readOnly={Boolean(attempt)} defaultValue={attempt?.question} placeholder="What goes into this price? What does the evidence leave unknown?" />
        <p>A local model may take up to a couple of minutes. If it is unavailable, no answer is invented and no cloud fallback is used.</p>
        {attempt && <p>The same question and retry identifier are retained until it succeeds or you reload the conversation.</p>}
        <div className="workspace-actions"><button className="button-primary" type="submit">{action.busy ? 'Checking evidence and asking the local model…' : attempt ? 'Retry the same question' : 'Ask FairMade'}</button></div>
      </fieldset></form>{action.busy && <p role="status">Waiting for the local model. You can leave this page; reopen history before sending another question if the result is uncertain.</p>}</section>
    </>}
    <details className="workspace-panel"><summary>Delete this conversation</summary><form onSubmit={(event) => {
      event.preventDefault()
      if (!new FormData(event.currentTarget).has('confirm-delete-conversation')) return
      void action.run(async () => { await deleteConversation(id); window.location.hash = '/assistant' })
    }}><p>Deletes this conversation and its saved turns from your account.</p><label className="workspace-check"><input type="checkbox" name="confirm-delete-conversation" required />Delete this conversation and its history.</label><button className="calculator-secondary" disabled={action.busy} type="submit">Delete conversation</button></form></details>
  </>
}
