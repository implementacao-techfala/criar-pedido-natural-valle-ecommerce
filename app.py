import sys, asyncio
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import os, random, time, logging, pathlib
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from playwright.async_api import async_playwright
from dotenv import load_dotenv

# ───── LOGS ─────
LOG_DIR = pathlib.Path(__file__).with_name("logs")
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "checkout_bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ───── ENV ─────
load_dotenv()
CHECKOUT_URL      = os.getenv("CHECKOUT_URL", "https://naturalvalle.com.br/checkout/")
ACTION_TIMEOUT_MS = int(os.getenv("ACTION_TIMEOUT_MS", "15000"))
INSTANCE_NAME     = os.getenv("INSTANCE_NAME", "instancia-padrao")

# ───── MODELOS ─────
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

# ───── FASTAPI ─────
app = FastAPI(title="Checkout‑Bot Python")

async def human_delay(a=0.3, b=0.8):
    await asyncio.sleep(random.uniform(a, b))

def normalize_qty(q: str) -> str:
    return f"{float(q.replace(',', '.')):.2f}"

async def process_request(data: Payload):
    async with async_playwright() as p:
        logger.info("🟢 Iniciando processo para instância: %s", INSTANCE_NAME)

        browser = await p.chromium.launch(headless=False, slow_mo=300)
        context = await browser.new_context()
        page = await context.new_page()
        page.set_default_timeout(ACTION_TIMEOUT_MS)

        result = {"items": [], "checkout": "pending"}

        try:
            for linha in data.produtos:
                try:
                    url, qty_raw = linha.rsplit(':', 1)
                except ValueError:
                    logger.warning("❗ Formato inválido na linha: %s", linha)
                    continue

                qty = normalize_qty(qty_raw)
                logger.info("➡️ Abrindo %s (qty=%s)", url, qty)

                try:
                    await page.goto(url)
                    logger.info("🌐 Página carregada")
                except Exception as e:
                    logger.error("❌ Falha ao carregar página %s: %s", url, e)
                    continue

                try:
                    await page.fill("input.qty", qty)
                    await human_delay()
                    async with page.expect_response(lambda r: "wc-ajax" in r.url and r.status == 200):
                        await page.click('button[name="add-to-cart"]')
                    logger.info("✅ Produto adicionado ao carrinho: %s", url)
                    result["items"].append({"url": url, "qty": qty, "added": True})
                except Exception as e:
                    logger.warning("⚠️ Falha ao adicionar produto: %s — %s", url, e)
                    html = await page.content()
                    if "não pode adicionar a quantidade" in html:
                        logger.warning("🚫 Produto sem estoque: %s", url)
                    result["items"].append({"url": url, "qty": qty, "added": False})
                    continue

                await human_delay(0.5, 1.2)

            logger.info("🛒 Indo para o checkout: %s", CHECKOUT_URL)
            try:
                await page.goto(CHECKOUT_URL)
            except Exception as e:
                logger.error("❌ Falha ao acessar página de checkout: %s", e)
                raise

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
                try:
                    await page.fill(f"#{field}", value)
                    logger.info("✍️ Preenchido: %s", field)
                except Exception as e:
                    logger.warning("⚠️ Erro ao preencher %s: %s", field, e)
                await human_delay(0.2, 0.6)

            try:
                await page.click("#select2-billing_state-container")
                await human_delay(0.4, 0.7)
                await page.fill(".select2-search__field", "São Paulo")
                await page.keyboard.press("Enter")
                await human_delay(0.4, 0.7)
                await page.click("#select2-billing_state-container")
                await page.fill(".select2-search__field", "São Paulo")
                await page.keyboard.press("Enter")
                logger.info("📍 Estado 'São Paulo' selecionado com dupla verificação")
            except Exception as e:
                logger.warning("⚠️ Falha ao selecionar estado 'São Paulo': %s", e)

            html = await page.content()
            if "Ocorreu um erro ao processar seu pedido" in html:
                logger.error("❌ Erro detectado na tela de checkout. Abortando envio.")
                raise HTTPException(status_code=500, detail="Erro ao processar pedido na página WooCommerce.")

            try:
                radio_checked = await page.is_checked("#payment_method_asaas-pix")
                if not radio_checked:
                    await page.check("#payment_method_asaas-pix")
                    logger.info("✅ PIX selecionado manualmente")
                else:
                    logger.info("✅ PIX já estava selecionado")
            except Exception as e:
                logger.warning("⚠️ Falha ao verificar ou selecionar PIX: %s", e)

            try:
                await page.click("#place_order")
                logger.info("🚀 Botão de finalizar pedido clicado")
                await human_delay(6, 20)
                final_url = page.url
                result["checkout"] = "pedido_enviado"
                result["redirect_url"] = final_url
                logger.info("🔁 Página final após envio: %s", final_url)
            except Exception as e:
                logger.error("❌ Erro ao clicar no botão 'Fazer Pedido' ou redirecionar: %s", e)
                raise HTTPException(status_code=500, detail="Falha ao finalizar o pedido ou redirecionar.")

        except Exception as e:
            logger.exception("❌ Erro geral durante o processo")
            raise

        finally:
            await asyncio.sleep(10)
            await context.close()
            await browser.close()
            logger.info("🔒 Navegador fechado")

        return result

@app.post("/checkout")
async def checkout_endpoint(payload: Payload):
    t0 = time.time()
    try:
        result = await process_request(payload)
        result.update(status="success", duration_ms=int((time.time() - t0) * 1000))
        logger.info("✔ Pedido concluído em %sms", result["duration_ms"])
        return result
    except Exception as e:
        logger.error("✖ Falha geral: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))