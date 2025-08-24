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

# ROLES:
    # BOOKER : 3
    # DOOR : 4
    # SOUND : 5
    # TRAINING DOOR : 6
    # TRAINING SOUND : 7
    # ON CALL : 8
    # VENDOR : 9

async def addUserToThread(message, user):
        # add user to thread
        # get thread
        thread = message.thread
        await thread.add_user(user)

async def addUserToEmbed(message, slot, user):
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

    # No Timeout
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

# Sync Command Tree with Discord when connected
@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    await tree.sync(guild=None)
    ThreadViewInstance = ThreadView()
    client.add_view(ThreadViewInstance)

# Upcoming Command
@tree.command(name="upcoming", description="Display upcoming events")
async def upcoming(interaction: discord.Interaction):

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

# Add User Command
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


client.run(botToken)
