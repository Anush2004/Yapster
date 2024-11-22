import asyncio
import grpc
import time
import sys
import os
pwd = os.getcwd()
pwd = pwd.split('/')
pwd = '/'.join(pwd[:-1])
pwd = pwd + '/protofiles'
sys.path.append(pwd)
import broker_pb2
import broker_pb2_grpc

class NapsterClient:
    def __init__(self, client_id, server_address='192.168.2.220:50051', music_dir="music"):
        self.client_id = client_id
        self.server_address = server_address
        self.music_dir = music_dir
        self.local_songs = set()
        self.external_songs = set()

    async def heartbeat(self, stub):
        while True:
            try:
                response = await stub.Heartbeat(broker_pb2.ClientInfo(client_id=self.client_id))
                if response.success:
                    print(f"Heartbeat sent for client {self.client_id}.")
                else:
                    print(f"Heartbeat failed for client {self.client_id}.")
            except Exception as e:
                print(f"Error sending heartbeat: {e}")
            await asyncio.sleep(5)  # Send heartbeat every 5 seconds

    async def initialize_client(self, stub):
        # Load initial songs from the music directory
        self.local_songs = set(os.listdir(self.music_dir))
        async def song_update_stream():
            for song_name in self.local_songs:
                yield broker_pb2.SongUpdate(client_id=self.client_id, song_name=song_name)
        try:
            async for update in stub.InitializeClient(song_update_stream()):
                if update.type == "error":
                    print(f"Error during initialization: {update.song_name}")
                    return
                if update.type == "add":
                    self.external_songs.add(update.song_name)
        except Exception as e:
            print(f"Error during initialization: {e}")

    async def leave(self, stub):
        try:
            response = await stub.Leave(broker_pb2.ClientInfo(client_id=self.client_id))
            print(f"Leave response: {response.success}")
        except Exception as e:
            print(f"Error during leave: {e}")

    async def add_song(self, stub, song_name):
        try:
            response = await stub.AddSong(broker_pb2.SongUpdate(client_id=self.client_id, song_name=song_name))
            print(f"Add song response: {response.message}")
        except Exception as e:
            print(f"Error adding song: {e}")

    async def delete_song(self, stub, song_name):
        try:
            response = await stub.DeleteSong(broker_pb2.SongUpdate(client_id=self.client_id, song_name=song_name))
            print(f"Delete song response: {response.message}")
        except Exception as e:
            print(f"Error deleting song: {e}")

    async def song_request(self, stub, song_name):
        try:
            response = await stub.SongRequest(broker_pb2.SongRequestMessage(client_id=self.client_id, song_name=song_name))
            if response.found:
                print(f"Song '{song_name}' found on client: {response.client_id}.")
            else:
                print(f"Song '{song_name}' not found. Message: {response.message}")
        except Exception as e:
            print(f"Error requesting song: {e}")

    async def pull_updates(self, stub):
        try:
            async for update in stub.PullUpdates(broker_pb2.ClientInfo(client_id=self.client_id)):
                print(f"Received update: {update.type} - {update.song_name}")
                if(update.type == "add"):
                    self.external_songs.add(update.song_name)
                elif(update.type == "delete"):
                    self.external_songs.remove(update.song_name)
        except Exception as e:
            print(f"Error pulling updates: {e}")

    async def monitor_directory(self, stub):
        """Monitors the music directory for changes and synchronizes with the broker."""
        while True:
            current_songs = set(os.listdir(self.music_dir))
            new_songs = current_songs - self.local_songs
            deleted_songs = self.local_songs - current_songs

            for song in new_songs:
                await self.add_song(stub, song)
            for song in deleted_songs:
                await self.delete_song(stub, song)

            self.local_songs = current_songs
            await asyncio.sleep(2)  # Check for changes every 2 seconds

    async def command_interface(self, stub):
        """Handles interactive commands from the user."""
        print("Interactive mode started. Type 'help' for a list of commands.")
        while True:
            command = input("> ").strip().lower()
            if command == "list":
                print("Current songs in your music directory:")
                for song in sorted(self.local_songs):
                    print(f"- {song}")
            elif command.startswith("request "):
                song_name = command.split(" ", 1)[1]
                await self.song_request(stub, song_name)
            elif command == "help":
                print("Available commands:")
                print("  list          - List all songs in your music directory")
                print("  request <song> - Request a song from the broker")
                print("  help          - Show this help message")
                print("  exit          - Exit the client")
            elif command == "exit":
                print("Exiting client...")
                await self.leave(stub)
                break
            else:
                print("Unknown command. Type 'help' for a list of commands.")

    async def run(self):
        async with grpc.aio.insecure_channel(self.server_address) as channel:
            stub = broker_pb2_grpc.NapsterServiceStub(channel)

            # Initialize client
            await self.initialize_client(stub)

            # Start the heartbeat in the background
            asyncio.create_task(self.heartbeat(stub))

            # Start pulling updates in the background
            asyncio.create_task(self.pull_updates(stub))

            # Monitor the directory for changes
            asyncio.create_task(self.monitor_directory(stub))

            # Start the interactive command interface
            await self.command_interface(stub)


if __name__ == "__main__":
    client_id = input("Enter client ID: ")
    music_directory = "music"

    if not os.path.exists(music_directory):
        print("Music directory not found. Please create a 'music' directory in the current folder.")
        sys.exit(1)


    client = NapsterClient(client_id, music_dir=music_directory)
    asyncio.run(client.run())
