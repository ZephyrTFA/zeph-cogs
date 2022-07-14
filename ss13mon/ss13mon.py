import asyncio
from datetime import datetime
import discord
from redbot.core import commands, Config, checks
from threading import Timer
import socket
import struct
import urllib.parse
import html.parser as htmlparser

class SS13Mon(commands.Cog):
	_tick_timers: dict
	config: Config

	def __init__(self, bot: commands.Bot) -> None:
		self.bot = bot
		self.config = Config.get_conf(self, identifier=854168416161, force_registration=True)

		def_guild = {
			"update_interval": 10,
			"channel": None,
			"address": None,
			"port": None,
			"topic_key": None,
			"message_id": None
		}
		def_global = {
			"active_guilds": []
		}
		self.config.register_guild(**def_guild)
		self.config.register_global(**def_global)
	
	def cog_unload(self) -> None:
		asyncio.run(self.stop_guilds())
	
	async def resume_guilds(self) -> None:
		guilds = await self.config.active_guilds()
		for guild in guilds:
			guild = self.bot.get_guild(int(guild))
			if(guild == None): raise IOError()
			await self.start_guild(guild)
	
	async def stop_guilds(self) -> None:
		guilds = await self.config.active_guilds()
		for guild in guilds:
			guild = self.bot.get_guild(int(guild))
			if(guild == None): raise IOError()
			await self.stop_guild(guild)

	async def start_guild(self, guild: discord.Guild) -> None:
		g_timer: Timer = self._tick_timers.get(str(guild.id), None)
		if(g_timer != None): await self.stop_guild(guild)

		interval = await self.config.guild(guild).update_interval()
		if(isinstance(interval, float) == False): raise ArithmeticError()

		g_timer = Timer(interval, self.__tick__, [guild])
		self._tick_timers[str(guild.id)] = g_timer
		g_timer.start()

		g_guilds: list[discord.Guild] = await self.config.active_guilds()
		g_guilds.append(str(guild.id))
	
	async def stop_guild(self, guild: discord.Guild) -> None:
		g_timer: Timer = self._tick_timers.get(str(guild.id), None)
		if(g_timer != None):
			g_timer.cancel()
			self._tick_timers.pop(str(guild.id), None)
		g_guilds: list[discord.Guild] = await self.config.active_guilds()
		g_guilds.pop(g_guilds.index(str(guild.id)))
	
	@commands.command()
	@checks.is_owner()
	async def test_update(self, ctx: commands.Context):
		status = await self.query_server("localhost", 41372)
		for key in ["round_id", "players", "admins", "time_dilation_avg"]:
			val = status[key]
			await ctx.send("{} = {}".format(key, val))
		
		roundid = int(status["round_id"])
		player_count = int(status["players"])
		time_dilation_avg = float(status["time_dilation_avg"])
		players: list[str] = await self.query_server("localhost", 41372, "?whoIs")["players"]

		dat: list[str] = list()
		dat.append("Round ID: {}".format(roundid))
		dat.append("Players:  {}".format(player_count))
		dat.append("TIDI:     {}%".format(time_dilation_avg))
		dat.append("Players:\n```")
		dat.append(", ".join(players))
		dat.append("```")

		embed_builder: discord.Embed = discord.Embed(type="rich", title=status["version"], timestamp=datetime.now(), desc="\n".join(dat))
		await ctx.channel.send(embed=embed_builder)

	async def update_guild(self, guild: discord.Guild):
		cfg = self.config.guild(guild)
		channel: discord.TextChannel = guild.get_channel(await cfg.channel())
		address = await cfg.address()
		port = await cfg.port()
		message = await cfg.message_id()

		if(channel == None or address == None or port == None):
			raise Exception("Missing critical information for updating guild information")
		
		status = await self.query_server(address, port)
		for key in status:
			val = status[key]
			await channel.send("{} = {}".format(key, val))
	
	async def query_server(self, game_server:str, game_port:int, querystr="?status" ) -> dict:
		"""
		Queries the server for information
		"""
		conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 

		try:
			query = b"\x00\x83" + struct.pack('>H', len(querystr) + 6) + b"\x00\x00\x00\x00\x00" + querystr.encode() + b"\x00" #Creates a packet for byond according to TG's standard
			conn.settimeout(20) #Byond is slow, timeout set relatively high to account for any latency
			conn.connect((game_server, game_port)) 

			conn.sendall(query)

			data = conn.recv(4096) #Minimum number should be 4096, anything less will lose data

			parsed_data = urllib.parse.parse_qs(data[5:-1].decode())

			return parsed_data
			
		except (ConnectionRefusedError, socket.gaierror, socket.timeout):
			return None #Server is likely offline

		finally:
			conn.close()
	
	def __tick__(self, guild: discord.Guild) -> None:
		return
