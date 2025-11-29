// 类型定义
interface Log {
    type: 'success' | 'error' | 'info' | 'warning';
    message: string;
}

interface StatsPanelProps {
    logs: Log[];
    emails: string[];
    failedUrls: any[];
    noEmailUrls: any[];
}

interface Stat {
    label: string;
    value: number;
    color: 'blue' | 'red' | 'green' | 'purple' | 'yellow';
}

// 统计面板组件
function StatsPanel({ logs, emails, failedUrls, noEmailUrls }: StatsPanelProps) {
    const stats: Stat[] = [
        { label: '提取邮箱', value: emails.length, color: 'green' },
        { label: '失败 URL', value: failedUrls.length, color: 'red' },
        { label: '无邮箱 URL', value: noEmailUrls.length, color: 'yellow' },
        { label: '成功日志', value: logs.filter(l => l.type === 'success').length, color: 'blue' },
        { label: '总日志', value: logs.length, color: 'purple' },
    ];

    const colorMap: Record<Stat['color'], string> = {
        blue: 'bg-blue-100 text-blue-700 border-blue-200',
        red: 'bg-red-100 text-red-700 border-red-200',
        green: 'bg-green-100 text-green-700 border-green-200',
        purple: 'bg-purple-100 text-purple-700 border-purple-200',
        yellow: 'bg-yellow-100 text-yellow-700 border-yellow-200',
    };

    return (
        <div className="bg-white rounded-lg shadow p-4">
            <h2 className="text-lg font-semibold text-gray-800 mb-3 flex items-center gap-2">
                <span>📊</span>
                <span>实时统计</span>
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
                {stats.map((stat, index) => (
                    <div
                        key={index}
                        className={`${colorMap[stat.color]} border rounded-lg p-3 transition-all hover:scale-105 hover:shadow-md`}
                    >
                        <p className="text-xs font-medium opacity-80 mb-1">{stat.label}</p>
                        <p className="text-2xl font-bold">{stat.value}</p>
                    </div>
                ))}
            </div>
        </div>
    );
}

export default StatsPanel;