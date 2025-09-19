# Imports
import configparser
import discord
import gcal
import datetime
import re
import src.database as db
import src.models as models
import enum
from src.models import Event
from src.models import VolunteerRole

# Configuration Parsing
config = configparser.ConfigParser()
config.read('config.ini', encoding='utf-8')

# Discord bot token
botToken = config['DISCORD']['token']

# Channel & Guild to post show threads
guildID = config['DISCORD']['threadsGuild']
threadsChannel = config['DISCORD']['threadsChannel']

# Search limit for finding threads
searchLimit = config['DISCORD']['searchLimit']

# Administrator role name
botAdminRole = config['DISCORD']['botAdminRole']

# Emojis
bookerEmoji = config['DISCORD']['bookerEmoji']
doorEmoji = config['DISCORD']['doorEmoji']
soundEmoji = config['DISCORD']['soundEmoji']
doorTrainingEmoji = config['DISCORD']['doorTrainingEmoji']
soundTrainingEmoji = config['DISCORD']['soundTrainingEmoji']
onCallEmoji = config['DISCORD']['onCallEmoji']
vendorEmoji = config['DISCORD']['vendorEmoji']
warningConeEmoji = config['DISCORD']['warningConeEmoji']
attendingEmoji = config['DISCORD']['attendingEmoji']

# Google Calendar id 
calendar_id = config['CALENDAR']['id']

# Database file name
db_file = config['DATABASE']['file']

# Set up needed objects for Discord
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

"""
WHAT ARE SHOW POSTS, EMBEDS, AND THREADS

Show posts are made up of two components: The embed and the thread. 

A Show Embed is the root message sent by the bot. It displays the event summary, current signups, and contains the view to sign up for the show. 
A Show Thread is the discord thread that's created by the bot. The thread is where people can chat about the show itsself. 

"""


"""
SHOW ROLES

BOOKER : 0
DOOR : 1
SOUND : 2
TRAINING DOOR : 3
TRAINING SOUND : 4
ON CALL : 5
VENDOR : 6

ATTENDING : 7 (used for meetings)
"""

"""
SHOW MODES

Show modes are used to control the roles users can sign up for. 

STANDARD
- Regular show with standard volunteer roles

FESTIVAL
- Show with restricted training roles- door training and sound training are removed. 

MEETING
- All volunteer roles are removed and replaced with "Attending" role. 

NONE
- No volunteer roles are shown.
"""

async def threadExists(event: Event) -> bool:
    try:
        # Thread exists
        await client.get_channel(int(threadsChannel)).fetch_message(int(event.discordThreadID))
        return True
    except discord.NotFound:
        # Thread has been deleted, remove from db
        newEvent = event
        newEvent.discordThreadID = ""
        await updateEvent(newEvent)
        return False

async def getUpcomingEvents() -> list[Event]:
    """
    Gets a list of upcoming events from the Google Calendar. 

    Returns: list[Event] - List of Event objects as returned by database. 
    """
    events = gcal.upcomingEvents(calendar_id)

    # Connect to database
    session = db.connect(db_file)

    # Write events to db
    for event in events:
        # Check if event exists in db
        currentEvent = db.getEvent(session, event['id'])
        startTime = None
        if 'dateTime' not in event['start']:
        # All day event
            startTime = datetime.datetime.fromisoformat(event['start']['date'])
        else:
        # Normal event with start time
            startTime = datetime.datetime.fromisoformat(event['start']['dateTime'])
        
        if currentEvent:
            # Event exists
            newEvent = models.Event(
                summary=event['summary'],
                startTime=startTime,
                id=event['id'],
                # Keep existing values for show mode and needed volunteers
                discordThreadID=currentEvent.discordThreadID,
                mode=currentEvent.mode,
                neededBookers=currentEvent.neededBookers,
                neededDoors=currentEvent.neededDoors,
                neededSound=currentEvent.neededSound,
            )
        else:
            # Event does not exist
            newEvent = models.Event(
                summary=event['summary'],
                startTime=startTime,
                id=event['id'],
                discordThreadID="",
                mode='STANDARD',
                neededBookers=1,
                neededDoors=2,
                neededSound=1,
            )
        # Write event to db
        db.syncEvent(session, newEvent)
    return db.getUpcomingEvents(session)

async def addUserToThread(message: discord.Message, user: discord.User) -> None:
        """
        Adds the user to a show thread.

        Arguments: 
            Message - Discord.py message to add user to. This is the base of the thread- typically it's a show embed. 
            User - Discord.py user that's being added to a thread 

        Returns: None
        """
        thread = message.thread
        await thread.add_user(user)

