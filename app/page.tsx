'use client'

import React, { useState, useEffect, useRef } from 'react';
import { Upload, Download, Play, Pause, Trash2, Eye, EyeOff, Mail, CheckCircle, AlertCircle } from 'lucide-react';
import * as XLSX from 'xlsx';
import StatsPanel from './components/stats-panel';

interface LogEntry {
  timestamp: string;
  message: string;
  type: 'info' | 'success' | 'error' | 'warning';
}

interface FailedUrl {
  url: string;
  error: string;
  timestamp: number;
}

interface NoEmailUrl {
  url: string;
  timestamp: number;
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
  const [failedUrls, setFailedUrls] = useState<FailedUrl[]>([]);
  const [noEmailUrls, setNoEmailUrls] = useState<NoEmailUrl[]>([]);

  const logsContainerRef = useRef<HTMLDivElement>(null);

  const [fakePrefixes, setFakePrefixes] = useState<string[]>([]);
  const [showConfig, setShowConfig] = useState(false);

  // Backend Configuration State
  const [backendMode, setBackendMode] = useState<'online' | 'local'>('online');
  const [onlineUrl, setOnlineUrl] = useState(process.env.NEXT_PUBLIC_ONLINE_API_URL || 'http://localhost:8888');
  const [localUrl, setLocalUrl] = useState(process.env.NEXT_PUBLIC_LOCAL_API_URL || 'http://localhost:8888');
  const [apiUrl, setApiUrl] = useState('');

  // Initialize backend configuration from localStorage
  useEffect(() => {
    const savedMode = localStorage.getItem('backendMode') as 'online' | 'local';
    const savedOnlineUrl = localStorage.getItem('onlineUrl');
    const savedLocalUrl = localStorage.getItem('localUrl');

    const defaultOnlineUrl = process.env.NEXT_PUBLIC_ONLINE_API_URL || 'http://localhost:8888';

    setBackendMode(savedMode || 'online');
    setOnlineUrl(savedOnlineUrl || defaultOnlineUrl);
    if (savedLocalUrl) setLocalUrl(savedLocalUrl);
  }, []);
  // Update API URL when configuration changes
  useEffect(() => {
    const newApiUrl = backendMode === 'local' ? localUrl : (onlineUrl || process.env.NEXT_PUBLIC_ONLINE_API_URL || 'http://localhost:8888');
    console.log("🚀 ~ EmailExtractorApp ~ newApiUrl:", newApiUrl)
    setApiUrl(newApiUrl);

    // Save to localStorage
    localStorage.setItem('backendMode', backendMode);
    localStorage.setItem('onlineUrl', onlineUrl);
    localStorage.setItem('localUrl', localUrl);
  }, [backendMode, onlineUrl, localUrl]);
  // Fetch config when apiUrl changes
  useEffect(() => {
    if (!apiUrl) return;
    fetch(`${apiUrl}/api/config`)
      .then(res => res.json())
      .then(data => {
        if (data.fake_email_prefixes) {
          setFakePrefixes(data.fake_email_prefixes);
        }
      })
      .catch(err => console.error('获取配置失败:', err));
  }, [apiUrl]);

  useEffect(() => {
    const lines = urls.trim().split('\n').filter(line => line.trim());
    setUrlCount(lines.length);
  }, [urls]);

  useEffect(() => {
    if (logsContainerRef.current) {
      logsContainerRef.current.scrollTop = logsContainerRef.current.scrollHeight;
    }
  }, [logs]);

  const addLog = (message: string, type: LogEntry['type'] = 'info') => {
    const timestamp = new Date().toLocaleTimeString('zh-CN');
    setLogs(prev => [...prev, { timestamp, message, type }]);
  };

