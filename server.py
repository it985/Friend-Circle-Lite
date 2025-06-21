from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from starlette.middleware.cors import CORSMiddleware
import json
import random
import logging
import os

from friend_circle_lite.get_info import fetch_and_process_data, sort_articles_by_time
from friend_circle_lite.get_conf import load_config

app = FastAPI()

# 设置静态文件目录
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/main", StaticFiles(directory="main"), name="main")

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://*.vercel.app",
        "https://*.netlify.app", 
        "https://*.github.io",
        "http://localhost:3000",
        "http://localhost:4000"
    ],  # 限制允许的域名
    allow_credentials=True,
    allow_methods=["GET", "HEAD"],  # 只允许GET和HEAD方法
    allow_headers=["*"],
)

# 添加安全头
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

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
        logging.error("all.json 文件不存在")
        return JSONResponse(
            content={"error": "数据文件不存在，请检查爬虫是否正常运行"}, 
            status_code=404
        )
    except json.JSONDecodeError as e:
        logging.error(f"JSON解析错误: {e}")
        return JSONResponse(
            content={"error": "数据文件格式错误"}, 
            status_code=500
        )
    except Exception as e:
        logging.error(f"读取数据文件时发生未知错误: {e}")
        return JSONResponse(
            content={"error": "服务器内部错误"}, 
            status_code=500
        )

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

if __name__ == '__main__':
    # 在生产环境中，建议绑定到127.0.0.1而不是0.0.0.0
    host = os.getenv('HOST', '127.0.0.1')
    port = int(os.getenv('PORT', 1223))
    
    logging.info(f"启动API服务: {host}:{port}")
    import uvicorn
    uvicorn.run(app, host=host, port=port)
