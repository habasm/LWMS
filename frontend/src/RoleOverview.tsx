import { useEffect, useState } from 'react'
import { api } from './lib/api'
import type { Page } from './lib/api'
import type { SessionUser } from './RoleModules'
import { AssignedFacilityPanel } from './AssignedFacilityPanel'
import './overview-actions.css'

type Metric={label:string;value:number;detail:string}
type ActionItem={title:string;meta:string;status:string}
type OverviewState={metrics:Metric[];primary:ActionItem[];secondary:ActionItem[];notes:string[]}
type Project={id:number;title:string;stakeholder_name:string;approval_status:string;facility_name:string|null;created_at:string}
type Schedule={title:string;schedule_type:string;facility_name:string;schedule_state:string;period_start:string;period_end:string}
type Maintenance={title:string;status:string;priority:string;asset_identifier:string|null;facility_id:number}
type Resource={name:string;facility_id:number;review_status:string;submitted_by_name:string;acceptance_required:boolean;pending_change_summary:string}
type Usage={status:string;quantity:number;purpose:string;resource_id:number}
type Facility={id:number;name:string;kind:string}
type UserRecord={is_active:boolean;role_names:string[];full_name:string;added_by_name:string}

const has=(user:SessionUser,...roles:string[])=>roles.some(role=>user.role_names.includes(role))
const activeFacilityIds=(user:SessionUser)=>new Set(user.assigned_facility_ids?.length?user.assigned_facility_ids:(user.assigned_facility_id?[user.assigned_facility_id]:[]))
const label=(value:string)=>value.replaceAll('_',' ')
const emptyState:OverviewState={metrics:[],primary:[],secondary:[],notes:[]}

