from typing import Callable
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from .core.database import get_db
from .core.security import decode_token
from .models import User
bearer=HTTPBearer()
def current_user(credentials:HTTPAuthorizationCredentials=Depends(bearer),db:Session=Depends(get_db))->User:
    data=decode_token(credentials.credentials); user=db.get(User,int(data['sub']))
    if not user: raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail='Invalid session')
    if not user.is_active: raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail='Your account is disabled. Please contact the system administrator.')
    return user
def require_roles(*allowed:str)->Callable:
    def guard(user:User=Depends(current_user))->User:
        if not set(allowed).intersection({role.name for role in user.roles}): raise HTTPException(status_code=403,detail='Insufficient permissions')
        return user
    return guard
