import { useEffect,useState } from 'react'
import { UsersManager } from './UsersManager'
import { FacilitiesManager } from './FacilitiesManager'
import { ResourcesModule } from './ResourcesModule'
import type { SessionUser } from './RoleModules'
type Tab='users'|'facilities'|'resources'
export function ManagementModule({user}:{user:SessionUser}){const dean=user.role_names.includes('dean'),[tab,setTab]=useState<Tab>(()=>dean?'users':(localStorage.getItem('lwms_management_tab') as Tab)||'users');useEffect(()=>localStorage.setItem('lwms_management_tab',tab),[tab]);return <div><div className="smart-tabs" role="tablist"><button className={tab==='users'?'active':''} onClick={()=>setTab('users')}>{dean?'Coordinators':'Users & roles'}</button>{!dean&&<><button className={tab==='facilities'?'active':''} onClick={()=>setTab('facilities')}>Laboratories & workshops</button><button className={tab==='resources'?'active':''} onClick={()=>setTab('resources')}>Resources</button></>}</div>{tab==='users'?<UsersManager/>:tab==='facilities'?<FacilitiesManager/>:<ResourcesModule/>}</div>}
