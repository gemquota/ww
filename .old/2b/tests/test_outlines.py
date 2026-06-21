from llama_cpp import Llama
import outlines
from pydantic import BaseModel
import os

model_path = "/data/data/com.termux/files/home/local_ai/llama.cpp/gemma-2b.gguf"

if not os.path.exists(model_path):
    print("Model not found")
    exit(1)

print("Loading Llama...")
llm = Llama(model_path=model_path, n_ctx=512, verbose=False)
print("Wrapping with Outlines...")
model = outlines.from_llamacpp(llm)

print("Testing text generation...")
# In 1.3.0, use outlines.Generator
gen = outlines.Generator(model)
res = gen("Hello, who are you?", max_tokens=10)
print(f"Result: {res}")

class User(BaseModel):
    name: str

print("Testing JSON generation...")
gen_json = outlines.Generator(model, User)
res_json = gen_json("My name is Alice", max_tokens=20)
print(f"Result JSON: {res_json}")
