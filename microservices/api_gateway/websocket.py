import asyncio
import logging

import websockets
from fastapi import WebSocket, WebSocketDisconnect
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger("api_gateway.websocket")


async def forward_websocket(client_ws: WebSocket, target_url: str) -> None:
    """
    Proxies a WebSocket connection from the client to a target upstream URL.
    Handles handshake, subprotocol negotiation, and bidirectional message pumping.
    """
    try:
        # Extract headers (excluding problematic ones that interfere with handshake)
        extra_headers = {}
        for key, value in client_ws.headers.items():
            if key.lower() not in [
                "host",
                "sec-websocket-key",
                "sec-websocket-version",
                "connection",
                "upgrade",
                "sec-websocket-extensions",
            ]:
                extra_headers[key] = value

        # Extract subprotocols requested by the client
        subprotocols = client_ws.scope.get("subprotocols", [])

        # Connect to upstream WebSocket server
        async with websockets.connect(
            target_url,
            extra_headers=extra_headers,
            subprotocols=subprotocols,
        ) as upstream_ws:
            # Select the subprotocol accepted by upstream
            accepted_subprotocol = upstream_ws.subprotocol

            # Accept client connection with the same subprotocol
            await client_ws.accept(subprotocol=accepted_subprotocol)

            async def client_to_upstream():
                try:
                    while True:
                        msg = await client_ws.receive()
                        if msg["type"] == "websocket.receive":
                            if "text" in msg:
                                await upstream_ws.send(msg["text"])
                            elif "bytes" in msg:
                                await upstream_ws.send(msg["bytes"])
                        elif msg["type"] == "websocket.disconnect":
                            break
                except (WebSocketDisconnect, ConnectionClosed):
                    pass
                except Exception as e:
                    logger.error(f"Error client->upstream proxy: {e}")

            async def upstream_to_client():
                try:
                    async for msg in upstream_ws:
                        if isinstance(msg, str):
                            await client_ws.send_text(msg)
                        else:
                            await client_ws.send_bytes(msg)
                except (WebSocketDisconnect, ConnectionClosed):
                    pass
                except Exception as e:
                    logger.error(f"Error upstream->client proxy: {e}")

            # Run both tasks concurrently until one finishes or fails
            # We use wait with FIRST_COMPLETED to ensure if one side closes, we close the other
            tasks = [
                asyncio.create_task(client_to_upstream()),
                asyncio.create_task(upstream_to_client()),
            ]
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

            # Cancel pending tasks
            for task in pending:
                task.cancel()

    except Exception as e:
        logger.error(f"WebSocket proxy connection failed to {target_url}: {e}")
        # Attempt to close with internal error if strictly necessary,
        # but often the connection is already dead or not accepted.
        try:
            await client_ws.close(code=1011)
        except Exception:
            pass
