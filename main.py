import discord
from discord import app_commands
from discord.ui import View, Select, Button
import datetime
import math
import os

# ==============================================================================
# 🎨 UI CONFIGURATION & HELPER FUNCTIONS
# ==============================================================================
# The goal is to make the Embed look like a standalone dashboard application.

class UIStyles:
    # Discord Dark Mode Background Color (blends in seamlessly)
    BG_COLOR = 0x2b2d31 
    
    # ANSI Color Codes for the Code Block styling
    ANSI_RESET = "\u001b[0m"
    ANSI_BOLD = "\u001b[1m"
    ANSI_BLUE = "\u001b[34m"
    ANSI_CYAN = "\u001b[36m"
    ANSI_GREEN = "\u001b[32m"
    ANSI_MAGENTA = "\u001b[35m"
    ANSI_RED = "\u001b[31m"
    ANSI_WHITE = "\u001b[37m"
    ANSI_YELLOW = "\u001b[33m"

def create_progress_bar(percentage, length=12):
    """Generates a text-based progress bar."""
    filled = int(length * percentage)
    empty = length - filled
    # Using specific unicode block characters for a smooth look
    return "█" * filled + "░" * empty

def format_ansi_row(role_name, member_count, percentage, is_hoisted):
    """Formats a row for the main role list using ANSI coloring."""
    
    # Truncate long names to keep UI aligned
    name_display = (role_name[:18] + '..') if len(role_name) > 18 else role_name.ljust(20)
    
    # Color logic based on status
    name_color = UIStyles.ANSI_WHITE
    if is_hoisted:
        name_color = UIStyles.ANSI_CYAN
    if "Admin" in role_name or "Mod" in role_name:
        name_color = UIStyles.ANSI_MAGENTA

    bar = create_progress_bar(percentage, 8)
    
    # The actual string formatter
    return (
        f"{name_color}{name_display}{UIStyles.ANSI_RESET} "
        f"{UIStyles.ANSI_BLUE}│{UIStyles.ANSI_RESET} "
        f"{UIStyles.ANSI_YELLOW}{str(member_count).rjust(3)}{UIStyles.ANSI_RESET} "
        f"{UIStyles.ANSI_GREEN}{bar}{UIStyles.ANSI_RESET}"
    )

# ==============================================================================
# 🧩 INTERACTIVE COMPONENTS (VIEWS)
# ==============================================================================

