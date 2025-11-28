'use client'

import React, { useState, useEffect, useRef } from 'react';
import { Upload, Download, Play, Pause, Trash2, Eye, EyeOff, Mail, CheckCircle, AlertCircle } from 'lucide-react';
import * as XLSX from 'xlsx';

interface LogEntry {
  timestamp: string;
  message: string;
  type: 'info' | 'success' | 'error' | 'warning';
}

const EmailExtractorApp = () => {
  const [urls, setUrls] = useState('');
  const [urlCount, setUrlCount] = useState(0);
  const [isExtracting, setIsExtracting] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [progress, setProgress] = useState(0);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [emails, setEmails] = useState<string[]>([]);
  const [showBrowser, setShowBrowser] = useState(true);
  const [ws, setWs] = useState<WebSocket | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  const [fakePrefixes, setFakePrefixes] = useState<string[]>([]);
  const [showConfig, setShowConfig] = useState(false);

  useEffect(() => {
    // 获取配置信息
    fetch('http://localhost:8000/api/config')
      .then(res => res.json())
      .then(data => {
        if (data.fake_email_prefixes) {
          setFakePrefixes(data.fake_email_prefixes);
        }
      })
      .catch(err => console.error('获取配置失败:', err));
  }, []);

  useEffect(() => {
    const lines = urls.trim().split('\n').filter(line => line.trim());
    setUrlCount(lines.length);
  }, [urls]);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const addLog = (message: string, type: LogEntry['type'] = 'info') => {
    const timestamp = new Date().toLocaleTimeString('zh-CN');
    setLogs(prev => [...prev, { timestamp, message, type }]);
  };

  const connectWebSocket = () => {
    const websocket = new WebSocket('ws://localhost:8000/ws');

    websocket.onopen = () => {
      addLog('WebSocket连接已建立', 'success');
    };

    websocket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      console.log("🚀 ~ connectWebSocket ~ data:", data)

      if (data.type === 'log') {
        addLog(data.message, data.level);
      } else if (data.type === 'progress') {
        setProgress(data.progress);
      } else if (data.type === 'email') {
        console.log('data.emails:', data.emails);
        setEmails(prev => {
          const newEmails = [...prev, ...data.emails];
          return [...new Set(newEmails)];
        });
      } else if (data.type === 'complete') {
        addLog('邮箱提取完成！', 'success');
        setIsExtracting(false);
      } else if (data.type === 'error') {
        addLog(`错误: ${data.message}`, 'error');
      }
    };

    websocket.onerror = () => {
      addLog('WebSocket连接错误', 'error');
    };

    websocket.onclose = () => {
      addLog('WebSocket连接已关闭', 'warning');
    };

    setWs(websocket);
    return websocket;
  };

  const startExtraction = async () => {
    if (!urls.trim()) {
      addLog('请输入至少一个URL', 'error');
      return;
    }

    setIsExtracting(true);
    setProgress(0);
    setEmails([]);
    addLog('开始提取流程...', 'info');

    const websocket = connectWebSocket();

    const urlList = urls.trim().split('\n').filter(line => line.trim());

    // 等待 WebSocket 连接建立后再发送消息
    websocket.addEventListener('open', () => {
      try {
        websocket.send(JSON.stringify({
          action: 'start',
          urls: urlList,
          showBrowser
        }));
        addLog(`已提交 ${urlList.length} 个URL进行处理`, 'success');
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : '未知错误';
        addLog(`错误: ${errorMessage}`, 'error');
        setIsExtracting(false);
        websocket?.close();
      }
    }, { once: true });
  };

  const pauseExtraction = () => {
    setIsPaused(!isPaused);
    addLog(isPaused ? '继续提取...' : '已暂停提取', 'warning');

    if (ws) {
      ws.send(JSON.stringify({ action: isPaused ? 'resume' : 'pause' }));
    }
  };

  const stopExtraction = () => {
    setIsExtracting(false);
    setIsPaused(false);
    addLog('已停止提取', 'error');

    if (ws) {
      ws.send(JSON.stringify({ action: 'stop' }));
      ws.close();
    }
  };

  const clearAll = () => {
    setUrls('');
    setLogs([]);
    setEmails([]);
    setProgress(0);
    addLog('已清空所有数据', 'info');
  };

  const exportToCSV = () => {
    const csv = emails.map(email => `"${email}"`).join('\n');
    const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `emails_${Date.now()}.csv`;
    link.click();
    addLog(`已导出 ${emails.length} 个邮箱到CSV`, 'success');
  };



  const exportToExcel = () => {
    const data = emails.map(email => ({ Email: email }));
    const worksheet = XLSX.utils.json_to_sheet(data);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, "Emails");
    XLSX.writeFile(workbook, `emails_${Date.now()}.xlsx`);
    addLog(`已导出 ${emails.length} 个邮箱到Excel`, 'success');
  };

  const exportToJSON = () => {
    const json = JSON.stringify({ emails, count: emails.length, exportDate: new Date().toISOString() }, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `emails_${Date.now()}.json`;
    link.click();
    addLog(`已导出 ${emails.length} 个邮箱到JSON`, 'success');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-3 mb-2">
            <Mail className="w-10 h-10 text-indigo-600" />
            <h1 className="text-4xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
              批量URL邮箱提取工具
            </h1>
          </div>
          <p className="text-gray-600">基于 Playwright + Email Hunter 自动化提取</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left Panel */}
          <div className="space-y-6">
            {/* URL Input */}
            <div className="bg-white rounded-xl shadow-lg p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold text-gray-800">URL列表</h2>
                <span className="px-3 py-1 bg-indigo-100 text-indigo-700 rounded-full text-sm font-medium">
                  {urlCount} 个URL
                </span>
              </div>
              <textarea
                value={urls}
                onChange={(e) => setUrls(e.target.value)}
                placeholder="请输入URL，每行一个&#x0a;例如：&#x0a;https://example.com&#x0a;https://example2.com"
                className="w-full h-48 p-4 border-2 border-gray-200 rounded-lg focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 transition-all resize-none"
                disabled={isExtracting}
              />
            </div>

            {/* Controls */}
            <div className="bg-white rounded-xl shadow-lg p-6">
              <h2 className="text-xl font-semibold text-gray-800 mb-4">控制面板</h2>
              <div className="space-y-3">
                <div className="flex gap-3">
                  <button
                    onClick={startExtraction}
                    disabled={isExtracting || !urls.trim()}
                    className="flex-1 bg-gradient-to-r from-indigo-600 to-purple-600 text-white py-3 rounded-lg font-medium hover:from-indigo-700 hover:to-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2"
                  >
                    <Play className="w-5 h-5" />
                    开始提取
                  </button>
                  {isExtracting && (
                    <button
                      onClick={pauseExtraction}
                      className="px-6 bg-yellow-500 text-white py-3 rounded-lg font-medium hover:bg-yellow-600 transition-all flex items-center gap-2"
                    >
                      <Pause className="w-5 h-5" />
                      {isPaused ? '继续' : '暂停'}
                    </button>
                  )}
                </div>

                <div className="flex gap-3">
                  <button
                    onClick={stopExtraction}
                    disabled={!isExtracting}
                    className="flex-1 bg-red-500 text-white py-3 rounded-lg font-medium hover:bg-red-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2"
                  >
                    <AlertCircle className="w-5 h-5" />
                    停止
                  </button>
                  <button
                    onClick={clearAll}
                    disabled={isExtracting}
                    className="flex-1 bg-gray-500 text-white py-3 rounded-lg font-medium hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2"
                  >
                    <Trash2 className="w-5 h-5" />
                    清空
                  </button>
                </div>

                <div className="flex gap-3">
                  <button
                    onClick={() => setShowBrowser(!showBrowser)}
                    className="flex-1 bg-blue-500 text-white py-3 rounded-lg font-medium hover:bg-blue-600 transition-all flex items-center justify-center gap-2"
                  >
                    {showBrowser ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                    {showBrowser ? '隐藏浏览器' : '显示浏览器'}
                  </button>
                  <button
                    onClick={() => setShowConfig(true)}
                    className="px-6 bg-gray-700 text-white py-3 rounded-lg font-medium hover:bg-gray-800 transition-all flex items-center justify-center gap-2"
                  >
                    <AlertCircle className="w-5 h-5" />
                    过滤配置
                  </button>
                </div>
              </div>
            </div>

            {/* Progress */}
            {isExtracting && (
              <div className="bg-white rounded-xl shadow-lg p-6">
                <h2 className="text-xl font-semibold text-gray-800 mb-4">提取进度</h2>
                <div className="space-y-2">
                  <div className="flex justify-between text-sm text-gray-600">
                    <span>进度</span>
                    <span>{progress}%</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-4 overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 transition-all duration-300 rounded-full"
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Right Panel */}
          <div className="space-y-6">
            {/* Logs */}
            <div className="bg-white rounded-xl shadow-lg p-6">
              <h2 className="text-xl font-semibold text-gray-800 mb-4">实时日志</h2>
              <div className="bg-gray-900 rounded-lg p-4 h-64 overflow-y-auto font-mono text-sm">
                {logs.map((log, index) => (
                  <div key={index} className="mb-1">
                    <span className="text-gray-500">[{log.timestamp}]</span>
                    <span className={`ml-2 ${log.type === 'success' ? 'text-green-400' :
                      log.type === 'error' ? 'text-red-400' :
                        log.type === 'warning' ? 'text-yellow-400' :
                          'text-blue-400'
                      }`}>
                      {log.message}
                    </span>
                  </div>
                ))}
                <div ref={logsEndRef} />
              </div>
            </div>

            {/* Results */}
            <div className="bg-white rounded-xl shadow-lg p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold text-gray-800">提取结果</h2>
                <span className="px-3 py-1 bg-green-100 text-green-700 rounded-full text-sm font-medium">
                  {emails.length} 个邮箱
                </span>
              </div>

              <div className="bg-gray-50 rounded-lg p-4 h-48 overflow-y-auto mb-4">
                {emails.length === 0 ? (
                  <p className="text-gray-400 text-center py-8">暂无提取结果</p>
                ) : (
                  emails.map((email, index) => (
                    <div key={index} className="flex items-center gap-2 py-1 text-sm">
                      <CheckCircle className="w-4 h-4 text-green-500 flex-shrink-0" />
                      <span className="text-gray-700">{email}</span>
                    </div>
                  ))
                )}
              </div>

              {emails.length > 0 && (
                <div className="space-y-2">
                  <button
                    onClick={exportToCSV}
                    className="w-full bg-green-500 text-white py-2 rounded-lg font-medium hover:bg-green-600 transition-all flex items-center justify-center gap-2"
                  >
                    <Download className="w-4 h-4" />
                    导出为 CSV
                  </button>
                  <button
                    onClick={exportToExcel}
                    className="w-full bg-blue-500 text-white py-2 rounded-lg font-medium hover:bg-blue-600 transition-all flex items-center justify-center gap-2"
                  >
                    <Download className="w-4 h-4" />
                    导出为 Excel
                  </button>
                  <button
                    onClick={exportToJSON}
                    className="w-full bg-purple-500 text-white py-2 rounded-lg font-medium hover:bg-purple-600 transition-all flex items-center justify-center gap-2"
                  >
                    <Download className="w-4 h-4" />
                    导出为 JSON
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Config Modal */}
      {showConfig && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-2xl p-6 w-full max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold text-gray-800">过滤配置 (Fake Email Prefixes)</h2>
              <button
                onClick={() => setShowConfig(false)}
                className="text-gray-500 hover:text-gray-700"
              >
                <EyeOff className="w-6 h-6" />
              </button>
            </div>

            <div className="overflow-y-auto flex-1 p-4 bg-gray-50 rounded-lg border border-gray-200">
              <div className="flex flex-wrap gap-2">
                {fakePrefixes.map((prefix, index) => (
                  <span key={index} className="px-3 py-1 bg-white border border-gray-300 rounded-full text-sm text-gray-700 shadow-sm">
                    {prefix}
                  </span>
                ))}
              </div>
            </div>

            <div className="mt-4 text-right">
              <button
                onClick={() => setShowConfig(false)}
                className="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
              >
                关闭
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default EmailExtractorApp;