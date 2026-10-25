import type {SessionUser} from './RoleModules'
import {ChairDesk} from './ChairDesk'
import {StoreConsole} from './StoreConsole'

export function StoreModule({user}:{user:SessionUser}){
  const hasStoreManagement=user.role_names.some(role=>['dean','coordinator','super_admin','store_manager'].includes(role))
  return user.role_names.includes('chair')&&!hasStoreManagement?<ChairDesk/>:<StoreConsole user={user}/>
}
