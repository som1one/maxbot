import logging

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .config import settings
from .db import Base, engine, get_db
from .emailer import send_email
from .models import AppSetting, Application
from .schemas import ApplicationCreate, ApplicationOut, SettingsOut, SettingsUpdate
from .security import admin_auth
from .webhook import router as webhook_router


app = FastAPI(title=settings.project_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include webhook routes
app.include_router(webhook_router)


def resolve_notification_email(db: Session) -> str | None:
    setting = db.query(AppSetting).first()
    if setting and setting.notification_email:
        return setting.notification_email
    return settings.default_notification_email


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)

    try:
        with engine.begin() as conn:
            existing = conn.execute(AppSetting.__table__.select()).fetchone()
            if not existing and settings.default_notification_email:
                conn.execute(
                    AppSetting.__table__.insert().values(
                        notification_email=settings.default_notification_email
                    )
                )
    except Exception:
        logging.exception("Could not initialize app settings")


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.project_name, "env": settings.env}


@app.post("/applications", response_model=ApplicationOut)
def create_application(payload: ApplicationCreate, db: Session = Depends(get_db)):
    item = Application(
        user_id=payload.user_id,
        name=payload.name,
        phone=payload.phone,
        message=payload.message,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    notification_email = resolve_notification_email(db)
    if notification_email:
        subject = f"New application from {item.name}"
        body = (
            f"Name: {item.name}\n"
            f"Phone: {item.phone}\n"
            f"Message: {item.message}\n"
            f"User ID: {item.user_id}"
        )
        send_email(subject, body, notification_email)

    return item


@app.get("/admin/applications", response_model=list[ApplicationOut], dependencies=[Depends(admin_auth)])
def list_applications(db: Session = Depends(get_db)):
    return db.query(Application).order_by(Application.id.desc()).all()


@app.get("/admin/applications/{application_id}", response_model=ApplicationOut, dependencies=[Depends(admin_auth)])
def get_application(application_id: int, db: Session = Depends(get_db)):
    item = db.query(Application).filter(Application.id == application_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Application not found")
    return item


@app.delete("/admin/applications/{application_id}", dependencies=[Depends(admin_auth)])
def delete_application(application_id: int, db: Session = Depends(get_db)):
    item = db.query(Application).filter(Application.id == application_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Application not found")
    db.delete(item)
    db.commit()
    return {"message": "Application deleted successfully"}


@app.get("/admin/settings", response_model=SettingsOut, dependencies=[Depends(admin_auth)])
def get_settings(db: Session = Depends(get_db)):
    notification_email = resolve_notification_email(db)
    if not notification_email:
        raise HTTPException(status_code=404, detail="Settings not found")
    return SettingsOut(notification_email=notification_email)


@app.put("/admin/settings", response_model=SettingsOut, dependencies=[Depends(admin_auth)])
def update_settings(payload: SettingsUpdate, db: Session = Depends(get_db)):
    setting = db.query(AppSetting).first()
    if not setting:
        setting = AppSetting(notification_email=payload.notification_email)
        db.add(setting)
    else:
        setting.notification_email = payload.notification_email
    db.commit()
    return SettingsOut(notification_email=setting.notification_email)
