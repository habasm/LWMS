import { useEffect, useState } from 'react'
import { api } from './lib/api'
import type { Page } from './lib/api'
import { EquipmentQuickSummary } from './EquipmentQuickSummary'
import { ReportsModule } from './ReportsModule'
import type { SessionUser } from './RoleModules'

type Facility={id:number;name:string;kind:string}
type Resource={id:number;name:string;category:string;quantity:number;facility_id:number}
type Usage={id:number;resource_id:number;facility_id:number;quantity:number;usage_type:string;purpose:string;status:string;created_at:string}

export function DeanEquipmentReport(){
  const[resources,setResources]=useState<Resource[]>([]),[requests,setRequests]=useState<Usage[]>([]),[facilities,setFacilities]=useState<Facility[]>([]),[busy,setBusy]=useState(true),[error,setError]=useState('')
  useEffect(()=>{async function load(){try{const[r,u,f]=await Promise.all([api<{data:Resource[]}>('/facility-resources'),api<{data:Usage[]}>('/equipment-usage-requests'),api<Page<Facility>>('/facilities?limit=100')]);setResources(r.data);setRequests(u.data);setFacilities(f.data)}catch(value){setError(value instanceof Error?value.message:'Unable to load equipment report')}finally{setBusy(false)}}void load()},[])
  return <div className="reports-module"><div className="module-heading"><p className="eyebrow">DEAN / EQUIPMENT REPORT</p><h2>Equipment usage summary</h2><p>Read-only inventory, usage, discarded, and pending equipment numbers across facilities.</p></div>{error&&<div className="form-message report-notice">{error}</div>}{busy?<div className="panel report-loading">Loading equipment numbers…</div>:<EquipmentQuickSummary resources={resources} requests={requests} facilities={facilities}/>}</div>
}

export function DeanMaintenanceReport({user}:{user:SessionUser}){
  return <ReportsModule user={user}/>
}
