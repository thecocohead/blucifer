from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Event(Base):
    __tablename__ = "Events"

    # Show Information
    summary = Column(String, index=True)
    startTime = Column(DateTime, index=True)
    etag = Column(String, primary_key=True, index=True)
    discordThreadID = Column(String, index=True)

    # Show Mode
    mode = Column(String, index=True)

    # Volunteers needed
    neededBookers = Column(Integer, index=True)
    neededDoors = Column(Integer, index=True)
    neededSound = Column(Integer, index=True)