export function RoleOverview({user}:{user:SessionUser}){
  const[data,setData]=useState<OverviewState>(emptyState)
  const[loading,setLoading]=useState(true)
  const role=user.role_names[0]??'user'
  useEffect(()=>{let mounted=true;async function load(){
    setLoading(true)
    try{
      if(has(user,'dean')){
        const[users,projects,schedules,maintenance]=await Promise.all([api<Page<UserRecord>>('/users?limit=100&active=all'),api<{data:Project[]}>('/projects'),api<{data:Schedule[]}>('/schedules'),api<{data:Maintenance[]}>('/maintenance-workflow')])
        const pending=projects.data.filter(item=>item.approval_status==='pending')
        const decided=projects.data.filter(item=>item.approval_status!=='pending')
        const activeSchedules=schedules.data.filter(item=>item.schedule_state==='active')
        const upcomingSchedules=schedules.data.filter(item=>item.schedule_state==='upcoming')
        const openMaintenance=maintenance.data.filter(item=>!['completed','rejected'].includes(item.status))
        if(mounted)setData({
          metrics:[
            {label:'Pending projects',value:pending.length,detail:'need Dean decision'},
            {label:'Coordinators',value:users.meta.total,detail:'accounts under Dean control'},
            {label:'Active schedules',value:activeSchedules.length,detail:'running facility allocations'},
            {label:'Open maintenance',value:openMaintenance.length,detail:'facility issues in progress'},
          ],
          primary:pending.slice(0,5).map(item=>({title:item.title,meta:`${item.stakeholder_name} · ${item.facility_name??'No facility selected'}`,status:'awaiting decision'})),
          secondary:[...activeSchedules,...upcomingSchedules].slice(0,5).map(item=>({title:item.title,meta:`${item.facility_name} · ${item.period_start} to ${item.period_end}`,status:item.schedule_state})),
          notes:[`${decided.length} project decisions are already documented.`, openMaintenance.length?'Maintenance activity is visible for oversight.':'No open maintenance issues require Dean attention.'],
        })
      }else if(has(user,'coordinator','super_admin')){
        const[users,facilities,resources,maintenance,usage,schedules]=await Promise.all([api<Page<UserRecord>>('/users?limit=100&active=all'),api<Page<Facility>>('/facilities?limit=100'),api<{data:Resource[]}>('/facility-resources'),api<{data:Maintenance[]}>('/maintenance-workflow'),api<{data:Usage[]}>('/equipment-usage-requests'),api<{data:Schedule[]}>('/schedules')])
        const activeUsers=users.data.filter(item=>item.is_active)
        const disabledUsers=users.data.filter(item=>!item.is_active)
        const pendingResources=resources.data.filter(item=>item.acceptance_required)
        const pendingMaintenance=maintenance.data.filter(item=>item.status==='pending')
        const openMaintenance=maintenance.data.filter(item=>!['completed','rejected'].includes(item.status))
        const pendingUsage=usage.data.filter(item=>item.status==='pending')
        const upcoming=schedules.data.filter(item=>item.schedule_state==='upcoming')
        if(mounted)setData({
          metrics:[
            {label:'Active users',value:activeUsers.length,detail:`${disabledUsers.length} disabled`},
            {label:'Facilities',value:facilities.meta.total,detail:'laboratories and workshops'},
            {label:'Pending handovers',value:pendingResources.length,detail:'resources awaiting assistant acceptance'},
            {label:'Open maintenance',value:openMaintenance.length,detail:'requests not closed'},
          ],
          primary:[
            ...pendingMaintenance.slice(0,3).map(item=>({title:item.title,meta:`${item.asset_identifier??'Asset'} · ${item.priority} priority`,status:'review maintenance'})),
            ...pendingUsage.slice(0,2).map(item=>({title:item.purpose,meta:`Quantity ${item.quantity}`,status:'usage decision'})),
          ],
          secondary:[
            ...pendingResources.slice(0,3).map(item=>({title:item.name,meta:`${item.pending_change_summary} · Submitted by ${item.submitted_by_name}`,status:label(item.review_status)})),
            ...upcoming.slice(0,2).map(item=>({title:item.title,meta:`${item.facility_name} · ${item.period_start} to ${item.period_end}`,status:'upcoming'})),
          ],
          notes:[`${facilities.data.filter(item=>item.kind==='laboratory').length} laboratories and ${facilities.data.filter(item=>item.kind==='workshop').length} workshops are registered.`, pendingUsage.length?'Equipment usage requests need a decision.':'No pending equipment usage requests.'],
        })
      }else if(has(user,'lab_admin','laboratory_manager','workshop_manager')){
        const[r,u,m]=await Promise.all([api<{data:{facility_id:number;review_status:string;name:string;quantity:number;acceptance_required:boolean;pending_change_summary:string}[]}>('/facility-resources'),api<{data:{status:string;purpose:string;quantity:number}[]}>('/equipment-usage-requests'),api<{data:{status:string;assistant_verification:string|null;title:string;asset_identifier:string|null}[]}>('/maintenance-workflow')])
        const facilityIds=activeFacilityIds(user)
        const resources=r.data.filter(x=>facilityIds.has(x.facility_id))
        const openMaintenance=m.data.filter(x=>!['completed','rejected'].includes(x.status))
        const verify=m.data.filter(x=>x.status==='completed'&&!x.assistant_verification)
        if(mounted)setData({metrics:[{label:'My resources',value:resources.length,detail:'recorded in assigned facility'},{label:'Usage requests',value:u.data.length,detail:'submitted inventory changes'},{label:'Open maintenance',value:openMaintenance.length,detail:'requests being followed'},{label:'Awaiting verification',value:verify.length,detail:'repairs to check'}],primary:verify.slice(0,4).map(item=>({title:item.title,meta:item.asset_identifier??'Asset',status:'verify repair'})),secondary:resources.filter(item=>item.acceptance_required).slice(0,4).map(item=>({title:item.name,meta:item.pending_change_summary,status:label(item.review_status)})),notes:[]})
      }else if(has(user,'maintainer')){
        const m=await api<{data:{status:string;title:string;asset_identifier:string|null;priority:string}[]}>('/maintenance-workflow')
        if(mounted)setData({metrics:[{label:'Assigned tasks',value:m.data.length,detail:'total maintenance tasks'},{label:'Ready to start',value:m.data.filter(x=>x.status==='assigned').length,detail:'assigned work'},{label:'In progress',value:m.data.filter(x=>x.status==='in_progress').length,detail:'active repairs'},{label:'Completed',value:m.data.filter(x=>x.status==='completed').length,detail:'submitted outcomes'}],primary:m.data.filter(x=>['assigned','in_progress'].includes(x.status)).slice(0,5).map(item=>({title:item.title,meta:`${item.asset_identifier??'Asset'} · ${item.priority} priority`,status:label(item.status)})),secondary:[],notes:[]})
      }else if(mounted)setData(emptyState)
    }finally{if(mounted)setLoading(false)}
  }void load();return()=>{mounted=false}},[role,user.assigned_facility_id,user.assigned_facility_ids?.join(','),user.pending_facility_ids?.join(',')])
  return <div className="overview role-overview"><p className="eyebrow">{role.replaceAll('_',' ').toUpperCase()} OVERVIEW</p><h2>Welcome, {user.full_name.split(' ')[0]}</h2><p className="subcopy">{has(user,'dean')?'Your desk focuses on project decisions, coordinator oversight, schedules, and institutional reports.':has(user,'coordinator','super_admin')?'Your desk shows operational work needing action across users, facilities, resources, scheduling, and maintenance.':'Your summary is based on your assigned responsibilities and access.'}</p>{!has(user,'dean','coordinator','super_admin')&&<AssignedFacilityPanel user={user}/>}<div className="metrics">{data.metrics.map(x=><div className="metric" key={x.label}><span>{x.label}</span><strong>{x.value}</strong><p>{x.detail}</p></div>)}</div>{loading&&<p className="overview-loading">Loading overview...</p>}{!loading&&<div className="overview-action-grid"><OverviewPanel title={has(user,'dean')?'Needs Dean Decision':has(user,'coordinator','super_admin')?'Needs Coordinator Action':'Needs Attention'} items={data.primary}/><OverviewPanel title={has(user,'dean')?'Schedule Awareness':has(user,'coordinator','super_admin')?'Operational Follow-up':'Recent Status'} items={data.secondary}/>{data.notes.length>0&&<section className="overview-panel overview-notes"><h3>Basic Information</h3>{data.notes.map(note=><p key={note}>{note}</p>)}</section>}</div>}</div>
}

function OverviewPanel({title,items}:{title:string;items:ActionItem[]}){
  return <section className="overview-panel"><h3>{title}</h3>{items.length===0?<p className="overview-empty">Nothing urgent in this area.</p>:items.map(item=><article key={`${item.title}-${item.meta}`}><div><b>{item.title}</b><small>{item.meta}</small></div><span>{item.status}</span></article>)}</section>
}