  const connectWebSocket = () => {
    if (!apiUrl) return null;
    const protocol = apiUrl.startsWith('https') ? 'wss:' : 'ws:';

    // 处理 apiUrl 可能包含的协议头
    let wsBase = apiUrl.replace(/^https?:\/\//, '');

    const wsUrl = `${protocol}//${wsBase}/ws`;
    console.log('Connecting to WebSocket:', wsUrl);
    const websocket = new WebSocket(wsUrl);

    websocket.onopen = () => {
      addLog(`WebSocket连接已建立 (${backendMode === 'local' ? '本地' : '线上'})`, 'success');
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
      } else if (data.type === 'failed_urls') {
        setFailedUrls(data.failed_urls || []);
      } else if (data.type === 'no_email_urls') {
        setNoEmailUrls(data.no_email_urls || []);
      } else if (data.type === 'complete') {
        addLog(data.message || '任务完成', 'success');
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
    setFailedUrls([]);
    setNoEmailUrls([]);
    addLog('开始提取流程...', 'info');

    const websocket = connectWebSocket();

    const urlList = urls.trim().split('\n').filter(line => line.trim());

    // 等待 WebSocket 连接建立后再发送消息
    websocket?.addEventListener('open', () => {
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

  const exportFailedUrlsToExcel = () => {
    const data = failedUrls.map(item => ({
      'URL': item.url,
      '错误原因': item.error,
      '时间戳': new Date(item.timestamp * 1000).toLocaleString('zh-CN')
    }));
    const worksheet = XLSX.utils.json_to_sheet(data);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, "Failed URLs");
    XLSX.writeFile(workbook, `failed_urls_${Date.now()}.xlsx`);
    addLog(`已导出 ${failedUrls.length} 个失败URL到Excel`, 'success');
  };

  const exportNoEmailUrlsToExcel = () => {
    const data = noEmailUrls.map(item => ({
      'URL': item.url,
      '时间戳': new Date(item.timestamp * 1000).toLocaleString('zh-CN')
    }));
    const worksheet = XLSX.utils.json_to_sheet(data);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, "No Email URLs");
    XLSX.writeFile(workbook, `no_email_urls_${Date.now()}.xlsx`);
    addLog(`已导出 ${noEmailUrls.length} 个无邮箱URL到Excel`, 'success');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-3 mb-2">
            <Mail className="w-10 h-10 text-indigo-600" />
            <h1 className="text-4xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
              URL To Email Hunter
            </h1>
          </div>
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
                    className="flex-1 bg-gradient-to-r from-indigo-600 to-purple-600 text-white py-3 rounded-lg font-medium hover:from-indigo-700 hover:to-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2 cursor-pointer"
                  >
                    <Play className="w-5 h-5" />
                    开始提取
                  </button>
                  {isExtracting && (
                    <button
                      onClick={pauseExtraction}
                      className="px-6 bg-yellow-500 text-white py-3 rounded-lg font-medium hover:bg-yellow-600 transition-all flex items-center gap-2 cursor-pointer"
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
                    className="flex-1 bg-red-500 text-white py-3 rounded-lg font-medium hover:bg-red-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2 cursor-pointer"
                  >
                    <AlertCircle className="w-5 h-5" />
                    停止
                  </button>
                  <button
                    onClick={clearAll}
                    disabled={isExtracting}
                    className="flex-1 bg-gray-500 text-white py-3 rounded-lg font-medium hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2 cursor-pointer"
                  >
                    <Trash2 className="w-5 h-5" />
                    清空
                  </button>
                </div>

                <div className="flex gap-3">
                  <button
                    onClick={() => setShowConfig(true)}
                    className="px-6 bg-gray-700 text-white py-3 rounded-lg font-medium hover:bg-gray-800 transition-all flex items-center justify-center gap-2 cursor-pointer"
                  >
                    <AlertCircle className="w-5 h-5" />
                    配置
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
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold text-gray-800">实时日志</h2>
                <span className="px-3 py-1 bg-gray-100 text-gray-700 rounded-full text-xs font-medium">
                  共 {logs.length} 条
                </span>
              </div>
              <div
                ref={logsContainerRef}
                className="bg-gray-900 rounded-lg p-4 h-64 overflow-y-auto font-mono text-sm"
              >
                {logs.length === 0 ? (
                  <p className="text-gray-500 text-center py-8">等待日志输出...</p>
                ) : (
                  logs.map((log, index) => (
                    <div key={index} className="hover:bg-gray-800 p-1.5 rounded transition-colors">
                      <div className="flex items-start gap-2">
                        <div className="flex-1 min-w-0">
                          <span className="text-gray-500 text-xs">[{log.timestamp}]</span>
                          <span className={`ml-2 ${log.type === 'success' ? 'text-green-400' :
                            log.type === 'error' ? 'text-red-400' :
                              log.type === 'warning' ? 'text-yellow-400' :
                                'text-blue-400'
                            }`}>
                            {log.message}
                          </span>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Statistics Panel */}
            {isExtracting && (
              <StatsPanel
                logs={logs}
                emails={emails}
                failedUrls={failedUrls}
                noEmailUrls={noEmailUrls}
              />
            )}

            {/* Failed URLs Section */}
            {failedUrls.length > 0 && (
              <div className="bg-white rounded-xl shadow-lg p-6">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-xl font-semibold text-red-600">失败 URL</h2>
                  <span className="px-3 py-1 bg-red-100 text-red-700 rounded-full text-sm font-medium">
                    {failedUrls.length} 个
                  </span>
                </div>
                <div className="bg-red-50 rounded-lg p-4 h-32 overflow-y-auto mb-4 text-sm">
                  {failedUrls.map((item, index) => (
                    <div key={index} className="mb-2 last:mb-0 border-b border-red-100 last:border-0 pb-2 last:pb-0">
                      <div className="font-medium text-red-800 truncate">{item.url}</div>
                      <div className="text-red-500 text-xs mt-1">{item.error}</div>
                    </div>
                  ))}
                </div>
                <button
                  onClick={exportFailedUrlsToExcel}
                  className="w-full bg-red-500 text-white py-2 rounded-lg font-medium hover:bg-red-600 transition-all flex items-center justify-center gap-2 cursor-pointer"
                >
                  <Download className="w-4 h-4" />
                  导出失败记录
                </button>
              </div>
            )}

            {/* No Email URLs Section */}
            {noEmailUrls.length > 0 && (
              <div className="bg-white rounded-xl shadow-lg p-6">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-xl font-semibold text-yellow-600">无邮箱 URL</h2>
                  <span className="px-3 py-1 bg-yellow-100 text-yellow-700 rounded-full text-sm font-medium">
                    {noEmailUrls.length} 个
                  </span>
                </div>
                <div className="bg-yellow-50 rounded-lg p-4 h-32 overflow-y-auto mb-4 text-sm">
                  {noEmailUrls.map((item, index) => (
                    <div key={index} className="mb-1 last:mb-0 text-yellow-800 truncate">
                      {item.url}
                    </div>
                  ))}
                </div>
                <button
                  onClick={exportNoEmailUrlsToExcel}
                  className="w-full bg-yellow-500 text-white py-2 rounded-lg font-medium hover:bg-yellow-600 transition-all flex items-center justify-center gap-2 cursor-pointer"
                >
                  <Download className="w-4 h-4" />
                  导出无邮箱记录
                </button>
              </div>
            )}

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
                    className="w-full bg-green-500 text-white py-2 rounded-lg font-medium hover:bg-green-600 transition-all flex items-center justify-center gap-2 cursor-pointer"
                  >
                    <Download className="w-4 h-4" />
                    导出为 CSV
                  </button>
                  <button
                    onClick={exportToExcel}
                    className="w-full bg-blue-500 text-white py-2 rounded-lg font-medium hover:bg-blue-600 transition-all flex items-center justify-center gap-2 cursor-pointer"
                  >
                    <Download className="w-4 h-4" />
                    导出为 Excel
                  </button>
                  <button
                    onClick={exportToJSON}
                    className="w-full bg-purple-500 text-white py-2 rounded-lg font-medium hover:bg-purple-600 transition-all flex items-center justify-center gap-2 cursor-pointer"
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
          <div className="bg-white rounded-xl shadow-2xl p-6 w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold text-gray-800">系统配置</h2>
              <button
                onClick={() => setShowConfig(false)}
                className="text-gray-500 hover:text-gray-700 cursor-pointer"
              >
                <EyeOff className="w-6 h-6" />
              </button>
            </div>
            <div className="overflow-y-auto flex-1 space-y-6 p-1">
              {/* Backend Configuration */}
              <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
                <h3 className="text-lg font-semibold text-gray-800 mb-3 flex items-center gap-2">
                  <div className={`w-3 h-3 rounded-full ${backendMode === 'online' ? 'bg-green-500' : 'bg-blue-500'}`}></div>
                  后端服务设置
                </h3>

                <div className="flex gap-4 mb-4">
                  <button
                    onClick={() => setBackendMode('online')}
                    className={`flex-1 py-2 px-4 rounded-lg font-medium transition-all ${backendMode === 'online'
                      ? 'bg-indigo-600 text-white shadow-md'
                      : 'bg-white text-gray-600 border border-gray-300 hover:bg-gray-50'
                      }`}
                  >
                    线上环境 (Render)
                  </button>
                  <button
                    onClick={() => setBackendMode('local')}
                    className={`flex-1 py-2 px-4 rounded-lg font-medium transition-all ${backendMode === 'local'
                      ? 'bg-indigo-600 text-white shadow-md'
                      : 'bg-white text-gray-600 border border-gray-300 hover:bg-gray-50'
                      }`}
                  >
                    本地环境 (Localhost)
                  </button>
                </div>
                <div className="space-y-3">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      线上服务地址（包括端口）
                    </label>
                    <input
                      type="text"
                      value={onlineUrl}
                      onChange={(e) => setOnlineUrl(e.target.value)}
                      className="w-full p-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                      placeholder="https://your-app.onrender.com"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      本地服务地址（包括端口）
                    </label>
                    <input
                      type="text"
                      value={localUrl}
                      onChange={(e) => setLocalUrl(e.target.value)}
                      className="w-full p-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                      placeholder="http://localhost:8888"
                    />
                  </div>
                </div>

                <div className="mt-3 text-xs text-gray-500 flex items-center gap-1">
                  <AlertCircle className="w-3 h-3" />
                  当前生效: <span className="font-mono font-medium text-indigo-600">{apiUrl || '未设置'}</span>
                </div>
              </div>
              {/* Fake Email Prefixes */}
              <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
                <h3 className="text-lg font-semibold text-gray-800 mb-3">
                  过滤配置 (Fake Email Prefixes)
                </h3>
                <div className="flex flex-wrap gap-2 max-h-40 overflow-y-auto">
                  {fakePrefixes.map((prefix, index) => (
                    <span key={index} className="px-3 py-1 bg-white border border-gray-300 rounded-full text-sm text-gray-700 shadow-sm">
                      {prefix}
                    </span>
                  ))}
                </div>
              </div>
            </div>
            <div className="mt-4 text-right border-t pt-4">
              <button
                onClick={() => setShowConfig(false)}
                className="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors cursor-pointer"
              >
                保存并关闭
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default EmailExtractorApp;