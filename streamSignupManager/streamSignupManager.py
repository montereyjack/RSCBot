import re
import discord
from redbot.core import Config
from redbot.core import commands
from redbot.core import checks

defaults = {"Applications": {}, "Schedule": {}, "Time_Slots": {1: "11:00pm ET", 2: "11:30pm ET"}, "Stream_Channel": None}

# TODO: (All listed todos) +league approve applications, alert all game players when match has been updated, include which stream its on

# Roles: Captain, GM, <Tier>, <Franchise>, (Soon: Stream Committee)

class StreamSignupManager(commands.Cog):
    def __init__(self, bot):
        self.config = Config.get_conf(self, identifier=1234567892, force_registration=True)
        self.config.register_guild(**defaults)
        self.match_cog = bot.get_cog("Match")
        self.team_manager_cog = bot.get_cog("TeamManager")
        self.bot = bot

        # Application statuses
        self.PENDING_OPP_CONFIRMATION_STATUS = "PENDING_OPP_CONFIRMATION"
        self.PENDING_LEAGUE_APPROVAL_STATUS = "PENDING_LEAGUE_APPROVAL"
        self.SCHEDULED_ON_STREAM_STATUS = "SCHEDULED_ON_STREAM"
        self.REJECTED_STATUS = "REJECTED"
    
    @commands.command(aliases=["applications", "getapps", "listapps", "apps"])
    @commands.guild_only()
    async def viewapps(self, ctx, match_day=None, time_slot=None):
        embed = await self._format_apps(ctx.guild, match_day, time_slot)
        if embed:
            await ctx.send(embed)
        else:
            await ctx.send("No pending applications.")
        
    @commands.command(aliases=["streamapp", "streamapply", "streamApplications", "streamapplications"])
    @commands.guild_only()
    async def streamApp(self, ctx, action, match_day, time_slot=None, team=None):
        """
        Central command for managing stream signups. This is used to initiate stream applications, as well
        as accepting/rejecting requests to play on stream.

        command format:
        [p]streamApp <action> <match_day> <stream_slot> <team name (GMs only)>

        **action keywords:** apply, accept, reject
        
        Examples:
        [p]streamApp apply 1 1
        [p]streamApp accept 3
        [p]stream reject 3

        Note: If you are a General Manager, you must include the team name in applications
        [p]streamApp apply 1 1 Spartans
        [p]streamApp accept 4 Vikings
        [p]streamApp reject 3 Vikings
        """

        requesting_member = ctx.message.author
        gm_role = self.team_manager_cog._find_role_by_name(ctx, self.team_manager_cog.GM_ROLE)
        if gm_role not in requesting_member.roles:
            requesting_team = await team_manager_cog.get_current_team_name(ctx, requesting_member)
        else:
            requesting_team = team
            if not await self._verify_gm_team(ctx, requesting_member, requesting_team):
                return False
            if action in ['accept', 'reject'] and team == None:
                requesting_team = time_slot  # shifting places
            if not requesting_team:
                await ctx.send(":x: GMs must include the team name in their streamApp commands.")
                return False


        if action == "apply":
            if not time_slot:
                await ctx.send(":x: stream slot must be included in an application.")
                return False
            match = await self.match_cog.get_match_from_day_team(ctx, match_day, requesting_team)
            applied = await self._add_application(ctx, requesting_member, match, time_slot)
            if applied:
                await ctx.send("Done.")
                return True
        if action not in ["accept", "reject"]:
            await ctx.send("\"{0}\" is not a recognized action. Please either _accept_ or _reject_ the stream application.".format(response))
            return False

        accepted = True if action == "accept" else False
        if gm_role in requesting_member.roles:
            updated = await self._accept_reject_application(ctx.guild, ctx.author, match_day, accepted, requesting_team)
        else:
            updated = await self._accept_reject_application(ctx.guild, ctx.author, match_day, accepted)
        
        if updated:
            if accepted:
                await ctx.send("Your application to play match {0} on stream has been updated.".format(match_day))
                return True
            else:
                await ctx.send("Your application to play match {0} on stream has been removed.".format(match_day))
                return True
        else:
            await ctx.send(":x: Stream Application not found.")

    @commands.command(aliases=['clearapps', 'removeapps'])
    @commands.guild_only()
    async def clearApps(self, ctx):
        await self._clear_applications(ctx.guild)
        await ctx.send("Done.")

    @commands.command(aliases=['reviewapps', 'reviewApplications', 'approveApps'])
    @commands.guild_only()
    async def reviewApps(self, ctx, match_day=None, time_slot=None):
        embed = await self._format_apps(ctx.guild, match_day, time_slot)
        if embed:
            await ctx.send(embed)
        else:
            # TODO: have review only show completed applications
            await ctx.send("No completed applications have been found.")

    async def _add_application(self, ctx, requested_by, match_data, time_slot):
        applications = await self._applications(ctx.guild)
        if self._get_application(match_data):
            await ctx.send(":x: Application is already in progress.")
            return False
            
        requesting_team = await team_manager_cog.get_current_team_name(ctx, requesting_member)
        if match_data['home'] == requesting_team:
            other_team = match_data['away']
        else:
            other_team = match_data['home']
        other_franchise_role, tier_role = await self.team_manager_cog._roles_for_team(ctx, other_team)
        other_captain = await self.team_manager_cog.get_team_captain(ctx, other_franchise_role, tier_role)
        # send request to GM if team has no captain
        if not other_captain:
            other_captain = self.team_manager_cog._get_gm(ctx, other_franchise_role)

        new_payload = {
            "status": self.PENDING_OPPONENT_CONFIRMATION_STATUS,
            "requested_by": requested_by.id,
            "request_recipient": other_captain.id,
            "home": match_data['home'],
            "away": match_data['away'],
            "slot": time_slot
        }
        
        # Possible improvement: Update match info instead of adding a new field/don't duplicate saved data/get match ID reference?
        # Add application
        application[match_day].append(new_payload)
        await self._save_applications(ctx.guild, applications)

        # Challenge other team
        if self.team_manager_cog.is_gm(other_captain):
            message = gm_challenged_msg.format(match_day=match_day, home=home, away=away, time_slot=time_slot, channel=ctx.channel, gm_team=other_team)
        else:
            message = challenged_msg.format(match_day=match_day, home=home, away=away, time_slot=time_slot, channel=ctx.channel)
        await self._send_member_message(ctx, other_captain, message)
        return True

    async def _verify_gm_team(self, ctx, gm: discord.Member, team: str):
        try:
            franchise_role, tier_role = await self.team_manager_cog._roles_for_team(ctx, team)
            if franchise_role not in requesting_member.roles:
                await ctx.send(":x: The team **{0}** does not belong to the franchise, **{1}**.".format(team, franchise_role.name))
                return False
            return True
        except LookupError:
            await ctx.send(":x: {0} is not a valid team name".format(team))
            return False

    async def _accept_reject_application(self, ctx, recipient, match_day, is_accepted, responding_team=None):
        applications = self._applications(ctx.guild)
        if responding_team:
            gm_team_match = False
        else:
            gm_team_match = True

        for app in applications[match_day]:
            if app['request_recipient'] == recipient.id:
                if responding_team:
                    if app['home'] == responding_team or app['away'] == responding_team:
                        gm_team_match = True
                if app['status'] == self.PENDING_OPP_CONFIRMATION_STATUS and gm_team_match:
                    requesting_member = self._get_member_from_id(app['requested_by'])
                    if is_accepted:
                        # Send update message to other team - initial requester and that team's captain
                        if not responding_team:
                            responding_team = await self.team_manager_cog.get_current_team_name(ctx, requesting_member)
                        franchise_role, tier_role = await self.team_manager_cog._roles_for_team(ctx, responding_team)
                        other_captain = await self.team_manager_cog.get_team_captain(ctx, franchise_role, tier_role)
                        
                        message = challenge_accepted_msg.format(match_day=match_day, home=app['home'], away=app['away'])
                        await self._send_member_message(ctx, requesting_member, message)
                        if other_captain and requesting_member != other_captain:
                            await self._send_member_message(ctx, requesting_member, message)
                        
                        # TODO: send new complete app to media channel feed

                        # set status to pending league approval, save applications
                        app['status'] = self.PENDING_LEAGUE_APPROVAL_STATUS
                        await self._save_applications(guild, applications)
                        return True
                    else:
                        applications[match_day].remove(app)
                        await self._save_applications(guild, applications)
                        # TODO: send rejection message to requesting player
                        message = challenge_rejected_msg.format(match_day=match_day, home=app['home'], away=app['away'])
                        await self._send_member_message(ctx, requesting_member, message)
                        return True
        return False

    async def _format_apps(self, guild, match_day=None, time_slot=None):
        message = "Applications for Match Day {0}".format(match_day)
        if time_slot:
            message += " (time slot {0})".format(time_slot)
        embed = discord.Embed(title="Stream Applications", color=discord.Colour.blue(), description=message)

        home = []
        vs = []  # Probably not the best design choice, but it works...
        away = []
        slot = []
        status = []
        apps = await self._applications(guild)
        for md, data in apps:
            if (md == match_day or not match_day) and (md['slot'] == time_slot or not time_slot):
                home.append(data['home'])
                vs.append('vs.')
                away.append(data['away'])
                slot.append(data['slot'])
                status.append(data['status'])
            if match_day:
                break
        
        if not home:
            return None
        
        embed.add_field(name="Time Slot", value="{}\n".format("\n".join(slot)))
        embed.add_field(name="Home", value="{}\n".format("\n".join(home)))
        embed.add_field(name=" - ", value="{}\n".format("\n".join(vs)))
        embed.add_field(name="Away", value="{}\n".format("\n".join(home)))
        embed.add_field(name="Status", value="{}\n".format("\n".join(status)))

        return embed
        
    async def _applications(self, guild):
        return await self.config.guild(guild).Applications()

    async def _stream_schedule(self, guild):
        return await self.config.guild(guild).Schedule()

    async def _get_application(self, guild, match):
        for app in await self._applications(guild):
            if app['home_team'] == match['home'] and app['match_day'] == match['matchDay']:
                return app
        return None

    async def _save_applications(self, guild, applications):
        await self.config.guild(guild).Applications.set(applications)

    async def _save_stream_schedule(self, guild, schedule):
        await self.config.guild(guild).Schedule.set(schedule)

    async def _clear_applications(self, guild):
        await self.config.guild(guild).Applications.set({})
    
    async def _send_member_message(self, ctx, member, message):
        message_title = "**Message from {0}:**\n\n".format(ctx.guild.name)
        message = message.replace('[p]', ctx.prefix)
        message = message_title + message
        return await member.send(message)

    def _get_member_from_id(self, guild, member_id):
        for member in guild.members:
            if member.id == member_id:
                return member
        return None

