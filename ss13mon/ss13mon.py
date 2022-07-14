import asyncio
from datetime import datetime
from time import time
import discord
from redbot.core import commands, Config, checks
from threading import Timer
import socket
import struct
import urllib.parse

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
			"message_id": None,
			# internal status values
			"last_roundid": None,
			"last_title": None,
			"last_online": None,
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
	async def test_update(self, ctx: commands.Context, p=41372):
		cfg = self.config.guild(ctx.guild)
		status = await self.query_server("localhost", p)
		if(status == None):
			last_roundid = (await cfg.last_roundid()) or "Unknown"
			last_title = (await cfg.last_title()) or "Failed to fetch data"
			last_online = await cfg.last_online() or "Unknown"
			if(isinstance(last_online, float)): last_online = datetime.fromtimestamp(last_online)
			await ctx.channel.send(embed=discord.Embed(type="rich", color=discord.Colour.red(), title=last_title, timestamp=datetime.now()).add_field(name="Server Offline", value="Last Round: `{}`\nLast Seen: `{}`".format(last_roundid, last_online)))
			return

		roundid = int(status["round_id"][0])
		servtitle = status["version"][0]
		await self.config.guild(ctx.guild).last_roundid.set(roundid)
		player_count = int(status["players"][0])
		time_dilation_avg = float(status["time_dilation_avg"][0])
		players: list[str] = (await self.query_server("localhost", 41372, "?whoIs"))["players"]

		await cfg.last_roundid.set(roundid)
		await cfg.last_title.set(servtitle)
		await cfg.last_online.set(time())

		embbie: discord.Embed = discord.Embed(type="rich", color=discord.Colour.blue(), title=servtitle, timestamp=datetime.now())

		value_inf = "Round ID: `{}`\nPlayers: `{}`\nTIDI: `{}%`".format(roundid, player_count, time_dilation_avg)
		embbie.add_field(name="Server Information", value=value_inf)

		field_visi = "Visible Players ({})".format(len(players))
		value_visi = "```{}```".format(", ".join(players))
		embbie.add_field(name=field_visi, value=value_visi)

		await ctx.channel.send(embed=embbie)

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
