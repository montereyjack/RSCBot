import discord
import re

from discord.ext import commands
from cogs.utils import checks

class Transactions:
    """Used to set franchise and role prefixes and give to members in those franchises or with those roles"""
    
    CONFIG_COG = None

    def __init__(self, bot):
        self.bot = bot
        self.CONFIG_COG = self.bot.get_cog("TransactionConfiguration")
        self.TEAM_MANAGER = self.bot.get_cog("TeamManager")
        self.prefix_cog = self.bot.get_cog("PrefixManager")

    @commands.guild_only()
    @checks.admin_or_permissions(manage_roles=True)
    async def draft(self, ctx, user: discord.Member, team_name: str, round: int = None, pick: int = None):
        """Assigns the franchise, tier, and league role to a user when they are drafted and posts to the assigned channel"""
        server_dict = self.CONFIG_COG.get_server_dict(ctx)
        franchise_role, tier_role = self.TEAM_MANAGER._roles_for_team(ctx, team_name)
        gm_name = self.get_gm_name(franchise_role)
        if franchise_role in user.roles:
            message = "Round {0} Pick {1}: {2} was kept by the {3} ({4} - {5})".format(round, pick, user.mention, team_name, gm_name, tier_role.name)
        else:
            message = "Round {0} Pick {1}: {2} was drafted by the {3} ({4} - {5})".format(round, pick, user.mention, team_name, gm_name, tier_role.name)

        channel = await self.add_player_to_team(ctx, server_dict, user, team_name)
        if channel is not None:
            try:
                free_agent_dict = server_dict.setdefault("Free agent roles", {})
                freeAgentRole = self.find_free_agent_role(free_agent_dict, user)
                await channel.send(message)
                draftEligibleRole = None
                for role in user.roles:
                    if role.name == "Draft Eligible":
                        draftEligibleRole = role
                        break
                if freeAgentRole is not None:
                    await user.remove_roles(freeAgentRole)
                if draftEligibleRole is not None:
                    await user.remove_roles(draftEligibleRole)
                await ctx.send("Done")
            except KeyError:
                await ctx.send(":x: Free agent role not found in dictionary")
            except LookupError:
                await ctx.send(":x: Free agent role not found in server")
            return


    @commands.guild_only()
    @checks.admin_or_permissions(manage_roles=True)
    async def sign(self, ctx, user: discord.Member, team_name: str):
        """Assigns the team role, franchise role and prefix to a user when they are signed and posts to the assigned channel"""
        franchise_role, tier_role = self.TEAM_MANAGER._roles_for_team(ctx, team_name)
        if franchise_role in user.roles and tier_role in user.roles:
            await ctx.send(":x: {0} is already on the {1}".format(user.mention, team_name))
            return

        server_dict = self.CONFIG_COG.get_server_dict(ctx)
        channel = await self.add_player_to_team(ctx, server_dict, user, team_name)
        if channel is not None:
           try:
               free_agent_dict = server_dict.setdefault("Free agent roles", {})
               freeAgentRole = self.find_free_agent_role(free_agent_dict, user)
               gm_name = self.get_gm_name(franchise_role)
               message = "{0} was signed by the {1} ({2} - {3})".format(user.mention, team_name, gm_name, tier_role.name)
               await channel.send(message)
               if freeAgentRole is not None:
                   await user.remove_roles(freeAgentRole)
               await ctx.send("Done")
           except KeyError:
               await ctx.send(":x: Free agent role not found in dictionary")
           except LookupError:
               await ctx.send(":x: Free agent role not found in server")

    @commands.guild_only()
    @checks.admin_or_permissions(manage_roles=True)
    async def cut(self, ctx, user : discord.Member, team_name: str, freeAgentRole: discord.Role = None):
        """Removes the team role and franchise role. Adds the free agent prefix to a user and posts to the assigned channel"""
        server_dict = self.CONFIG_COG.get_server_dict(ctx)
        franchise_role, tier_role = self.TEAM_MANAGER._roles_for_team(ctx, team_name)
        channel = await self.remove_player_from_team(ctx, server_dict, user, team_name)
        if channel is not None:
            try:
                if freeAgentRole is None:
                    freeAgentRole = self.CONFIG_COG.find_role_by_name(ctx.message.server.roles, "{0}FA".format(self.TEAM_MANAGER.get_current_tier_role(ctx, user).name))
                await user.edit(nick="FA | {0}".format(self.get_player_nickname(user)))
                await user.add_roles(freeAgentRole)
                gm_name = self.get_gm_name(franchise_role)
                message = "{0} was cut by the {1} ({2} - {3})".format(user.mention, team_name, gm_name, tier_role.name)
                await channel.send(message)
                await ctx.send("Done")
            except KeyError:
                await ctx.send(":x: Free agent role not found in dictionary")
            except LookupError:
                await ctx.send(":x: Free agent role not found in server")

    @commands.guild_only()
    @checks.admin_or_permissions(manage_roles=True)
    async def trade(self, ctx, user: discord.Member, new_team_name: str, user_2: discord.Member, new_team_name_2: str):
        """Swaps the teams of the two players and announces the trade in the assigned channel"""
        franchise_role_1, tier_role_1 = self.TEAM_MANAGER._roles_for_team(ctx, new_team_name)
        franchise_role_2, tier_role_2 = self.TEAM_MANAGER._roles_for_team(ctx, new_team_name_2)
        gm_name_1 = self.get_gm_name(franchise_role_1)
        gm_name_2 = self.get_gm_name(franchise_role_2)
        if franchise_role_1 in user.roles and tier_role_1 in user.roles:
            await ctx.send(":x: {0} is already on the {1}".format(user.mention, new_team_name))
            return
        if franchise_role_2 in user_2.roles and tier_role_2 in user_2.roles:
            await ctx.send(":x: {0} is already on the {1}".format(user_2.mention, new_team_name_2))
            return

        server_dict = self.CONFIG_COG.get_server_dict(ctx)
        await self.remove_player_from_team(ctx, server_dict, user, new_team_name_2)
        await self.remove_player_from_team(ctx, server_dict, user_2, new_team_name)
        await self.add_player_to_team(ctx, server_dict, user, new_team_name)
        channel = await self.add_player_to_team(ctx, server_dict, user_2, new_team_name_2)
        if channel is not None:
           message = "{0} was traded by the {1} ({4} - {5}) to the {2} ({6} - {7}) for {3}".format(user.mention, new_team_name_2, new_team_name, 
                user_2.mention, gm_name_2, tier_role_2.name, gm_name_1, tier_role_1.name)
           await channel.send(message)
           await ctx.send("Done")

    @commands.guild_only()
    @checks.admin_or_permissions(manage_roles=True)
    async def sub(self, ctx, user: discord.Member, team_name: str):
        """Adds the team role to the user and posts to the assigned channel"""
        server_dict = self.CONFIG_COG.get_server_dict(ctx)

        channel = await self.CONFIG_COG.get_transaction_channel(ctx, server_dict, ctx.message.guild)
        if channel is not None:
            leagueRole = self.CONFIG_COG.find_role_by_name(ctx.message.guild.roles, "League")
            if leagueRole is not None:
                franchise_role, tier_role = self.TEAM_MANAGER._roles_for_team(ctx, team_name)
                gm_name = self.get_gm_name(franchise_role)
                if franchise_role in user.roles and tier_role in user.roles:
                    await user.remove_roles(franchise_role, tier_role)
                    message = "{0} has finished their time as a substitute for the {1} ({2} - {3})".format(user.name, team_name, gm_name, tier_role.name)
                else:
                    await user.add_roles(franchise_role, tier_role, leagueRole)
                    message = "{0} was signed to a temporary contract by the {1} ({2} - {3})".format(user.mention, team_name, gm_name, tier_role.name)
                await channel.send(message)
                await ctx.send("Done")

    @commands.guild_only()
    @checks.admin_or_permissions(manage_roles=True)
    async def promote(self, ctx, user: discord.Member, team_name: str):
        server_dict = self.CONFIG_COG.get_server_dict(ctx)
        old_team_name = await self.TEAM_MANAGER.get_current_team_name(ctx, user)
        if old_team_name is not None:
            if self.TEAM_MANAGER._roles_for_team(ctx, old_team_name)[0] != self.TEAM_MANAGER._roles_for_team(ctx, team_name)[0]:
                await ctx.send(":x: {0} is not in the same franchise as {1}'s current team, the {2}".format(team_name.name, user.name, old_team_name))
                return
            await self.remove_player_from_team(ctx, server_dict, user, old_team_name)
            channel = await self.add_player_to_team(ctx, server_dict, user, team_name)
            if channel:
                franchise_role, tier_role = self.TEAM_MANAGER._roles_for_team(ctx, team_name)
                gm_name = self.get_gm_name(franchise_role)
                message = "{0} was promoted to the {1} ({2} - {3})".format(user.mention, team_name, gm_name, tier_role.name)
                await channel.send(message)
                await ctx.send("Done")
        else:
            await ctx.send("Either {0} isn't on a team right now or his current team can't be found".format(user.name))

    def get_gm_name(self, franchiseRole):
        try:
            return re.findall(r'(?<=\().*(?=\))', franchiseRole.name)[0]
        except:
            raise LookupError('GM name not found from role {0}'.format(franchiseRole.name))

    def find_free_agent_role(self, free_agent_dict, user):
        if(len(free_agent_dict.items()) > 0):
            for value in free_agent_dict.items():
                for role in user.roles:
                    if role.id == value[1]:
                        return role
        return None

    async def add_player_to_team(self, ctx, server_dict, user, team_name):
        franchise_role, tier_role = self.TEAM_MANAGER._roles_for_team(ctx, team_name)
        # if franchise_role in user.roles and tier_role in user.roles:
        #     await ctx.send(":x: {0} is already on the {1}".format(user.mention, team_name))
        #     return

        channel = await self.CONFIG_COG.get_transaction_channel(ctx, server_dict, ctx.message.guild)
        if channel is not None:
            leagueRole = self.CONFIG_COG.find_role_by_name(ctx.message.guild.roles, "League")
            if leagueRole is not None:
                prefix = await self.get_prefix(ctx, franchise_role)
                if prefix is not None:
                    currentTier = self.TEAM_MANAGER.get_current_tier_role(ctx, user)
                    if currentTier is not None and currentTier != tier_role:
                        await user.remove_roles(currentTier)
                    await user.edit(nick="{0} | {1}".format(prefix, self.get_player_nickname(user)))
                    await user.add_roles(tier_role, leagueRole, franchise_role)
                    return channel


    async def remove_player_from_team(self, ctx, server_dict, user, team_name):
        franchise_role, tier_role = self.TEAM_MANAGER._roles_for_team(ctx, team_name)
        if franchise_role not in user.roles or tier_role not in user.roles:
            await ctx.send(":x: {0} is not on the {1}".format(user.mention, team_name))
            return

        channel = await self.CONFIG_COG.get_transaction_channel(ctx, server_dict, ctx.message.guild)
        if channel is not None:
            if franchise_role is not None:
                prefix = await self.get_prefix(ctx, franchise_role)
                if prefix is not None:
                    await user.remove_roles(franchise_role)
                    return channel

    def get_player_nickname(self, user : discord.Member):
        if user.nick is not None:
            array = user.nick.split(' | ', 1)
            if len(array) == 2:
                currentNickname = array[1].strip()
            else:
                currentNickname = array[0]
            return currentNickname
        return user.name

    async def get_prefix(self, ctx, franchiseRole: discord.Role):
        try:
            prefix_dict = self.prefix_cog._prefixes(ctx)
            try:
                gmName = self.get_gm_name(franchiseRole)
                try:
                    return prefix_dict[gmName]
                except KeyError:
                    await ctx.send(":x: Prefix not found for {0}".format(gmName))
            except LookupError:
                await ctx.send(':x: GM name not found from role {0}'.format(franchiseRole.name))
        except KeyError:
            await ctx.send(":x: Couldn't find prefix dictionary")

def setup(bot):
    bot.add_cog(Transactions(bot))