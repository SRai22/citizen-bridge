from grpc import aio


def create_server(port: int) -> aio.Server:
    server = aio.server()
    server.add_insecure_port(f"[::]:{port}")
    return server
