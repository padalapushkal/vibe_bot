from discord import Embed, Color
import discord
from discord.ext import commands
import os
import asyncio
import yt_dlp
from dotenv import load_dotenv
import urllib.parse, urllib.request, re
import math

PAGE_SIZE = 5  # Number of items per page
LEFT_ARROW = '⬅️'
RIGHT_ARROW = '➡️'
STOP_SIGN = '🛑'

def run_bot():
    load_dotenv()
    TOKEN = os.getenv('discord_token')
    intents = discord.Intents.default()
    intents.message_content = True
    client = commands.Bot(command_prefix=".", intents=intents)

    queues = {}
    voice_clients = {}
    current_songs = {}
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

    async def play_next(ctx):
        if ctx.guild.id in queues and queues[ctx.guild.id]:
            link = queues[ctx.guild.id].pop(0)  
            await play(ctx, link=link)
        else:
            await ctx.send("Queue is empty.")

    @client.command(name="play", help="Play a song from a YouTube link or search query.")
    @commands.cooldown(1, 5, commands.BucketType.guild) # to make sure it doesn't get spammed. 
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
            song_title = data.get('title', 'Unknown Title')
            song_duration = data.get('duration', 0)
            song_duration_str = f"{song_duration // 60}:{song_duration % 60:02d}"
            player = discord.FFmpegOpusAudio(song, **ffmpeg_options)
            current_songs[ctx.guild.id] = {
                'title': song_title,
                'url': link,
                'duration': song_duration_str
            }
            if not voice_client.is_playing():
                voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), client.loop))
            else:
                await ctx.send("Current Song in progress, Added to queue.")
                queues[ctx.guild.id].append(link)
        except Exception as e:
            print(e)
            await ctx.send("An error occurred while playing the song.")
    
    @client.command(name="kwee", help="Add a song or playlist to the queue from a YouTube link.")
    async def queue(ctx, *, url):
        if ctx.guild.id not in queues:
            queues[ctx.guild.id] = []
        queues[ctx.guild.id].append(url)
        await ctx.send("Added to queue!")

    @client.command(name="current", help="Display the details of the current song.")
    async def current(ctx):     
        if ctx.guild.id in current_songs:
            song_info = current_songs[ctx.guild.id]
            embed = Embed(title="Now Playing", color=Color.green())
            embed.add_field(name="Title", value=song_info['title'])
            embed.add_field(name="URL", value=song_info['url'])
            embed.add_field(name="Duration", value=song_info['duration'])
            await ctx.send(embed=embed)
        else:
            await ctx.send("No song is currently playing.")

    @client.command(name="skip", help="Skip the currently playing song and move to the next one.")
    async def skip(ctx):
        if ctx.guild.id in voice_clients:
            voice_client = voice_clients[ctx.guild.id]
            if voice_client.is_playing():
                voice_client.stop()
                await asyncio.sleep(1)  # Small delay to ensure stop completes

            if queues[ctx.guild.id]:
                next_track = queues[ctx.guild.id].pop(0)
                song_url = next_track['url']
                song_title = next_track['title']
                song_duration_str = next_track['duration']
                player = discord.FFmpegOpusAudio(song_url, **ffmpeg_options)
                current_songs[ctx.guild.id] = {
                    'title': song_title,
                    'url': song_url,
                    'duration': song_duration_str
                }
                voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(skip(ctx), client.loop))
                await ctx.send(f"Now playing: {song_title}")
            else:
                await ctx.send("Queue is empty.")
        else:
            await ctx.send("Bot is not connected to a voice channel.")

    @client.command(name="clear_kwee", help="Clear the current queue of songs.")
    async def clear_queue(ctx):
        if ctx.guild.id in queues:
            queues[ctx.guild.id].clear()
            await ctx.send("Queue cleared!")
        else:
            await ctx.send("There is no queue to clear")

    @client.command(name="pause", help="Pause the currently playing song.")
    async def pause(ctx):
        if ctx.guild.id in voice_clients and voice_clients[ctx.guild.id].is_playing():
            voice_clients[ctx.guild.id].pause()
            await ctx.send("Playback paused.")
        else:
            await ctx.send("No audio is currently playing.")

    @client.command(name="resume", help="Resume the paused song.")
    async def resume(ctx):
        if ctx.guild.id in voice_clients and voice_clients[ctx.guild.id].is_paused():
            voice_clients[ctx.guild.id].resume()
            await ctx.send("Playback resumed.")
        else:
            await ctx.send("No audio is currently paused.")

    @client.command(name="boom", help="Stop the current song and disconnect from the voice channel.")
    async def stop(ctx):
        if ctx.guild.id in voice_clients:
            voice_clients[ctx.guild.id].stop()
            await voice_clients[ctx.guild.id].disconnect()
            del voice_clients[ctx.guild.id]
            await ctx.send("Playback stopped and disconnected.")
        else:
            await ctx.send("Not connected to a voice channel.")

    # @client.command(name="check_kwee", help="Display the current queue of songs.")
    # async def check_queue(ctx):
    #     if ctx.guild.id in queues and queues[ctx.guild.id]:
    #         queue_list = "\n".join([f"{i + 1}. {url}" for i, url in enumerate(queues[ctx.guild.id])])
    #         await ctx.send(f"Current Queue:\n{queue_list}")
    #     else:
    #         await ctx.send("The queue is currently empty.")

    @client.command(name="check_kwee", help="Display the current queue of songs.")
    async def check_queue(ctx):
        if ctx.guild.id not in queues or not queues[ctx.guild.id]:
            await ctx.send("The queue is currently empty.")
            return
        queue = queues[ctx.guild.id]
        num_pages = math.ceil(len(queue) / PAGE_SIZE)

        def get_page_embed(page_number):
            start_index = page_number * PAGE_SIZE
            end_index = min(start_index + PAGE_SIZE, len(queue))
            queue_list = "\n".join([f"{i + 1}. {url}" for i, url in enumerate(queue[start_index:end_index], start=start_index)])
            # queue_list = "\n".join([
            # f"{i + 1}. [{item['title']}]({item['url']})"
            # for i, item in enumerate(queue[start_index:end_index], start=start_index)
            # ])
            # return f"Page {page_number + 1}/{num_pages}\n{queue_list}"
            embed = discord.Embed(
            title="Current Queue",
            description=f"Page {page_number + 1}/{num_pages}\n{queue_list}",
            color=discord.Color.blue()
            )
            return embed
        
        current_page = 0
        # message = await ctx.send(get_page(current_page))
        embed_message = await ctx.send(embed=get_page_embed(current_page))
        if num_pages > 1:
            await embed_message.add_reaction(LEFT_ARROW)
            await embed_message.add_reaction(RIGHT_ARROW)
            await embed_message.add_reaction(STOP_SIGN)
        
        def check(reaction, user):
            return user != client.user and str(reaction.emoji) in [LEFT_ARROW, RIGHT_ARROW, STOP_SIGN]
        
        while True:
            try:
                reaction, user = await client.wait_for('reaction_add', timeout=60.0, check=check)
                if str(reaction.emoji) == LEFT_ARROW:
                    if current_page > 0:
                        current_page -= 1
                elif str(reaction.emoji) == RIGHT_ARROW:
                    if current_page < num_pages - 1:
                        current_page += 1
                elif str(reaction.emoji) == STOP_SIGN:
                    break

                # await message.edit(content=get_page(current_page))
                # await message.remove_reaction(reaction.emoji, user)
                await embed_message.edit(embed=get_page_embed(current_page))
                await embed_message.remove_reaction(reaction.emoji, user)
            except asyncio.TimeoutError:
                await embed_message.clear_reactions()
                break

    @client.command(name="info", help = "Show a list of all commands or detailed information about a specific command")
    async def help_command(ctx):
        # Create an embed
        embed = Embed(
            title="Bot Commands",
            color=Color.blue()
        )
        for command in client.commands:
            if not command.hidden:  
                description = command.help or "No description available."
                embed.add_field(name=f".{command.name}", value=description, inline=False)

        embed.set_footer(text="Use .help [command] for more details on a specific command.")
        
        await ctx.send(embed=embed)

    client.run(TOKEN)

