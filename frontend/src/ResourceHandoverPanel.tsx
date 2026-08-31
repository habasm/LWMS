import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from './lib/api'
import './resource-handover.css'

type Asset = { id: number; identifier: string; status: string; notes?: string | null }
type Facility = { id: number; name: string; kind: string; location?: string }
type PendingChange = {
  revision: number
  baseline_missing: boolean
  from_quantity: number
  to_quantity: number
  added_identifiers: string[]
  removed_identifiers: string[]
  unchanged_identifiers: string[]
  details_changed: boolean
  baseline_name: string | null
  baseline_category: string | null
}
export type HandoverResource = {
  id: number
  facility_id: number
  name: string
  category: string
  quantity: number
  properties: Record<string, string>
  revision: number
  review_status: 'pending' | 'accepted' | 'rejected' | 'archived'
  review_notes: string | null
  submitted_by_name: string
  reviewed_by_name: string | null
  reviewed_at: string | null
  updated_at: string
  assets: Asset[]
  retired_assets: Asset[]
  acceptance_required: boolean
  pending_change: PendingChange
  pending_change_summary: string
}
export type ResourceHistoryEvent = { id: number; action: string; revision: number; notes: string | null; actor_name: string; created_at: string; before_snapshot: Record<string, unknown> | null; after_snapshot: Record<string, unknown> | null }

const list = (snapshot: Record<string, unknown> | null, key: string) => Array.isArray(snapshot?.[key]) ? snapshot[key] as string[] : []
const text = (snapshot: Record<string, unknown> | null, key: string) => typeof snapshot?.[key] === 'string' ? String(snapshot[key]) : ''
const qty = (snapshot: Record<string, unknown> | null) => typeof snapshot?.quantity === 'number' ? snapshot.quantity : null

function diff(event: ResourceHistoryEvent) {
  const before = event.before_snapshot
  const after = event.after_snapshot
  const beforeSerials = list(before, 'asset_identifiers')
  const afterSerials = list(after, 'asset_identifiers')
  const added = afterSerials.filter(value => !beforeSerials.includes(value))
  const removed = beforeSerials.filter(value => !afterSerials.includes(value))
  const changes = [
    text(before, 'name') !== text(after, 'name') && after ? `Name: ${text(before, 'name') || 'new'} -> ${text(after, 'name')}` : '',
    text(before, 'category') !== text(after, 'category') && after ? `Category: ${text(before, 'category') || 'new'} -> ${text(after, 'category')}` : '',
    qty(before) !== qty(after) ? `Quantity: ${qty(before) ?? 0} -> ${qty(after) ?? 0}` : '',
  ].filter(Boolean)
  return { beforeQty: qty(before), afterQty: qty(after), added, removed, changes, beforeSerials, afterSerials }
}

export function resourceStageTitle(event: ResourceHistoryEvent) {
  if (event.action === 'created_and_submitted') return `Version ${event.revision} original registration submitted`
  if (event.action === 'accepted') return `Version ${event.revision} accepted by assistant`
  if (event.action === 'rejected') return `Version ${event.revision} rejected for correction`
  if (event.action === 'added_units_submitted') return `Version ${event.revision} added devices submitted`
  if (event.action === 'removed_units_submitted') return `Version ${event.revision} removed devices submitted`
  if (event.action === 'usage_consumed') return `Version ${event.revision} used devices approved`
  if (event.action === 'usage_discarded') return `Version ${event.revision} discarded devices approved`
  if (event.action === 'archived') return `Version ${event.revision} archived from active inventory`
  return `Version ${event.revision} ${event.action.replaceAll('_', ' ')}`
}

function ChangeBlock({ title, values, tone }: { title: string; values: string[]; tone: 'added' | 'removed' | 'neutral' }) {
  if (values.length === 0) return null
  return <div className={'change-block ' + tone}><b>{title}</b><div>{values.map(value => <span key={value}>{value}</span>)}</div></div>
}

