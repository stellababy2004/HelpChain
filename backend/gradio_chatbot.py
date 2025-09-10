from huggingface_hub import InferenceClient
import gradio as gr
import os
from dotenv import load_dotenv

load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN")
client = InferenceClient("gpt2", token=HF_TOKEN)  # <-- смени модела!

def chat(prompt):
    return client.text_generation(prompt)

gr.Interface(fn=chat, inputs="text", outputs="text").launch()