from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from .config import settings
from .db import Base, engine, get_db
from .models import Application, AppSetting
from .schemas import ApplicationCreate, ApplicationOut, SettingsOut, SettingsUpdate
from .security import admin_auth
from .emailer import send_email

app = FastAPI(title=settings.project_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize settings on startup
@app.on_event("startup")
def on_startup():
    # Ensure one settings row exists
    try:
        with engine.begin() as conn:
            existing = conn.execute(AppSetting.__table__.select()).fetchone()
            if not existing:
                conn.execute(
                    AppSetting.__table__.insert().values(
                        notification_email=settings.default_notification_email
                    )
                )
    except Exception as e:
        # Log error but don't fail startup
        print(f"Warning: Could not initialize settings: {e}")


@app.get("/health")
def health():
    return {"status": "ok"}


# Applications endpoints
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

    # Send email to admin using environment variable
    if settings.default_notification_email:
        subject = f"New application from {item.name}"
        body = f"Name: {item.name}\nPhone: {item.phone}\nMessage: {item.message}\nUser ID: {item.user_id}"
        try:
            send_email(subject, body, settings.default_notification_email)
        except Exception:
            # Do not fail request if email sending fails
            pass

    return item


@app.get("/admin/applications", response_model=list[ApplicationOut], dependencies=[Depends(admin_auth)])
def list_applications(db: Session = Depends(get_db)):
    items = db.query(Application).order_by(Application.id.desc()).all()
    return items


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


# Settings endpoints
@app.get("/admin/settings", response_model=SettingsOut, dependencies=[Depends(admin_auth)])
def get_settings(db: Session = Depends(get_db)):
    setting = db.query(AppSetting).first()
    if not setting:
        raise HTTPException(status_code=404, detail="Settings not found")
    return SettingsOut(notification_email=setting.notification_email)


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