async def addUserToEmbed(message: discord.Message, role: VolunteerRole, user: discord.User, bypassOldCheck: bool) -> None:
    """
    Adds the user to the show embed. This function edits the embed to add the user onto it. 

    Arguments:
        Message - Discord.py message to add the user to. For this function, we assume it's a show thread message.
        Slot - Show role to add user to.
        User - Discord.py user to add. 

    Returns: None
    """
    # check if user exists in embed, and if they do remove them from the old role    
    if (not bypassOldCheck) and (await getUserCurrentRole(user, message) != None):
        await removeUserFromEmbed(user, message)
        await removeSignupFromDatabase(user, message)

    # get embed
    embed = message.embeds[0]
    showMode = db.getShowMode(db.connect(db_file), str(message.id))

    # get correct field to add user to
    field = 0
    
    if showMode == "MEETING" and role == VolunteerRole.ATTENDING:
        field = 3
    elif showMode == "STANDARD":
        field = role.value + 3
    elif showMode == "FESTIVAL":
        if role in [VolunteerRole.BOOKER, VolunteerRole.DOOR, VolunteerRole.SOUND]:
            field = role.value + 3
        elif role in [VolunteerRole.ON_CALL, VolunteerRole.VENDOR]:
            field = role.value + 1

    # temporarily store embed into dictionary 
    embedDict = embed.to_dict()
    


    #recalculate and change count of users 
    session = db.connect(db_file)
    event = db.getEventByThreadID(session, str(message.id))
    currentCount = db.getVolunteerSignupsFromEvent(session, event.id).__len__()
    if not bypassOldCheck:
        currentCount += 1
    # change fields

    embedDict['fields'][0]['value'] = f":busts_in_silhouette: {currentCount}"

    embedDict['fields'][field]['value'] = embedDict['fields'][field]['value'] + f"\n<@{user.id}>"

    # send new embed for edit
    newEmbed = discord.Embed.from_dict(embedDict)
    await message.edit(embed=newEmbed)
    
async def getUserCurrentRole(user: discord.User, message: discord.Message) -> VolunteerRole | None:
    """
    Gets the user's current role in a show embed if they are currently signed up. 

    Arguments:
        User - Discord.py user to search for. 
        Message - Discord.py message to search. The message should be a show embed.  

    Returns: int - show role id or -1 if user is not currently signed up.  
    """
    session = db.connect(db_file)
    event = db.getEventByThreadID(session, str(message.id))
    if event is None:
        return None
    # Check if user is signed up for the event
    signups = db.getVolunteerSignupsFromEvent(session, event.id)
    for signup in signups:
        if signup.userid == user.id:
            return signup.role
    return None

async def removeUserFromEmbed(user: discord.User, message: discord.Message) -> None:
    """
    Removes a user from a show embed. 

    Arguments:
        User - Discord.py user to remove from the show embed
        Message - Discord.py message to remove the user from. Should be a show embed. 

    Returns: None
    """
    embed = message.embeds[0]
    fields = embed.fields
    embedDict = embed.to_dict()

    if not await getUserCurrentRole(user, message) == None:
        # decrement signups
        session = db.connect(db_file)
        event = db.getEventByThreadID(session, str(message.id))
        currentCount = db.getVolunteerSignupsFromEvent(session, event.id).__len__()
        currentCount -= 1
        # change fields
        embedDict['fields'][0]['value'] = f":busts_in_silhouette: {currentCount}"
        
        # evil regex fuckery to remove user from role
        targetField = -1
        for field in embedDict['fields']:
            if re.search(f"<@{user.id}>", field['value']):
                targetField = embedDict['fields'].index(field)
                break
        if not targetField == -1:
            newValue = re.sub(f"<@{user.id}>(\\n)?", "", embedDict['fields'][targetField]['value'])
            embedDict['fields'][targetField]['value'] = newValue
        else:
            return

        # send new embed for edit
        newEmbed = discord.Embed.from_dict(embedDict)
        await message.edit(embed=newEmbed)

async def isUserBotAdmin(user: discord.User) -> bool:
    """
    Checks if the user has the bot admin role as specified in config file. 

    Arguments-
        user: discord.py user object to check

    Returns - true if user has the specified bot administrator role, false otherwise. 
    """

    userRoles = [role.name for role in user.roles]
    if botAdminRole in userRoles:
        # user is a bot admin
        return True
    else: 
        # user is not a bot admin
        return False

