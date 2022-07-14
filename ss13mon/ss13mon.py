import asyncio
from datetime import datetime
from dis import disco
from sqlite3 import Timestamp
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
		self.config.register_guild(**def_guild)
	
	@commands.command()
	async def ss13status(self, ctx: commands.Context, p=41372):
		await ctx.channel.send(embed=(await self.generate_embed(ctx.guild)))
	
	@commands.command()
	@checks.admin()
	async def ss13mon(self, ctx: commands.Context, key, value = None):
		cfg = self.config.guild(ctx.guild)
		if(key == "address"):
			await cfg.address.set(value)
		elif(key == "port"):
			await cfg.port.set((int(value), None)[value == None])
		elif(key == "channel"):
			await self.delete_message(ctx.guild)
			await cfg.channel.set((int(value), None)[value == None])
			await self.update_guild_message(ctx.guild)
		elif(key == "update"):
			await self.update_guild_message(ctx.guild)
			await ctx.send("Forcibly triggered a guild update")
		else:
			await ctx.send("Not implemented yet")
			return
		
		await ctx.send("{} is now set to {}".format(key, value))

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

		await cfg.last_roundid.set(roundid)
		await cfg.last_title.set(servtitle)
		await cfg.last_online.set(time())

		embbie: discord.Embed = discord.Embed(type="rich", color=discord.Colour.blue(), title=servtitle, timestamp=datetime.now())

		value_inf = "Round ID: `{}`\nPlayers: `{}`\nTIDI: `{}%`".format(roundid, player_count, time_dilation_avg)
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
			cached = await channel.fetch_message(message)
			if(cached == None): cached = await channel.send("caching initial context")
		
		cached.edit(content=None, embed=(await self.generate_embed()))
	
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
			cached = await channel.fetch_message(message)
		
		await cached.delete()
