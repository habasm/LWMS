import { useEffect, useMemo, useState } from 'react'
import { api } from './lib/api'
import type { Page } from './lib/api'
import { EquipmentQuickSummary } from './EquipmentQuickSummary'
import './facility-manager.css'
import './equipment.css'

type Facility = { id: number; name: string; kind: string }
type Resource = { id: number; name: string; category: string; quantity: number; facility_id: number; accepted: boolean; assets?: {id:number;identifier:string;status:string}[]; retired_assets?: {id:number;identifier:string;status:string;notes?:string|null}[] }
type Usage = { id: number; resource_id: number; facility_id: number; quantity: number; usage_type: string; purpose: string; asset_identifiers: string[]; status: string; created_at: string }
const SIZE = 10

export function EquipmentModule() {
  const [facilities, setFacilities] = useState<Facility[]>([])
  const [resources, setResources] = useState<Resource[]>([])
  const [requests, setRequests] = useState<Usage[]>([])
  const [tab, setTab] = useState<'summary' | 'inventory' | 'requests'>('summary')
  const [search, setSearch] = useState('')
  const [facility, setFacility] = useState('all')
  const [page, setPage] = useState(1)
  const [decision, setDecision] = useState<{ item: Usage; value: 'approved' | 'rejected' } | null>(null)
  const [notice, setNotice] = useState('')

  const load = async () => {
    setFacilities((await api<Page<Facility>>('/facilities?limit=100')).data)
    setResources((await api<{ data: Resource[] }>('/facility-resources')).data)
    setRequests((await api<{ data: Usage[] }>('/equipment-usage-requests')).data)
  }
  useEffect(() => { void load() }, [])
  useEffect(() => setPage(1), [search, facility, tab])

  const filtered = useMemo(() => resources.filter(resource => {
    const facilityName = facilities.find(item => item.id === resource.facility_id)?.name ?? ''
    return (facility === 'all' || resource.facility_id === Number(facility)) && `${resource.name} ${resource.category} ${facilityName}`.toLowerCase().includes(search.toLowerCase())
  }), [resources, facilities, facility, search])
  const pages = Math.max(1, Math.ceil(filtered.length / SIZE))
  const visible = filtered.slice((page - 1) * SIZE, page * SIZE)
  const facilityGroups = Array.from(visible.reduce((map, item) => {
    map.set(item.facility_id, [...(map.get(item.facility_id) ?? []), item])
    return map
  }, new Map<number, Resource[]>()).entries())

  async function decide() {
    if (!decision) return
    try {
      await api(`/equipment-usage-requests/${decision.item.id}/decision`, { method: 'PATCH', body: JSON.stringify({ decision: decision.value }) })
      setDecision(null)
      await load()
      setNotice(decision.value === 'approved' ? 'Request approved and inventory reduced.' : 'Request rejected; inventory unchanged.')
    } catch (error) {
      setDecision(null)
      setNotice(error instanceof Error ? error.message : 'Unable to process request')
    }
  }

  return <div className="admin-module equipment-module">
    <div className="module-heading"><p className="eyebrow">COORDINATOR / EQUIPMENT</p><h2>Equipment & resource control</h2><p>Monitor facility inventory and decide usage requests from assigned administrators.</p></div>
    <div className="smart-tabs equipment-tabs"><button className={tab === 'summary' ? 'active' : ''} onClick={() => setTab('summary')}>Quick summary</button><button className={tab === 'inventory' ? 'active' : ''} onClick={() => setTab('inventory')}>Inventory</button><button className={tab === 'requests' ? 'active' : ''} onClick={() => setTab('requests')}>Usage requests <span>{requests.filter(request => request.status === 'pending').length}</span></button></div>
    {notice && <div className="form-message module-notice">{notice}<button onClick={() => setNotice('')}>x</button></div>}
    {tab === 'summary' ? <EquipmentQuickSummary resources={resources} requests={requests} facilities={facilities} /> : tab === 'inventory' ? <section className="panel equipment-panel">
      <div className="facility-tools"><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search resource, category, or facility..." /><select value={facility} onChange={event => setFacility(event.target.value)}><option value="all">All facilities</option>{facilities.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></div>
      {facilityGroups.length === 0 ? <p className="empty-state">No resources match this search.</p> : facilityGroups.map(([facilityId, group]) => {
        const facilityRecord = facilities.find(item => item.id === facilityId)
        const facilityName = facilityRecord?.name ?? 'Facility'
        const available = group.reduce((sum, item) => sum + item.quantity, 0)
        const retired = group.reduce((sum, item) => sum + (item.retired_assets?.length??0), 0)
        return <details className="equipment-facility-group clean-equipment-group" key={facilityId}><summary><div><b>{facilityName}</b><small>{facilityRecord?.kind??'facility'} · {group.length} equipment famil{group.length === 1 ? 'y' : 'ies'}</small></div><span>{available} available</span><span>{retired} used/discarded</span></summary><div className="equipment-resource-grid">{group.map(item => <details className="equipment-resource-card" key={item.id}><summary><div><b>{item.name}</b><small>{item.category}</small></div><strong>{item.quantity}</strong><span className={item.quantity ? 'active-tag' : 'pending-tag'}>{item.quantity ? 'In stock' : 'Out of stock'}</span></summary>{(item.assets?.length??0)>0&&<p className="usage-serials"><b>Available</b>{item.assets!.map(asset=><span key={asset.id}>{asset.identifier}</span>)}</p>}{(item.retired_assets?.length??0)>0&&<p className="usage-serials retired"><b>Used / discarded</b>{item.retired_assets!.map(asset=><span key={asset.id}>{asset.identifier}{asset.notes?` - ${asset.notes}`:''}</span>)}</p>}</details>)}</div></details>
      })}
      <div className="pagination"><span>{filtered.length} resources · Page {page} of {pages}</span><div><button disabled={page === 1} onClick={() => setPage(value => value - 1)}>Previous</button><button disabled={page === pages} onClick={() => setPage(value => value + 1)}>Next</button></div></div>
    </section> : <section className="panel equipment-panel">
      <div className="request-summary"><strong>{requests.filter(request => request.status === 'pending').length}</strong><span>requests awaiting decision</span></div>
      {requests.length === 0 ? <p className="empty-state">No equipment usage requests.</p> : requests.map(request => <div className="usage-row" key={request.id}><div><b>{resources.find(item => item.id === request.resource_id)?.name ?? `Resource #${request.resource_id}`}</b><small>{facilities.find(item => item.id === request.facility_id)?.name} · Qty {request.quantity} · {request.asset_identifiers?.length ? 'Serial selected' : 'Quantity only'} · {request.purpose}</small>{request.asset_identifiers?.length > 0 && <p className="usage-serials">{request.asset_identifiers.map(serial => <span key={serial}>{serial}</span>)}</p>}</div><span className={'request-status ' + request.status}>{request.status}</span>{request.status === 'pending' ? <div className="decision-actions"><button onClick={() => setDecision({ item: request, value: 'rejected' })}>Reject</button><button onClick={() => setDecision({ item: request, value: 'approved' })}>Approve</button></div> : <span />}</div>)}
    </section>}
    {decision && <div className="modal-backdrop"><div className="modal"><p className="eyebrow">{decision.value.toUpperCase()} REQUEST</p><h2>{decision.value === 'approved' ? 'Approve usage?' : 'Reject usage?'}</h2><p className="confirm-copy">{decision.value === 'approved' ? `${decision.item.quantity} item(s) will be deducted immediately from the facility inventory.` : 'The inventory quantity will remain unchanged.'}</p>{decision.item.asset_identifiers?.length > 0 && <p className="usage-serials">{decision.item.asset_identifiers.map(serial => <span key={serial}>{serial}</span>)}</p>}<div className="modal-actions"><button className="secondary" onClick={() => setDecision(null)}>Cancel</button><button className={'primary ' + (decision.value === 'rejected' ? 'danger' : '')} onClick={decide}>Confirm {decision.value}</button></div></div></div>}
  </div>
}
