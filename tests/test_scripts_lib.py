import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from _lib import pick_gguf, pick_llama_asset


def sib(*n): return [{"rfilename": x} for x in n]


def test_pick_gguf():
    files = sib("README.md", "m.Q4_K_M.gguf", "m.Q4_K_S.gguf", "m.Q5_K_M.gguf", "m.i1-Q4_K_M.gguf", "m.Q8_0.gguf", "big.Q4_K_M-00001-of-00002.gguf")
    assert pick_gguf(files, "Q4_K_M") == "m.Q4_K_M.gguf"
    assert pick_gguf(files, "Q5_K_M") == "m.Q5_K_M.gguf" and pick_gguf(files, "Q6_K") is None
    assert pick_gguf(sib("model-q4_k_m.gguf"), "Q4_K_M") == "model-q4_k_m.gguf"


NAMES = ["llama-b7000-bin-win-cpu-x64.zip", "llama-b7000-bin-win-vulkan-x64.zip", "llama-b7000-bin-win-cuda-12.4-x64.zip", "cudart-llama-bin-win-cuda-12.4-x64.zip",
         "llama-b7000-bin-ubuntu-vulkan-x64.tar.gz", "llama-b7000-bin-ubuntu-x64.tar.gz", "llama-b7000-bin-macos-arm64.tar.gz", "llama-b7000-bin-macos-x64.tar.gz"]


def test_pick_llama_asset():
    assert pick_llama_asset(NAMES, "Windows", "AMD64") == "llama-b7000-bin-win-vulkan-x64.zip"
    assert pick_llama_asset(NAMES, "Linux", "x86_64") == "llama-b7000-bin-ubuntu-vulkan-x64.tar.gz"
    assert pick_llama_asset(NAMES, "Darwin", "arm64") == "llama-b7000-bin-macos-arm64.tar.gz"
    assert pick_llama_asset(["x.txt"], "Windows", "AMD64") is None
