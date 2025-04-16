# checkout_bot_py

API em **Python + FastAPI + Playwright** que adiciona produtos WooCommerce ao carrinho
e preenche o checkout.

```bash
# instalação local
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
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