function PendingChangeSummary({ item }: { item: HandoverResource }) {
  const change = item.pending_change
  const addedTitle = change.baseline_missing ? `New devices in version ${item.revision}` : `Added in version ${item.revision}`
  return <div className="version-change">
    <div className="version-strip">
      <span>Version {item.revision}</span>
      <b>{item.pending_change_summary}</b>
      <em>{change.from_quantity} before {'->'} {change.to_quantity} after</em>
    </div>
    <ChangeBlock title={addedTitle} values={change.added_identifiers} tone="added" />
    <ChangeBlock title="Removed from accepted inventory" values={change.removed_identifiers} tone="removed" />
    {change.details_changed && !change.baseline_missing && <div className="change-block neutral"><b>Details changed</b><div><span>{change.baseline_name || 'Previous record'} {'->'} {item.name}</span><span>{change.baseline_category || 'Previous category'} {'->'} {item.category}</span></div></div>}
    {change.unchanged_identifiers.length > 0 && <p className="unchanged-count">{change.unchanged_identifiers.length} previously accepted unit{change.unchanged_identifiers.length === 1 ? '' : 's'} stay unchanged.</p>}
  </div>
}

export function versionSourceEvent(events: ResourceHistoryEvent[], event: ResourceHistoryEvent) {
  if (event.action !== 'accepted' && event.action !== 'rejected') return event
  return [...events].reverse().find(item => item.revision === event.revision && item.id < event.id && item.action !== 'accepted' && item.action !== 'rejected') || event
}

export function ResourceHistoryDetails({ event, sourceEvent }: { event: ResourceHistoryEvent; sourceEvent?: ResourceHistoryEvent }) {
  const data = diff(sourceEvent || event)
  const isDecision = event.action === 'accepted' || event.action === 'rejected'
  const isCreated = event.action === 'created_and_submitted'
  const decisionText = event.action === 'accepted' ? 'This version became the current accepted inventory. No new acceptance is needed until another coordinator change is submitted.' : 'This version did not become current inventory. Coordinator must correct and resubmit it.'
  const decisionLabel = event.action === 'accepted' ? 'Accepted units in this version' : 'Rejected units in this version'
  const decisionUnits = data.added.length > 0 ? data.added : data.afterSerials
  const submittedLabel = isCreated ? 'Original units submitted in this version' : data.added.length > 0 ? 'Added units in this version' : 'Submitted units in this version'
  const missingAddedUnits = !isDecision && !isCreated && data.added.length === 0 && (data.afterQty ?? 0) > (data.beforeQty ?? 0)
  const isUsage = event.action === 'usage_consumed' || event.action === 'usage_discarded'
  const quantityOnlyUsage = isUsage && data.removed.length === 0
  return <div className="history-diff">
    {isDecision && <p className={'history-decision ' + event.action}>{decisionText}</p>}
    {isDecision && decisionUnits.length > 0 && <p className="history-added"><b>{decisionLabel}</b>{decisionUnits.map(value => <span key={value}>{value}</span>)}</p>}
    {!isDecision && data.added.length > 0 && <p className="history-added"><b>{submittedLabel}</b>{data.added.map(value => <span key={value}>{value}</span>)}</p>}
    {missingAddedUnits && <p className="history-warning">This older history entry increased quantity, but the added unit identifier was not captured in the saved snapshot. New version records will list the exact added units.</p>}
    {!isDecision && !isUsage && data.added.length === 0 && data.afterSerials.length > 0 && <p className="history-serials"><b>{submittedLabel}</b>{data.afterSerials.map(value => <span key={value}>{value}</span>)}</p>}
    {data.removed.length > 0 && <p className="history-removed"><b>{isDecision ? 'Removed units confirmed in this version' : 'Removed units in this version'}</b>{data.removed.map(value => <span key={value}>{value}</span>)}</p>}
    {quantityOnlyUsage && <p className="history-warning">Quantity-only usage was approved for this stage. No serial number was selected for this request.</p>}
    {data.changes.length > 0 && <p className="history-changes">{data.changes.map(change => <span key={change}>{change}</span>)}</p>}
    <div className="history-quantities compact"><span>Before <b>{data.beforeQty ?? 0}</b></span><span>After <b>{data.afterQty ?? 0}</b></span></div>
  </div>
}

