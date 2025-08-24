# Imports
import configparser
import discord
import gcal
import datetime
import re

# Configuration Parsing
config = configparser.ConfigParser()
config.read('config.ini')

botToken = config['DISCORD']['token']
threadsChannel = config['DISCORD']['threadsChannel']
calendar_id = config['CALENDAR']['id']
botAdminRole = config['DISCORD']['botAdminRole']

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

Show roles are given from the embed field number for the show. They are used for numberical identification throughout the bot.

BOOKER : 3
DOOR : 4
SOUND : 5
TRAINING DOOR : 6
TRAINING SOUND : 7
ON CALL : 8
VENDOR : 9
"""


async def addUserToThread(message, user):
        """
        Adds the user to a show thread.

        Arguments: 
            Message - Discord.py message to add user to. This is the base of the thread- typically it's a show embed. 
            User - Discord.py user that's being added to a thread 

        Returns: None
        """
        thread = message.thread
        await thread.add_user(user)

async def addUserToEmbed(message, slot, user):
    """
    Adds the user to the show embed. This function edits the embed to add the user onto it. 

    Arguments:
        Message - Discord.py message to add the user to. For this function, we assume it's a show thread message.
        Slot - Show role to add user to.
        User - Discord.py user to add. 

    Returns: None
    """
    # get embed
    embed = message.embeds[0]
    # temporarily store embed into dictionary 
    embedDict = embed.to_dict()
    
    # check if user exists in embed, and if they do remove them from the old role
    if not await getUserCurrentRole(user, message) == -1:
        await removeUserFromEmbed(user, message)

    #recalculate and change count of users 
    currentCount = int(re.search(r'\d+', embed.fields[0].value).group())
    currentCount += 1
    # change fields
    embedDict['fields'][0]['value'] = f":busts_in_silhouette: {currentCount}"
    embedDict['fields'][slot]['value'] = embedDict['fields'][slot]['value'] + f"\n<@{user.id}>"
    # send new embed for edit
    newEmbed = discord.Embed.from_dict(embedDict)
    await message.edit(embed=newEmbed)
    
async def getUserCurrentRole(user, message):
    """
    Gets the user's current role in a show embed if they are currently signed up. 

    Arguments:
        User - Discord.py user to search for. 
        Message - Discord.py message to search. The message should be a show embed.  

    Returns: int - show role id or -1 if user is not currently signed up.  
    """
    embed = message.embeds[0]
    fields = embed.fields
    currentField = 0
    for field in fields:
        if str(user.id) in field.value:
            # User is listed in current field
            return currentField
        else:
            currentField += 1
    # User not found
    return -1

async def removeUserFromEmbed(user, message):
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
    
    targetField = await getUserCurrentRole(user, message)

    if not targetField == -1:
        # decrement signups
        currentCount = int(re.search(r'\d+', embed.fields[0].value).group())
        currentCount -= 1
        # change fields
        embedDict['fields'][0]['value'] = f":busts_in_silhouette: {currentCount}"
        
        # evil regex fuckery to remove user from role
        newValue = re.sub(f"<@{user.id}>(\\n)?", "", embedDict['fields'][targetField]['value'])
        embedDict['fields'][targetField]['value'] = newValue

        # send new embed for edit
        newEmbed = discord.Embed.from_dict(embedDict)
        await message.edit(embed=newEmbed)

class ThreadView(discord.ui.View):
    """
    View to create show signup buttons for show embeds. Also handles users that press each button on a show thread to add them to a show embed & thread. 
    """

    # Needed function for buttons to persist past bot reboot
    def __init__(self):
        super().__init__(timeout=None)

    async def userSignUp(button, slot):
        message = button.message
        await addUserToThread(message, button.user)
        await addUserToEmbed(message, slot, button.user)
        await button.response.send_message("Added you to the show thread!", ephemeral=True)

    @discord.ui.button(label="Booker", emoji="<:7th_Mammoth:858151066679640074>", row=0, style=discord.ButtonStyle.primary, custom_id="bookerButton")
    async def bookerButtonCallback(self, button, interaction):
        await ThreadView.userSignUp(button, 3)

    @discord.ui.button(label="Door", emoji="<:7CDoor:857389356893339648>", row=0, style=discord.ButtonStyle.primary, custom_id="doorButton")
    async def doorButtonCallback(self, button, interaction):
        await ThreadView.userSignUp(button, 4)

    @discord.ui.button(label="Sound", emoji="<:7CSound:857389356837765140>", row=0, style=discord.ButtonStyle.primary, custom_id="soundButton")
    async def soundButtonCallback(self, button, interaction):
        await ThreadView.userSignUp(button, 5)

    @discord.ui.button(label="Door Training", emoji="📖", row=1, style=discord.ButtonStyle.primary, custom_id="doorTrainingButton")
    async def doorTrainingButtonCallback(self, button, interaction):
        await ThreadView.userSignUp(button, 6)

    @discord.ui.button(label="Sound Training", emoji="📖", row=1, style=discord.ButtonStyle.primary, custom_id="soundTrainingButton")
    async def soundTrainingButtonCallback(self, button, interaction):
        await ThreadView.userSignUp(button, 7)

    @discord.ui.button(label="On Call", emoji="☎️", row=1, style=discord.ButtonStyle.primary, custom_id="onCallButton")
    async def onCallButtonCallback(self, button, interaction):
        await ThreadView.userSignUp(button, 8)
        
    @discord.ui.button(label="Vendor", emoji="🤝", row=1, style=discord.ButtonStyle.primary, custom_id="vendorButton")
    async def vendorButtonCallback(self, button, interaction):
        await ThreadView.userSignUp(button, 9)
        
    @discord.ui.button(label="Remove", row=2, style=discord.ButtonStyle.danger, custom_id="RemoveButton")
    async def removeButtonCallback(self, button, interaction):
        message = button.message
        # check if user is in thread
        if await getUserCurrentRole(button.user, button.message) == -1:
            # user not in thread
            await button.response.send_message("You aren't in the thread.", ephemeral=True)
        else:
            # remove user from embed
            await removeUserFromEmbed(button.user, button.message)
            # remove user from thread
            # get base message
            message = button.message
            # get thread
            thread = message.thread
            await thread.remove_user(button.user)
            await button.response.send_message("Removed you from the show thread.", ephemeral=True)

@client.event
async def on_ready():
    """
    Ran when the bot connects to Discord. Prints to console that it connected successfully, syncs the command tree (all the slash commands used to interact with the bot), and adds the buttons above so they can be used past reboot. 

    Arguments- None
    Returns- None
    """
    print(f'Logged in as {client.user}')
    await tree.sync(guild=None)
    ThreadViewInstance = ThreadView()
    client.add_view(ThreadViewInstance)

@tree.command(name="upcoming", description="Display upcoming events")
async def upcoming(interaction: discord.Interaction):
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
    userRoles = [role.name for role in interaction.user.roles]
    if botAdminRole not in userRoles:
        # User is not a bot admin
        await interaction.response.defer(ephemeral=True)
    else:
        # User is a bot admin
        await interaction.response.defer(ephemeral=False)
    
    events = gcal.upcomingEvents(calendar_id)

    # Create embed
    embed = discord.Embed(title="Upcoming Events")
    
    # Search for threads
    channel = client.get_channel(int(threadsChannel))

    threads = []
    async for message in channel.history(limit=100):
        if message.embeds:
            for searchEmbed in message.embeds:
                for field in searchEmbed.fields:
                    if "Calendar ID:" in field.value:
                        eventETAG = field.value[13:]
                        foundThread = {
                            "etag": eventETAG,
                            "summary": searchEmbed.title,
                            "url": message.jump_url, 
                            "fields": message.embeds[0].fields,
                        }
                        threads.append(foundThread)

    for event in events:

        foundThreadDict = None
        for d in threads:
            if event['etag'] == d['etag']:
                # thread found
                foundThreadDict = d
        
        # Create listing of upcoming shows
        startTime = datetime.datetime.fromisoformat(event['start']['dateTime'])
        startTimeUNIXSeconds = int(startTime.timestamp())
        if foundThreadDict:
            # Get volunteer counts
            bookerCount = 0
            doorCount = 0
            soundCount = 0
            bookerCount += foundThreadDict['fields'][3].value.count('@') # Add number of bookers
            doorCount += foundThreadDict['fields'][4].value.count('@') # Add number of door volunteers
            soundCount += foundThreadDict['fields'][5].value.count('@') # Add number of sound volunteers
            doorCount += foundThreadDict['fields'][6].value.count('@') # Add number of door trainees
            soundCount += foundThreadDict['fields'][7].value.count('@') # Add number of sound trainees

            # Create string of emojis representing needed volunteers
            neededVolunteerString = ""
            if bookerCount == 0:
                neededVolunteerString += "<:7th_Mammoth:858151066679640074> "
            if doorCount == 0:
                neededVolunteerString += "<:7CDoor:857389356893339648> <:7CDoor:857389356893339648> "
            if doorCount == 1:
                neededVolunteerString += "<:7CDoor:857389356893339648> "
            if soundCount == 0:
                neededVolunteerString += "<:7CSound:857389356837765140> "

            # Put field together
            embed.add_field(name=event['summary'],
                            value=f"**Date**: <t:{startTimeUNIXSeconds}:F> // <t:{startTimeUNIXSeconds}:R>\n**Thread**: {foundThreadDict['url']}\n**Needed Volunteers**: {neededVolunteerString if neededVolunteerString else 'None!'}", 
                            inline = False)
        else:
            embed.add_field(name=event['summary'],
                            value=f"**Date**: <t:{startTimeUNIXSeconds}:F> // <t:{startTimeUNIXSeconds}:R>", 
                            inline = False)
            
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)

    # Send result
    await interaction.followup.send(embed=embed)

# Threads Command
@tree.command(name="threads", description="Create new show threads")
async def threads(interaction: discord.Interaction):
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
    userRoles = [role.name for role in interaction.user.roles]
    if botAdminRole not in userRoles:
        await interaction.response.send_message(f"You must have the {botAdminRole} role to use this command.", ephemeral=True)
        return

    # Prompt discord for the "Bot is thinking...." message
    await interaction.response.defer(ephemeral=True)

    # Get Upcoming Events
    events = gcal.upcomingEvents(calendar_id)
    
    # Get previously posted embeds
    invalidETAGs = []

    channel = client.get_channel(int(threadsChannel))
    async for message in channel.history(limit=100):
        if message.embeds:
            for embed in message.embeds:
                for field in embed.fields:
                    if "Calendar ID:" in field.value:
                        eventETAG = field.value[13:]
                        invalidETAGs.append(eventETAG)

    # Count of threads created
    createdThreads = 0
    ignoredEvents = 0

    for event in events:
        # Check if thread has already been posted
        if not event['etag'] in invalidETAGs: 
            # If thread has not been posted, create a new thread. 
            startTime = datetime.datetime.fromisoformat(event['start']['dateTime'])
            startTimeUNIXSeconds = int(startTime.timestamp())

            embed = discord.Embed(title=f"{event['summary']}",
                        description="")
            
            # Fields!
            embed.add_field(name="", 
                            value=":busts_in_silhouette: 0",
                            inline=False)
            embed.add_field(name="", 
                            value=f":calendar: <t:{startTimeUNIXSeconds}:F>",
                            inline=False)
            embed.add_field(name="", 
                            value=f":hourglass: <t:{startTimeUNIXSeconds}:R>",
                            inline=False)
            embed.add_field(name="<:7th_Mammoth:858151066679640074> Booker",
                            value="",
                            inline=True)
            embed.add_field(name="<:7CDoor:857389356893339648> Door",
                            value="",
                            inline=True)
            embed.add_field(name="<:7CSound:857389356837765140> Sound",
                            value="",
                            inline=True)
            embed.add_field(name="📖 Training: Door",
                            value="",
                            inline=True)
            embed.add_field(name="📖 Training: Sound",
                            value="",
                            inline=True)
            embed.add_field(name="☎️ On-Call",
                            value="",
                            inline=True)
            embed.add_field(name="Vendors",
                            value="",
                            inline=True)
            embed.add_field(name="",
                            value=f"Calendar ID: {event['etag']}",
                            inline=False)
            
            currentThreadView = ThreadView()

            # Send embed
            newThread = await channel.send(embed=embed, view=currentThreadView)
            # Create Thread
            await newThread.create_thread(name=event['summary'])
            createdThreads += 1
        else:
            ignoredEvents += 1
    
    # Send closing message
    await interaction.followup.send(f"{createdThreads} thread(s) were created successfully. {ignoredEvents} calendar events were ignored.", ephemeral=True)

# Role choices for adduser command. 
@discord.app_commands.choices(role=[
    discord.app_commands.Choice(name="Booker", value="3"),
    discord.app_commands.Choice(name="Door", value="4"),
    discord.app_commands.Choice(name="Sound", value="5"),
    discord.app_commands.Choice(name="Door Training", value="6"),
    discord.app_commands.Choice(name="Sound Training", value="7"),
    discord.app_commands.Choice(name="On Call", value="8"),
    discord.app_commands.Choice(name="Vendor", value="9"),
])


@tree.command(name="adduser", description="Add a user to a show thread")
async def adduser(interaction: discord.Interaction, user: discord.Member, thread: str, role: str):
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
    userRoles = [role.name for role in interaction.user.roles]
    if botAdminRole not in userRoles:
        await interaction.response.send_message(f"You must have the {botAdminRole} role to use this command.", ephemeral=True)
        return
    
    # Tell discord we're thinking
    await interaction.response.defer(ephemeral=True)

    # Thread can only be in the specified threads channel. 
    channel = client.get_channel(int(threadsChannel))

    # Find thread
    try:
        message = await channel.fetch_message(int(thread))
    except:
        # thread is not found
        await interaction.followup.send(f"Thread not found.")
        return

    # thread is found

    # check if user is already in thread
    if await getUserCurrentRole(user, message) == int(role):
        # user is already in thread as selected role
        await interaction.followup.send(f"<@{user.id}> is already in the thread as selected role.")
        return
    elif await getUserCurrentRole(user, message) != -1:
        # user is in thread, but in a different role
        await removeUserFromEmbed(user, message)
    
    await addUserToThread(message, user)
    await addUserToEmbed(message, int(role), user)
    await interaction.followup.send(f"Added <@{user.id}> to the thread.")
    return

# Start of "Main"
# Connect to Discord
client.run(botToken)
