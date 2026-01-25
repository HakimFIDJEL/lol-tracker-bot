import discord
import os
from dotenv import load_dotenv
import requests
import datetime
from discord.ext import tasks

# Load environment variables
load_dotenv()
ENVIRONNEMENT = os.getenv('ENVIRONMENT', 'testing')

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
RIOT_API_KEY = os.getenv('RIOT_API_KEY')
USER_GAMENAME = os.getenv('USER_GAMENAME')
USER_TAGLINE = os.getenv('USER_TAGLINE')

DISCORD_CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL_ID'))
DISCORD_USER_TO_PING_ID = os.getenv('DISCORD_USER_TO_PING_ID')

LAST_MATCH_ID = None

# --- Fonctions Riot ---

def get_puuid(gameName, tagLine):
    try:
        response = requests.get(
            f'https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{gameName}/{tagLine}',
            headers={'X-Riot-Token': RIOT_API_KEY}
        )
        return response.json().get('puuid')
    except:
        return None

def get_last_match_id(puuid):
    try:
        response = requests.get(
            f'https://europe.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids',
            params={'count': 1},
            headers={'X-Riot-Token': RIOT_API_KEY}
        )
        return response.json()[0]
    except:
        return None

def generate_score(p):
    duration_min = max(1, p.get('gameDuration', 0) / 60)
    k, d, a = p.get('kills', 0), p.get('deaths', 0), p.get('assists', 0)
    kda_ratio = (k + a) / max(1, d)
    score_kda = min(40, kda_ratio * 8)
    pos = p.get('individualPosition', 'UNKNOWN')
    if pos == 'UTILITY':
        vision_min = p.get('visionScore', 0) / duration_min
        score_res = min(30, (vision_min / 1.5) * 30)
    else:
        cs = p.get('totalMinionsKilled', 0) + p.get('neutralMinionsKilled', 0)
        score_res = min(30, (cs / duration_min / 8) * 30)
    kp = p.get('challenges', {}).get('killParticipation', 0)
    score_impact = min(30, kp * 50)
    final = score_kda + score_res + score_impact + (10 if p.get('win') else -10)
    return max(0, min(100, int(final)))

def get_game_mode(qId):
    return {420:'Solo / Duo', 440:'Flex 5v5', 400:'Draft', 450:'ARAM'}.get(qId, 'Autre')

def get_lane(lane):
    return {'TOP':'Toplane','JUNGLE':'Jungle','MIDDLE':'Midlane','BOTTOM':'Adc','UTILITY':'Support'}.get(lane, 'Inconnue')

def get_match_details(matchId, puuid):
    try:
        res = requests.get(f'https://europe.api.riotgames.com/lol/match/v5/matches/{matchId}', headers={'X-Riot-Token': RIOT_API_KEY}).json()
        for p in res['info']['participants']:
            if p['puuid'] == puuid:
                return {
                    'assists': p['assists'], 'deaths': p['deaths'], 'kills': p['kills'],
                    'score': generate_score(p), 'championName': p['championName'],
                    'lane': get_lane(p['individualPosition']), 'win': p['win'],
                    'queueId': get_game_mode(res['info']['queueId']),
                    'gameDuration': res['info']['gameDuration'] // 60,
                    'gameEndTimestamp': datetime.datetime.fromtimestamp(res['info']['gameEndTimestamp']/1000).strftime("%d/%m/%Y %H:%M"),
                    'gameEndedInSurrender': p['gameEndedInSurrender'] or p['gameEndedInEarlySurrender']
                }
    except: return None

# --- Fonctions Discord ---

async def send_match_report(matchDetails):
    channel = client.get_channel(DISCORD_CHANNEL_ID)
    if not channel: return

    color = 0x2ecc71 if matchDetails['win'] else 0xe74c3c
    title = "🏆 Victoire !" if matchDetails['win'] else "💀 Défaite !"

    embed = discord.Embed(title=title, color=color)
    embed.add_field(name=f"Champion joué", value=matchDetails['championName'], inline=True)
    embed.add_field(name="Mode de jeu", value=matchDetails['queueId'], inline=True)
    embed.add_field(name="Poste", value=matchDetails['lane'], inline=True)
    embed.add_field(name="Score", value=f"**{matchDetails['score']}/100**", inline=True)
    embed.add_field(name="KDA", value=f"{matchDetails['kills']}/{matchDetails['deaths']}/{matchDetails['assists']}", inline=True)
    embed.add_field(name="Durée", value=f"{matchDetails['gameDuration']} min", inline=True)

    if(matchDetails['win'] == False):
        embed.add_field(
            name="FF ?", 
            value="Oui" if matchDetails['gameEndedInSurrender'] else "Non", 
            inline=True
        )
    
    embed.set_footer(text=f"Fin : {matchDetails['gameEndTimestamp']}")

    content = f"<@{DISCORD_USER_TO_PING_ID}>" if DISCORD_USER_TO_PING_ID else None
    await channel.send(content=content, embed=embed)


# --- Initialisation Bot ---

intents = discord.Intents.default()
client = discord.Client(intents=intents)

@tasks.loop(minutes=1.0)
async def monitor_lol():
    global LAST_MATCH_ID
    puuid = get_puuid(USER_GAMENAME, USER_TAGLINE)
    if not puuid: return
    
    m_id = get_last_match_id(puuid)
    if not m_id or m_id == LAST_MATCH_ID:
        return

    details = get_match_details(m_id, puuid)
    if details:
        if ENVIRONNEMENT == 'testing':
            print(f"[TESTING] Nouveau match détecté : {m_id}")
        else:
            await send_match_report(details)
            print(f"Match {m_id} envoyé !")
        LAST_MATCH_ID = m_id

@client.event
async def on_ready():
    print(f'Bot connecté en tant que {client.user} !')
    
    print("Surveillance active : vérification du dernier match en cours...")
    
    if not monitor_lol.is_running():
        print('Démarrage de la surveillance des matchs LoL...')
        monitor_lol.start()

client.run(DISCORD_TOKEN)