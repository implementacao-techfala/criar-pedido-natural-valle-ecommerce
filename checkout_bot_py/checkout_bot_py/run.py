# run.py ─ inicia a API garantindo SelectorEventLoopPolicy
import asyncio, os, uvicorn

def main():
    if os.name == "nt":                               # ← Windows
        asyncio.set_event_loop_policy(
            asyncio.WindowsSelectorEventLoopPolicy()  # ← AQUI!
        )

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,          # hot‑reload em dev
    )

# proteção obrigatória para multiprocessing no Windows
if __name__ == "__main__":
    main()
