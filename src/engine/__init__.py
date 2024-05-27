# 注册不同的Engine
from .base_engine import Engine
# from .gpt import GPTEngine
# from .chatglm import ChatGLMEngine
# from .minimax import MiniMaxEngine
# from .wenxin import WenXinEngine
# from .qwen import QwenEngine
# from .huatuogpt import HuatuoGPTEngine
# from .hf import HFEngine
from .litellm import LiteLLMEngine

# __all__ = [
#     "Engine",
#     "GPTEngine",
#     "ChatGLMEngine",
#     "MiniMaxEngine",
#     "WenXinEngine",
#     "QwenEngine",
#     "HuatuoGPTEngine",
#     "HFEngine",
#     "LiteLLMEngine"
# ]

__all__ = [
    "Engine",
    "LiteLLMEngine"
]
