import { useEffect,useState } from 'react'
import { UsersManager } from './UsersManager'
import { FacilitiesManager } from './FacilitiesManager'
import { ResourcesModule } from './ResourcesModule'
type Tab='users'|'facilities'|'resources'
export function ManagementModule(){const[tab,setTab]=useState<Tab>(()=>(localStorage.getItem('lwms_management_tab') as Tab)||'users');useEffect(()=>localStorage.setItem('lwms_management_tab',tab),[tab]);return <div><div className="smart-tabs" role="tablist"><button className={tab==='users'?'active':''} onClick={()=>setTab('users')}>Users & roles</button><button className={tab==='facilities'?'active':''} onClick={()=>setTab('facilities')}>Laboratories & workshops</button><button className={tab==='resources'?'active':''} onClick={()=>setTab('resources')}>Resources</button></div>{tab==='users'?<UsersManager/>:tab==='facilities'?<FacilitiesManager/>:<ResourcesModule/>}</div>}
