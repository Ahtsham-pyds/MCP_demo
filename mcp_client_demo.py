"""
mcp_client_demo.py

A minimal asyncio-based demo MCP (Message Control Protocol) client.
Protocol assumptions (for demo purposes):
- Each message is framed as: 4-byte big-endian unsigned int length, followed by UTF-8 JSON payload.
- Requests and responses are JSON objects with at least a "type" field.
This client demonstrates connect, send, receive, heartbeat, and graceful shutdown.
"""

import asyncio
import json
import struct
from typing import Any, Dict, Optional

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9000
LENGTH_PREFIX = ">I"  # big-endian unsigned int (4 bytes)


class MCPClient:
    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, heartbeat_interval: float = 10.0):
        self.host = host
        self.port = port
        self.heartbeat_interval = heartbeat_interval
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._receive_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._response_futures: Dict[str, asyncio.Future] = {}
        self._msg_id_counter = 0
        self._closed = False

    async def connect(self, timeout: float = 5.0) -> None:
        if self._reader and not self._reader.at_eof():
            return
        self._reader, self._writer = await asyncio.wait_for(asyncio.open_connection(self.host, self.port), timeout)
        self._receive_task = asyncio.create_task(self._reader_loop())
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def close(self) -> None:
        self._closed = True
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._receive_task:
            self._receive_task.cancel()
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
        # Fail any pending futures
        for fut in self._response_futures.values():
            if not fut.done():
                fut.set_exception(ConnectionError("Client closed"))

    async def send_request(self, payload: Dict[str, Any], timeout: float = 5.0) -> Dict[str, Any]:
        """
        Send a JSON request and wait for a response associated with the generated message id.
        The server is expected to echo back a response with {"reply_to": <msg_id>, ...}.
        """
        if self._closed:
            raise ConnectionError("Client is closed")
        if self._writer is None:
            await self.connect()

        msg_id = self._next_msg_id()
        payload = dict(payload)  # copy
        payload.setdefault("type", "request")
        payload["msg_id"] = msg_id

        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._response_futures[str(msg_id)] = fut

        await self._write_message(payload)

        try:
            response = await asyncio.wait_for(fut, timeout)
            return response
        finally:
            self._response_futures.pop(str(msg_id), None)

    async def _write_message(self, obj: Dict[str, Any]) -> None:
        if self._writer is None:
            raise ConnectionError("Not connected")
        data = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        prefix = struct.pack(LENGTH_PREFIX, len(data))
        self._writer.write(prefix + data)
        await self._writer.drain()

    async def _reader_loop(self) -> None:
        assert self._reader is not None
        try:
            while not self._reader.at_eof():
                msg = await self._read_message()
                if msg is None:
                    break
                await self._handle_message(msg)
        except asyncio.CancelledError:
            pass
        except Exception:
            # In a real client you'd add logging and reconnection logic here.
            pass
        finally:
            # Fail any outstanding futures
            for fut in self._response_futures.values():
                if not fut.done():
                    fut.set_exception(ConnectionError("Connection lost"))
 
    async def _read_message(self) -> Optional[Dict[str, Any]]:
        assert self._reader is not None
        # Read length prefix
        prefix_bytes = await self._read_exact(4)
        if prefix_bytes is None:
            return None
        (length,) = struct.unpack(LENGTH_PREFIX, prefix_bytes)
        if length == 0:
            return None
        body = await self._read_exact(length)
        if body is None:
            return None
        try:
            return json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            return None

    async def _read_exact(self, n: int) -> Optional[bytes]:
        assert self._reader is not None
        try:
            data = await self._reader.readexactly(n)
            return data
        except (asyncio.IncompleteReadError, ConnectionResetError):
            return None

    async def _handle_message(self, msg: Dict[str, Any]) -> None:
        # Simple handling: if message has "reply_to", complete corresponding future.
        reply_to = msg.get("reply_to")
        if reply_to is not None:
            fut = self._response_futures.get(str(reply_to))
            if fut and not fut.done():
                fut.set_result(msg)
                return
        # Otherwise, handle notifications or other types (demo: print).
        # In a library you'd expose a callback or queue to the user.
        print("Notification:", msg)

    async def _heartbeat_loop(self) -> None:
        try:
            while not self._closed:
                await asyncio.sleep(self.heartbeat_interval)
                try:
                    await self.send_request({"type": "heartbeat"}, timeout=3.0)
                except Exception:
                    # ignore heartbeat failures here; real client could reconnect
                    pass
        except asyncio.CancelledError:
            pass

    def _next_msg_id(self) -> int:
        self._msg_id_counter += 1
        return self._msg_id_counter


async def main() -> None:
    client = MCPClient(host=DEFAULT_HOST, port=DEFAULT_PORT, heartbeat_interval=15.0)
    try:
        await client.connect()
        # Example: ping request
        try:
            resp = await client.send_request({"type": "ping"}, timeout=3.0)
            print("Ping response:", resp)
        except Exception as e:
            print("Ping failed:", e)

        # Example: echo
        try:
            resp = await client.send_request({"type": "echo", "payload": {"text": "hello mcp"}}, timeout=3.0)
            print("Echo response:", resp)
        except Exception as e:
            print("Echo failed:", e)

        # Keep running shortly to receive notifications (demo)
        await asyncio.sleep(2.0)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())