async def createNeededVolunteers(event: models.Event) -> str:
    """
    With a given embed, get the currently signed up users and format it into a "Needed Volunteers" string. 

    Arguments:
        embed(dict) - Dictionary version of a discord embed. Should be from a show thread message.
    
    Returns: String containing needed volunteer emojis for each needed volunteer. 
    """
    # Get volunteer counts

    # Bail on non-needed show modes
    if event.mode in ["NONE", "MEETING"]:
        return ""

    volunteers = db.getVolunteerSignupsFromEvent(db.connect(db_file), event.id)

    bookerCount = sum(1 for v in volunteers if v.role == models.VolunteerRole.BOOKER)
    doorCount = sum(1 for v in volunteers if v.role == models.VolunteerRole.DOOR or v.role == models.VolunteerRole.TRAINING_DOOR)
    soundCount = sum(1 for v in volunteers if v.role == models.VolunteerRole.SOUND or v.role == models.VolunteerRole.TRAINING_SOUND)

    # Create string of emojis representing needed volunteers
    neededVolunteerString = ""

    while bookerCount < event.neededBookers:
        neededVolunteerString += f"{bookerEmoji} "
        bookerCount += 1

    while doorCount < event.neededDoors:
        neededVolunteerString += f"{doorEmoji} "
        doorCount += 1

    while soundCount < event.neededSound:
        neededVolunteerString += f"{soundEmoji} "
        soundCount += 1
    
    return neededVolunteerString
    
async def createUpcomingShows(events: list[Event]) -> discord.Embed:
    """
    Creates an upcoming shows embed. The embed is formatted as the following:

    Title: Upcoming Events
    Fields: Repeating for each event:
        Field title: Event Summary
        Field value: Start Date (absolute and relative), thread link (if one exists), and volunteers needed (if thread link exists)
    Footer: Timestamp

    Arguments:
        events(list[Event]) - List of event objects as given by database.

    Returns: discord.Embed - Created upcoming shows embed.

    """
    # Create embed
    embed = discord.Embed(title="Upcoming Events")
    for event in events:
        startTimeUNIXSeconds = int(event.startTime.timestamp())

        if not(event.discordThreadID == "") and await threadExists(event):
            # event has a thread, get the message
            jumpURL = "https://discord.com/channels/" + str(guildID) + "/" + str(threadsChannel) + "/" + str(event.discordThreadID)
            neededVolunteerString = await createNeededVolunteers(event)
            warningText = ""
            if event.mode == "FESTIVAL":
                warningText = f"{warningConeEmoji} This show is a festival, no training will be provided."
            elif event.mode == "NONE":
                warningText = f"{warningConeEmoji} This event is for information only and does not have any signups."
            elif event.mode == "MEETING":
                warningText = f"{warningConeEmoji} This event is a meeting."

            if event.mode in ["NONE", "MEETING"]:
                embed.add_field(name=event.summary, value=f"**Date**: <t:{startTimeUNIXSeconds}:F> // <t:{startTimeUNIXSeconds}:R>\n**Thread**: {jumpURL}\n{warningText}", inline = False)   
            else:
                embed.add_field(name=event.summary, value=f"**Date**: <t:{startTimeUNIXSeconds}:F> // <t:{startTimeUNIXSeconds}:R>\n**Thread**: {jumpURL}\n**Needed Volunteers**: {neededVolunteerString if neededVolunteerString else 'None'}\n{warningText}", inline = False)   
        else:
            # event does not have a thread, so skip it
            embed.add_field(name=event.summary, value=f"**Date**: <t:{startTimeUNIXSeconds}:F> // <t:{startTimeUNIXSeconds}:R>", inline = False)
            
            
    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)

    return embed

