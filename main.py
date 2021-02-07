import discord
from discord.ext import commands, tasks
import asyncio
import asyncpg
import os
from discord.utils import get
from dotenv import load_dotenv

load_dotenv()


class Tokens:
    TOKEN: str = os.getenv('DISCORD_BOT_TOKEN')
    GUILD: str = os.getenv('DISCORD_GUILD')
    DB_USER: str = os.getenv('DB_USER')
    DB_PW: str = os.getenv('DB_PW')
    DB_NAME: str = os.getenv('DB_NAME')
    DB_HOST: str = os.getenv('DB_HOST')
    DB_PORT: str = os.getenv('DB_PORT')


intents = discord.Intents.default()
intents.members = True


async def run():
    description = "COOLER BOT"

    # NOTE: 127.0.0.1 is the loopback address. If your db is running on the same machine as the code, this address will work
    credentials = {"user": Tokens.DB_USER, "password": Tokens.DB_PW, "database": Tokens.DB_NAME, "host": Tokens.DB_HOST, "port": Tokens.DB_PORT}
    db = await asyncpg.create_pool(**credentials)

    # Example create table code, you'll probably change it to suit you

    bot = Bot(description=description, db=db, intents=intents)
    try:
        await bot.start(Tokens.TOKEN)
    except KeyboardInterrupt:
        await db.close()
        await bot.logout()


class Bot(commands.Bot):
    def __init__(self, **kwargs):
        super().__init__(
            description=kwargs.pop("description"),
            command_prefix="!",
            intents=intents,
            help_command=None
        )

        self.db = kwargs.pop("db")
        self.index = 0

    async def on_ready(self):
        # .format() is for the lazy people who aren't on 3.6+
        print("Username: {0}\nID: {0.id}".format(self.user))

        self.roleassign.start()
        self.reactiondelete.start()
        self.sendmessage.start()

    @tasks.loop(seconds=2)
    async def roleassign(self):
        assignees = await self.db.fetch("SELECT * FROM role_assign")

        for assign in assignees:
            if assign['to_delete'] == False:
                user_id = assign['discord_id']
                role_name = assign['role']
                umember = get(self.get_all_members(), id=user_id)
                await umember.add_roles(get(umember.guild.roles, name=role_name))
                role = get(umember.guild.roles, name=role_name)
                if role in umember.guild.roles:
                    await self.db.execute("DELETE FROM role_assign WHERE discord_id = $1 AND role = $2", user_id, role_name)
            elif assign['to_delete'] == True:
                user_id = assign['discord_id']
                role_name = assign['role']
                umember = get(self.get_all_members(), id=user_id)
                await umember.remove_roles(get(umember.guild.roles, name=role_name))
                role = get(umember.guild.roles, name=role_name)
                await self.db.execute("DELETE FROM role_assign WHERE discord_id = $1 AND role = $2", user_id, role_name)

    @tasks.loop(seconds=0.5)
    async def reactiondelete(self):
        reactions = await self.db.fetch("SELECT * FROM reaction_to_delete")
        for reaction in reactions:
            channel = self.get_channel(reaction['channel_id'])
            message = await channel.fetch_message(reaction['message_id'])
            member = self.get_user(reaction['discord_id'])
            if reaction['emoji_id']:
                emoji = self.get_emoji(reaction['emoji_id'])
            else:
                emoji = reaction['emoji_name']
            await message.remove_reaction(emoji, member)
            await self.db.execute("DELETE FROM reaction_to_delete WHERE (emoji_id = $1 OR emoji_name = $2) AND discord_id = $3 AND "
                                  "message_id = $4", reaction['emoji_id'], reaction['emoji_name'], reaction['discord_id'],
                                  reaction['message_id'])

    @tasks.loop(seconds=0.5)
    async def sendmessage(self):
        messages = await self.db.fetch("SELECT * FROM message_to_send")
        for message in messages:
            user = self.get_user(message['discord_id'])
            if message['message_type_id'] == 0:
                await user.send(f'Herzlichen Glückwunsch dein Account `{message["summonerName"]}` '
                                f'wurde erfolgreich verifziert.\n'
                                f'Du kannst dich ab sofort für Clash anmelden.\n'
                                f'Mehr dazu in #rollen')
                await self.db.execute("DELETE FROM message_to_send WHERE unique_id = $1", int(message['unique_id']))
            elif message['message_type_id'] == 1:
                await user.send(f'Beim überprüfen gab es einen Fehler bitte versuche es bitte mit dem gleichen Befehl nochmals. '
                                f'Sollte der Fehler bestehen bleiben melde dich bitte bei @geozukunft')
                await self.db.execute("DELETE FROM message_to_send WHERE unique_id = $1", int(message['unique_id']))
            else:
                print("dunno what happend")


loop = asyncio.get_event_loop()
loop.run_until_complete(run())
