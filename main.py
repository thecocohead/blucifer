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

async def addUserToThread(button):
        # add user to thread
        # get base message
        message = button.message
        # get thread
        thread = message.thread
        await thread.add_user(button.user)

async def addUserToEmbed(button, slot):
    # get base message & embed
    message = button.message
    embed = message.embeds[0]
    # temporarily store embed into dictionary 
    embedDict = embed.to_dict()
    
    # check if user exists in embed, and if they do remove them from the old role
    if not await getUserCurrentRole(button) == -1:
        await removeUserFromEmbed(button)

    #recalculate and change count of users 
    currentCount = int(re.search(r'\d+', embed.fields[0].value).group())
    currentCount += 1
    # change fields
    embedDict['fields'][0]['value'] = f":busts_in_silhouette: {currentCount}"
    embedDict['fields'][slot]['value'] = embedDict['fields'][slot]['value'] + f"\n<@{button.user.id}>"
    # send new embed for edit
    newEmbed = discord.Embed.from_dict(embedDict)
    await message.edit(embed=newEmbed)
    
async def getUserCurrentRole(button):
    userID = button.user.id
    message = button.message
    embed = message.embeds[0]
    fields = embed.fields
    currentField = 0
    for field in fields:
        if str(userID) in field.value:
            # User is listed in current field
            return currentField
        else:
            currentField += 1
    # User not found
    return -1

async def removeUserFromEmbed(button):
    userID = button.user.id
    message = button.message
    embed = message.embeds[0]
    fields = embed.fields
    embedDict = embed.to_dict()
    
    targetField = await getUserCurrentRole(button)

    if not targetField == -1:
        # decrement signups
        currentCount = int(re.search(r'\d+', embed.fields[0].value).group())
        currentCount -= 1
        # change fields
        embedDict['fields'][0]['value'] = f":busts_in_silhouette: {currentCount}"
        
        # evil regex fuckery to remove user from role
        newValue = re.sub(f"<@102080114975588352>(\\n)?", "", embedDict['fields'][targetField]['value'])
        embedDict['fields'][targetField]['value'] = newValue

        # send new embed for edit
        newEmbed = discord.Embed.from_dict(embedDict)
        await message.edit(embed=newEmbed)

class ThreadView(discord.ui.View):
    @discord.ui.button(label="Booker", emoji="<:7th_Mammoth:858151066679640074>", row=0, style=discord.ButtonStyle.primary)
    async def bookerButtonCallback(self, button, interaction):
        print(button.message)
        await addUserToThread(button)
        await addUserToEmbed(button, 3)
        await button.response.send_message("Added you to the show thread!", ephemeral=True)

    @discord.ui.button(label="Door", emoji="<:7CDoor:857389356893339648>", row=0, style=discord.ButtonStyle.primary)
    async def doorButtonCallback(self, button, interaction):
        await addUserToThread(button)
        await addUserToEmbed(button, 4)
        await button.response.send_message("Added you to the show thread!", ephemeral=True)

    @discord.ui.button(label="Sound", emoji="<:7CSound:857389356837765140>", row=0, style=discord.ButtonStyle.primary)
    async def soundButtonCallback(self, button, interaction):
        await addUserToThread(button)
        await addUserToEmbed(button, 5)
        await button.response.send_message("Added you to the show thread!", ephemeral=True)

    @discord.ui.button(label="Door Training", emoji="📖", row=1, style=discord.ButtonStyle.primary)
    async def doorTrainingButtonCallback(self, button, interaction):
        await addUserToThread(button)
        await addUserToEmbed(button, 6)
        await button.response.send_message("Added you to the show thread!", ephemeral=True)

    @discord.ui.button(label="Sound Training", emoji="📖", row=1, style=discord.ButtonStyle.primary)
    async def soundTrainingButtonCallback(self, button, interaction):
        await addUserToThread(button)
        await addUserToEmbed(button, 7)
        await button.response.send_message("Added you to the show thread!", ephemeral=True)

    @discord.ui.button(label="On Call", emoji="☎️", row=1, style=discord.ButtonStyle.primary)
    async def onCallButtonCallback(self, button, interaction):
        await addUserToThread(button)
        await addUserToEmbed(button, 8)
        await button.response.send_message("Added you to the show thread!", ephemeral=True)
        
    @discord.ui.button(label="Vendor", emoji="🤝", row=1, style=discord.ButtonStyle.primary)
    async def vendorButtonCallback(self, button, interaction):
        await addUserToThread(button)
        await addUserToEmbed(button, 9)
        await button.response.send_message("Added you to the show thread!", ephemeral=True)
        
    @discord.ui.button(label="Remove", row=2, style=discord.ButtonStyle.danger)
    async def removeButtonCallback(self, button, interaction):
        # check if user is in thread
        if await getUserCurrentRole(button) == -1:
            # user not in thread
            await button.response.send_message("You aren't in the thread.", ephemeral=True)
        else:
            # remove user from embed
            await removeUserFromEmbed(button)
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
                            "url": message.jump_url
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
            embed.add_field(name=event['summary'],
                            value=f"**Date**: <t:{startTimeUNIXSeconds}:F> // <t:{startTimeUNIXSeconds}:R>\n**Thread**: {foundThreadDict['url']}", 
                            inline = False)
        else:
            embed.add_field(name=event['summary'],
                            value=f"**Date**: <t:{startTimeUNIXSeconds}:F> // <t:{startTimeUNIXSeconds}:R>", 
                            inline = False)

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

client.run(botToken)
