import os
import yaml
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from starlette.middleware.cors import CORSMiddleware
import json
import random
import time
from typing import List, Dict, Any
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from friend_circle_lite.get_info import fetch_and_process_data, sort_articles_by_time

app = FastAPI()

# 加载配置文件
def load_config():
    with open('conf.yaml', 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

config = load_config()
server_config = config.get('server', {})

# 配置请求频率限制
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=server_config.get('allowed_origins', []),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"]
)

# 设置静态文件目录
app.mount("/static", StaticFiles(directory=server_config.get('static_dir', 'static')), name="static")
app.mount("/main", StaticFiles(directory=server_config.get('main_dir', 'main')), name="main")

# 请求频率限制
# 使用简单的内存缓存实现请求频率限制
request_cache: Dict[str, List[float]] = {}

def check_rate_limit(request: Request, limit: int = 60, window: int = 60) -> bool:
    """
    检查请求频率是否超过限制
    
    :param request: 请求对象
    :param limit: 时间窗口内允许的最大请求数
    :param window: 时间窗口大小（秒）
    :return: 是否允许请求
    """
    client_ip = request.client.host
    current_time = time.time()
    
    # 清理过期的请求记录
    if client_ip in request_cache:
        request_cache[client_ip] = [t for t in request_cache[client_ip] if current_time - t < window]
    
    # 检查请求频率
    if client_ip not in request_cache:
        request_cache[client_ip] = []
    
    if len(request_cache[client_ip]) >= limit:
        return False
    
    request_cache[client_ip].append(current_time)
    return True

# 请求频率限制中间件
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if not check_rate_limit(request):
        return JSONResponse(
            status_code=429,
            content={"error": "Too many requests, please try again later."}
        )
    return await call_next(request)

# 返回图标图片
@app.get("/favicon.ico", response_class=HTMLResponse)
async def favicon():
    return FileResponse('static/favicon.ico')

# 返回背景图片
@app.get("/bg-light.webp", response_class=HTMLResponse)
async def bg_light():
    return FileResponse('static/bg-light.webp')
    
# 返回背景图片
@app.get("/bg-dark.webp", response_class=HTMLResponse)
async def bg_dark():
    return FileResponse('static/bg-dark.webp')

# 返回资源文件
# 返回 CSS 文件
@app.get("/fclite.css", response_class=HTMLResponse)
async def get_fclite_css():
    return FileResponse('./main/fclite.css')

# 返回 JS 文件
@app.get("/fclite.js", response_class=HTMLResponse)
async def get_fclite_js():
    return FileResponse('./main/fclite.js')

@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse('./static/index.html')

@app.get('/all.json')
async def get_all_articles():
    try:
        with open('./all.json', 'r', encoding='utf-8') as f:
            articles_data = json.load(f)
        return JSONResponse(content=articles_data)
    except FileNotFoundError:
        return JSONResponse(content={"error": "File not found"}, status_code=404)
    except json.JSONDecodeError:
        return JSONResponse(content={"error": "Failed to decode JSON"}, status_code=500)

@app.get('/errors.json')
async def get_error_friends():
    try:
        with open('./errors.json', 'r', encoding='utf-8') as f:
            errors_data = json.load(f)
        return JSONResponse(content=errors_data)
    except FileNotFoundError:
        return JSONResponse(content={"error": "File not found"}, status_code=404)
    except json.JSONDecodeError:
        return JSONResponse(content={"error": "Failed to decode JSON"}, status_code=500)

@app.get('/random')
async def get_random_article():
    try:
        with open('./all.json', 'r', encoding='utf-8') as f:
            articles_data = json.load(f)
        if articles_data.get("article_data"):
            random_article = random.choice(articles_data["article_data"])
            return JSONResponse(content=random_article)
        else:
            return JSONResponse(content={"error": "No articles available"}, status_code=404)
    except FileNotFoundError:
        return JSONResponse(content={"error": "File not found"}, status_code=404)
    except json.JSONDecodeError:
        return JSONResponse(content={"error": "Failed to decode JSON"}, status_code=500)

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(server_config.get('static_dir', 'static'), path)

@app.get("/api/friend")
@limiter.limit(f"{server_config.get('rate_limit', {}).get('limit', 60)}/{server_config.get('rate_limit', {}).get('window', 60)}")
async def get_friend():
    try:
        with open(os.path.join(server_config.get('main_dir', 'main'), 'all.json'), 'r', encoding='utf-8') as f:
            return JSONResponse(content=f.read())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == '__main__':
    # 启动 FastAPI 应用
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=3000)
