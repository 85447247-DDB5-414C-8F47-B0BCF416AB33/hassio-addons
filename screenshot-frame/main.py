import os
import asyncio
import json
from aiohttp import web, ClientSession, BasicAuth
from pathlib import Path

# pyppeteer for browser automation (Python port of Puppeteer)
import pyppeteer

_preferred_path = Path('/data/art.jpg')
# If /data is writable (typical add-on runtime), use it; otherwise fall back to
# the workspace-local `./data/art.jpg` so local testing doesn't require root.
if _preferred_path.parent.exists() or os.access(str(_preferred_path.parent), os.W_OK):
    ART_PATH = _preferred_path
else:
    ART_PATH = Path('./data/art.jpg')
    

# Ensure the chosen data directory exists
try:
    ART_PATH.parent.mkdir(parents=True, exist_ok=True)
except Exception:
    pass

INTERVAL = int(os.environ.get('INTERVAL_SECONDS', os.environ.get('INTERVAL', 300)))
HTTP_PORT = int(os.environ.get('HTTP_PORT', 8200))
SCREENSHOT_WIDTH = int(os.environ.get('SCREENSHOT_WIDTH', '1920'))
SCREENSHOT_HEIGHT = int(os.environ.get('SCREENSHOT_HEIGHT', '1080'))
SCREENSHOT_ZOOM = int(os.environ.get('SCREENSHOT_ZOOM', '100'))  # percentage: 100 = 100%, 150 = 150%, etc.

# Local TV options (from add-on options.json exported by run.sh)
TV_IP = os.environ.get('TV_IP') or ''
TV_PORT = int(os.environ.get('TV_PORT', '8001'))
TV_MATTE = os.environ.get('TV_MATTE') or None
TV_SHOW_AFTER_UPLOAD = os.environ.get('TV_SHOW_AFTER_UPLOAD', 'true').lower() in ('1','true','yes')
TARGET_URL = os.environ.get('TARGET_URL') or ''
# Target URL auth settings (supports multiple auth types)
# TARGET_AUTH_TYPE: none|bearer|basic|headers
TARGET_AUTH_TYPE = os.environ.get('TARGET_AUTH_TYPE', 'none').lower()
TARGET_TOKEN = os.environ.get('TARGET_TOKEN')
TARGET_TOKEN_HEADER = os.environ.get('TARGET_TOKEN_HEADER', 'Authorization')
TARGET_TOKEN_PREFIX = os.environ.get('TARGET_TOKEN_PREFIX', 'Bearer')
TARGET_USERNAME = os.environ.get('TARGET_USERNAME')
TARGET_PASSWORD = os.environ.get('TARGET_PASSWORD')
TARGET_HEADERS = os.environ.get('TARGET_HEADERS')  # optional JSON map of headers

# Always replace last art file (hard-coded path for persistence)
TV_LAST_ART_FILE = '/data/last-art-id.txt'

