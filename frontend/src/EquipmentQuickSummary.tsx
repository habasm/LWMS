import { useMemo, useState } from 'react'
import './reports.css'

type Resource = { id: number; name: string; category?: string; quantity: number; facility_id: number }
type Usage = { id: number; resource_id: number; facility_id?: number; quantity: number; usage_type?: string; purpose: string; status: string; created_at: string }
type Facility = { id: number; name: string; kind?: string }
type Focus = 'available' | 'used' | 'discarded' | 'pending'

const approved = (request: Usage) => request.status === 'approved'
const sameFacility = (resource: Resource, facilityId: number | null) => facilityId === null || resource.facility_id === facilityId

export function EquipmentQuickSummary({ resources, requests, facilities = [], facilityId = null }: { resources: Resource[]; requests: Usage[]; facilities?: Facility[]; facilityId?: number | null }) {
  const [focus, setFocus] = useState<Focus>('available')
  const data = useMemo(() => {
    const scopedResources = resources.filter(resource => sameFacility(resource, facilityId))
    const resourceIds = new Set(scopedResources.map(resource => resource.id))
    const scopedRequests = requests.filter(request => resourceIds.has(request.resource_id))
    const rows = scopedResources.map(resource => {
      const usage = scopedRequests.filter(request => request.resource_id === resource.id)
      return {
        resource,
        consumed: usage.filter(request => approved(request) && request.usage_type === 'consumed').reduce((sum, request) => sum + request.quantity, 0),
        discarded: usage.filter(request => approved(request) && request.usage_type === 'discarded').reduce((sum, request) => sum + request.quantity, 0),
        pending: usage.filter(request => request.status === 'pending').reduce((sum, request) => sum + request.quantity, 0),
      }
    }).sort((a, b) => (b.consumed + b.discarded + b.pending) - (a.consumed + a.discarded + a.pending))
    return {
      scopedResources,
      scopedRequests,
      rows,
      available: scopedResources.reduce((sum, resource) => sum + resource.quantity, 0),
      consumed: scopedRequests.filter(request => approved(request) && request.usage_type === 'consumed').reduce((sum, request) => sum + request.quantity, 0),
      discarded: scopedRequests.filter(request => approved(request) && request.usage_type === 'discarded').reduce((sum, request) => sum + request.quantity, 0),
      pending: scopedRequests.filter(request => request.status === 'pending').reduce((sum, request) => sum + request.quantity, 0),
      approvedCount: scopedRequests.filter(approved).length,
      rejectedCount: scopedRequests.filter(request => request.status === 'rejected').length,
    }
  }, [resources, requests, facilityId])
  const totalMovement = data.available + data.consumed + data.discarded + data.pending || 1
  const groups = Array.from(data.rows.reduce((map, row) => {
    const key = row.resource.facility_id
    map.set(key, [...(map.get(key) ?? []), row])
    return map
  }, new Map<number, typeof data.rows>()).entries())
  const focusLabel = focus === 'available' ? 'available now' : focus === 'used' ? 'approved used' : focus === 'discarded' ? 'approved discarded' : 'waiting decision'
  const metrics: { key: Focus; label: string; value: number; detail: string }[] = [
    { key: 'available', label: 'Available', value: data.available, detail: 'current balance' },
    { key: 'used', label: 'Used', value: data.consumed, detail: `${data.approvedCount} approved request(s)` },
    { key: 'discarded', label: 'Discarded', value: data.discarded, detail: 'damaged or removed' },
    { key: 'pending', label: 'Pending', value: data.pending, detail: 'waiting coordinator' },
  ]
  const segments = [
    { key: 'available', label: 'Available', value: data.available, detail: 'Units ready in the facility' },
    { key: 'used', label: 'Used', value: data.consumed, detail: 'Approved consumed or used units' },
    { key: 'discarded', label: 'Discarded', value: data.discarded, detail: 'Approved damaged or removed units' },
    { key: 'pending', label: 'Pending', value: data.pending, detail: 'Units waiting for coordinator decision' },
  ]
  return <div className="equipment-quick-summary smart-equipment-summary">
    <section className="equipment-summary-hero panel">
      <div><p className="eyebrow">LIVE INVENTORY BALANCE</p><h3>{data.scopedResources.length} resource families</h3><p>{data.available} available units, {data.consumed + data.discarded} already approved out, and {data.pending} waiting for decision.</p></div>
      <div className="equipment-graph-wrap">
        <div className="equipment-balance-bar" aria-label="Inventory balance">{segments.map(segment => <span key={segment.key} className={segment.key} style={{ width: `${segment.value / totalMovement * 100}%` }} title={`${segment.label}: ${segment.value} - ${segment.detail}`}><em>{segment.value}</em></span>)}</div>
        <div className="equipment-graph-legend">{segments.map(segment => <button type="button" key={segment.key} className={focus === segment.key ? 'active ' + segment.key : segment.key} onClick={() => setFocus(segment.key as Focus)} title={segment.detail}><i />{segment.label}<b>{segment.value}</b></button>)}</div>
      </div>
    </section>
    <section className="equipment-focus-cards">{metrics.map(metric => <button type="button" key={metric.key} className={focus === metric.key ? 'active' : ''} onClick={() => setFocus(metric.key)}><span>{metric.label}</span><strong>{metric.value}</strong><small>{metric.detail}</small></button>)}</section>
    <section className="panel report-table equipment-report-table smart-resource-table"><div className="panel-title"><div><h3>Resource detail</h3><p>Showing {focusLabel}</p></div><span className="request-status approved">{data.rejectedCount} rejected</span></div>{groups.length === 0 ? <p className="empty-state">No equipment resources yet.</p> : groups.map(([id, group]) => {
      const facility = facilities.find(item => item.id === id)?.name ?? 'Assigned facility'
      const totals = {
        available: group.reduce((sum, row) => sum + row.resource.quantity, 0),
        used: group.reduce((sum, row) => sum + row.consumed, 0),
        discarded: group.reduce((sum, row) => sum + row.discarded, 0),
        pending: group.reduce((sum, row) => sum + row.pending, 0),
      }
      return <details className="equipment-facility-group" key={id}><summary><div><b>{facility}</b><small>{group.length} resource group{group.length === 1 ? '' : 's'}</small></div><span>{totals.available} available</span><span>{totals.used} used</span><span>{totals.discarded} discarded</span><span>{totals.pending} pending</span></summary><div className="equipment-report-head"><span>Resource</span><span>Category</span><span>Available</span><span>Used</span><span>Discarded</span><span>Pending</span></div>{group.map(row => <div className={'equipment-report-row focus-' + focus} key={row.resource.id}><b>{row.resource.name}</b><span>{row.resource.category}</span><span>{row.resource.quantity}</span><span>{row.consumed}</span><span>{row.discarded}</span><span>{row.pending}</span></div>)}</details>
    })}</section>
  </div>
}
