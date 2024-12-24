from pygame.event import Event
import pygame
from dpongpy import PongGame, Settings
from dpongpy.model import *
from dpongpy.controller import ControlEvent
from dpongpy.model import Direction, Pong
from dpongpy.remote.udp import UdpClient, UdpServer, Address
from dpongpy.remote.presentation import serialize, deserialize
import threading


DEFAULT_HOST = "localhost"
DEFAULT_PORT = 12345


class PongCoordinator(PongGame):

    def __init__(self, settings: Settings = None):
        settings = settings or Settings()
        settings.initial_paddles = []
        super().__init__(settings)
        self.pong.reset_ball(Vector2(0))
        self.server = UdpServer(self.settings.port or DEFAULT_PORT)
        self._thread_receiver = threading.Thread(target=self._handle_ingoing_messages, daemon=True)
        self._thread_receiver.start()
        self._peers: set[Address] = set()
        self._lock = threading.RLock()
        self._laggy = settings.laggy

    def create_view(coordinator):
        from dpongpy.view import ShowNothingPongView
        from dpongpy.controller.local import ControlEvent

        class SendToPeersPongView(ShowNothingPongView):
            def render(self):
                event = coordinator.controller.create_event(ControlEvent.TIME_ELAPSED, dt=coordinator.dt, status=self._pong)
                coordinator._broadcast_to_all_peers(event)

        return SendToPeersPongView(coordinator.pong)

    def create_controller(coordinator, paddle_commands):
        from dpongpy.controller.local import PongEventHandler, InputHandler

        class Controller(PongEventHandler, InputHandler):
            def __init__(self, pong: Pong):
                PongEventHandler.__init__(self, pong)

            def on_player_join(self, pong: Pong, paddle_index: Direction):
                super().on_player_join(pong, paddle_index)
                pong.reset_ball()

            def on_player_leave(self, pong: Pong, paddle_index: Direction):
                if pong.has_paddle(paddle_index):
                    pong.remove_paddle(paddle_index)
                if len(pong.paddles) == 0:
                    self.on_game_over(pong)
                else:
                    pong.reset_ball()

            def on_game_over(self, pong: Pong):
                coordinator.stop()

            def handle_inputs(self, dt=None):
                self.time_elapsed(dt)

        return Controller(coordinator.pong)

    def at_each_run(self):
        pass

    def after_run(self):
        super().after_run()
        self.server.close()

    @property
    def peers(self):
        with self._lock:
            return set(self._peers)

    @peers.setter
    def peers(self, value):
        with self._lock:
            self._peers = set(value)

    def add_peer(self, peer):
        with self._lock:
            self._peers.add(peer)

    def _broadcast_to_all_peers(self, message):
        import time, random
        event = serialize(message)
        if(self._laggy):
            time.sleep(random.uniform(0.01, 0.15))
        for peer in self.peers:
            self.server.send(payload=event, address=peer)

    def _handle_ingoing_messages(self):
        while self.running:
            message, sender = self.server.receive()
            self.add_peer(sender)
            message = deserialize(message)
            assert isinstance(message, pygame.event.Event), f"Expected {pygame.event.Event}, got {type(message)}"
            pygame.event.post(message)


class PongTerminal(PongGame):

    def __init__(self, settings: Settings = None):
        settings = settings or Settings()
        assert len(settings.initial_paddles) == 1, "Only one paddle is allowed in terminal mode"
        super().__init__(settings)
        self.pong.reset_ball(Vector2(0))
        self.client = UdpClient(Address(self.settings.host or DEFAULT_HOST, self.settings.port or DEFAULT_PORT))
        from threading import Thread
        self._thread = Thread(daemon=True, target=self._handle_ingoing_messages)
        self._thread.start()

    def create_controller(terminal, paddle_commands = None):
        from dpongpy.controller.local import PongInputHandler, EventHandler

        class Controller(PongInputHandler, EventHandler):
            def __init__(self, pong: Pong, paddle_commands):
                PongInputHandler.__init__(self, pong, paddle_commands)

            def post_event(self, event: Event | ControlEvent, **kwargs):
                event = super().post_event(event, **kwargs)
                if not ControlEvent.TIME_ELAPSED.matches(event):
                    terminal.client.send(serialize(event))
                return event

            def handle_inputs(self, dt=None):
                return super().handle_inputs(dt) # just handle input events, do not handle time elapsed
            
            def handle_events(self):
                super().handle_events()
            
            def on_time_elapsed(self, pong: Pong, dt: float, status: Pong = None): # type: ignore[override]
                if (status is not None):
                    pong.override(status)
                else:
                    pong.update(dt)

            def on_paddle_move(self, pong, paddle_index, direction):
                pong.move_paddle(paddle_index, direction)

            def on_player_leave(self, pong: Pong, paddle_index: Direction):
                terminal.stop()
        
        return Controller(terminal.pong, paddle_commands)
    
    def _handle_ingoing_messages(self):
        while self.running:
            message = self.client.receive()
            message = deserialize(message)
            assert isinstance(message, pygame.event.Event), f"Expected {pygame.event.Event}, got {type(message)}"
            pygame.event.post(message)

    def before_run(self):
        super().before_run()
        for paddle in self.pong.paddles:
            self.controller.post_event(ControlEvent.PLAYER_JOIN, paddle_index=paddle.side)

    def after_run(self):
        self.client.close()
        super().after_run()


def main_coordinator(settings = None):
    PongCoordinator(settings).run()


def main_terminal(settings = None):
    PongTerminal(settings).run()