async def upload_image_to_tv_async(host: str, port: int, image_path: str, matte: str = None, show: bool = True):
    try:
        from samsungtvws.async_art import SamsungTVAsyncArt
    except Exception as e:
        print('samsungtvws.async_art library not available:', e)
        return None

    token_file = '/data/tv-token.txt'
    tv = None
    try:
        tv = SamsungTVAsyncArt(host=host, port=port, token_file=token_file)
        await tv.start_listening()

        supported = await tv.supported()
        if not supported:
            print('TV does not support art mode via this API')
            await tv.close()
            return None

        # read image bytes
        with open(image_path, 'rb') as f:
            data = f.read()

        file_type = os.path.splitext(image_path)[1][1:].upper() or 'JPEG'
        print(f'Uploading image to TV {host}:{port} (type={file_type})')
        content_id = None

        # Always attempt to replace last art if we have a cached ID
        last_id = None
        if os.path.exists(TV_LAST_ART_FILE):
            try:
                with open(TV_LAST_ART_FILE, 'r') as lf:
                    last_id = lf.read().strip() or None
            except Exception:
                last_id = None

        if last_id:
            print('Replacing art id', last_id)
            try:
                kwargs = {'content_id': last_id, 'file_type': file_type}
                if matte:
                    kwargs['matte'] = matte
                content_id = await tv.upload(data, **kwargs)
                if not content_id:
                    raise RuntimeError('Replace returned no content id')
                print('In-place replace succeeded; using id', content_id)
            except Exception as e:
                print('In-place replace failed; not falling back to new upload:', e)
                await tv.close()
                return None
        else:
            # Seed initial art id on first upload
            try:
                content_id = await tv.upload(data, file_type=file_type, matte=matte) if matte else await tv.upload(data, file_type=file_type)
            except TypeError:
                content_id = await tv.upload(data, file_type=file_type)

        print('Upload returned id:', content_id)
        if content_id is not None:
            try:
                # Try to select with show parameter (controls whether image is displayed)
                await tv.select_image(content_id, show=show)
                print(f'Selected uploaded image on TV (show={show})')
            except TypeError:
                # If show parameter not supported, try without it
                try:
                    await tv.select_image(content_id)
                    print('Selected uploaded image on TV (without show parameter)')
                except Exception as e:
                    print('Failed to select uploaded image:', e)
            except Exception as e:
                print('Failed to select uploaded image:', e)

        await tv.close()

        # Persist last art id for future replace attempts
        try:
            if content_id:
                with open(TV_LAST_ART_FILE, 'w') as lf:
                    lf.write(str(content_id))
        except Exception:
            pass

        return content_id
    except Exception as e:
        print('Error interacting with TV (async):', e)
        try:
            if tv:
                await tv.close()
        except Exception:
            pass
        return None


async def render_url_with_pyppeteer(url: str, headers: dict | None = None, timeout: int = 30000, width: int = 1920, height: int = 1080, zoom: int = 100):
    """Render the given URL to a PNG using pyppeteer and return bytes.

    Args:
        zoom: Zoom percentage (100 = 100%, 150 = 150%, 50 = 50%)

    Raises an exception on failure so the add-on fails fast if pyppeteer
    cannot render. pyppeteer is required for this add-on's primary purpose.
    """
    # Try launching with default args first; fall back to no-sandbox
    # Prefer system Chromium if available to avoid downloads
    executable_candidates = ['/usr/bin/chromium-browser', '/usr/bin/chromium']
    executable_path = None
    for cand in executable_candidates:
        if os.path.exists(cand):
            executable_path = cand
            break
    try:
        if executable_path:
            browser = await pyppeteer.launch(headless=True, executablePath=executable_path)
        else:
            browser = await pyppeteer.launch(headless=True)
    except Exception:
        args = ['--no-sandbox']
        if executable_path:
            browser = await pyppeteer.launch(headless=True, executablePath=executable_path, args=args)
        else:
            browser = await pyppeteer.launch(headless=True, args=args)
    
    page = await browser.newPage()
    # Set viewport for the desired width/height
    await page.setViewport({'width': width, 'height': height})
    
    # Set user agent and extra headers if provided
    if headers:
        await page.setExtraHTTPHeaders(headers)
    
    # Navigate to URL with timeout
    await page.goto(url, {'waitUntil': 'networkidle2', 'timeout': timeout})
    
    # Apply zoom by scaling the page
    if zoom != 100:
        await page.evaluate(f'() => {{ document.body.style.zoom = "{zoom}%" }}')
    
    # Take screenshot
    screenshot = await page.screenshot({'fullPage': False})
    await page.close()
    await browser.close()
    return screenshot


