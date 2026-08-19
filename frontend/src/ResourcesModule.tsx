import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from './lib/api'
import type { Page } from './lib/api'
import { ResourceHistoryDetails } from './ResourceHandoverPanel'
import './facility-actions.css'
import './facility-manager.css'

type Facility = { id: number; name: string }
type Asset = { id: number; identifier: string; status: string }
type Resource = { id: number; name: string; category: string; quantity: number; facility_id: number; assets: Asset[]; review_status:string; review_notes:string|null; revision:number; submitted_by_name:string; added_by_name:string; reviewed_by_name:string|null; has_accepted_version:boolean }
type HistoryEvent={id:number;action:string;revision:number;notes:string|null;actor_name:string;created_at:string;before_snapshot:Record<string,unknown>|null;after_snapshot:Record<string,unknown>|null}
const PAGE_SIZE = 10

export function ResourcesModule() {
  const [facilities, setFacilities] = useState<Facility[]>([])
  const [resources, setResources] = useState<Resource[]>([])
  const [facilityId, setFacilityId] = useState('')
  const [editing, setEditing] = useState<Resource | null>(null)
  const [deleting, setDeleting] = useState<Resource | null>(null)
  const [history,setHistory]=useState<{resource:Resource;events:HistoryEvent[]}|null>(null)
  const [action,setAction]=useState<{resource:Resource;kind:'resubmit'|'restore'}|null>(null)
  const [notice, setNotice] = useState('')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [quantity, setQuantity] = useState(1)
  const [identifiers, setIdentifiers] = useState([''])

  const load = async () => {
    setFacilities((await api<Page<Facility>>('/facilities')).data)
    setResources((await api<{ data: Resource[] }>('/facility-resources')).data)
  }

  useEffect(() => { void load() }, [])
  useEffect(() => { setPage(1) }, [facilityId, search])

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const data = new FormData(form)
    const values = {
      name: data.get('name'),
      category: data.get('category'),
      quantity,
      asset_identifiers: identifiers,
    }
    try {
      await api(editing ? `/facility-resources/${editing.id}` : '/facility-resources', {
        method: editing ? 'PATCH' : 'POST',
        body: JSON.stringify(editing ? values : { ...values, facility_id: Number(facilityId), properties: {} }),
      })
      setEditing(null)
      setQuantity(1)
      setIdentifiers([''])
      form.reset()
      await load()
      setNotice(editing ? 'Resource updated and sent for assistant review.' : 'Resource recorded and sent for assistant review.')
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Unable to save resource')
    }
  }

  async function confirmDelete() {
    if (!deleting) return
    try {
      await api(`/facility-resources/${deleting.id}`, { method: 'DELETE' })
      if (editing?.id === deleting.id) setEditing(null)
      setDeleting(null)
      await load()
      setNotice('Resource deleted successfully.')
    } catch (error) {
      setDeleting(null)
      setNotice(error instanceof Error ? error.message : 'Unable to delete resource')
    }
  }
  async function showHistory(resource:Resource){setHistory({resource,events:(await api<{data:HistoryEvent[]}>(`/facility-resources/${resource.id}/history`)).data})}
  async function submitAction(event:FormEvent<HTMLFormElement>){event.preventDefault();if(!action)return;const notes=new FormData(event.currentTarget).get('notes');try{await api(`/facility-resources/${action.resource.id}/${action.kind}`,{method:'POST',body:JSON.stringify({notes})});const kind=action.kind;setAction(null);await load();setNotice(kind==='restore'?'Last accepted version restored and sent for review.':'Resource sent to the assistant again.')}catch(error){setNotice(error instanceof Error?error.message:'Unable to complete action')}}

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase()
    return resources.filter(resource => resource.facility_id === Number(facilityId) && (!query || `${resource.name} ${resource.category}`.toLowerCase().includes(query)))
  }, [resources, facilityId, search])
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const visible = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
  function changeQuantity(value: number) {
    const next = Math.max(1, value || 1)
    setQuantity(next)
    setIdentifiers(current => Array.from({ length: next }, (_, index) => current[index] ?? ''))
  }
  function beginEdit(resource: Resource) {
    setFacilityId(String(resource.facility_id)); setEditing(resource); setQuantity(resource.quantity)
    setIdentifiers(resource.assets.map(asset => asset.identifier).slice(0, resource.quantity))
  }
  function cancelEdit() { setEditing(null); setQuantity(1); setIdentifiers(['']) }

  return <div className="admin-module">
    <div className="module-grid">
      <section className="panel form-panel">
        <h3>{editing ? 'Edit resource' : 'Add a resource'}</h3>
        <form onSubmit={save} key={editing?.id ?? 'new'}>
          <label>Facility<select value={facilityId} onChange={event => setFacilityId(event.target.value)} disabled={!!editing} required><option value="">Choose facility</option>{facilities.map(facility => <option value={facility.id} key={facility.id}>{facility.name}</option>)}</select></label>
          <label>Name<input name="name" defaultValue={editing?.name} required /></label>
          <label>Category<input name="category" defaultValue={editing?.category} required /></label>
          <label>Quantity<input name="quantity" type="number" min="1" value={quantity} onChange={event => changeQuantity(Number(event.target.value))} required /></label>
          <fieldset className="asset-identifiers"><legend>Serial / unique asset numbers</legend><p>Enter one identifier for each physical unit. These numbers are used for maintenance tracking.</p>{identifiers.map((identifier,index)=><label key={index}><span>Unit {index+1}</span><input value={identifier} onChange={event=>setIdentifiers(values=>values.map((value,itemIndex)=>itemIndex===index?event.target.value:value))} placeholder={`e.g. ${editing?'ASSET':'LAB-EQP'}-${String(index+1).padStart(3,'0')}`} required /></label>)}</fieldset>
          <div className="form-actions"><button className="primary">{editing ? 'Update resource' : 'Save resource'}</button>{editing && <button type="button" className="secondary" onClick={cancelEdit}>Cancel</button>}</div>
        </form>
        {notice && <div className="form-message">{notice}<button type="button" onClick={() => setNotice('')}>×</button></div>}
      </section>
      <section className="panel list-panel">
        <div className="panel-title"><div><h3>Recorded resources</h3><p>{filtered.length} matching records</p></div></div>
        {facilityId && <div className="facility-tools"><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search name or category…" /></div>}
        {!facilityId ? <p className="form-hint">Select a facility to view its resources.</p> : visible.length === 0 ? <p className="empty-state">No resources match this search.</p> : visible.map(resource => <div className="table-row resource-record" key={resource.id}><div><div className="resource-title-line"><b>{resource.name}</b><span className={'handover-status '+resource.review_status}>{resource.review_status} · R{resource.revision}</span></div><small>{resource.category} · {resource.quantity} individually tracked unit{resource.quantity===1?'':'s'} · Added by {resource.added_by_name}</small><div className="serial-preview">{resource.assets.slice(0,3).map(asset=><span key={asset.id}>{asset.identifier}</span>)}{resource.assets.length>3&&<em>+{resource.assets.length-3} more</em>}</div>{resource.review_notes&&<small className="review-note">Review: {resource.review_notes}</small>}</div><span className="resource-actions"><button type="button" onClick={()=>showHistory(resource)}>History</button>{resource.review_status==='rejected'&&<button type="button" onClick={()=>setAction({resource,kind:'resubmit'})}>Resend</button>}{resource.has_accepted_version&&resource.review_status!=='accepted'&&<button type="button" onClick={()=>setAction({resource,kind:'restore'})}>Restore accepted</button>}<button type="button" onClick={() => beginEdit(resource)}>Edit</button><button type="button" onClick={() => setDeleting(resource)}>Delete</button></span></div>)}
        {facilityId && <div className="pagination"><span>Page {page} of {pages}</span><div><button type="button" disabled={page === 1} onClick={() => setPage(value => value - 1)}>Previous</button><button type="button" disabled={page === pages} onClick={() => setPage(value => value + 1)}>Next</button></div></div>}
      </section>
    </div>
    {deleting && <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="delete-resource-title"><div className="modal"><p className="eyebrow">ARCHIVE RESOURCE</p><h2 id="delete-resource-title">Remove {deleting.name}?</h2><p className="confirm-copy">It will disappear from active inventory, while its complete audit and operational history remains preserved.</p><div className="modal-actions"><button type="button" className="secondary" onClick={() => setDeleting(null)}>Keep resource</button><button type="button" className="primary danger" onClick={confirmDelete}>Archive resource</button></div></div></div>}
    {action&&<div className="modal-backdrop"><form className="modal" onSubmit={submitAction}><p className="eyebrow">{action.kind==='restore'?'RESTORE ACCEPTED VERSION':'RESEND HANDOVER'}</p><h2>{action.resource.name}</h2><p className="confirm-copy">{action.kind==='restore'?'The last version accepted by the assistant will replace the current details and require acceptance again.':'Send the corrected resource back to the assigned assistant as a new revision.'}</p><label>Action note<textarea name="notes" minLength={3} required/></label><div className="modal-actions"><button type="button" className="secondary" onClick={()=>setAction(null)}>Cancel</button><button className="primary">{action.kind==='restore'?'Restore & send':'Resend resource'}</button></div></form></div>}
    {history&&<div className="modal-backdrop"><div className="modal handover-history"><button className="modal-close" onClick={()=>setHistory(null)}>×</button><p className="eyebrow">IMMUTABLE RESOURCE HISTORY</p><h2>{history.resource.name}</h2>{history.events.map(event=><article key={event.id}><i/><div><b>{event.action.replaceAll('_',' ')}</b><small>Revision {event.revision} · {event.actor_name} · {new Date(event.created_at).toLocaleString()}</small><p>{event.notes||'No note recorded'}</p><ResourceHistoryDetails event={event}/></div></article>)}</div></div>}
  </div>
}
