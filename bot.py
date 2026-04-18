import os
import discord
from discord import app_commands
from datetime import datetime
import database as db

TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_BOT_TOKEN ist nicht gesetzt!")

intents = discord.Intents.default()

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)


def format_euro(betrag: float) -> str:
    return f"**{betrag:.2f} €**"


def datum_format(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return iso


@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Bot ist online als {bot.user} (ID: {bot.user.id})")
    print("Slash-Befehle wurden synchronisiert.")


@tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    print(f"❌ Fehler bei Befehl: {error}")
    try:
        await interaction.response.send_message(f"❌ Fehler: {error}", ephemeral=True)
    except Exception:
        await interaction.followup.send(f"❌ Fehler: {error}", ephemeral=True)


@tree.command(name="schuld_add", description="Füge eine Schuld hinzu (wer schuldet wem was)")
@app_commands.describe(
    schuldner="Der User, der die Schuld hat",
    betrag="Betrag in Euro (z.B. 12.50)",
    beschreibung="Wofür ist die Schuld? (z.B. Pizza, Kino)"
)
async def schuld_add(interaction: discord.Interaction, schuldner: discord.Member, betrag: float, beschreibung: str):
    if betrag <= 0:
        await interaction.response.send_message("❌ Der Betrag muss größer als 0 sein.", ephemeral=True)
        return
    if schuldner.id == interaction.user.id:
        await interaction.response.send_message("❌ Du kannst dir selbst keine Schulden eintragen.", ephemeral=True)
        return

    eintrag = db.schuld_hinzufuegen(
        schuldner_id=str(schuldner.id),
        schuldner_name=schuldner.display_name,
        glaeubiger_id=str(interaction.user.id),
        glaeubiger_name=interaction.user.display_name,
        betrag=betrag,
        beschreibung=beschreibung
    )

    embed = discord.Embed(title="💸 Neue Schuld eingetragen", color=discord.Color.red())
    embed.add_field(name="Schuldner", value=schuldner.mention, inline=True)
    embed.add_field(name="Gläubiger", value=interaction.user.mention, inline=True)
    embed.add_field(name="Betrag", value=format_euro(betrag), inline=True)
    embed.add_field(name="Beschreibung", value=beschreibung, inline=False)
    embed.set_footer(text=f"Schuld-ID: #{eintrag['id']} | {datum_format(eintrag['datum'])}")
    await interaction.response.send_message(embed=embed)


@tree.command(name="schuld_bezahlt", description="Markiere eine Schuld (per ID) als bezahlt")
@app_commands.describe(schuld_id="Die ID der Schuld (aus /schulden_liste oder /meine_schulden)")
async def schuld_bezahlt(interaction: discord.Interaction, schuld_id: int):
    eintrag = db.schuld_bezahlen(schuld_id, str(interaction.user.id))
    if eintrag is None:
        await interaction.response.send_message(
            f"❌ Schuld #{schuld_id} nicht gefunden oder du bist nicht der Schuldner.", ephemeral=True)
        return

    embed = discord.Embed(title="✅ Schuld als bezahlt markiert!", color=discord.Color.green())
    embed.add_field(name="Schuld-ID", value=f"#{eintrag['id']}", inline=True)
    embed.add_field(name="Betrag", value=format_euro(eintrag['betrag']), inline=True)
    embed.add_field(name="Beschreibung", value=eintrag['beschreibung'], inline=False)
    embed.add_field(name="Gläubiger", value=f"<@{eintrag['glaeubiger_id']}>", inline=True)
    embed.set_footer(text=f"Bezahlt am: {datum_format(eintrag['bezahlt_datum'])}")
    await interaction.response.send_message(embed=embed)


@tree.command(name="schulden_quittieren", description="Alle Schulden zwischen dir und einem anderen User als bezahlt markieren")
@app_commands.describe(glaeubiger="Der User, dem du Geld schuldest")
async def schulden_quittieren(interaction: discord.Interaction, glaeubiger: discord.Member):
    count = db.alle_schulden_bezahlen(str(interaction.user.id), str(glaeubiger.id))
    if count == 0:
        await interaction.response.send_message(
            f"❌ Du hast keine offenen Schulden bei {glaeubiger.mention}.", ephemeral=True)
        return

    embed = discord.Embed(
        title="✅ Schulden beglichen!",
        description=f"{count} Schuld(en) gegenüber {glaeubiger.mention} als bezahlt markiert.",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)


@tree.command(name="meine_schulden", description="Zeige deine offenen Schulden und Forderungen")
async def meine_schulden(interaction: discord.Interaction):
    schulden, forderungen = db.schulden_auflisten(str(interaction.user.id))

    embed = discord.Embed(
        title=f"📋 Schuldenübersicht von {interaction.user.display_name}",
        color=discord.Color.blurple()
    )

    if schulden:
        schulden_text = ""
        for s in schulden:
            schulden_text += f"`#{s['id']}` {format_euro(s['betrag'])} → <@{s['glaeubiger_id']}> — _{s['beschreibung']}_\n"
        schulden_text += f"\n**Gesamt: {sum(s['betrag'] for s in schulden):.2f} €**"
        embed.add_field(name="💸 Du schuldest", value=schulden_text, inline=False)
    else:
        embed.add_field(name="💸 Du schuldest", value="Keine offenen Schulden! 🎉", inline=False)

    if forderungen:
        forderungen_text = ""
        for f in forderungen:
            forderungen_text += f"`#{f['id']}` {format_euro(f['betrag'])} ← <@{f['schuldner_id']}> — _{f['beschreibung']}_\n"
        forderungen_text += f"\n**Gesamt: {sum(f['betrag'] for f in forderungen):.2f} €**"
        embed.add_field(name="💰 Du bekommst", value=forderungen_text, inline=False)
    else:
        embed.add_field(name="💰 Du bekommst", value="Keine offenen Forderungen.", inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="schulden_liste", description="Alle offenen Schulden auf dem Server anzeigen")
async def schulden_liste(interaction: discord.Interaction):
    alle = db.server_schulden_auflisten()

    if not alle:
        await interaction.response.send_message("🎉 Keine offenen Schulden auf dem Server!", ephemeral=True)
        return

    embed = discord.Embed(title="📊 Alle offenen Schulden", color=discord.Color.orange())

    grouped: dict[str, list] = {}
    for s in alle:
        key = f"<@{s['schuldner_id']}> → <@{s['glaeubiger_id']}>"
        grouped.setdefault(key, []).append(s)

    for key, eintraege in list(grouped.items())[:10]:
        text = ""
        for e in eintraege:
            text += f"`#{e['id']}` {format_euro(e['betrag'])} — _{e['beschreibung']}_\n"
        text += f"Gesamt: **{sum(e['betrag'] for e in eintraege):.2f} €**"
        embed.add_field(name=key, value=text, inline=False)

    if len(grouped) > 10:
        embed.set_footer(text=f"... und {len(grouped) - 10} weitere Schuldenpaare")

    await interaction.response.send_message(embed=embed)


@tree.command(name="stats", description="Zeige deine Schulden-Statistiken")
@app_commands.describe(user="Optionaler User (leer = du selbst)")
async def stats(interaction: discord.Interaction, user: discord.Member = None):
    ziel = user or interaction.user
    s = db.stats_berechnen(str(ziel.id))

    netto = s["netto"]
    if netto > 0:
        netto_text = f"🟢 +{netto:.2f} € (du bekommst mehr als du schuldest)"
        color = discord.Color.green()
    elif netto < 0:
        netto_text = f"🔴 {netto:.2f} € (du schuldest mehr als du bekommst)"
        color = discord.Color.red()
    else:
        netto_text = "⚖️ 0.00 € (ausgeglichen)"
        color = discord.Color.greyple()

    embed = discord.Embed(title=f"📈 Statistiken von {ziel.display_name}", color=color)
    embed.add_field(name="💸 Offene Schulden", value=f"{s['total_schulden']:.2f} € ({s['anzahl_offen']} Einträge)", inline=True)
    embed.add_field(name="💰 Offene Forderungen", value=f"{s['total_forderungen']:.2f} € ({s['anzahl_forderungen_offen']} Einträge)", inline=True)
    embed.add_field(name="⚖️ Netto", value=netto_text, inline=False)
    embed.add_field(name="✅ Bereits bezahlt (als Schuldner)", value=f"{s['bezahlt_als_schuldner']:.2f} €", inline=True)
    embed.add_field(name="✅ Bereits erhalten (als Gläubiger)", value=f"{s['bezahlt_als_glaeubiger']:.2f} €", inline=True)

    if s["glaeubiger_stats"]:
        embed.add_field(name="💸 Schulden nach Person",
            value="\n".join(f"• **{n}**: {b:.2f} €" for n, b in s["glaeubiger_stats"].items()), inline=False)
    if s["schuldner_stats"]:
        embed.add_field(name="💰 Forderungen nach Person",
            value="\n".join(f"• **{n}**: {b:.2f} €" for n, b in s["schuldner_stats"].items()), inline=False)

    await interaction.response.send_message(embed=embed)


@tree.command(name="verlauf", description="Zeige deinen Schulden-Verlauf (letzte 10 Einträge)")
@app_commands.describe(user="Optionaler User (leer = du selbst)")
async def verlauf(interaction: discord.Interaction, user: discord.Member = None):
    ziel = user or interaction.user
    eintraege = db.verlauf_abrufen(str(ziel.id), limit=10)

    if not eintraege:
        await interaction.response.send_message(f"📭 Kein Verlauf für {ziel.display_name} gefunden.", ephemeral=True)
        return

    embed = discord.Embed(title=f"🕐 Schulden-Verlauf von {ziel.display_name}", color=discord.Color.blurple())

    for e in eintraege:
        status = "✅ Bezahlt" if e["bezahlt"] else "⏳ Offen"
        andere_id = e["glaeubiger_id"] if e["schuldner_id"] == str(ziel.id) else e["schuldner_id"]
        embed.add_field(
            name=f"`#{e['id']}` {status} | {datum_format(e['datum'])}",
            value=f"<@{andere_id}> **{e['betrag']:.2f} €** — _{e['beschreibung']}_",
            inline=False
        )

    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="rangliste", description="Zeige die Schulden-Rangliste des Servers")
