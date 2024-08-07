#INSTALL pynacl, discord, yt_dlp using the terminal
#you need to put your token where it says 'TOKEN HERE'
import discord
from discord import PCMVolumeTransformer, FFmpegPCMAudio
from discord.ext import commands
import yt_dlp
import asyncio
import speech_recognition as sr
from typing import Optional
from pydub import AudioSegment

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True

recognizer = sr.Recognizer()
microphone = sr.Microphone()

FFMPEG_OPTIONS = {'options': '-vn'}
YDL_OPTIONS = {'format': 'bestaudio', 'noplaylist': True}

class AudioProcessor(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.voice_client = None

    async def on_voice_state_update(self, member, before, after):
        if member == self.user:
            return

        if after.channel is not None and (before.channel != after.channel):
            self.voice_client = await after.channel.connect()

        elif before.channel is not None and (before.channel != after.channel):
            if self.voice_client and len(before.channel.members) == 1:  # Only bot left
                await self.voice_client.disconnect()
                self.voice_client = None

class MusicBot(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.queue = []
        self.listening = False
        self.voice_client = None
        
    @commands.command()
    async def play(self, ctx, *, search):
        voice_channel = ctx.author.voice.channel if ctx.author.voice else None
        if not voice_channel:
            return await ctx.send("You're not in a voice channel!")
        if not ctx.voice_client or not ctx.voice_client.is_connected():
            await voice_channel.connect()
        async with ctx.typing():
            with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                info = ydl.extract_info(f"ytsearch:{search}", download=False)
                if 'entries' in info:
                    info = info['entries'][0]
                url = info['url']
                title = info['title']
                self.queue.append((url, title))
                await ctx.send(f'Added to queue: **{title}**')
        if not ctx.voice_client.is_playing():
            await self.play_next(ctx)
            
    async def play_next(self, ctx):
        if self.queue:
            url, title = self.queue.pop(0)
            source = await discord.FFmpegOpusAudio.from_probe(url, **FFMPEG_OPTIONS)
            if ctx.voice_client is not None:  # Ensure voice_client is not None
                ctx.voice_client.play(source, after=lambda _: self.client.loop.create_task(self.play_next(ctx)))
                await ctx.send(f'Now playing: **{title}**')
            else:
                await ctx.send("Voice client is not connected.")
        elif ctx.voice_client is not None and not ctx.voice_client.is_playing():
            await ctx.send("Queue is empty!")
            
    @commands.command()
    async def skip(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await ctx.send("Skipped ⏭")
        else:
            await ctx.send("No song is currently playing.")

    @commands.command()
    async def join(self, ctx):
        voice_channel = ctx.author.voice.channel if ctx.author.voice else None
        if not ctx.voice_client:
            await voice_channel.connect()
            await ctx.send("Joining!")
        else:
            await ctx.send("I'm already in your channel!")

    @commands.command()
    async def leave(self, ctx):
        if ctx.voice_client:
            self.listening = False
            await ctx.voice_client.disconnect()
            await ctx.send("Leaving!")
        else:
            await ctx.send("I'm not in the voice channel")

    async def recognize_speech(self, ctx):
        with microphone as source:
            recognizer.adjust_for_ambient_noise(source)
            #await ctx.send("Listening...")
            audio = recognizer.listen(source)
            try:
                command = recognizer.recognize_google(audio)
                #await ctx.send(f"Recognized: {command}")
                return command
            except sr.UnknownValueError:
                return None  # Return None on unknown value error
            except sr.RequestError as e:
                await ctx.send(f"Could not request results; {e}")
                return None

    
    @commands.command()
    async def continuous_listen(self, ctx):
        self.listening = True
        await ctx.send("Started listening for voice commands.")
        while self.listening:
            command = await self.recognize_speech(ctx)
            if command:
                command = command.lower()
                if "play" in command and ("bot" in command):
                    song = command.replace("play", "").replace("bot", "").strip()
                    song = song + " official audio"
                    await self.play(ctx, search=song)
                if "skip" in command:
                    await self.skip(ctx)
            await asyncio.sleep(1)  # Add a small delay to avoid rapid looping

    @commands.command()
    async def listen(self, ctx):
        if not self.listening:
            self.client.loop.create_task(self.continuous_listen(ctx))
        else:
            await ctx.send("Already listening for voice commands.")

    @commands.command()
    async def stop_listening(self, ctx):
        self.listening = False
        await ctx.send("Stopped listening for voice commands.")

    async def capture_audio(self, voice_client):
        # Ensure ffmpeg is properly set up to capture audio
        if voice_client:
            audio_source = discord.PCMAudio('your_audio_source_path', pipe=True)  # Specify the correct audio source
            return audio_source
        return None

client = commands.Bot(command_prefix="!", intents=intents)
async def main():
    await client.add_cog(MusicBot(client))
    await client.start('TOKEN')
    
asyncio.run(main())
