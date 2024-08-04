import discord
from discord.ext import commands
import os
import asyncio
import yt_dlp
from dotenv import load_dotenv
import urllib.parse, urllib.request, re

def run_bot():
    load_dotenv()
    TOKEN = os.getenv('discord_token')
    intents = discord.Intents.default()
    intents.message_content = True
    client = commands.Bot(command_prefix=".", intents=intents)

    queues = {}
    voice_clients = {}
    youtube_base_url = 'https://www.youtube.com/'
    youtube_results_url = youtube_base_url + 'results?'
    youtube_watch_url = youtube_base_url + 'watch?v='
    yt_dl_options = {"format": "bestaudio/best"}
    ytdl = yt_dlp.YoutubeDL(yt_dl_options)

    #ffmpeg_options = {'options': '-vn -filter:a "volume=0.6"'}
    ffmpeg_options = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5','options': '-vn -filter:a "volume=0.5"'}


    @client.event
    async def on_ready():
        print(f'{client.user} is now jamming')

    @client.command(name="play")
    async def play(ctx, *, link):
        if ctx.guild.id not in queues:
            queues[ctx.guild.id] = []

        if ctx.guild.id in voice_clients:
            voice_client = voice_clients[ctx.guild.id]
        else:
            try:
                voice_client = await ctx.author.voice.channel.connect()
                voice_clients[ctx.guild.id] = voice_client
            except Exception as e:
                print(e)
                await ctx.send("Could not connect to the voice channel.")
                return

        if youtube_base_url not in link:
            query_string = urllib.parse.urlencode({'search_query': link})
            content = urllib.request.urlopen(youtube_results_url + query_string)
            search_results = re.findall(r'/watch\?v=(.{11})', content.read().decode())
            if not search_results:
                await ctx.send("No search results found.")
                return
            link = youtube_watch_url + search_results[0]

        try:
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(link, download=False))
            song = data['url']
            player = discord.FFmpegOpusAudio(song, **ffmpeg_options)
            if not voice_client.is_playing():
                voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), client.loop))
            else:
                await ctx.send("Already playing. Added to queue.")
                queues[ctx.guild.id].append(link)
        except Exception as e:
            print(e)
            await ctx.send("An error occurred while playing the song.")
    

    
    @client.command(name="skip")
    async def play_next(ctx):
        if queues[ctx.guild.id]:
            link = queues[ctx.guild.id].pop(0)
            await play(ctx, link=link)
        else:
            await ctx.send("Queue is empty.")

    @client.command(name="clear_kwee")
    async def clear_queue(ctx):
        if ctx.guild.id in queues:
            queues[ctx.guild.id].clear()
            await ctx.send("Queue cleared!")
        else:
            await ctx.send("There is no queue to clear")

    @client.command(name="pause")
    async def pause(ctx):
        if ctx.guild.id in voice_clients and voice_clients[ctx.guild.id].is_playing():
            voice_clients[ctx.guild.id].pause()
            await ctx.send("Playback paused.")
        else:
            await ctx.send("No audio is currently playing.")

    @client.command(name="resume")
    async def resume(ctx):
        if ctx.guild.id in voice_clients and voice_clients[ctx.guild.id].is_paused():
            voice_clients[ctx.guild.id].resume()
            await ctx.send("Playback resumed.")
        else:
            await ctx.send("No audio is currently paused.")

    @client.command(name="boom")
    async def stop(ctx):
        if ctx.guild.id in voice_clients:
            voice_clients[ctx.guild.id].stop()
            await voice_clients[ctx.guild.id].disconnect()
            del voice_clients[ctx.guild.id]
            await ctx.send("Playback stopped and disconnected.")
        else:
            await ctx.send("Not connected to a voice channel.")

    @client.command(name="kwee")
    async def queue(ctx, *, url):
        if ctx.guild.id not in queues:
            queues[ctx.guild.id] = []
        queues[ctx.guild.id].append(url)
        await ctx.send("Added to queue!")
    
    @client.command(name="check_kwee")
    async def check_queue(ctx):
        if ctx.guild.id in queues and queues[ctx.guild.id]:
            queue_list = "\n".join([f"{i + 1}. {url}" for i, url in enumerate(queues[ctx.guild.id])])
            await ctx.send(f"Current Queue:\n{queue_list}")
        else:
            await ctx.send("The queue is currently empty.")
    
    @client.command(name="info")
    async def help_command(ctx):
        help_text = """
    **Available Commands:**
    **.play [link]** - Play a song from a YouTube link or search query.
    **.kwee [url]** - Add a song to the queue from a YouTube link.
    **.skip** - Skip the currently playing song and move to the next one.
    **.clear_kwee** - Clear the current queue of songs.
    **.pause** - Pause the currently playing song.
    **.resume** - Resume the paused song.
    **.boom** - Stop the current song and disconnect from the voice channel.
    **.check_kwee** - Display the current queue of songs.
                    """
        await ctx.send(help_text)


    client.run(TOKEN)

