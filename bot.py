import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise ValueError("TOKEN not found")

conn = sqlite3.connect("data.db")
c = conn.cursor()
c.execute("CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value INTEGER)")
conn.commit()

def get_total():
    c.execute("SELECT value FROM state WHERE key='total'")
    row = c.fetchone()
    if row:
        return row[0]
    return 0

def set_total(amount):
    c.execute("INSERT OR REPLACE INTO state (key, value) VALUES ('total', ?)", (amount,))
    conn.commit()

def subtract(amount_sum):
    total = get_total()
    new_total = total - amount_sum
    set_total(new_total)
    return new_total

# Только стандартные интенты – слэш-команды работают без привилегий
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Bot {bot.user} ready")

@bot.tree.command(name="settotal", description="Set initial balance (admin only)")
@app_commands.describe(amount="New balance")
async def settotal(interaction: discord.Interaction, amount: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admin only", ephemeral=True)
        return
    try:
        val = int(amount.replace(" ", "").replace(",", "").replace(".", ""))
    except:
        await interaction.response.send_message("❌ Invalid number", ephemeral=True)
        return
    set_total(val)
    await interaction.response.send_message(f"✅ Balance set: **{val:,}** $")

@bot.tree.command(name="status", description="Show current balance")
async def status(interaction: discord.Interaction):
    total = get_total()
    embed = discord.Embed(title="📊 Current balance", description=f"**{total:,}** $", color=discord.Color.blue())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="addrent", description="Add earned amounts (space separated)")
@app_commands.describe(date="Date (e.g. 05.07)", sums="Amounts (e.g. 75000 85500)")
async def addrent(interaction: discord.Interaction, date: str, sums: str):
    total_before = get_total()
    parts = sums.split()
    amounts = []
    for p in parts:
        try:
            val = int(p.replace(" ", "").replace(",", "").replace(".", ""))
            amounts.append(val)
        except:
            await interaction.response.send_message(f"❌ Invalid: `{p}`", ephemeral=True)
            return
    sum_earned = sum(amounts)
    if sum_earned == 0:
        await interaction.response.send_message("❌ Sum cannot be zero", ephemeral=True)
        return
    new_total = subtract(sum_earned)
    embed = discord.Embed(title="📋 Rent record", color=discord.Color.blue(), timestamp=discord.utils.utcnow())
    embed.add_field(name="📅 Date", value=date, inline=False)
    embed.add_field(name="💰 Earned", value="\n".join(f"+ {a:,}" for a in amounts), inline=False)
    embed.add_field(name="📊 Before", value=f"{total_before:,} $", inline=True)
    embed.add_field(name="💵 New balance", value=f"{new_total:,} $", inline=True)
    embed.set_footer(text="Foxhole Bot")
    await interaction.response.send_message(embed=embed)

bot.run(TOKEN)
