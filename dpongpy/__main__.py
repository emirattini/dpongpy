import dpongpy
from dpongpy.model import Direction
import argparse


def arg_parser():
    ap = argparse.ArgumentParser()
    ap.prog = "python -m " + dpongpy.__name__
    mode = ap.add_argument_group("mode")
    mode.add_argument("--mode", '-m', choices=['local', 'centralised'],
                      help="Run the game in local or centralised mode")
    mode.add_argument("--role", '-r', required=False, choices=['coordinator', 'terminal'],
                      help="Run the game with a central coordinator, in either coordinator or terminal role")
    networking = ap.add_argument_group("networking")
    networking.add_argument("--host", '-H', help="Host to connect to", type=str, default="localhost")
    networking.add_argument("--port", '-p', help="Port to connect to", type=int, default=None)
    game = ap.add_argument_group("game")
    game.add_argument("--side", '-s', 
                      choices=[dir.name.lower() for dir in Direction.values() if dir != Direction.NONE],
                      help="Side to play on", action="append", default=[], dest="sides")
    game.add_argument("--keys", '-k', 
                      choices=dpongpy.controller.ActionMap.all_mappings().keys(),
                      help="Keymaps for sides", action="append", default=None)
    game.add_argument("--debug", '-d', help="Enable debug mode", action="store_true")
    game.add_argument("--size", '-S', help="Size of the game window", type=int, nargs=2, default=[900, 600])
    game.add_argument("--fps", '-f', help="Frames per second", type=int, default=60)
    game.add_argument("--no-gui", help="Disable GUI", action="store_true", default=False)
    game.add_argument("--laggy", '-l', help="Make the coordinator laggy", action="store_true", default=False)
    return ap


def args_to_settings(args):
    settings = dpongpy.Settings()
    settings.host = args.host
    settings.port = args.port
    settings.debug = args.debug
    settings.size = tuple(args.size)
    settings.fps = args.fps
    if args.keys is None:
        args.keys = list(dpongpy.controller.ActionMap.all_mappings().keys())[:len(args.sides)]
    assert len(args.sides) == len(args.keys), "Number of sides and keymaps must match"
    settings.initial_paddles = {
        Direction[direction.upper()]: dpongpy.controller.ActionMap.all_mappings()[keymap]
        for direction, keymap in zip(args.sides, args.keys)
    }
    settings.gui = not args.no_gui
    settings.laggy = args.laggy
    return settings


parser = arg_parser()
args = parser.parse_args()
settings = args_to_settings(args)
if args.mode == 'local':
    if not settings.initial_paddles:
        settings.initial_paddles = [Direction.LEFT, Direction.RIGHT]
    dpongpy.main(settings)
    exit(0)
if args.mode == 'centralised':
    import dpongpy.remote.centralised
    if args.role == 'coordinator':
        dpongpy.remote.centralised.main_coordinator(settings)
        exit(0)
    if args.role == 'terminal':
        dpongpy.remote.centralised.main_terminal(settings)
        exit(0)
    print(f"Invalid role: {args.role}. Must be either 'coordinator' or 'terminal'")
parser.print_help()
exit(1)
