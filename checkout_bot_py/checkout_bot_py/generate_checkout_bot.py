#!/usr/bin/env python3
"""
Gera o projeto 'checkout_bot_py' completo:
  checkout_bot_py/
  ├ app.py
  ├ requirements.txt
  ├ .env.example
  ├ Dockerfile
  └ README.md

Depois instala dependências e baixa o Chromium.
Execute com:  python generate_checkout_bot.py
"""

import os, subprocess, sys, textwrap, venv, pathlib, shutil

APP_DIR = "checkout_bot_py"

FILES = {
    "app.py": r'''
import os, asyncio, random, time
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()

CHECKOUT_URL      = os.getenv("CHECKOUT_URL", "https://naturalvalle.com.br/finalizar-compra/")
ACTION_TIMEOUT_MS = int(os.getenv("ACTION_TIMEOUT_MS", "15000"))

# ---------- Modelos ----------
class CheckoutInfo(BaseModel):
    email: str
    first_name: str
    last_name: str
    cpf: str
    cep: str
    address_1: str
    number: str
    address_2: str | None = ""
    neighborhood: str
    city: str
    state: str = Field(..., min_length=2, max_length=2)
    phone: str

class Payload(BaseModel):
    produtos: list[str]
    checkout: CheckoutInfo

# ---------- FastAPI ----------
app = FastAPI(title="Checkout‑Bot Python")

async def human_delay(a=0.3, b=0.8):
    await asyncio.sleep(random.uniform(a, b))

def normalize_qty(q: str) -> str:
    return f"{float(q.replace(',', '.')):.2f}"

async def process_request(data: Payload):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context()
        page    = await context.new_page()
        page.set_default_timeout(ACTION_TIMEOUT_MS)

        result = {"items": [], "checkout": "pending"}
        try:
            # --- produtos ---
            for linha in data.produtos:
                url, qty_raw = linha.split(':')
                qty = normalize_qty(qty_raw)
                await page.goto(url)
                await page.fill("input.qty", qty)
                await human_delay()
                await asyncio.gather(
                    page.wait_for_response(lambda r: "wc-ajax" in r.url and r.status == 200),
                    page.click('button[name="add-to-cart"]')
                )
                result["items"].append({"url": url, "qty": qty, "added": True})
                await human_delay(0.5, 1.2)

            # --- checkout ---
            await page.goto(CHECKOUT_URL)
            c = data.checkout
            mapping = {
                "billing_email": c.email,
                "billing_first_name": c.first_name,
                "billing_last_name": c.last_name,
                "billing_cpf": c.cpf,
                "billing_postcode": c.cep,
                "billing_address_1": c.address_1,
                "billing_number": c.number,
                "billing_address_2": c.address_2 or "",
                "billing_neighborhood": c.neighborhood,
                "billing_city": c.city,
                "billing_phone": c.phone,
            }
            for field, value in mapping.items():
                await page.fill(f"#{field}", value)
                await human_delay(0.2, 0.6)

            # estado (select2)
            await page.click("#select2-billing_state-container")
            await page.fill(".select2-search__field", c.state)
            await page.keyboard.press("Enter")

            result["checkout"] = "filled"
        finally:
            await context.close()
            await browser.close()
        return result

@app.post("/checkout")
async def checkout_endpoint(payload: Payload):
    t0 = time.time()
    try:
        result = await process_request(payload)
        result.update(status="success", duration_ms=int((time.time()-t0)*1000))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
''',

    "requirements.txt": '''
fastapi==0.111.0
uvicorn[standard]==0.29.0
python-dotenv==1.0.1
playwright==1.44.0
pydantic==2.7.1
    '''.strip(),

    ".env.example": '''
CHECKOUT_URL=https://naturalvalle.com.br/finalizar-compra/
ACTION_TIMEOUT_MS=15000
    '''.strip(),

    "Dockerfile": '''
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    playwright install --with-deps chromium
COPY . .
ENV PYTHONUNBUFFERED=1
CMD ["uvicorn","app:app","--host","0.0.0.0","--port","8000"]
    '''.strip(),

    "README.md": textwrap.dedent('''
        # checkout_bot_py

        API em **Python + FastAPI + Playwright** que adiciona produtos WooCommerce ao carrinho
        e preenche o checkout.

        ```bash
        # instalação local
        python -m venv .venv && source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
        pip install -r requirements.txt
        playwright install chromium
        uvicorn app:app --reload
        ```

        Endpoint:

        ```http
        POST /checkout
        {
          "produtos": ["<url>:0,05", "..."],
          "checkout": { "email":"...", "first_name":"...", ... }
        }
        ```
    ''')
}

def write_files():
    os.makedirs(APP_DIR, exist_ok=True)
    for name, content in FILES.items():
        path = pathlib.Path(APP_DIR) / name
        with open(path, "w", encoding="utf-8") as f:
            f.write(content.lstrip("\n"))
    print("📄 Arquivos criados.")

def create_venv_and_install():
    venv_dir = pathlib.Path(APP_DIR) / ".venv"
    print("🐍 Criando venv…")
    venv.EnvBuilder(with_pip=True).create(venv_dir)
    python_bin = venv_dir / ("Scripts\\python.exe" if os.name == "nt" else "bin/python")
    pip = [str(python_bin), "-m", "pip"]
    subprocess.check_call(pip + ["install", "--upgrade", "pip"])
    subprocess.check_call(pip + ["install", "-r", "requirements.txt"], cwd=APP_DIR)
    subprocess.check_call([str(python_bin), "-m", "playwright", "install", "chromium"])
    print("✅ Dependências instaladas.")
    activate = venv_dir / ("Scripts\\activate" if os.name == "nt" else "bin/activate")
    print(f"\n👉 Para iniciar:\n  cd {APP_DIR}\n  source {activate}\n  uvicorn app:app --reload\n")

def main():
    if os.path.exists(APP_DIR):
        resp = input(f"Diretório '{APP_DIR}' já existe. Sobrescrever? (s/N) ").lower()
        if resp != 's':
            print("Abortado.")
            sys.exit(0)
        shutil.rmtree(APP_DIR)
    write_files()
    create_venv_and_install()

if __name__ == "__main__":
    main()
