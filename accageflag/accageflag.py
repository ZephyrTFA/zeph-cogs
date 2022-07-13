from datetime import datetime, timedelta
from distutils.command.config import config
import discord
from redbot.core import commands, Config, checks


class AccountAgeFlagger(commands.Cog):
	"""Class to manage flagging accounts under a specified age"""

	async def _cfg_set(self, ctx: commands.Context, debug: bool = False) -> bool:
		cfg: Config = self.config.guild(ctx.guild)

		nvr = int(await cfg.needs_verification_role())
		nvl = int(await cfg.needs_verification_log())
		vr = int(await cfg.verifier_role())
		ad = int(await cfg.account_age_minimum_days())

		nvr = ctx.guild.get_role(nvr)
		nvl = ctx.guild.get_channel(nvl)
		vr = ctx.guild.get_role(vr)

		return (nvr != None and nvl != None and vr != None and ad != None)

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
	async def on_member_join(self, ctx: commands.Context, member: discord.Member = None, debug: bool = False):
		if(await self._cfg_set(ctx, debug) == False):
			if(debug): await ctx.send("Config not set correctly!")
			return

		if(isinstance(ctx, commands.Context)):
			member = ctx.author
		elif(isinstance(ctx, discord.Member)):
			member = ctx
		else: raise Exception("unable to determine method call context")

		day_cutoff: int = int(await self.config.guild(ctx.guild).account_age_minimum_days())
		mem_age: datetime = member.created_at
		mem_delta: timedelta = datetime.now() - mem_age

		if(debug):
			await ctx.send("Running test on {}".format(member.display_name))
			await ctx.send("Age cutoff is {}".format(day_cutoff))
			await ctx.send("Member age is {}".format(mem_delta.days))

		if(mem_delta.days > day_cutoff):
			if(debug): await ctx.send("Member is not going to be flagged but continuing test")
			else: return
		
		guild: discord.Guild = ctx.guild
		role: discord.Role = guild.get_role(int(await self.config.guild(ctx.guild).needs_verification_role()))
		await member.add_roles(role)

		verifier_role: discord.Role = guild.get_role(int(await self.config.guild(ctx.guild).verifier_role()))
		channel: discord.TextChannel = guild.get_channel(int(await self.config.guild(ctx.guild).needs_verification_log()))
		await channel.send("[VERIFICATION]: {} is only {} days old! {}".format(member.mention, mem_delta.days, verifier_role.mention))

	@commands.command()
	@checks.admin()
	async def aaf(self, ctx: commands.Context, subcom: str = "", cfg_name = "", cfg_val = ""):
		if(subcom == ""):
			await ctx.send("Subcommands: `configset`, `configget`, `test_self`")
		elif(subcom == "configset"):
			if(cfg_val == "None"): cfg_val = None
			if(cfg_name not in ["needs_verification_role", "needs_verification_log", "verifier_role", "account_age_minimum_days"]):
				await ctx.send("Unknown config key?")
				return
			if(isinstance(cfg_val, str)):
				cfg_val = int(cfg_val)
			cfg = self.config.guild(ctx.guild)
			await getattr(cfg, cfg_name).set(cfg_val)
			await ctx.send("{} set to {}".format(cfg_name, cfg_val))
		elif(subcom == "configget"):
			cfg: config = self.config.guild(ctx.guild)
			resp = "Config:\n\
```\n\
needs_verification_role =  {}\n\
needs_verification_log =   {}\n\
verifier_role =            {}\n\
account_age_minimum_days = {}\n\
```".format(await cfg.needs_verification_role(), await cfg.needs_verification_log(), await cfg.verifier_role(), await cfg.account_age_minimum_days())
			await ctx.send(resp)
		elif(subcom == "test_self"):
			await self.on_member_join(ctx, ctx.author, debug=True)
