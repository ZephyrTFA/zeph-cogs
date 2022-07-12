from datetime import datetime, timedelta
from distutils.command.config import config
import discord
from redbot.core import commands, Config, checks


class AccountAgeFlagger(commands.Cog):
	"""Class to manage flagging accounts under a specified age"""

	def __init__(self, bot: commands.Bot) -> None:
		self.bot = bot
		self.config = Config.get_conf(self, identifier=51360816380568, force_registration=True)

		def_guild = {
			"needs_verification_role": None,
			"needs_verification_log": None,
			"verifier_role": None,
			"account_age_minimum_days": 15,
		}
		self.config.register_guild(**def_guild)
	
	@commands.Cog.listener()
	async def on_member_join(self, ctx: commands.Context, member: discord.Member):
		day_cutoff: int = self.config.guild(ctx.guild).account_age_minimum_days()
		mem_age: datetime = member.created_at
		mem_delta: timedelta = mem_age - datetime.now()
		if(mem_delta.days > day_cutoff):
			return
		
		guild: discord.Guild = ctx.guild
		
		role: discord.Role = guild.get_role(self.config.guild(ctx.guild).needs_verification_role())
		await member.add_roles(role)

		verifier_role: discord.Role = guild.get_role(await self.config.guild(ctx.guild).verifier_role())
		channel: discord.TextChannel = guild.get_channel(await self.config.guild(ctx.guild).needs_verification_log())
		channel.send("[VERIFICATION]: {} is only {} days old! {}".format(member.mention, mem_delta.days, verifier_role.mention))

	async def test_command(self, ctx: commands.Context):
		member: discord.Member = ctx.author
		await ctx.send("Running test on {}".format(member.display_name))

		day_cutoff: int = await self.config.guild(ctx.guild).account_age_minimum_days()
		await ctx.send("Age cutoff is {}".format(day_cutoff))

		mem_age: datetime = member.created_at
		mem_delta: timedelta = datetime.now() - mem_age
		await ctx.send("Member age is {}".format(mem_delta.days))
		if(mem_delta.days > day_cutoff):
			await ctx.send("Member is not going to be flagged but continuing test")
			# return
		
		guild: discord.Guild = ctx.guild
		
		role: discord.Role = guild.get_role(await self.config.guild(ctx.guild).needs_verification_role())
		await member.add_roles(role)

		verifier_role: discord.Role = guild.get_role(await self.config.guild(ctx.guild).verifier_role())
		channel: discord.TextChannel = guild.get_channel(await self.config.guild(ctx.guild).needs_verification_log())
		channel.send("[VERIFICATION]: {} is only {} days old! {}".format(member.mention, mem_delta.days, verifier_role.mention))

	@commands.command()
	@checks.admin()
	async def aaf(self, ctx: commands.Context, subcom: str):
		if(subcom == ""):
			await ctx.send("Subcommands: `config`, `test_self`")
		elif(subcom == "config"):
			return
		elif(subcom == "test_self"):
			cfg: config = self.config.guild(ctx.guild)
			resp = "Config:\n\
				```\n\
				needs_verification_role =  {}\n\
				needs_verification_log =   {}\n\
				verifier_role =            {}\n\
				account_age_minimum_days = {}\n\
				```".format(await cfg.needs_verification_role(), await cfg.needs_verification_log(), await cfg.verifier_role(), await cfg.account_age_minimum_days())
			await ctx.send(resp)
			await self.test_command(ctx)
		else:
			await self.account_age(ctx, "")
