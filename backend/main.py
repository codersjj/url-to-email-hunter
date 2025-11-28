from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from email_extractor import EmailExtractor
import json
import asyncio
from typing import Dict
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get configuration from environment variables
BACKEND_HOST = os.getenv("BACKEND_HOST", "0.0.0.0")
# 自动从环境变量拿 PORT（Render 必须）
BACKEND_PORT = int(os.getenv("PORT", os.getenv("BACKEND_PORT", "8000")))
FRONTEND_URL = os.getenv("NEXT_PUBLIC_API_URL", "http://localhost:3000").replace(f":{BACKEND_PORT}", ":3000")

app = FastAPI()

# CORS配置，CORS 允许所有来源（生产最简单）或动态允许 Render 域名
app.add_middleware(CORSMiddleware,
    allow_origins=["*"],  # 改成 "*" 最保险！或者下面动态方式
    # allow_origins=[FRONTEND_URL, "https://你的...
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 存储活动的提取任务
active_extractors: Dict[str, EmailExtractor] = {}

@app.get("/api/config")
async def get_config():
    """获取配置信息"""
    return {
        "fake_email_prefixes": EmailExtractor.FAKE_EMAIL_PREFIXES
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    extractor = None
    session_id = id(websocket)
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message['action'] == 'start':
                urls = message.get('urls', [])
                show_browser = message.get('showBrowser', True)
                
                # 创建提取器
                extractor = EmailExtractor(headless=True)
                current_dir = os.path.dirname(os.path.abspath(__file__))
                extension_path = os.path.join(current_dir, 'chrome-extensions', 'extracted-email-hunter-crx')
                await extractor.initialize(extension_path)
                active_extractors[session_id] = extractor
                
                # 回调函数：发送消息到前端
                async def send_callback(msg_type, data, level='info'):
                    await websocket.send_json({
                        'type': msg_type,
                        'message': data if msg_type == 'log' else None,
                        'level': level if msg_type == 'log' else None,
                        'emails': data if msg_type == 'email' else None,
                        'progress': data if msg_type == 'progress' else None,
                    })
                
                # 开始提取
                asyncio.create_task(
                    extractor.extract_from_urls(urls, send_callback)
                )
                
                await websocket.send_json({
                    'type': 'log',
                    'message': '开始提取邮箱...',
                    'level': 'info'
                })
            
            elif message['action'] == 'pause':
                if extractor:
                    extractor.pause()
                    await websocket.send_json({
                        'type': 'log',
                        'message': '已暂停',
                        'level': 'warning'
                    })
            
            elif message['action'] == 'resume':
                if extractor:
                    extractor.resume()
                    await websocket.send_json({
                        'type': 'log',
                        'message': '已继续',
                        'level': 'info'
                    })
            
            elif message['action'] == 'stop':
                if extractor:
                    extractor.stop()
                    await extractor.close()
                    if session_id in active_extractors:
                        del active_extractors[session_id]
                    await websocket.send_json({
                        'type': 'log',
                        'message': '已停止',
                        'level': 'error'
                    })
    
    except WebSocketDisconnect:
        if extractor:
            await extractor.close()
        if session_id in active_extractors:
            del active_extractors[session_id]
    except Exception as e:
        await websocket.send_json({
            'type': 'error',
            'message': str(e)
        })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=BACKEND_HOST, port=BACKEND_PORT)