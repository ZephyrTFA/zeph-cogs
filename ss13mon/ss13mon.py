import asyncio
from datetime import datetime
from threading import Timer
from time import time
import discord
from redbot.core import commands, Config, checks, utils
import socket
import struct
import urllib.parse

class SS13Mon(commands.Cog):
	_tick_timers: dict = dict()
	config: Config

	def cog_unload(self):
		for key in self._tick_timers:
			timer: Timer = self._tick_timers[key]
			timer.cancel()
		return super().cog_unload()

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
		self.config.register_guild(**def_guild)
	
	@commands.command()
	async def ss13status(self, ctx: commands.Context, p=41372):
		await ctx.channel.send(embed=(await self.generate_embed(ctx.guild)))
	
	@commands.group()
	@checks.admin()
	async def ss13mon(self, ctx: commands.Context):
		pass

	@ss13mon.command()
	async def current(self, ctx: commands.Context):
		cfg = self.config.guild(ctx.guild)
		address = await cfg.address()
		port =  await cfg.port()
		channel =  await cfg.channel()
		update_interval =  await cfg.update_interval()
		await ctx.send("Current Config: ```\naddress: {}\nport: {}\nchannel: {}\nupdate_interval: {}\n```".format(address, port, channel, update_interval))
	
	@ss13mon.command()
	async def address(self, ctx: commands.Context, value = None):
		cfg = self.config.guild(ctx.guild)
		await cfg.address.set(value)
		await ctx.send("Updated the config entry for address.")

	@ss13mon.command()
	async def port(self, ctx: commands.Context, value = None):
		cfg = self.config.guild(ctx.guild)
		await cfg.port.set(value)
		await ctx.send("Updated the config entry for port.")
	
	@ss13mon.command()
	async def channel(self, ctx: commands.Context, value = None):
		await self.delete_message(ctx.guild)
		cfg = self.config.guild(ctx.guild)
		if(not value == None): value = int(value)
		await cfg.channel.set(value)
		await ctx.send("Update the config entry for address and deleted the old message if found.")

	@ss13mon.command()
	async def update(self, ctx: commands.Context):
		await self.update_guild_message(ctx.guild)
		await ctx.send("Forced a guild update.")
	
	@ss13mon.command()
	async def update_interval(self, ctx: commands.Context, value = None):
		cfg = self.config.guild(ctx.guild)
		await cfg.update_interval.set(value)
		await ctx.send("Changed the update interval, consider forcing an update to reset the active Timer")

	async def generate_embed(self, guild: discord.Guild):
		cfg = self.config.guild(guild)
		address = await cfg.address()
		port = await cfg.port()

		if(address == None or port == None):
			return discord.Embed(type="rich", title="FAILED TO GENERATE EMBED", timestamp=datetime.now(), description="ADDRESS OR PORT NOT SET")

		status = await self.query_server(address, port)
		if(status == None):
			last_roundid = (await cfg.last_roundid()) or "Unknown"
			last_title = (await cfg.last_title()) or "Failed to fetch data"
			last_online = await cfg.last_online() or "Unknown"
			if(isinstance(last_online, float)): last_online = datetime.fromtimestamp(last_online)
			return discord.Embed(type="rich", color=discord.Colour.red(), title=last_title, timestamp=datetime.now()).add_field(name="Server Offline", value="Last Round: `{}`\nLast Seen: `{}`".format(last_roundid, last_online))

		roundid = int(status["round_id"][0])
		servtitle = status["version"][0]
		await self.config.guild(guild).last_roundid.set(roundid)
		player_count = int(status["players"][0])
		time_dilation_avg = float(status["time_dilation_avg"][0])
		players: list[str] = (await self.query_server("localhost", 41372, "?whoIs"))["players"]
		players.sort()

		await cfg.last_roundid.set(roundid)
		await cfg.last_title.set(servtitle)
		await cfg.last_online.set(time())

		update_interval = await cfg.update_interval()
		if(update_interval == None):
			update_interval = 0
		embbie: discord.Embed = discord.Embed(type="rich", color=discord.Colour.blue(), title=servtitle, timestamp=datetime.now())

		value_inf = "Round ID: `{}`\nPlayers: `{}`\nTIDI: `{}%`\nNext Update: `{}`".format(roundid, player_count, time_dilation_avg, ("{}s".format(update_interval), "Disabled")[update_interval == 0])
		embbie.add_field(name="Server Information", value=value_inf)

		field_visi = "Visible Players ({})".format(len(players))
		value_visi = "```{}```".format(", ".join(players))
		embbie.add_field(name=field_visi, value=value_visi)

		return embbie
	
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

	async def update_guild_message(self, guild: discord.Guild):
		existing_timer: Timer = self._tick_timers.pop(guild.id, None)
		if(not existing_timer == None): existing_timer.cancel()

		cfg = self.config.guild(guild)
		channel = await cfg.channel()
		if(channel == None):
			return
		channel: discord.TextChannel = guild.get_channel(channel)
		if(isinstance(channel, discord.TextChannel) == False):
			return
		
		message = await cfg.message_id()
		cached: discord.Message
		if(message == None):
			cached = await channel.send("caching initial context")
			await cfg.message_id.set(cached.id)
		else:
			try:
				cached = await channel.fetch_message(message)
			except(discord.NotFound):
				cached = await channel.send("caching initial context")
				await cfg.message_id.set(cached.id)
		
		await cached.edit(content=None, embed=(await self.generate_embed(guild)))
		update_interval = await cfg.update_interval()
		if(update_interval == None or update_interval == 0):
			return

		new_timer: Timer = Timer(update_interval, self._timer_wrapper, [guild])
		self._tick_timers[guild.id] = new_timer
	
	def _timer_wrapper(self, guild):
		utils.bounded_gather(self.update_guild_message(guild))
	
	async def delete_message(self, guild: discord.Guild):
		cfg = self.config.guild(guild)
		channel = await cfg.channel()
		if(channel == None):
			return
		channel: discord.TextChannel = guild.get_channel(channel)
		if(isinstance(channel, discord.TextChannel) == False):
			return
		
		message = await cfg.message_id()
		cached: discord.Message
		if(message == None):
			return
		else:
			try:
				cached = await channel.fetch_message(message)
			except(discord.NotFound):
				return
		
		await cached.delete()
