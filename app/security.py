from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from .config import settings

security = HTTPBasic()


def admin_auth(credentials: HTTPBasicCredentials = Depends(security)):
    if credentials.username != settings.admin_username or credentials.password != settings.admin_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return credentials.username