async def createShowEmbed(event: Event) -> discord.Embed:
    """
    Creates a show embed for the given event- used for /threads

        The show embeds include a title and 11 fields.
        Field 0- number of people signed up for the show. 
        Field 1- absolute start date of show
        Field 2- relative start date of show
        Field 3- Booker signups
        Field 4- Door signups
        Field 5- Sound signups
        Field 6- Door Training signups
        Field 7- Sound Training signups
        Field 8- On-Call signups
        Field 9- Vendor signups
    
    Arguments: event(Event) - event object to create embed for. Should be from database. 

    Returns: discord.Embed - Created show embed.
    """
    startTimeUNIXSeconds = int(event.startTime.timestamp())

    embed = discord.Embed(title=f"{event.summary}", description="")
    
    # Standard fields

    embed.add_field(name="", value=":busts_in_silhouette: 0", inline=False)
    embed.add_field(name="", value=f":calendar: <t:{startTimeUNIXSeconds}:F>", inline=False)
    embed.add_field(name="", value=f":hourglass: <t:{startTimeUNIXSeconds}:R>", inline=False)

    if event.mode == "STANDARD":
        embed.add_field(name=f"{bookerEmoji} Booker", value="", inline=True)
        embed.add_field(name=f"{doorEmoji} Door", value="", inline=True)
        embed.add_field(name=f"{soundEmoji} Sound", value="", inline=True)
        embed.add_field(name=f"{doorTrainingEmoji} Training: Door", value="", inline=True)
        embed.add_field(name=f"{soundTrainingEmoji} Training: Sound", value="", inline=True)
        embed.add_field(name=f"{onCallEmoji} On-Call", value="", inline=True)
        embed.add_field(name=f"{vendorEmoji} Vendors", value="", inline=True)

    if event.mode == "FESTIVAL":
        embed.add_field(name=f"{bookerEmoji} Booker", value="", inline=True)
        embed.add_field(name=f"{doorEmoji} Door", value="", inline=True)
        embed.add_field(name=f"{soundEmoji} Sound", value="", inline=True)
        embed.add_field(name=f"{onCallEmoji} On-Call", value="", inline=True)
        embed.add_field(name=f"{vendorEmoji} Vendors", value="", inline=True)
        embed.add_field(name="", value=f"{warningConeEmoji} This show is a festival, no training will be provided.", inline=False)

    if event.mode == "MEETING":
        embed.add_field(name=f"{attendingEmoji} Attending", value="", inline=True)

    if event.mode == "NONE":
        embed.add_field(name="", value=f"{warningConeEmoji} This event is for information only and does not have any signups.", inline=False)

    return embed

async def updateEvent(event: Event) -> None:
    """
    Updates an event in the database. If the event does not exist (based on etag), it is created.

    Arguments: event(Event) - event object to update with edits. 

    Returns: None
    """
    session = db.connect(db_file)
    db.syncEvent(session, event)

async def userSignUp(button: discord.Button, role: VolunteerRole) -> None:
    message = button.message
    session = db.connect(db_file)
    event = db.getEventByThreadID(session, str(message.id))
    if event is not None:
        await addUserToThread(message, button.user)
        await addUserToEmbed(message, role, button.user, False)
        db.addVolunteerSignUp(session, event.id, button.user.id, role)
    await button.response.send_message("Added you to the show thread!", ephemeral=True)

async def removeSignupFromDatabase(user: discord.User, message: discord.Message) -> None:
    session = db.connect(db_file)
    event = db.getEventByThreadID(session, str(message.id))
    if event is not None:
        db.removeVolunteerSignUp(session, event.id, user.id)

async def removeUserFromEvent(button: discord.Button) -> None:
    message = button.message
    # check if user is in thread
    if await getUserCurrentRole(button.user, button.message) == None:
        # user not in thread
        await button.response.send_message("You aren't in the thread.", ephemeral=True)
    else:
        # remove user from embed
        await removeUserFromEmbed(button.user, button.message)

        # remove user from database
        await removeSignupFromDatabase(button.user, button.message)

        # get base message
        message = button.message
        # get thread
        thread = message.thread
        await thread.remove_user(button.user)
        await button.response.send_message("Removed you from the show thread.", ephemeral=True)

async def generateVolunteerReport(startDate: datetime.datetime, endDate: datetime.datetime) -> str:
    """
    Generates a volunteer report for all users that have signed up for shows between the given start and end dates. 

    Arguments:
        startDate(datetime.datetime) - Start date of report range
        endDate(datetime.datetime) - End date of report range
    
    Returns: str - Formatted volunteer report.
    """
    session = db.connect(db_file)
    signups = db.getVolunteerSignupsForTimeperiod(session, startDate, endDate)

    users = {}
    for signup in signups:
        if signup.userid in users:
            users[signup.userid] += 1
        else:
            users[signup.userid] = 1
    
    usersSorted = sorted(users.items(), key=lambda count: count[1] , reverse=True)

    report = ""
    for user in usersSorted:
        report += f"<@{user[0]}>: {user[1]} signups\n"

    return report

