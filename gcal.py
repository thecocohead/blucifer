import configparser

import datetime
import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Gcal scopes - read only access needed for app
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

# Get all upcoming events on calendar specified as calendar_id
def upcomingEvents(calID):
  # Connect to Google Calendar
  creds = None
  if os.path.exists("token.json"):
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
  if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
      creds.refresh(Request())
    else:
      flow = InstalledAppFlow.from_client_secrets_file(
          "gcal_creds.json", SCOPES
      )
      creds = flow.run_local_server(port=0)
    with open("token.json", "w") as token:
      token.write(creds.to_json())
  
  try:
    service = build("calendar", "v3", credentials=creds)

    # Google Calendar API Calls
    now = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
    events_result = (
        service.events()
        .list(
            calendarId=calID,
            timeMin=now,
            singleEvents=True,
            orderBy="startTime"
        )
        .execute()
    )



    # Parse upcoming events
    events = events_result.get("items", [])

    # deduplicate events based on recurringEventId (so that only the next recurrence is returned)
    invalidRecurrenceIds = []
    output = []
    for event in events:
      # if no recurrengEventId is listed, then we can just get out of this iteration and copy event to output
      if not "recurringEventId" in event:
        output.append(event)
      else:
        # else, event is part of a recurrence
        # first, check if recurrence id is already in list
        if not event['recurringEventId'] in invalidRecurrenceIds:
            # first found occurence of event
            invalidRecurrenceIds.append(event['recurringEventId'])
            # append to output
            output.append(event)

# Prints out upcoming events, but not needed atm
    return output

#    if not events:
#      print("No upcoming events found.")
#      return
#
#    for event in events:
#      start = event["start"].get("dateTime", event["start"].get("date"))
#      print(event["etag"], start, event["summary"])

  except HttpError as error:
    print(f"An error occurred: {error}")