async def screenshot_loop(app):
    if not TARGET_URL:
        print('No TARGET_URL configured; the add-on will only upload if this is set.')

    while True:
        try:
            if not TARGET_URL:
                print('Skipping fetch; TARGET_URL not set')
            else:
                try:
                    # Build headers/auth dynamically so the target URL can be
                    # Home Assistant (token header), DakBoard (basic auth), or
                    # any other URL requiring custom headers.
                    headers = {}
                    auth = None
                    if TARGET_HEADERS:
                        try:
                            parsed = json.loads(TARGET_HEADERS)
                            if isinstance(parsed, dict):
                                headers.update(parsed)
                        except Exception:
                            print('Failed to parse TARGET_HEADERS; expecting JSON map')

                    if TARGET_AUTH_TYPE == 'bearer' and TARGET_TOKEN:
                        headers[TARGET_TOKEN_HEADER] = f"{TARGET_TOKEN_PREFIX} {TARGET_TOKEN}"
                    elif TARGET_AUTH_TYPE == 'basic' and TARGET_USERNAME and TARGET_PASSWORD:
                        auth = BasicAuth(TARGET_USERNAME, TARGET_PASSWORD)

                    async with ClientSession() as session:
                        print(f'Fetching from target URL: {TARGET_URL} (auth={TARGET_AUTH_TYPE})')
                        async with session.get(TARGET_URL, timeout=30, headers=headers or None, auth=auth) as resp:
                            if resp.status == 200:
                                ctype = (resp.headers.get('content-type') or '').lower()
                                content = await resp.read()
                                # If the target returns HTML, render it with pyppeteer
                                if ctype.startswith('text/html') or (len(content) > 0 and content.lstrip().startswith(b'<')):
                                    print('Target returned HTML; attempting pyppeteer render')
                                    rendered = await render_url_with_pyppeteer(TARGET_URL, headers=headers, width=SCREENSHOT_WIDTH, height=SCREENSHOT_HEIGHT, zoom=SCREENSHOT_ZOOM)
                                    if rendered:
                                        with open(str(ART_PATH), 'wb') as f:
                                            f.write(rendered)
                                        print('Saved pyppeteer-rendered image to', ART_PATH)
                                    else:
                                        # Fallback: save the raw response (likely HTML) for debugging
                                        with open(str(ART_PATH), 'wb') as f:
                                            f.write(content)
                                        print('pyppeteer not available or failed; saved raw target response to', ART_PATH)
                                else:
                                    with open(str(ART_PATH), 'wb') as f:
                                        f.write(content)
                                    print('Saved image from target to', ART_PATH)
                            else:
                                print('Target URL returned status', resp.status)
                except Exception as e:
                    print('Error fetching from target URL:', e)
        except Exception as e:
            print('Fetch loop error:', e)

        if TV_IP:
            try:
                content_id = await upload_image_to_tv_async(TV_IP, TV_PORT, str(ART_PATH), TV_MATTE, TV_SHOW_AFTER_UPLOAD)
                if not content_id:
                    print('Async upload returned no id; upload may have failed or TV returned no id')
            except Exception as e:
                print('Local TV upload error:', e)
        else:
            print('Local TV not configured; skipping upload (set use_local_tv and tv_ip).')

        await asyncio.sleep(INTERVAL)


async def handle_art(request):
    if not ART_PATH.exists():
        raise web.HTTPNotFound()
    return web.FileResponse(path=str(ART_PATH))


async def init_app():
    app = web.Application()
    app.router.add_get('/art.jpg', handle_art)
    return app


async def async_main():
    app = await init_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', HTTP_PORT)
    await site.start()
    print(f'HTTP server running on 0.0.0.0:{HTTP_PORT} serving /art.jpg')

    loop = asyncio.get_running_loop()
    screenshot_task = loop.create_task(screenshot_loop(app))
    try:
        await asyncio.Event().wait()  # run indefinitely until cancelled/interrupt
    finally:
        screenshot_task.cancel()
        try:
            await screenshot_task
        except asyncio.CancelledError:
            pass
        await runner.cleanup()


def main():
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
