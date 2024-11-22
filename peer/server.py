import asyncio
import os

server_folder = "."

async def handle_client(reader, writer):
    addr = writer.get_extra_info('peername')
    print(f"Connection established with {addr}")
    
    try:
        # Receive initial connection request
        init_request = await reader.read(1024)
        if init_request.decode() != "CONNECT":
            print("Invalid connection request")
            writer.write(b"ERROR: Invalid connection request")
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            return
        
        writer.write(b"ACK: Connection established")
        await writer.drain()
        
        # Receive file request
        file_request = await reader.read(1024)
        file_request = os.path.join(server_folder, file_request.decode().strip())
        print(f"Client requested file: {file_request}")
        
        if os.path.exists(file_request):
            writer.write(b"ACK: File found. Sending file...")
            await writer.drain()
            
            # Send the file in chunks
            with open(file_request, 'rb') as file:
                while chunk := file.read(1024):
                    writer.write(chunk)
                    await writer.drain()
            print("File sent successfully.")
        else:
            writer.write(b"ERROR: File not found")
            await writer.drain()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        writer.close()
        await writer.wait_closed()

async def start_server(host='0.0.0.0', port=12345):
    server = await asyncio.start_server(handle_client, host, port)
    addr = server.sockets[0].getsockname()
    print(f"Server is listening on {addr}")
    
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(start_server())