async def rangliste_cmd(interaction: discord.Interaction):
    rang = db.rangliste()

    if not rang:
        await interaction.response.send_message("📭 Keine Daten für die Rangliste vorhanden.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🏆 Schulden-Rangliste",
        description="Sortiert nach Netto-Guthaben",
        color=discord.Color.gold()
    )

    for i, eintrag in enumerate(rang[:10], 1):
        netto = eintrag["netto"]
        emoji = "🟢" if netto > 0 else ("🔴" if netto < 0 else "⚖️")
        embed.add_field(name=f"{i}. {eintrag['name']}", value=f"{emoji} {netto:+.2f} €", inline=True)

    await interaction.response.send_message(embed=embed)


@tree.command(name="hilfe", description="Zeige alle verfügbaren Befehle")
async def hilfe(interaction: discord.Interaction):
    embed = discord.Embed(title="📖 Schulden-Tracker Hilfe", description="Alle verfügbaren Befehle:", color=discord.Color.blurple())
    befehle = [
        ("/schuld_add", "Neue Schuld eintragen"),
        ("/schuld_bezahlt", "Einzelne Schuld per ID als bezahlt markieren"),
        ("/schulden_quittieren", "Alle Schulden gegenüber einer Person begleichen"),
        ("/meine_schulden", "Deine offenen Schulden & Forderungen"),
        ("/schulden_liste", "Alle offenen Schulden auf dem Server"),
        ("/stats", "Statistiken anzeigen"),
        ("/verlauf", "Letzte 10 Einträge im Verlauf"),
        ("/rangliste", "Server-Rangliste nach Netto-Guthaben"),
        ("/hilfe", "Diese Hilfemeldung"),
    ]
    for name, beschreibung in befehle:
        embed.add_field(name=name, value=beschreibung, inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


bot.run(TOKEN)
