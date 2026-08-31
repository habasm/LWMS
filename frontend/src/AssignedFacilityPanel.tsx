import { useEffect, useState } from 'react'
import { api } from './lib/api'
import './assigned-facility.css'

type Facility = { id: number; name: string; kind: string; location: string; capacity: number }
type U = { assigned_facility_id: number | null; assigned_facility: Facility | null; assigned_facility_ids?: number[]; assigned_facilities?: Facility[]; pending_facility_ids?: number[]; pending_facilities?: Facility[] }
type Asset = { id: number; identifier: string; status: string; notes?: string | null }
type R = { id: number; name: string; category: string; quantity: number; facility_id: number; properties: Record<string, string>; assets?: Asset[]; retired_assets?: Asset[] }

export function AssignedFacilityPanel({ user }: { user: U }) {
  const [resources, setResources] = useState<R[]>([])
  const activeFacilities = user.assigned_facilities?.length ? user.assigned_facilities : (user.assigned_facility ? [user.assigned_facility] : [])
  const activeIds = new Set(activeFacilities.map(item => item.id))
  useEffect(() => { api<{ data: R[] }>('/facility-resources').then(result => setResources(result.data.filter(item => activeIds.has(item.facility_id)))) }, [user.assigned_facility_id, user.assigned_facility_ids?.join(',')])
  if (!activeFacilities.length && !user.pending_facilities?.length) return <div className="unassigned-warning">No laboratory or workshop is assigned to this account. Contact Coordinator.</div>
  return <section className="assigned-facility">
    <div className="facility-identity"><span>{activeFacilities[0]?.kind === 'laboratory' ? 'LAB' : 'WS'}</span><div><p className="eyebrow">YOUR WORKING FACILITIES</p><h3>{activeFacilities.length ? activeFacilities.map(item => item.name).join(', ') : 'Pending transfer only'}</h3><small>{activeFacilities.map(item => `${item.location} · Capacity ${item.capacity}`).join(' | ')}</small>{(user.pending_facilities?.length ?? 0) > 0 && <p className="assigned-pending">Pending acceptance: {user.pending_facilities!.map(item => item.name).join(', ')}</p>}</div><strong>{resources.length}<small>resources</small></strong></div>
    <div className="assigned-resource-grid">{resources.map(resource => <details key={resource.id} className="assigned-resource-item"><summary><div><b>{resource.name}</b><small>{resource.category}</small></div><em>{resource.quantity} available</em></summary>{resource.assets && resource.assets.length > 0 && <p className="assigned-serials"><b>Available</b>{resource.assets.map(asset => <span key={asset.id}>{asset.identifier}: <b>{asset.status}</b></span>)}</p>}{resource.retired_assets && resource.retired_assets.length > 0 && <p className="assigned-serials retired"><b>Used / discarded</b>{resource.retired_assets.map(asset => <span key={asset.id}>{asset.identifier}: <b>{asset.notes || 'removed from active inventory'}</b></span>)}</p>}{Object.keys(resource.properties ?? {}).length > 0 && <p>{Object.entries(resource.properties).map(([key, value]) => <span key={key}>{key}: <b>{value}</b></span>)}</p>}</details>)}</div>
  </section>
}