class RoleDetailSelect(Select):
    """A dropdown menu to select a specific role for detailed stats."""
    def __init__(self, roles):
        options = []
        # Limit to first 25 roles for the dropdown (Discord limitation)
        # In a full production bot, you'd handle this with more logic
        for role in roles[:25]:
            if role.name == "@everyone": continue
            options.append(discord.SelectOption(
                label=role.name,
                value=str(role.id),
                description=f"ID: {role.id} • {len(role.members)} members",
                emoji="🛡️" if role.permissions.administrator else "🏷️"
            ))
        
        super().__init__(
            placeholder="🔍 Inspect a specific role...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        role_id = int(self.values[0])
        role = interaction.guild.get_role(role_id)
        
        # Create a "Drill Down" embed
        embed = discord.Embed(
            title=f"🔹 {role.name}",
            description=f"Detailed analysis for {role.mention}",
            color=role.color if role.color.value != 0 else UIStyles.BG_COLOR
        )
        
        # Permissions visualizer
        perms = [p[0].replace('_', ' ').title() for p in role.permissions if p[1]]
        perm_str = "\n".join([f"✅ {p}" for p in perms[:8]])
        if len(perms) > 8: perm_str += f"\n...and {len(perms)-8} more"
        
        embed.add_field(name="🔑 Key Permissions", value=f"```diff\n{perm_str or 'No special perms'}\n```", inline=True)
        
        # Stats visualizer
        stats = (
            f"**Hoisted:** {'Yes' if role.hoist else 'No'}\n"
            f"**Mentionable:** {'Yes' if role.mentionable else 'No'}\n"
            f"**Created:** <t:{int(role.created_at.timestamp())}:R>\n"
            f"**Color Hex:** {str(role.color)}"
        )
        embed.add_field(name="📊 Configuration", value=stats, inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class PaginationView(View):
    """Controls the buttons and state of the role list."""
    def __init__(self, roles, author_id):
        super().__init__(timeout=60)
        self.roles = [r for r in roles if r.name != "@everyone"]
        self.roles.reverse() # Show highest roles first usually
        self.author_id = author_id
        self.current_page = 0
        self.items_per_page = 10
        self.total_pages = math.ceil(len(self.roles) / self.items_per_page)
        
        # Add the dropdown for details
        self.add_item(RoleDetailSelect(self.roles))
        self.update_buttons()

    def update_buttons(self):
        # Disable/Enable buttons based on page
        self.prev_btn.disabled = self.current_page == 0
        self.next_btn.disabled = self.current_page == self.total_pages - 1
        self.page_counter.label = f"Page {self.current_page + 1}/{self.total_pages}"

    def generate_dashboard_embed(self, guild):
        """Generates the main 'Mind Blowing' UI Embed."""
        
        # Slicing the roles for the current page
        start = self.current_page * self.items_per_page
        end = start + self.items_per_page
        page_roles = self.roles[start:end]
        
        total_members = guild.member_count
        
        # --- HEADER SECTION ---
        embed = discord.Embed(color=UIStyles.BG_COLOR)
        embed.set_author(name=f"SERVER ROLE MATRIX: {guild.name.upper()}", icon_url=guild.icon.url if guild.icon else None)
        
        # --- ANSI TABLE SECTION ---
        # We build a string that looks like a terminal output
        header = f"{UIStyles.ANSI_BOLD}ROLE NAME            │ MEM PREVALENCE{UIStyles.ANSI_RESET}"
        rows = []
        
        for role in page_roles:
            perc = len(role.members) / total_members if total_members > 0 else 0
            rows.append(format_ansi_row(role.name, len(role.members), perc, role.hoist))
            
        ansi_block = f"```ansi\n{header}\n{'━'*35}\n" + "\n".join(rows) + "\n```"
        
        embed.description = ansi_block
        
        # --- FOOTER METADATA ---
        # Using fields to look like status indicators
        embed.add_field(name="TOTAL ROLES", value=f"**{len(self.roles)}**", inline=True)
        embed.add_field(name="HIGHEST ROLE", value=self.roles[0].mention, inline=True)
        embed.add_field(name="UPDATED", value=f"<t:{int(datetime.datetime.now().timestamp())}:R>", inline=True)
        
        embed.set_image(url="https://media.discordapp.net/attachments/1000000000000000000/1000000000000000000/transparent_divider.png") # Optional: Use a transparent pixel for padding if needed, or remove.
        embed.set_footer(text="System ID: R-800 • Interactive Dashboard")
        
        return embed

    @discord.ui.button(label="◄ Previous", style=discord.ButtonStyle.secondary, custom_id="prev")
    async def prev_btn(self, interaction: discord.Interaction, button: discord.Button):
        if interaction.user.id != self.author_id: return await interaction.response.send_message("This isn't your dashboard.", ephemeral=True)
        self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.generate_dashboard_embed(interaction.guild), view=self)

    @discord.ui.button(label="Page 1/1", style=discord.ButtonStyle.primary, disabled=True, custom_id="counter")
    async def page_counter(self, interaction: discord.Interaction, button: discord.Button):
        pass # Just a display button

    @discord.ui.button(label="Next ►", style=discord.ButtonStyle.secondary, custom_id="next")
    async def next_btn(self, interaction: discord.Interaction, button: discord.Button):
        if interaction.user.id != self.author_id: return await interaction.response.send_message("This isn't your dashboard.", ephemeral=True)
        self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.generate_dashboard_embed(interaction.guild), view=self)

# ==============================================================================
# 🤖 BOT SETUP
# ==============================================================================

class AdvancedBot(discord.Client):
    def __init__(self):
        # Intents are critical for role/member data
        intents = discord.Intents.default()
        intents.members = True 
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        await self.tree.sync()
        print('Slash commands synced!')

client = AdvancedBot()

@client.tree.command(name="roles", description="Launch the advanced Role Matrix dashboard")
async def roles(interaction: discord.Interaction):
    """
    The main command. Creates the View and the Embed.
    """
    # 1. Defer response so we have time to process logic without timing out
    await interaction.response.defer()
    
    # 2. Get Roles
    roles = interaction.guild.roles
    if not roles:
        await interaction.followup.send("No roles found!")
        return

    # 3. Create the View (Logic)
    view = PaginationView(roles, interaction.user.id)
    
    # 4. Create the Embed (Visuals)
    embed = view.generate_dashboard_embed(interaction.guild)
    
    # 5. Send
    await interaction.followup.send(embed=embed, view=view)

# ==============================================================================
# 🚀 EXECUTION
# ==============================================================================

if __name__ == "__main__":
    # Get token from Railway environment variable
    TOKEN = os.getenv("DISCORD_TOKEN")

    if not TOKEN:
        print("❌ ERROR: DISCORD_TOKEN environment variable is missing.")
        print("Please set 'DISCORD_TOKEN' in your Railway project variables.")
    else:
        client.run(TOKEN)