class StandardView(discord.ui.View):
    """
    View to create show signup buttons for show embeds. Also handles users that press each button on a show thread to add them to a show embed & thread. 
    """

    # Needed function for buttons to persist past bot reboot
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Booker", emoji=bookerEmoji, row=0, style=discord.ButtonStyle.primary, custom_id="bookerButton")
    async def bookerButtonCallback(self, button: discord.Button, interaction: discord.Interaction) -> None:
        await userSignUp(button, VolunteerRole.BOOKER)

    @discord.ui.button(label="Door", emoji=doorEmoji, row=0, style=discord.ButtonStyle.primary, custom_id="doorButton")
    async def doorButtonCallback(self, button: discord.Button, interaction: discord.Interaction) -> None:
        await userSignUp(button, VolunteerRole.DOOR)

    @discord.ui.button(label="Sound", emoji=soundEmoji, row=0, style=discord.ButtonStyle.primary, custom_id="soundButton")
    async def soundButtonCallback(self, button: discord.Button, interaction: discord.Interaction) -> None:
        await userSignUp(button, VolunteerRole.SOUND)

    @discord.ui.button(label="Door Training", emoji=doorTrainingEmoji, row=1, style=discord.ButtonStyle.primary, custom_id="doorTrainingButton")
    async def doorTrainingButtonCallback(self, button: discord.Button, interaction: discord.Interaction) -> None:
        await userSignUp(button, VolunteerRole.TRAINING_DOOR)

    @discord.ui.button(label="Sound Training", emoji=soundTrainingEmoji, row=1, style=discord.ButtonStyle.primary, custom_id="soundTrainingButton")
    async def soundTrainingButtonCallback(self, button: discord.Button, interaction: discord.Interaction) -> None:
        await userSignUp(button, VolunteerRole.TRAINING_SOUND)

    @discord.ui.button(label="On Call", emoji=onCallEmoji, row=1, style=discord.ButtonStyle.primary, custom_id="onCallButton")
    async def onCallButtonCallback(self, button: discord.Button, interaction: discord.Interaction) -> None:
        await userSignUp(button, VolunteerRole.ON_CALL)

    @discord.ui.button(label="Vendor", emoji=vendorEmoji, row=1, style=discord.ButtonStyle.primary, custom_id="vendorButton")
    async def vendorButtonCallback(self, button: discord.Button, interaction: discord.Interaction) -> None:
        await userSignUp(button, VolunteerRole.VENDOR)

    @discord.ui.button(label="Remove", row=2, style=discord.ButtonStyle.danger, custom_id="RemoveButton")
    async def removeButtonCallback(self, button: discord.Button, interaction: discord.Interaction) -> None:
        await removeUserFromEvent(button)


class FestivalView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Booker", emoji=bookerEmoji, row=0, style=discord.ButtonStyle.primary, custom_id="bookerButton")
    async def bookerButtonCallback(self, button: discord.Button, interaction: discord.Interaction) -> None:
        await userSignUp(button, VolunteerRole.BOOKER)

    @discord.ui.button(label="Door", emoji=doorEmoji, row=0, style=discord.ButtonStyle.primary, custom_id="doorButton")
    async def doorButtonCallback(self, button: discord.Button, interaction: discord.Interaction) -> None:
        await userSignUp(button, VolunteerRole.DOOR)

    @discord.ui.button(label="Sound", emoji=soundEmoji, row=0, style=discord.ButtonStyle.primary, custom_id="soundButton")
    async def soundButtonCallback(self, button: discord.Button, interaction: discord.Interaction) -> None:
        await userSignUp(button, VolunteerRole.SOUND)

    @discord.ui.button(label="On Call", emoji=onCallEmoji, row=1, style=discord.ButtonStyle.primary, custom_id="onCallButton")
    async def onCallButtonCallback(self, button: discord.Button, interaction: discord.Interaction) -> None:
        await userSignUp(button, VolunteerRole.ON_CALL)

    @discord.ui.button(label="Vendor", emoji=vendorEmoji, row=1, style=discord.ButtonStyle.primary, custom_id="vendorButton")
    async def vendorButtonCallback(self, button: discord.Button, interaction: discord.Interaction) -> None:
        await userSignUp(button, VolunteerRole.VENDOR)

    @discord.ui.button(label="Remove", row=2, style=discord.ButtonStyle.danger, custom_id="RemoveButton")
    async def removeButtonCallback(self, button: discord.Button, interaction: discord.Interaction) -> None:
        await removeUserFromEvent(button)

class MeetingView(discord.ui.View):

    # Needed function for buttons to persist past bot reboot
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Attending", emoji=attendingEmoji, row=1, style=discord.ButtonStyle.primary, custom_id="attendingButton")
    async def attendingButtonCallback(self, button: discord.Button, interaction: discord.Interaction) -> None:
        await userSignUp(button, VolunteerRole.ATTENDING)
        
    @discord.ui.button(label="Remove", row=2, style=discord.ButtonStyle.danger, custom_id="RemoveButton")
    async def removeButtonCallback(self, button: discord.Button, interaction: discord.Interaction) -> None:
        await removeUserFromEvent(button)

