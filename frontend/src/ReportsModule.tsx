import { useEffect, useMemo, useState } from 'react'
import { api } from './lib/api'
import type { Page } from './lib/api'
import './reports.css'

type Maintenance={id:number;title:string;details:string;priority:string;kind:string;status:string;resource_id:number;asset_identifier?:string|null;facility_id?:number|null;resolution?:string|null;assistant_verification?:string|null;cost?:number|null;created_at?:string}
type Resource={id:number;name:string;category?:string;facility_id?:number}
type Facility={id:number;name:string;kind?:string}
type ReportUser={role_names:string[];assigned_facility_id:number|null;assigned_facility_ids?:number[]}
type Row={label:string;total:number;open:number;fixed:number;notFixed:number;pending:number;verification:number}

const isOpen=(item:Maintenance)=>!['completed','rejected'].includes(item.status)
const canSeeAll=(user:ReportUser)=>user.role_names.some(role=>['dean','coordinator','super_admin'].includes(role))
const activeFacilityIds=(user:ReportUser)=>new Set(user.assigned_facility_ids?.length?user.assigned_facility_ids:(user.assigned_facility_id?[user.assigned_facility_id]:[]))

function count(items:Maintenance[]){
  return {
    total: items.length,
    open: items.filter(isOpen).length,
    fixed: items.filter(item=>item.resolution==='fixed').length,
    notFixed: items.filter(item=>item.resolution==='not_fixed').length,
    pending: items.filter(item=>item.status==='pending').length,
    verification: items.filter(item=>item.status==='completed'&&!item.assistant_verification).length,
    cost: items.reduce((sum,item)=>sum+(item.cost??0),0),
  }
}

function grouped(items:Maintenance[],label:(item:Maintenance)=>string):Row[]{
  const map=new Map<string,Maintenance[]>()
  items.forEach(item=>{const key=label(item);map.set(key,[...(map.get(key)??[]),item])})
  return Array.from(map.entries()).map(([key,value])=>({label:key,...count(value)})).sort((a,b)=>b.total-a.total)
}

export function MaintenanceQuickSummary({user,items,resources,facilities}:{user:ReportUser;items:Maintenance[];resources:Resource[];facilities:Facility[]}){
  const scoped=useMemo(()=>{const ids=activeFacilityIds(user);return canSeeAll(user)?items:items.filter(item=>item.facility_id&&ids.has(item.facility_id))},[items,user])
  const summary=count(scoped),resourceRows=grouped(scoped,item=>resources.find(resource=>resource.id===item.resource_id)?.name??`Resource #${item.resource_id}`),facilityRows=grouped(scoped,item=>facilities.find(facility=>facility.id===item.facility_id)?.name??'Unassigned facility')
  return <div className="maintenance-quick-summary"><section className="report-metrics"><div><span>Total reports</span><strong>{summary.total}</strong><small>all maintenance records</small></div><div><span>Open</span><strong>{summary.open}</strong><small>not completed or rejected</small></div><div><span>Fixed</span><strong>{summary.fixed}</strong><small>successful repairs</small></div><div><span>Not fixed</span><strong>{summary.notFixed}</strong><small>failed or unresolved repairs</small></div><div><span>Pending</span><strong>{summary.pending}</strong><small>awaiting approval</small></div><div><span>Needs check</span><strong>{summary.verification}</strong><small>assistant verification required</small></div></section><section className="report-grid"><ReportTable title="By resource" rows={resourceRows}/>{canSeeAll(user)&&<ReportTable title="By facility" rows={facilityRows}/>}</section></div>
}

export function ReportsModule({user}:{user:ReportUser}){
  const[items,setItems]=useState<Maintenance[]>([]),[resources,setResources]=useState<Resource[]>([]),[facilities,setFacilities]=useState<Facility[]>([]),[busy,setBusy]=useState(true),[error,setError]=useState('')
  useEffect(()=>{async function load(){try{const[m,r,f]=await Promise.all([api<{data:Maintenance[]}>('/maintenance-workflow'),api<{data:Resource[]}>('/facility-resources'),api<Page<Facility>>('/facilities?limit=100')]);setItems(m.data);setResources(r.data);setFacilities(f.data)}catch(value){setError(value instanceof Error?value.message:'Unable to load reports')}finally{setBusy(false)}}void load()},[])
  return <div className="reports-module"><div className="module-heading"><p className="eyebrow">SMART REPORT</p><h2>Maintenance summary</h2><p>{canSeeAll(user)?'Overall maintenance numbers across all facilities.':'Maintenance numbers for your assigned laboratory or workshop.'}</p></div>{error&&<div className="form-message report-notice">{error}</div>}{busy?<div className="panel report-loading">Loading report numbers…</div>:<MaintenanceQuickSummary user={user} items={items} resources={resources} facilities={facilities}/>}</div>
}

function ReportTable({title,rows}:{title:string;rows:Row[]}){
  const[page,setPage]=useState(1),size=8,pages=Math.max(1,Math.ceil(rows.length/size)),visible=rows.slice((page-1)*size,page*size)
  useEffect(()=>setPage(1),[rows.length])
  return <section className="panel report-table"><h3>{title}</h3>{rows.length===0?<p className="empty-state">No maintenance records yet.</p>:<><div className="report-head"><span>Name</span><span>Total</span><span>Open</span><span>Fixed</span><span>Not fixed</span></div>{visible.map(row=><div className="report-row" key={row.label}><b>{row.label}</b><span>{row.total}</span><span>{row.open}</span><span>{row.fixed}</span><span>{row.notFixed}</span></div>)}{rows.length>size&&<div className="pagination report-pagination"><span>{rows.length} rows · Page {page} of {pages}</span><div><button type="button" disabled={page===1} onClick={()=>setPage(value=>value-1)}>Previous</button><button type="button" disabled={page===pages} onClick={()=>setPage(value=>value+1)}>Next</button></div></div>}</>}</section>
}
