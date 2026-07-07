import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import os
import threading
import http.server
import socketserver
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

@bot.tree.command(name="суммаотбить", description="Установить сумму, которую нужно отбить (всего капитал)")
@app_commands.describe(сумма="Общая сумма для отбития (только цифры)")
async def суммаотбить(interaction: discord.Interaction, сумма: str):
    try:
        val = int(сумма.replace(" ", "").replace(",", "").replace(".", ""))
    except:
        await interaction.response.send_message("❌ Неверный формат. Введите число, например 117108658.", ephemeral=True)
        return
    set_total(val)
    await interaction.response.send_message(f"✅ Сумма для отбития установлена: **{val:,}** $")

class RentModal(discord.ui.Modal, title="Пополнение отбития"):
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
        if total_before == 0:
            await interaction.response.send_message("❌ Сначала установите сумму для отбития командой `/суммаотбить`.", ephemeral=True)
            return

        new_total = subtract(sum_earned)

        embed = discord.Embed(
            title="📋 Пополнение отбития",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.add_field(name="📅 Дата", value=date, inline=False)
        amounts_text = "\n".join(f"+ {a:,}" for a in amounts)
        embed.add_field(name="💰 Заработано", value=amounts_text, inline=False)
        embed.add_field(
            name="📊 Осталось отбить",
            value=f"**{new_total:,}** $",
            inline=False
        )
        embed.add_field(
            name="🖼 Скриншоты",
            value="Прикрепите их к этому сообщению вручную",
            inline=False
        )
        embed.set_footer(text=f"Выдано: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")

        await interaction.response.send_message(embed=embed)

@bot.tree.command(name="пополнить", description="Добавить заработанные суммы (откроется форма)")
async def пополнить(interaction: discord.Interaction):
    await interaction.response.send_modal(RentModal())

@bot.tree.command(name="остаток", description="Показать текущий остаток для отбития")
async def остаток(interaction: discord.Interaction):
    total = get_total()
    embed = discord.Embed(title="📊 Текущий остаток", description=f"**{total:,}** $", color=discord.Color.blue())
    await interaction.response.send_message(embed=embed)

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("0.0.0.0", port), handler) as httpd:
        print(f"🌐 Веб-сервер запущен на порту {port}")
        httpd.serve_forever()

if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    bot.run(TOKEN)
