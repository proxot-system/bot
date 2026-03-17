import asyncio
import importlib
import os
from pathlib import Path

from aiohttp import web

from utilities.config import get_config
from utilities.localization.localization import Localization, locale_format

from .misc import get_browser_locale, http_status_names

app = web.Application()

files = [f for f in os.listdir("src/utilities/textbox/web/endpoints") if f != "__pycache__"]
endpoints = [f.replace(".py", "") for f in files]
endpoints = [None if len(f) < 0 or f.startswith(".") else f for f in endpoints]
endpoints = [e for e in endpoints if e is not None]
print("Processing endpoints")
i = 0
for endpoint in endpoints:
	i = +1
	imported = importlib.import_module("utilities.textbox.web.endpoints." + endpoint)
	imported.process(app)
	print(f"| {endpoint}")
print(f"Done ({i})")


@web.middleware
async def error_middleware(request, handler):
	try:
		return await handler(request)
	except web.HTTPException as ex:
		status = ex.status
		if status in http_status_names:
			loc = Localization(get_browser_locale(request))

			with open(
				Path("src/utilities/textbox/web/static/paiges/error.html"),
				"r",
				encoding="utf-8",
			) as f:
				error_paige = f.read()
			return web.Response(
				text=await locale_format(
					loc,
					error_paige,
					status=status,
					status_description=http_status_names[status],
				),
				headers={"Content-Type": "text/html"},
			)
		raise
	except Exception:
		request.protocol.logger.exception("Error handling request")
		return web.Response(
			text=f"<h1 style='text-align: center'> 500: Internal Machine Error </h1>",
			headers={"Content-Type": "text/html"},
		)


def get_ip(request):
	if "Cf-Connecting-Ip" in request.headers:
		return f"{request.headers['Cf-Connecting-Ip']}:{request.headers['Cf-Ipcountry']}"
	return request.remote


@web.middleware
async def logging_middleware(request, handler):
	print(f"{'📓' if request.path == '/generate' else '⚡'} {request.method} {request.path} [{get_ip(request)}]")
	response = await handler(request)

	return response


app.router.add_static("/static/", path="src/utilities/textbox/web/static/", name="static")
app.middlewares.extend([error_middleware, logging_middleware])


async def main():
	PORT = get_config("textbox.web.port", typecheck=int)

	runner = web.AppRunner(app)
	await runner.setup()
	site = web.TCPSite(runner, None, PORT)
	await site.start()
	if os.environ.get("AIOHTTP_RELOADER") != "1":
		print(f"- Textboxweb server started ( http://localhost:{PORT} )")

	await asyncio.Event().wait()


def run_server():
	asyncio.run(main())
