import { useEffect, useRef, useState } from "react";
import { Card, Empty } from "antd";
import dayjs from "dayjs";

interface LogEntry {
  time: string;
  level: "info" | "warn" | "error";
  message: string;
}

function generateMockLogs(): LogEntry[] {
  const logs: LogEntry[] = [];
  const messages = [
    "[Worker] 加载训练数据...",
    "[Worker] 数据预处理完成",
    "[Worker] 开始训练 epoch 1/50",
    "[Worker] Epoch 1: loss=0.4521, acc=0.7234",
    "[Worker] Epoch 2: loss=0.3812, acc=0.7511",
    "[Worker] Epoch 3: loss=0.3245, acc=0.7890",
    "[Worker] 验证集评估: val_acc=0.8012",
    "[Worker] 保存 checkpoint...",
  ];
  for (let i = 0; i < messages.length; i++) {
    logs.push({
      time: dayjs().subtract(messages.length - i, "minute").format("HH:mm:ss"),
      level: "info",
      message: messages[i],
    });
  }
  return logs;
}

export default function TaskLogPanel() {
  const [logs, _setLogs] = useState<LogEntry[]>(generateMockLogs());
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [logs]);

  return (
    <Card
      title="训练日志"
      className="industrial-card"
      classNames={{ body: "p-0" }}
      extra={<span className="text-xs text-gray-400">实时</span>}
    >
      <div ref={containerRef} className="terminal-log">
        {logs.length === 0 ? (
          <Empty description="暂无日志" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : (
          logs.map((log, i) => (
            <div key={i} className="flex gap-2">
              <span className="log-time shrink-0">[{log.time}]</span>
              <span className={log.level === "error" ? "log-error" : log.level === "warn" ? "log-warn" : ""}>
                {log.message}
              </span>
            </div>
          ))
        )}
        <div className="flex items-center gap-2 mt-2">
          <span className="inline-block w-2 h-2 bg-green-400 rounded-full animate-pulse" />
          <span className="text-xs text-gray-500">等待任务...</span>
        </div>
      </div>
    </Card>
  );
}
