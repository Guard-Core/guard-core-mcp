import uvicorn

from guard_core_mcp.hosting import HostingConfig, create_hosted_app


def main() -> None:
    config = HostingConfig.from_env()
    uvicorn.run(
        create_hosted_app(config), host=config.host, port=config.port, log_level="info"
    )
