import './reports.css'

type Resource={id:number;name:string;category?:string;quantity:number;facility_id:number}
type Usage={id:number;resource_id:number;facility_id?:number;quantity:number;usage_type?:string;purpose:string;status:string;created_at:string}
type Facility={id:number;name:string;kind?:string}

const approved=(request:Usage)=>request.status==='approved'
const sameFacility=(resource:Resource,facilityId:number|null)=>facilityId===null||resource.facility_id===facilityId

export function EquipmentQuickSummary({resources,requests,facilities=[],facilityId=null}:{resources:Resource[];requests:Usage[];facilities?:Facility[];facilityId?:number|null}){
  const scopedResources=resources.filter(resource=>sameFacility(resource,facilityId))
  const resourceIds=new Set(scopedResources.map(resource=>resource.id))
  const scopedRequests=requests.filter(request=>resourceIds.has(request.resource_id))
  const available=scopedResources.reduce((sum,resource)=>sum+resource.quantity,0)
  const consumed=scopedRequests.filter(request=>approved(request)&&request.usage_type==='consumed').reduce((sum,request)=>sum+request.quantity,0)
  const discarded=scopedRequests.filter(request=>approved(request)&&request.usage_type==='discarded').reduce((sum,request)=>sum+request.quantity,0)
  const pending=scopedRequests.filter(request=>request.status==='pending').reduce((sum,request)=>sum+request.quantity,0)
  const approvedCount=scopedRequests.filter(approved).length
  const rejectedCount=scopedRequests.filter(request=>request.status==='rejected').length
  const rows=scopedResources.map(resource=>{
    const usage=scopedRequests.filter(request=>request.resource_id===resource.id)
    return {
      resource,
      consumed: usage.filter(request=>approved(request)&&request.usage_type==='consumed').reduce((sum,request)=>sum+request.quantity,0),
      discarded: usage.filter(request=>approved(request)&&request.usage_type==='discarded').reduce((sum,request)=>sum+request.quantity,0),
      pending: usage.filter(request=>request.status==='pending').reduce((sum,request)=>sum+request.quantity,0),
    }
  }).sort((a,b)=>(b.consumed+b.discarded+b.pending)-(a.consumed+a.discarded+a.pending))
  const groups=Array.from(rows.reduce((map,row)=>{const key=row.resource.facility_id;map.set(key,[...(map.get(key)??[]),row]);return map},new Map<number,typeof rows>()).entries())
  return <div className="equipment-quick-summary"><section className="report-metrics"><div><span>Available</span><strong>{available}</strong><small>current inventory balance</small></div><div><span>Used</span><strong>{consumed}</strong><small>approved consumed quantity</small></div><div><span>Minus / discarded</span><strong>{discarded}</strong><small>approved damaged or removed</small></div><div><span>Pending</span><strong>{pending}</strong><small>waiting for decision</small></div><div><span>Approved</span><strong>{approvedCount}</strong><small>accepted usage requests</small></div><div><span>Rejected</span><strong>{rejectedCount}</strong><small>unchanged inventory</small></div></section><section className="panel report-table equipment-report-table"><h3>By facility</h3>{groups.length===0?<p className="empty-state">No equipment resources yet.</p>:groups.map(([id,group])=>{const facility=facilities.find(item=>item.id===id)?.name??'Assigned facility',facilityAvailable=group.reduce((sum,row)=>sum+row.resource.quantity,0),facilityConsumed=group.reduce((sum,row)=>sum+row.consumed,0),facilityDiscarded=group.reduce((sum,row)=>sum+row.discarded,0),facilityPending=group.reduce((sum,row)=>sum+row.pending,0);return <details className="equipment-facility-group" key={id}><summary><div><b>{facility}</b><small>{group.length} resource group{group.length===1?'':'s'}</small></div><span>{facilityAvailable} available</span><span>{facilityConsumed} used</span><span>{facilityDiscarded} discarded</span><span>{facilityPending} pending</span></summary><div className="equipment-report-head"><span>Resource</span><span>Category</span><span>Available</span><span>Used</span><span>Discarded</span><span>Pending</span></div>{group.map(row=><div className="equipment-report-row" key={row.resource.id}><b>{row.resource.name}</b><span>{row.resource.category}</span><span>{row.resource.quantity}</span><span>{row.consumed}</span><span>{row.discarded}</span><span>{row.pending}</span></div>)}</details>})}</section></div>
}
