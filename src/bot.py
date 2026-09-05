import discord
from discord.ext import commands
import sys
import os

from src.database.sqlite_db import Database

class ConfigBot(commands.Bot):
    def __init__(self, config):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True
        
        super().__init__(
            command_prefix=config.command_prefix,
            intents=intents,
            help_command=None
        )
        self.config = config
        self.db = Database(config.db_path)

    async def setup_hook(self):
        print(f"[{self.config.name}] Configurando cogs...")
        try:
            from src.cogs.commands import setup as setup_commands
            from src.cogs.tasks import setup as setup_tasks
            
            commands_cog = await setup_commands(self)
            await setup_tasks(self, commands_cog)
            
            print(f"[{self.config.name}] Cogs configurados com sucesso.")
            
            try:
                synced = await self.tree.sync()
                print(f"[{self.config.name}] Sincronizados {len(synced)} comandos.")
            except Exception as e:
                print(f"[{self.config.name}] Erro ao sincronizar comandos: {e}")
                
        except Exception as e:
            print(f"[{self.config.name}] Erro ao carregar cogs: {e}")

    async def on_ready(self):
        print("="*40)
        print(f"[{self.config.name}] Bot Iniciado!")
        print(f"[{self.config.name}] Nome: {self.user.name}")
        print(f"[{self.config.name}] ID: {self.user.id}")
        print("="*40)
        
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"Lançamentos em {self.config.name}"
            )
        )
