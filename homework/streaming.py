from llama_cpp import Llama

MODEL_PATH = "model.gguf"

llm = Llama(
    model_path=MODEL_PATH,
    n_ctx=512,
    n_threads=4
)

print("💬 Streaming mode (no memory). Type 'exit' to quit\n")

while True:
    user_input = input("You: ")

    if user_input.lower() in ["exit", "quit"]:
        break

    prompt = f"User: {user_input}\nAssistant:"

    print("Assistant: ", end="", flush=True)

    stream = llm(
        prompt,
        max_tokens=200,
        stream=True
    )

    for chunk in stream:
        token = chunk["choices"][0]["text"]
        print(token, end="", flush=True)

    print("\n")
