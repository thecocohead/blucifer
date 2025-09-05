import sqlalchemy
import sqlalchemy.orm
import os
import src.models as models
import datetime


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
    # Check if event already exists
    if session.query(sqlalchemy.exists().where(newEvent.etag == models.Event.etag)).scalar():
        # If it does, update it
        session.query(models.Event).filter(models.Event.etag == newEvent.etag).update(newEvent)
    else:
        # Otherwise, create it
        session.add(newEvent)
    session.commit()

def getEvent(session: sqlalchemy.orm.Session, etag: str) -> models.Event | None:
    return session.query(models.Event).filter(models.Event.etag == etag).first()

def getUpcomingEvents(session: sqlalchemy.orm.Session) -> list[models.Event]:
    return session.query(models.Event).filter(models.Event.startTime > datetime.datetime.now()).order_by(models.Event.startTime).all()