@client.event
async def on_ready():
    """
    Ran when the bot connects to Discord. Prints to console that it connected successfully, syncs the command tree (all the slash commands used to interact with the bot), and adds the buttons above so they can be used past reboot. 

    Arguments- None
    Returns- None
    """
    print(f'Logged in as {client.user}')
    await tree.sync(guild=None)
    StandardViewInstance = StandardView()
    FestivalViewInstance = FestivalView()
    MeetingViewInstance = MeetingView()
    client.add_view(StandardViewInstance)
    client.add_view(FestivalViewInstance)
    client.add_view(MeetingViewInstance)

@tree.command(name="upcoming", description="Display upcoming events")
async def upcoming(interaction: discord.Interaction) -> None:
    """
    Handles /upcoming command. 

    It creates a list of events from the google calendar with the following information:
        Event summary (title of event from Google Calendar)
        Date of event (both in absolute time and relative to current time)
        Link to show thread, if one exists
        Needed volunteers, if a show thread exists (Standard need requirements are one booker, two door volunteers, and one sound volunteer). Trainees are considered in their main role if signed up. (Door trainees are considered door volunteers and sound trainees are considered sound volunteers). 

    The embed created has a title of "Upcoming Events" and the body of the embed consists of fields with one field per event. 

    If the user is a bot admin as defined by the role in the config.ini file, the embed is sent to all users. Otherwise, it is sent ephemerally (to that user only).

    Arguments - 
        interaction: Discord.py interaction information

    Returns - None
    """

    # Prompt discord for the "Bot is thinking...." message

    # If user has the botAdminRole, the message should be sent to all (not ephermerally)
    # otherwise, it's still ok to run, but it should be sent to the user only. (ephermerally)

    if await isUserBotAdmin(interaction.user):
        # user is a bot admin
        await interaction.response.defer(ephemeral=False)
    else:
        # user is not a bot admin
        await interaction.response.defer(ephemeral=True)

    events = await getUpcomingEvents()

    embed = await createUpcomingShows(events)

    # Send result
    await interaction.followup.send(embed=embed)

# Threads Command
@tree.command(name="threads", description="Create new show threads")
async def threads(interaction: discord.Interaction) -> None:
    """
    Handles /threads command. 

    Command requires user to be a bot admin, as defined by the role in the config.ini file.

    If the user is a bot admin, /threads will create new show threads in the channel defined in the config.ini file. 
    
    To setup the event, each event has a unique etag as returned by Google. The etag changes every time the event is edited.

    The bot checks over the last 100 messages to see if the etag is present in any embed in the defined thread channel. If the etag is present, it ignores the event as it assumes the show already has a thread. Otherwise, it continues to create the show embed and show thread. 

    The show embeds include a title and 11 fields.
        Field 0- number of people signed up for the show. 
        Field 1- absolute start date of show
        Field 2- relative start date of show
        Field 3- Booker signups
        Field 4- Door signups
        Field 5- Sound signups
        Field 6- Door Training signups
        Field 7- Sound Training signups
        Field 8- On-Call signups
        Field 9- Vendor signups
        Field 10- etag

    Arguments:
        interaction - Discord.py interaction information

    Returns: None
    """

    # Check if user can run command

    if not await isUserBotAdmin(interaction.user):
        # User is not a bot admin
        await interaction.response.send_message(f"You must have the {botAdminRole} role to use this command.", ephemeral=True)
        return        

    # Prompt discord for the "Bot is thinking...." message
    await interaction.response.defer(ephemeral=True)

    # Get Upcoming Events
    events = await getUpcomingEvents()

    # Get previously posted embeds

    createdThreads = 0
    ignoredEvents = 0

    for event in events:
        if not event.discordThreadID == "" and await threadExists(event):
            # Event already has a thread, so skip it
            events.remove(event)
            ignoredEvents += 1
    
    for event in events:
        # Create embed for event
        embed = await createShowEmbed(event)

        # Post embed to threads channel
        channel = client.get_channel(int(threadsChannel))
        message = await channel.send(embed=embed, view=StandardView())

        # Create thread for event
        thread = await message.create_thread(name=event.summary)

        # Update event in database with discord thread ID
        event.discordThreadID = str(message.id)
        await updateEvent(event)
        createdThreads += 1


    # Send closing message
    await interaction.followup.send(f"{createdThreads} thread(s) were created successfully. {ignoredEvents} calendar events were ignored.", ephemeral=True)

