# Apex Velocity online room relay

Single-instance WebSocket relay for the Apex Velocity racing game. The host creates a room, the relay generates an eight-character code, and one friend joins with that code. The host owns the race simulation; the guest can only send validated controls.

Run `pip install -r requirements.txt` and `python relay_server.py`. The process listens on `0.0.0.0` and reads `PORT` (default 10000). Use a TLS reverse proxy in production; connect clients to `wss://your-service/ws`. `/health` is a bounded HTTP readiness endpoint. The bundled game receives this URL at build time; players never configure it.

Rooms live in memory and close if the host or server exits. Run exactly one instance. Waiting rooms expire after 30 minutes. There is no persistent player database, public room directory, game logging, or player account requirement. Rooms permit one host and one guest. Input validation, bounded message sizes, room limits, join-attempt limits, and per-connection message limits are enforced.

The relay sees race updates and controls; public connections use TLS. Room codes are invitations: share them only with the intended friend. Hosting restarts require creating a fresh room. Third-party hosting may sleep when idle; the game retries startup in the background.
