import sqlalchemy
import sqlalchemy.orm
import os
import src.models as models
import datetime

# Events
def getEngine(fileName: str) -> sqlalchemy.engine.Engine:
    engine = sqlalchemy.create_engine(f"sqlite:///{fileName}")
    return engine
    
def initializeDatabase(fileName: str) -> None:
    engine = getEngine(fileName)
    models.Base.metadata.create_all(engine)

def connect(fileName: str) -> sqlalchemy.orm.Session:
    engine = getEngine(fileName)

    # Check if the database file exists, if not create & initialize it
    if os.path.exists(fileName) == False:
        initializeDatabase(fileName)
    session = sqlalchemy.orm.sessionmaker(bind=engine)
    return session()

def syncEvent(session: sqlalchemy.orm.Session, newEvent: models.Event) -> None:
    session.merge(newEvent)
    session.commit()

def getEvent(session: sqlalchemy.orm.Session, etag: str) -> models.Event | None:
    return session.query(models.Event).filter(models.Event.id == etag).first()

def getEventByThreadID(session: sqlalchemy.orm.Session, discordThreadId: str) -> models.Event | None:
    return session.query(models.Event).filter(models.Event.discordThreadID == discordThreadId).first()

def getUpcomingEvents(session: sqlalchemy.orm.Session) -> list[models.Event]:
    return session.query(models.Event).filter(models.Event.startTime > datetime.datetime.now()).order_by(models.Event.startTime).all()

def setShowMode(session: sqlalchemy.orm.Session, discordThreadId: str, mode: str) -> None:
    event = session.query(models.Event).filter(models.Event.discordThreadID == discordThreadId).first()
    if event is not None:
        event.mode = mode
        syncEvent(session, event)

def getShowMode(session: sqlalchemy.orm.Session, discordThreadId: str) -> str | None:
    event = getEventByThreadID(session, discordThreadId)
    if event is not None:
        return event.mode
    return None

# Volunteer Sign-Ups

def addVolunteerSignUp(session: sqlalchemy.orm.Session, eventid: str, userid: int, role: models.VolunteerRole) -> None:
    newSignup = models.VolunteerSignUp(eventid=eventid, userid=userid, role=role)
    session.add(newSignup)
    session.commit()

def removeVolunteerSignUp(session: sqlalchemy.orm.Session, eventid: str, userid: int) -> None:
    foundSignup = session.query(models.VolunteerSignUp).filter(models.VolunteerSignUp.eventid == eventid, models.VolunteerSignUp.userid == userid).first()
    if foundSignup is not None:
        session.delete(foundSignup)
        session.commit()

def getVolunteerSignupsFromEvent(session: sqlalchemy.orm.Session, eventid: str) -> list[models.VolunteerSignUp]:
    return session.query(models.VolunteerSignUp).filter(models.VolunteerSignUp.eventid == eventid).all()

def getVolunteerSignupsForTimeperiod(session: sqlalchemy.orm.Session, startTime: datetime.datetime, endTime: datetime.datetime) -> list[models.VolunteerSignUp]:
    return session.query(models.VolunteerSignUp).join(models.Event).filter(models.Event.startTime >= startTime, models.Event.startTime <= endTime).all()