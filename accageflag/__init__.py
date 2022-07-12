from .accageflag import AccountAgeFlagger

def setup(bot):
    bot.add_cog(AccountAgeFlagger(bot))
