from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from email_extractor import EmailExtractor
import json
import asyncio
from typing import Dict
import os
import logging
from dotenv import load_dotenv

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Get configuration from environment variables
BACKEND_HOST = os.getenv("BACKEND_HOST", "0.0.0.0")
BACKEND_PORT = int(os.getenv("PORT", os.getenv("BACKEND_PORT", "8000")))
USE_PROXY = os.getenv("USE_PROXY", "false").lower() == "true"
logger.info(f"配置: USE_PROXY={USE_PROXY} (智能代理回退)")

app = FastAPI()

# CORS配置
app.add_middleware(CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 存储活动的提取任务
active_extractors: Dict[str, EmailExtractor] = {}
active_tasks: Dict[str, asyncio.Task] = {}

async def cleanup_extractor(session_id: str, extractor: EmailExtractor):
    """安全清理提取器实例"""
    try:
        logger.info(f"开始清理 session {session_id} 的浏览器实例...")
        
        # 取消正在运行的任务
        if session_id in active_tasks:
            task = active_tasks[session_id]
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    logger.info(f"任务 {session_id} 已取消")
            del active_tasks[session_id]
        
        # 关闭提取器
        if extractor:
            await extractor.close()
            logger.info(f"Extractor {session_id} 已关闭")
        
        # 从活动列表移除
        if session_id in active_extractors:
            del active_extractors[session_id]
            logger.info(f"已从活动列表移除 {session_id}")
        
        # 额外等待确保资源释放
        await asyncio.sleep(0.5)
        
    except Exception as e:
        logger.error(f"清理 extractor 时出错: {e}", exc_info=True)

@app.get("/api/config")
async def get_config():
    """获取配置信息"""
    return {
        "fake_email_prefixes": EmailExtractor.FAKE_EMAIL_PREFIXES
    }

@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {
        "status": "ok",
        "active_sessions": len(active_extractors),
        "use_proxy": USE_PROXY,
        "proxy_mode": "smart_fallback" if USE_PROXY else "disabled"
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    extractor = None
    session_id = str(id(websocket))
    
    logger.info(f"WebSocket 连接建立: {session_id}")
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            action = message.get('action')
            
            logger.info(f"收到消息: {action} from {session_id}")
            
            if action == 'start':
                # 如果已有运行中的实例,先清理
                if session_id in active_extractors:
                    logger.warning(f"检测到 {session_id} 已有运行实例,先清理...")
                    old_extractor = active_extractors[session_id]
                    await cleanup_extractor(session_id, old_extractor)
                    # 等待资源完全释放
                    await asyncio.sleep(1)
                
                urls = message.get('urls', [])
                # show_browser = message.get('showBrowser', True)
                show_browser = False
                
                logger.info(f"创建新的提取器实例: {session_id}, headless={not show_browser}, use_proxy_fallback={USE_PROXY}")
                
                # 创建新提取器（启用智能代理回退）
                extractor = EmailExtractor(headless=not show_browser, use_proxy=USE_PROXY)
                
                try:
                    await extractor.initialize()
                    active_extractors[session_id] = extractor
                    
                    logger.info(f"提取器初始化成功: {session_id}")
                    
                    # 回调函数
                    async def send_callback(msg_type, data, level='info'):
                        try:
                            await websocket.send_json({
                                'type': msg_type,
                                'message': data if msg_type == 'log' else None,
                                'level': level if msg_type == 'log' else None,
                                'emails': data if msg_type == 'email' else None,
                                'progress': data if msg_type == 'progress' else None,
                                'failed_urls': data if msg_type == 'failed_urls' else None,
                                'no_email_urls': data if msg_type == 'no_email_urls' else None,
                            })
                        except Exception as e:
                            logger.error(f"发送消息失败: {e}")
                    
                    # 创建提取任务
                    async def run_extraction():
                        try:
                            await extractor.extract_from_urls(urls, send_callback)
                            await websocket.send_json({
                                'type': 'complete',
                                'message': '所有任务处理完毕'
                            })
                        except asyncio.CancelledError:
                            logger.info(f"提取任务 {session_id} 被取消")
                            raise
                        except Exception as e:
                            logger.error(f"提取任务出错: {e}", exc_info=True)
                            await websocket.send_json({
                                'type': 'error',
                                'message': str(e)
                            })
                        finally:
                            # 任务完成后自动清理
                            await cleanup_extractor(session_id, extractor)
                    
                    task = asyncio.create_task(run_extraction())
                    active_tasks[session_id] = task
                    
                    await websocket.send_json({
                        'type': 'log',
                        'message': f'开始提取 {len(urls)} 个URL的邮箱...',
                        'level': 'info'
                    })
                    
                except Exception as e:
                    logger.error(f"初始化提取器失败: {e}", exc_info=True)
                    await websocket.send_json({
                        'type': 'error',
                        'message': f'初始化失败: {str(e)}'
                    })
                    if extractor:
                        await cleanup_extractor(session_id, extractor)
                        extractor = None
            
            elif action == 'pause':
                if session_id in active_extractors:
                    active_extractors[session_id].pause()
                    await websocket.send_json({
                        'type': 'log',
                        'message': '已暂停',
                        'level': 'warning'
                    })
            
            elif action == 'resume':
                if session_id in active_extractors:
                    active_extractors[session_id].resume()
                    await websocket.send_json({
                        'type': 'log',
                        'message': '已继续',
                        'level': 'info'
                    })
            
            elif action == 'stop':
                if session_id in active_extractors:
                    active_extractors[session_id].stop()
                    await cleanup_extractor(session_id, active_extractors[session_id])
                    await websocket.send_json({
                        'type': 'log',
                        'message': '已停止',
                        'level': 'error'
                    })
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket 断开: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket 错误: {e}", exc_info=True)
        try:
            await websocket.send_json({
                'type': 'error',
                'message': str(e)
            })
        except:
            pass
    finally:
        # 确保清理资源
        if session_id in active_extractors:
            logger.info(f"清理断开连接的 session: {session_id}")
            await cleanup_extractor(session_id, active_extractors.get(session_id))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=BACKEND_HOST, port=BACKEND_PORT)