challenged_msg = ("You have been asked to play **match day {match_day}** ({home} vs. {away}) on stream at the **{time_slot} time slot**. "
    "Please respond to this request in the **#{channel}** channel with one of the following:"
    "\n\t - To accept: `[p]streamapp accept {match_day}`"
    "\n\t - To reject: `[p]streamapp reject {match_day}`"
    "\nThis stream application will not be considered until you respond.")

gm_challenged_msg = ("You have been asked to play **match day {match_day}** ({home} vs. {away}) on stream at the **{time_slot} time slot**. "
    "Please respond to this request in the **#{channel}** channel with one of the following:"
    "\n\t - To accept: `[p]streamapp accept {match_day} {gm_team}`"
    "\n\t - To reject: `[p]streamapp reject {match_day} {gm_team}`"
    "\nThis stream application will not be considered until you respond.")

challenge_accepted_msg = (":white_check_mark: Your stream application for **match day {match_day}** ({home} vs. {away}) has been accepted by your opponents, and is "
    "now pending league approval. An additional message will be sent when a decision is made regarding this application.")

challenge_rejected_msg = (":x: Your stream application for **match day {match_day}** ({home} vs. {away}) has been rejected by your opponents, and will "
    "not be considered moving forward.")

#TODO: add stream channel (rsc vs rsc_2, etc)
league_approved_msg = ("**Congratulations!** You have been selected to play **match day {match_day}** ({home} vs. {away}) on stream at "
    "the **{3} time slot**. Feel free to use the `[p]match {match_day}` in your designated bot input channel see updated "
    "details of this match. We look forward to seeing you on stream!")

league_rejected_msg = ("Your application to play **match day {match_day}** ({home} vs. {away}) on stream has been denied. "
    "However, we will keep your application on file in case anything changes.")

