from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import declarative_base
from enum import Enum
import discord

class VolunteerRole(Enum):
    BOOKER = 0
    DOOR = 1
    SOUND = 2
    TRAINING_DOOR = 3
    TRAINING_SOUND = 4
    ON_CALL = 5
    VENDOR = 6
    ATTENDING = 7


Base = declarative_base()

class Event(Base):
    __tablename__ = "Events"

    # Show Information
    summary = Column(String, index=True)
    startTime = Column(DateTime, index=True)
    id = Column(String, primary_key=True, index=True)
    discordThreadID = Column(String, index=True)

    # Show Mode
    mode = Column(String, index=True)

    # Volunteers needed
    neededBookers = Column(Integer, index=True)
    neededDoors = Column(Integer, index=True)
    neededSound = Column(Integer, index=True)

class VolunteerSignUp(Base):
    __tablename__ = "Volunteer Sign-Ups"

    id = Column(Integer, primary_key=True, index=True)
    eventid = Column(String, ForeignKey("Events.id"), index=True)
    userid = Column(Integer, index=True)
    role = Column(SQLEnum(VolunteerRole), index=True)