# Role choices for adduser command. 
@discord.app_commands.choices(role=[
    discord.app_commands.Choice(name="Booker", value="0"),
    discord.app_commands.Choice(name="Door", value="1"),
    discord.app_commands.Choice(name="Sound", value="2"),
    discord.app_commands.Choice(name="Door Training", value="3"),
    discord.app_commands.Choice(name="Sound Training", value="4"),
    discord.app_commands.Choice(name="On Call", value="5"),
    discord.app_commands.Choice(name="Vendor", value="6"),
    discord.app_commands.Choice(name="Attending", value="7")
])

@tree.command(name="adduser", description="Add a user to a show thread")
async def adduser(interaction: discord.Interaction, user: discord.Member, thread: str, role: str) -> None:
    """
    Handles /adduser <user> <thread> <role>
    
    Command to forcefully add a user to a show thread. The command requires the user to have the bot admin role, as defined in config.ini. 

    If the user is a bot admin, the mentioned user is added the mentioned thread as the mentioned role. 

    Arguments:
        User - Discord.py user object that is sent from the slash command argument. 
        Thread - string that should be a discord message id of the show embed message.
        Role - string of the role to add the user as. This is passed in as the "value" field of the choices above- most notably, it does NOT contain the textual description of the role but only contains the numerical value. The role ids are configured to match the show roles defined at the start of this file. 

    Returns- None
    """
    # Check if user can run command
    if not await isUserBotAdmin(interaction.user):
        await interaction.response.send_message(f"You must have the {botAdminRole} role to use this command.", ephemeral=True)
        return
    
    # Tell discord we're thinking
    await interaction.response.defer(ephemeral=True)

    event = db.getEventByThreadID(db.connect(db_file), thread)
    
    # Check if event mode allows for selected role
    if event.mode != "MEETING" and int(role) == VolunteerRole.ATTENDING.value:
        await interaction.followup.send(f"This event is not a meeting, the attending role is not available.")
        return
    if event.mode == "FESTIVAL" and int(role) in [VolunteerRole.TRAINING_DOOR.value, VolunteerRole.TRAINING_SOUND.value]:
        await interaction.followup.send(f"This show is a festival, door training and sound training roles are not available.")
        return
    if event.mode == "MEETING" and int(role) != VolunteerRole.ATTENDING.value:
        await interaction.followup.send(f"This event is a meeting, the only available role is attending.")
        return
    if event.mode == "NONE":
        await interaction.followup.send(f"This event does not have any signups.")
        return
    
    # Add user to embed
    try:
        message = await client.get_channel(int(threadsChannel)).fetch_message(int(thread))
        await addUserToThread(message, user)
        await addUserToEmbed(message, VolunteerRole(int(role)), user, False)
        db.addVolunteerSignUp(db.connect(db_file), event.id, user.id, VolunteerRole(int(role)))
        await interaction.followup.send(f"Added {user.display_name} to the show thread as a {VolunteerRole(int(role)).name.lower()} volunteer.")
    except discord.NotFound:
        await interaction.followup.send(f"The specified thread ID is not valid.")

    return