export function ResourceHistoryList({ events }: { events: ResourceHistoryEvent[] }) {
  const [count, setCount] = useState(3)
  const visible = events.slice(0, count)
  const remaining = Math.max(0, events.length - count)
  return <div className="history-scroll">
    <div className="history-toolbar"><span>Latest {visible.length} of {events.length} stage{events.length === 1 ? '' : 's'}</span>{events.length > 3 && <div><button type="button" disabled={count <= 3} onClick={() => setCount(3)}>Latest 3</button><button type="button" disabled={remaining === 0} onClick={() => setCount(value => Math.min(events.length, value + 3))}>Show older{remaining ? ` (${remaining})` : ''}</button></div>}</div>
    {visible.map(event => <article key={event.id} className={'history-stage ' + event.action}><i /><div><b>{resourceStageTitle(event)}</b><small>{event.actor_name} · {new Date(event.created_at).toLocaleString()}</small><p>{event.notes || 'No note recorded'}</p><ResourceHistoryDetails event={event} sourceEvent={versionSourceEvent(events, event)} /></div></article>)}
  </div>
}

export function ResourceHandoverPanel({ facilityId, onChange, compact = false }: { facilityId: number | null; onChange?: () => void; compact?: boolean }) {
  const [items, setItems] = useState<HandoverResource[]>([])
  const [facility, setFacility] = useState<Facility | null>(null)
  const [tab, setTab] = useState<'pending' | 'current'>('pending')
  const [review, setReview] = useState<{ item: HandoverResource; decision: 'accepted' | 'rejected' } | null>(null)
  const [history, setHistory] = useState<{ item: HandoverResource; events: ResourceHistoryEvent[] } | null>(null)
  const [notice, setNotice] = useState('')
  const load = async () => {
    setItems((await api<{ data: HandoverResource[] }>('/facility-resources')).data.filter(x => x.facility_id === facilityId))
    const facilities = (await api<{ data: Facility[] }>('/facilities?limit=100')).data
    setFacility(facilities.find(item => item.id === facilityId) ?? null)
  }

  useEffect(() => { if (facilityId) void load() }, [facilityId])
  const pending = useMemo(() => items.filter(item => item.acceptance_required), [items])
  const current = useMemo(() => items.filter(item => !item.acceptance_required && item.review_status === 'accepted'), [items])

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!review) return
    const notes = String(new FormData(e.currentTarget).get('notes'))
    try {
      await api(`/facility-resources/${review.item.id}/review`, { method: 'POST', body: JSON.stringify({ decision: review.decision, notes }) })
      setReview(null)
      await load()
      onChange?.()
      setNotice(review.decision === 'accepted' ? 'Only this submitted resource revision was accepted.' : 'Resource revision returned to Coordinator with your reason.')
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Unable to save review')
    }
  }
  async function showHistory(item: HandoverResource) {
    setHistory({ item, events: (await api<{ data: ResourceHistoryEvent[] }>(`/facility-resources/${item.id}/history`)).data })
  }

  if (!facilityId) return null
  const activeList = tab === 'pending' ? pending : current
  return <section className={'handover ' + (compact ? 'compact' : '')}>
    <header><div><p className="eyebrow">EQUIPMENT HANDOVER / {facility?.kind?.toUpperCase()??'FACILITY'}</p><h3>{facility?.name??`Facility #${facilityId}`} {pending.length ? `· ${pending.length} equipment version${pending.length === 1 ? '' : 's'} need review` : '· inventory handover complete'}</h3><p>{pending.length ? 'Accept or reject each equipment version after checking the listed units.' : 'All current equipment versions are accepted and ready for use.'}</p></div><div className={'handover-score ' + (pending.length ? 'waiting' : 'ready')}><strong>{pending.length}</strong><span>pending</span></div></header>
    <div className="handover-tabs"><button className={tab === 'pending' ? 'active' : ''} onClick={() => setTab('pending')}>Pending requests ({pending.length})</button><button className={tab === 'current' ? 'active' : ''} onClick={() => setTab('current')}>Current devices ({current.length})</button></div>
    {notice && <div className="form-message">{notice}<button onClick={() => setNotice('')}>x</button></div>}
    <div className="handover-list">
      {activeList.length === 0 ? <p className="empty-state">{tab === 'pending' ? 'No equipment version is waiting for acceptance.' : 'No accepted equipment is available yet.'}</p> : activeList.map(item => <details key={item.id} className={'handover-item ' + item.review_status}>
        <summary><div className="handover-main"><span className={'handover-status ' + item.review_status}>{item.review_status}</span><div><b>{item.name}</b><small>{item.category} · Revision {item.revision} · {item.quantity} current unit{item.quantity === 1 ? '' : 's'}</small></div></div><em>Expand</em></summary>
        {tab === 'pending' ? <PendingChangeSummary item={item} /> : <div className="current-device-groups"><ChangeBlock title="Available devices" values={item.assets.map(asset => asset.identifier)} tone="added" /><ChangeBlock title="Used / discarded devices" values={(item.retired_assets || []).map(asset => asset.notes ? `${asset.identifier} - ${asset.notes}` : asset.identifier)} tone="removed" /></div>}
        {Object.keys(item.properties || {}).length > 0 && <p className="handover-properties">{Object.entries(item.properties).map(([key, value]) => <span key={key}>{key}: <b>{value}</b></span>)}</p>}
        <p className="handover-meta">Submitted by {item.submitted_by_name} · {new Date(item.updated_at).toLocaleString()}{item.reviewed_by_name ? ` · Reviewed by ${item.reviewed_by_name}` : ''}</p>
        {item.review_notes && <blockquote>{item.review_notes}</blockquote>}
        <div className="handover-actions"><button onClick={() => showHistory(item)}>Full history</button>{tab === 'pending' && <><button className="reject" onClick={() => setReview({ item, decision: 'rejected' })}>Reject version</button><button className="accept" onClick={() => setReview({ item, decision: 'accepted' })}>Accept version</button></>}</div>
      </details>)}
    </div>
    {review && <div className="modal-backdrop"><form className="modal" onSubmit={submit}><p className="eyebrow">REVISION {review.item.revision} · {review.decision.toUpperCase()}</p><h2>{review.item.name}</h2><p className="confirm-copy">{review.decision === 'accepted' ? 'Confirm only the listed change set for this version. Accepted versions will move to current devices.' : 'Describe every mismatch so the Coordinator can correct and resend this version.'}</p><label>{review.decision === 'accepted' ? 'Acceptance note' : 'Rejection reason'}<textarea name="notes" minLength={3} required placeholder={review.decision === 'accepted' ? 'Checked the added/removed units for this version.' : 'Explain missing, incorrect, or damaged items.'} /></label><div className="modal-actions"><button type="button" className="secondary" onClick={() => setReview(null)}>Cancel</button><button className={'primary ' + (review.decision === 'rejected' ? 'danger' : '')}>{review.decision === 'accepted' ? 'Confirm acceptance' : 'Reject and return'}</button></div></form></div>}
    {history && <div className="modal-backdrop"><div className="modal handover-history"><button className="modal-close" onClick={() => setHistory(null)}>x</button><p className="eyebrow">VERSIONED RESOURCE HISTORY</p><h2>{history.item.name}</h2><ResourceHistoryList events={history.events} /></div></div>}
  </section>
}
