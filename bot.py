#!/usr/bin/env python3
"""QQ AI Chat Bot - Entry Point.

Starts NoneBot2 with OneBot V11 adapter for NapCat connection.
"""

import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter

# Initialize NoneBot2 (reads .env for configuration)
nonebot.init()

# Register OneBot V11 adapter (for NapCat reverse WebSocket)
driver = nonebot.get_driver()
driver.register_adapter(OneBotV11Adapter)

# Load plugins
nonebot.load_plugins("src/plugins")

if __name__ == "__main__":
    nonebot.run()
