import argparse

from .config import Config
from .gateway import create_gateway


def main():
    parser = argparse.ArgumentParser(description="ForIT OpenAPI-to-MCP gateway")
    parser.add_argument("--config", required=True, help="Administrator JSON configuration")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    gateway = create_gateway(Config.load(args.config))
    gateway.run(transport="http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
