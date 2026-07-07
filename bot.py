import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("Токен не найден в переменной окружения TOKEN")

conn = sqlite3.connect("data.db")
c = conn.cursor()
c.execute("CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value INTEGER)")
conn.commit()

def get_total():
    c.execute("SELECT value FROM state WHERE key='total'")
    row = c.fetchone()
    return row[0] if row else 0

def set_total(amount):
    c.execute("INSERT OR REPLACE INTO state (key, value) VALUES ('total', ?)", (amount,))
    conn.commit()

def subtract(amount_sum):
    total = get_total()
    new_total = total - amount_sum
    set_total(new_total)
    return new_total

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Бот {bot.user} запущен!")

@bot.tree.command(name="settotal", description="Установить начальную сумму (только для админов)")
@app_commands.describe(amount="Новая сумма остатка (только цифры)")
async def settotal(interaction: discord.Interaction, amount: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Только администраторы могут использовать эту команду.", ephemeral=True)
        return
    try:
        val = int(amount.replace(" ", "").replace(",", "").replace(".", ""))
    except:
        await interaction.response.send_message("❌ Неверный формат. Введите число, например 117108658.", ephemeral=True)
        return
    set_total(val)
    await interaction.response.send_message(f"✅ Начальный остаток установлен: **{val:,}** $")

@bot.tree.command(name="status", description="Показать текущий остаток")
async def status(interaction: discord.Interaction):
    total = get_total()
    embed = discord.Embed(title="📊 Текущий остаток", description=f"**{total:,}** $", color=discord.Color.blue())
    await interaction.response.send_message(embed=embed)

class RentModal(discord.ui.Modal, title="Добавление аренды"):
    date = discord.ui.TextInput(
        label="📅 Дата",
        placeholder="Например: 05.07",
        required=True,
        max_length=50
    )
    sums = discord.ui.TextInput(
        label="💰 Суммы (через пробел)",
        placeholder="Например: 75000 85500",
        required=True,
        max_length=200
    )

    async def on_submit(self, interaction: discord.Interaction):
        date = self.date.value
        sums_str = self.sums.value

        parts = sums_str.split()
        amounts = []
        for p in parts:
            try:
                val = int(p.replace(" ", "").replace(",", "").replace(".", ""))
                amounts.append(val)
            except:
                await interaction.response.send_message(
                    f"❌ Некорректное число: `{p}`. Используйте только цифры, разделяйте пробелами.",
                    ephemeral=True
                )
                return

        if not amounts:
            await interaction.response.send_message("❌ Вы не ввели ни одной суммы.", ephemeral=True)
            return

        sum_earned = sum(amounts)
        if sum_earned == 0:
            await interaction.response.send_message("❌ Сумма не может быть равна 0.", ephemeral=True)
            return

        total_before = get_total()
        new_total = subtract(sum_earned)

        embed = discord.Embed(
            title="📋 Запись аренды",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.add_field(name="📅 Дата", value=date, inline=False)
        amounts_text = "\n".join(f"+ {a:,}" for a in amounts)
        embed.add_field(name="💰 Заработано", value=amounts_text, inline=False)
        embed.add_field(
            name="📊 Итоговая цена (сколько осталось отбить)",
            value=f"**{new_total:,}** $",
            inline=False
        )
        embed.set_footer(text=f"Выдано: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")

        await interaction.response.send_message(embed=embed)

@bot.tree.command(name="addrent", description="Добавить заработок (откроется форма)")
async def addrent(interaction: discord.Interaction):
    await interaction.response.send_modal(RentModal())

if __name__ == "__main__":
    bot.run(TOKEN)