# Set Show Mode Command
@discord.app_commands.choices(mode=[
    discord.app_commands.Choice(name="Standard", value="STANDARD"),
    discord.app_commands.Choice(name="Festival", value="FESTIVAL"),
    discord.app_commands.Choice(name="Meeting", value="MEETING"),
    discord.app_commands.Choice(name="No Signups", value="NONE")
])
@tree.command(name="setmode", description="Set the show mode for an event")
async def setmode(interaction: discord.Interaction, mode: str) -> None:
    
    threadId = str(interaction.channel.id)
    # Check if user can run command
    if not await isUserBotAdmin(interaction.user):
        await interaction.response.send_message(f"You must have the {botAdminRole} role to use this command.", ephemeral=True)
        return
    
    # Check if channel id is valid
    if db.getShowMode(db.connect(db_file), threadId) is None:
        await interaction.response.send_message(f"This is not a valid show thread. Please run this command from inside the show thread you want to change the mode on.", ephemeral=True)
        return


    event = db.getEventByThreadID(db.connect(db_file), threadId)
    event.mode = mode
    db.setShowMode(db.connect(db_file), threadId, mode)

    baseMessage = await client.get_channel(int(threadsChannel)).fetch_message(int(threadId))

    newEmbed = await createShowEmbed(event)
    newView = None
    if mode == "STANDARD":
        newView = StandardView()
    elif mode == "FESTIVAL":
        newView = FestivalView()
    elif mode == "MEETING":
        newView = MeetingView()
    elif mode == "NONE":
        newView = None

    baseMessage = await baseMessage.edit(embed=newEmbed, view=newView)

    # Drop any signups that don't fit the new mode
    signups = db.getVolunteerSignupsFromEvent(db.connect(db_file), event.id)
    for signup in signups:
        if mode == "NONE":
            # drop all signups
            db.removeVolunteerSignUp(db.connect(db_file), event.id, signup.userid)
            continue
        if mode == "MEETING" and not signup.role == VolunteerRole.ATTENDING:
            # drop non-attending signups
            db.removeVolunteerSignUp(db.connect(db_file), event.id, signup.userid)
            continue
        if mode == "FESTIVAL" and signup.role not in [VolunteerRole.BOOKER, VolunteerRole.DOOR, VolunteerRole.SOUND, VolunteerRole.ON_CALL, VolunteerRole.VENDOR]:
            # drop training signups
            db.removeVolunteerSignUp(db.connect(db_file), event.id, signup.userid)
            continue
        if mode == "STANDARD" and signup.role == VolunteerRole.ATTENDING:
            # drop attending signups
            db.removeVolunteerSignUp(db.connect(db_file), event.id, signup.userid)
            continue
    
    # Add existing signups to embed
    for signup in db.getVolunteerSignupsFromEvent(db.connect(db_file), event.id):
        await addUserToEmbed(baseMessage, signup.role, await client.fetch_user(signup.userid), True)

    await interaction.response.send_message(f"Set show mode to {mode.lower()}.", ephemeral=True)

@tree.command(name="setvolunteers", description="Set the needed volunteers for an event")
async def setvolunteers(interaction: discord.Interaction, bookers: int, doors: int, sound: int) -> None:
    """
    Handles /setvolunteers <bookers> <doors> <sound>

    Command sets the number of needed volunteers for each role, to be used in the needed volunteer string. 

    Arguments:
        interaction - discord.py interaction information
        bookers, doors, sound - discord command arguments to set event to. 

    Returns: None

    """
    threadId = str(interaction.channel.id)
    # Check if user can run command
    if not await isUserBotAdmin(interaction.user):
        await interaction.response.send_message(f"You must have the {botAdminRole} role to use this command.", ephemeral=True)
        return
    
    # Check if channel id is valid
    if db.getShowMode(db.connect(db_file), threadId) is None:
        await interaction.response.send_message(f"This is not a valid show thread. Please run this command from inside the show thread you want to change the needed volunteers on.", ephemeral=True)
        return

    event = db.getEventByThreadID(db.connect(db_file), threadId)
    event.neededBookers = bookers
    event.neededDoors = doors
    event.neededSound = sound
    await updateEvent(event)

    await interaction.response.send_message(f"Set needed volunteers to {bookers} booker(s), {doors} door volunteer(s), and {sound} sound volunteer(s).", ephemeral=True)

@tree.command(name="report", description="Create a report of volunteer signups")
async def report(interaction: discord.Interaction, start_date: str, end_date: str) -> None:
    """
    Handles /report <startDate> <endDate>

    Command generates a report of volunteer signups between the specified dates.

    Arguments:
        interaction - discord.py interaction information
        startDate, endDate - date range for the report

    Returns: None

    """
    # Check if user can run command
    if not await isUserBotAdmin(interaction.user):
        await interaction.response.send_message(f"You must have the {botAdminRole} role to use this command.", ephemeral=True)
        return

    # Generate report

    startDate = datetime.datetime.strptime(start_date, "%m/%d/%Y")
    endDate = datetime.datetime.strptime(end_date, "%m/%d/%Y")

    if startDate > endDate:
        await interaction.response.send_message("Start date must be before end date.", ephemeral=True)
        return
    if startDate == None or endDate == None:
        await interaction.response.send_message("Invalid date format. Please use MM/DD/YYYY.", ephemeral=True)
        return

    report = await generateVolunteerReport(startDate, endDate)

    embed = discord.Embed()
    embed.title = f"Volunteer Report: {startDate.strftime('%m/%d/%Y')} to {endDate.strftime('%m/%d/%Y')}"
    embed.description = report if report != "" else "No signups in this time period."
    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)

    await interaction.response.send_message(embed=embed, ephemeral=True)

# Start of "Main"
# Connect to Discord
client.run(botToken)
