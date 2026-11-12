import { useState } from 'react'
import { useAction } from '../hooks/useAction'
import { proposeBuyerMemory } from '../services/preferences'
import { ErrorNotice } from './Feedback'
import { PreferenceEditor } from './PreferenceEditor'

export function RememberBuyerTurn({
  conversationId,
  turnId,
}: {
  conversationId: string
  turnId: string
}) {
  const action = useAction()
  const [proposal, setProposal] = useState<Awaited<
    ReturnType<typeof proposeBuyerMemory>
  > | null>(null)
  return (
    <details>
      <summary>Review preferences from this question</summary>
      <p>
        The local model can propose a budget and product interests from your own
        saved question. Nothing is remembered until you review and explicitly
        save the proposal.
      </p>
      <ErrorNotice error={action.error} />
      {!proposal && (
        <button
          className="calculator-secondary"
          disabled={action.busy}
          onClick={() =>
            action.run(async () =>
              setProposal(await proposeBuyerMemory(conversationId, turnId)),
            )
          }
        >
          {action.busy
            ? 'Preparing a private proposal…'
            : 'Propose preferences from my question'}
        </button>
      )}
      {proposal && (
        <>
          <ul>
            {proposal.notices.map((notice, index) => (
              <li key={index}>{notice}</li>
            ))}
          </ul>
          <PreferenceEditor
            revision={proposal.profile_revision}
            initial={proposal.preferences}
            onSaved={() => {
              setProposal(null)
              window.location.hash = '/preferences'
            }}
          />
          <button
            className="calculator-secondary"
            onClick={() => setProposal(null)}
          >
            Discard unsaved proposal
          </button>
        </>
      )}
    </details>
  )
}
