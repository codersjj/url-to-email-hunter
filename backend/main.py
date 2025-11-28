from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from email_extractor import EmailExtractor
import json
import asyncio
from typing import Dict
import os

app = FastAPI()

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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
                extractor = EmailExtractor(headless=not show_browser)
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
    uvicorn.run(app, host="0.0.0.0", port=8000)