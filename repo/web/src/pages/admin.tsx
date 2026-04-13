import React, { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/router";
import ReactECharts from "echarts-for-react";

import { useAuth } from "../providers/AuthProvider";
import {
  AdminAccessLog,
  AdminAccessStats,
  AdminClearCacheResult,
  AdminSystemStatus,
  AdminUser,
  clearAdminCache,
  getAdminAccessLogs,
  getAdminAccessStats,
  getAdminSystemStatus,
  getAdminUsers,
  updateAdminUser,
} from "../services/api";

function formatDateTime(value: string | null | undefined) {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "--";
  return date.toLocaleString("zh-CN");
}

function formatDuration(ms: number) {
  if (ms >= 1000) return `${(ms / 1000).toFixed(2)} s`;
  return `${ms.toFixed(1)} ms`;
}

export default function AdminPage() {
  const router = useRouter();
  const { isAuthenticated, isAdmin, token } = useAuth();

  const [users, setUsers] = useState<AdminUser[]>([]);
  const [usersTotal, setUsersTotal] = useState(0);
  const [usersLimit] = useState(20);
  const [usersOffset, setUsersOffset] = useState(0);
  const [usersLoading, setUsersLoading] = useState(false);
  const [usersError, setUsersError] = useState<string | null>(null);

  const [systemStatus, setSystemStatus] = useState<AdminSystemStatus | null>(null);
  const [systemLoading, setSystemLoading] = useState(false);
  const [systemError, setSystemError] = useState<string | null>(null);

  const [cachePattern, setCachePattern] = useState("");
  const [cacheClearing, setCacheClearing] = useState(false);
  const [cacheResult, setCacheResult] = useState<AdminClearCacheResult | null>(null);
  const [cacheError, setCacheError] = useState<string | null>(null);

  const [accessStats, setAccessStats] = useState<AdminAccessStats | null>(null);
  const [accessLogs, setAccessLogs] = useState<AdminAccessLog[]>([]);
  const [accessLoading, setAccessLoading] = useState(false);
  const [accessError, setAccessError] = useState<string | null>(null);

  useEffect(() => {
    if (!isAuthenticated) {
      router.replace("/auth");
      return;
    }
    if (!isAdmin) {
      router.replace("/");
      return;
    }
  }, [isAuthenticated, isAdmin, router]);

  const fetchUsers = async (offset = 0) => {
    if (!token) return;
    setUsersLoading(true);
    setUsersError(null);
    try {
      const res = await getAdminUsers(token, { limit: usersLimit, offset });
      setUsers(res.items);
      setUsersTotal(res.total);
      setUsersOffset(res.offset);
    } catch (err) {
      setUsersError(err instanceof Error ? err.message : "加载用户列表失败");
    } finally {
      setUsersLoading(false);
    }
  };

  const fetchSystemStatus = async () => {
    if (!token) return;
    setSystemLoading(true);
    setSystemError(null);
    try {
      const res = await getAdminSystemStatus(token);
      setSystemStatus(res);
    } catch (err) {
      setSystemError(err instanceof Error ? err.message : "加载系统状态失败");
    } finally {
      setSystemLoading(false);
    }
  };

  const fetchAccessData = async () => {
    if (!token) return;
    setAccessLoading(true);
    setAccessError(null);
    try {
      const [stats, logs] = await Promise.all([
        getAdminAccessStats(token),
        getAdminAccessLogs(token, 100),
      ]);
      setAccessStats(stats);
      setAccessLogs(logs);
    } catch (err) {
      setAccessError(err instanceof Error ? err.message : "加载访问数据失败");
    } finally {
      setAccessLoading(false);
    }
  };

  useEffect(() => {
    if (isAdmin && token) {
      fetchUsers(0);
      fetchSystemStatus();
      fetchAccessData();
      const interval = setInterval(() => {
        fetchAccessData();
      }, 10000);
      return () => clearInterval(interval);
    }
  }, [isAdmin, token]);

  const handleToggleUserActive = async (user: AdminUser) => {
    if (!token) return;
    try {
      await updateAdminUser(token, user.id, { is_active: !user.is_active });
      fetchUsers(usersOffset);
    } catch (err) {
      alert(err instanceof Error ? err.message : "操作失败");
    }
  };

  const handleToggleUserAdmin = async (user: AdminUser) => {
    if (!token) return;
    try {
      await updateAdminUser(token, user.id, { is_admin: !user.is_admin });
      fetchUsers(usersOffset);
    } catch (err) {
      alert(err instanceof Error ? err.message : "操作失败");
    }
  };

  const handleClearCache = async (pattern?: string) => {
    if (!token) return;
    setCacheClearing(true);
    setCacheResult(null);
    setCacheError(null);
    try {
      const res = await clearAdminCache(token, { pattern: pattern || null });
      setCacheResult(res);
      fetchSystemStatus();
    } catch (err) {
      setCacheError(err instanceof Error ? err.message : "清理缓存失败");
    } finally {
      setCacheClearing(false);
    }
  };

  const perfMetrics = useMemo(() => {
    if (!accessLogs.length) {
      return { avg: 0, p95: 0, p99: 0, errorRate: 0, qps: 0 };
    }
    const durations = accessLogs.map((l) => l.duration_ms).sort((a, b) => a - b);
    const avg = durations.reduce((a, b) => a + b, 0) / durations.length;
    const p95 = durations[Math.floor(durations.length * 0.95)] || durations[durations.length - 1];
    const p99 = durations[Math.floor(durations.length * 0.99)] || durations[durations.length - 1];
    const errors = accessLogs.filter((l) => l.status >= 500).length;
    const errorRate = errors / accessLogs.length;
    const timeSpanSec = Math.max(1, (new Date(accessLogs[accessLogs.length - 1].timestamp).getTime() - new Date(accessLogs[0].timestamp).getTime()) / 1000);
    const qps = accessLogs.length / timeSpanSec;
    return { avg, p95, p99, errorRate, qps };
  }, [accessLogs]);

  const hourlyChartOption = useMemo(() => {
    const data = accessStats?.hourly_counts || [];
    return {
      tooltip: { trigger: "axis" },
      grid: { left: "3%", right: "4%", bottom: "3%", containLabel: true },
      xAxis: { type: "category", data: data.map((d) => d.hour.slice(11, 13) + ":00"), boundaryGap: false },
      yAxis: { type: "value", minInterval: 1 },
      series: [
        {
          data: data.map((d) => d.count),
          type: "line",
          smooth: true,
          areaStyle: { color: "rgba(37, 99, 235, 0.15)" },
          itemStyle: { color: "#2563eb" },
        },
      ],
    };
  }, [accessStats]);

  const statusChartOption = useMemo(() => {
    const data = accessStats?.status_distribution || [];
    return {
      tooltip: { trigger: "item" },
      series: [
        {
          type: "pie",
          radius: ["40%", "70%"],
          data: data.map((d) => ({ value: d.count, name: String(d.status) })),
          label: { formatter: "{b}: {c} ({d}%)" },
        },
      ],
    };
  }, [accessStats]);

  const totalPages = useMemo(() => Math.max(1, Math.ceil(usersTotal / usersLimit)), [usersTotal, usersLimit]);
  const currentPage = useMemo(() => Math.floor(usersOffset / usersLimit) + 1, [usersOffset, usersLimit]);

  if (!isAuthenticated || !isAdmin) {
    return (
      <div style={{ padding: 40, textAlign: "center", color: "var(--muted)" }}>
        检查权限中...
      </div>
    );
  }

  return (
    <div className="stack-lg" style={{ padding: "24px 28px", maxWidth: 1400, margin: "0 auto" }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0 }}>管理后台</h1>

      <section className="surface-panel" style={{ borderRadius: 16, padding: 20 }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, margin: "0 0 14px" }}>系统状态</h2>
        {systemLoading && !systemStatus ? (
          <div style={{ color: "var(--muted)" }}>加载中...</div>
        ) : systemError ? (
          <div style={{ color: "#b91c1c" }}>{systemError}</div>
        ) : systemStatus ? (
          <div className="metric-grid">
            <div className="metric-panel">
              <div className="metric-panel__label">应用名称</div>
              <div className="metric-panel__value" style={{ fontSize: 18 }}>{systemStatus.app_name}</div>
            </div>
            <div className="metric-panel">
              <div className="metric-panel__label">数据库</div>
              <div className="metric-panel__value" style={{ fontSize: 14, wordBreak: "break-all" }}>{systemStatus.database_url}</div>
            </div>
            <div className="metric-panel">
              <div className="metric-panel__label">Redis</div>
              <div className="metric-panel__value" style={{ fontSize: 14, wordBreak: "break-all" }}>{systemStatus.redis_url}</div>
            </div>
            <div className="metric-panel">
              <div className="metric-panel__label">内存缓存条目</div>
              <div className="metric-panel__value">{systemStatus.cache_stats.memory_cache?.size ?? "--"}</div>
              <div className="metric-panel__helper">
                上限 {systemStatus.cache_stats.memory_cache?.max_size ?? "--"}
              </div>
            </div>
            <div className="metric-panel">
              <div className="metric-panel__label">Redis 命中次数</div>
              <div className="metric-panel__value">
                {systemStatus.cache_stats.redis_cache?.keyspace_hits ?? "--"}
              </div>
            </div>
            <div className="metric-panel">
              <div className="metric-panel__label">Redis 未命中次数</div>
              <div className="metric-panel__value">
                {systemStatus.cache_stats.redis_cache?.keyspace_misses ?? "--"}
              </div>
            </div>
          </div>
        ) : null}
      </section>

      <section className="surface-panel" style={{ borderRadius: 16, padding: 20 }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, margin: "0 0 14px" }}>性能监控</h2>
        {accessLoading && !accessStats ? (
          <div style={{ color: "var(--muted)" }}>加载中...</div>
        ) : accessError ? (
          <div style={{ color: "#b91c1c" }}>{accessError}</div>
        ) : (
          <div className="metric-grid">
            <div className="metric-panel">
              <div className="metric-panel__label">平均响应时间</div>
              <div className="metric-panel__value">{formatDuration(perfMetrics.avg)}</div>
            </div>
            <div className="metric-panel">
              <div className="metric-panel__label">P95 响应时间</div>
              <div className="metric-panel__value">{formatDuration(perfMetrics.p95)}</div>
            </div>
            <div className="metric-panel">
              <div className="metric-panel__label">P99 响应时间</div>
              <div className="metric-panel__value">{formatDuration(perfMetrics.p99)}</div>
            </div>
            <div className="metric-panel">
              <div className="metric-panel__label">错误率 (5xx)</div>
              <div className="metric-panel__value">{(perfMetrics.errorRate * 100).toFixed(2)}%</div>
            </div>
            <div className="metric-panel">
              <div className="metric-panel__label">实时 QPS</div>
              <div className="metric-panel__value">{perfMetrics.qps.toFixed(2)}</div>
            </div>
            <div className="metric-panel">
              <div className="metric-panel__label">总请求数（近 2000 条）</div>
              <div className="metric-panel__value">{accessStats?.total_requests ?? "--"}</div>
            </div>
          </div>
        )}
      </section>

      <section className="surface-panel" style={{ borderRadius: 16, padding: 20 }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, margin: "0 0 14px" }}>访问分析</h2>
        {accessLoading && !accessStats ? (
          <div style={{ color: "var(--muted)" }}>加载中...</div>
        ) : accessError ? (
          <div style={{ color: "#b91c1c" }}>{accessError}</div>
        ) : (
          <div className="stack-md">
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 16 }}>
              <div>
                <div style={{ fontWeight: 600, marginBottom: 8 }}>每小时访问量趋势</div>
                <ReactECharts option={hourlyChartOption} style={{ height: 260 }} />
              </div>
              <div>
                <div style={{ fontWeight: 600, marginBottom: 8 }}>状态码分布</div>
                <ReactECharts option={statusChartOption} style={{ height: 260 }} />
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16 }}>
              <div className="surface-panel" style={{ borderRadius: 12, padding: 16 }}>
                <div style={{ fontWeight: 600, marginBottom: 10 }}>Top 10 访问 IP</div>
                <table className="data-table dense-table">
                  <thead>
                    <tr>
                      <th>IP 地址</th>
                      <th>请求数</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(accessStats?.top_ips || []).map((item) => (
                      <tr key={item.ip}>
                        <td>{item.ip}</td>
                        <td>{item.count}</td>
                      </tr>
                    ))}
                    {!accessStats?.top_ips?.length && (
                      <tr><td colSpan={2} style={{ color: "var(--muted)" }}>暂无数据</td></tr>
                    )}
                  </tbody>
                </table>
              </div>

              <div className="surface-panel" style={{ borderRadius: 12, padding: 16 }}>
                <div style={{ fontWeight: 600, marginBottom: 10 }}>Top 10 访问路径</div>
                <table className="data-table dense-table">
                  <thead>
                    <tr>
                      <th>路径</th>
                      <th>请求数</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(accessStats?.path_distribution || []).map((item) => (
                      <tr key={item.path}>
                        <td style={{ maxWidth: 240, overflow: "hidden", textOverflow: "ellipsis" }}>{item.path}</td>
                        <td>{item.count}</td>
                      </tr>
                    ))}
                    {!accessStats?.path_distribution?.length && (
                      <tr><td colSpan={2} style={{ color: "var(--muted)" }}>暂无数据</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="surface-panel" style={{ borderRadius: 12, padding: 16 }}>
              <div style={{ fontWeight: 600, marginBottom: 10 }}>最近访问记录（含 IP）</div>
              <div style={{ overflow: "auto", maxHeight: 320 }}>
                <table className="data-table dense-table">
                  <thead>
                    <tr>
                      <th>时间</th>
                      <th>IP</th>
                      <th>方法</th>
                      <th>路径</th>
                      <th>状态</th>
                      <th>耗时</th>
                    </tr>
                  </thead>
                  <tbody>
                    {accessLogs.map((log, idx) => (
                      <tr key={`${log.timestamp}-${idx}`}>
                        <td>{formatDateTime(log.timestamp)}</td>
                        <td>{log.client_ip}</td>
                        <td>{log.method}</td>
                        <td style={{ maxWidth: 280, overflow: "hidden", textOverflow: "ellipsis" }}>{log.path}</td>
                        <td>
                          <span
                            style={{
                              display: "inline-block",
                              padding: "2px 8px",
                              borderRadius: 999,
                              fontSize: 12,
                              fontWeight: 600,
                              background: log.status < 400 ? "rgba(21,128,61,0.12)" : log.status < 500 ? "rgba(194,65,12,0.12)" : "rgba(185,28,28,0.12)",
                              color: log.status < 400 ? "#15803d" : log.status < 500 ? "#c2410c" : "#b91c1c",
                            }}
                          >
                            {log.status}
                          </span>
                        </td>
                        <td>{formatDuration(log.duration_ms)}</td>
                      </tr>
                    ))}
                    {!accessLogs.length && (
                      <tr><td colSpan={6} style={{ color: "var(--muted)" }}>暂无数据</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </section>

      <section className="surface-panel" style={{ borderRadius: 16, padding: 20 }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, margin: "0 0 14px" }}>缓存清理</h2>
        <div className="control-bar">
          <button
            type="button"
            className="action-card action-card-blue"
            style={{ padding: "10px 16px", fontWeight: 600 }}
            disabled={cacheClearing}
            onClick={() => handleClearCache()}
          >
            {cacheClearing ? "清理中..." : "清理全部缓存"}
          </button>
          <div className="field-stack" style={{ flex: 1, minWidth: 200 }}>
            <label>按前缀/通配符清理</label>
            <input
              type="text"
              value={cachePattern}
              onChange={(e) => setCachePattern(e.target.value)}
              placeholder="例如 macro:*"
              style={{
                padding: "8px 12px",
                borderRadius: 10,
                border: "1px solid var(--border)",
                fontSize: 14,
              }}
            />
          </div>
          <button
            type="button"
            className="action-card"
            style={{ padding: "10px 16px", fontWeight: 600 }}
            disabled={cacheClearing || !cachePattern.trim()}
            onClick={() => handleClearCache(cachePattern.trim())}
          >
            {cacheClearing ? "清理中..." : "按规则清理"}
          </button>
        </div>
        {cacheResult ? (
          <div style={{ marginTop: 12, color: "#15803d", fontWeight: 600 }}>
            成功清理 {cacheResult.cleared_count} 条缓存
            {cacheResult.pattern ? `（规则：${cacheResult.pattern}）` : "（全部缓存）"}
          </div>
        ) : null}
        {cacheError ? (
          <div style={{ marginTop: 12, color: "#b91c1c" }}>{cacheError}</div>
        ) : null}
      </section>

      <section className="surface-panel" style={{ borderRadius: 16, padding: 20 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          <h2 style={{ fontSize: 16, fontWeight: 700, margin: 0 }}>用户管理</h2>
          <div style={{ color: "var(--muted)", fontSize: 12 }}>共 {usersTotal} 位用户</div>
        </div>

        {usersLoading && users.length === 0 ? (
          <div style={{ color: "var(--muted)" }}>加载中...</div>
        ) : usersError ? (
          <div style={{ color: "#b91c1c" }}>{usersError}</div>
        ) : (
          <div style={{ overflow: "auto" }}>
            <table className="data-table dense-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>邮箱</th>
                  <th>状态</th>
                  <th>管理员</th>
                  <th>创建时间</th>
                  <th>最后登录</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id}>
                    <td>{user.id}</td>
                    <td>{user.email}</td>
                    <td>
                      <span
                        style={{
                          display: "inline-block",
                          padding: "2px 8px",
                          borderRadius: 999,
                          fontSize: 12,
                          fontWeight: 600,
                          background: user.is_active ? "rgba(21,128,61,0.12)" : "rgba(185,28,28,0.12)",
                          color: user.is_active ? "#15803d" : "#b91c1c",
                        }}
                      >
                        {user.is_active ? "正常" : "禁用"}
                      </span>
                    </td>
                    <td>
                      <span
                        style={{
                          display: "inline-block",
                          padding: "2px 8px",
                          borderRadius: 999,
                          fontSize: 12,
                          fontWeight: 600,
                          background: user.is_admin ? "rgba(37,99,235,0.12)" : "rgba(71,85,103,0.12)",
                          color: user.is_admin ? "#2563eb" : "#475467",
                        }}
                      >
                        {user.is_admin ? "是" : "否"}
                      </span>
                    </td>
                    <td>{formatDateTime(user.created_at)}</td>
                    <td>{formatDateTime(user.last_login_at)}</td>
                    <td>
                      <div style={{ display: "flex", gap: 8 }}>
                        <button
                          type="button"
                          className="nav-link"
                          style={{
                            padding: "4px 10px",
                            fontSize: 12,
                            background: user.is_active ? "rgba(185,28,28,0.12)" : "rgba(21,128,61,0.12)",
                            color: user.is_active ? "#b91c1c" : "#15803d",
                          }}
                          onClick={() => handleToggleUserActive(user)}
                        >
                          {user.is_active ? "禁用" : "启用"}
                        </button>
                        <button
                          type="button"
                          className="nav-link"
                          style={{
                            padding: "4px 10px",
                            fontSize: 12,
                            background: user.is_admin ? "rgba(71,85,103,0.12)" : "rgba(37,99,235,0.12)",
                            color: user.is_admin ? "#475467" : "#2563eb",
                          }}
                          onClick={() => handleToggleUserAdmin(user)}
                        >
                          {user.is_admin ? "取消管理员" : "设为管理员"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {usersTotal > usersLimit ? (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 12, marginTop: 16 }}>
            <button
              type="button"
              className="nav-link"
              style={{ fontSize: 12 }}
              disabled={usersOffset === 0 || usersLoading}
              onClick={() => fetchUsers(Math.max(0, usersOffset - usersLimit))}
            >
              上一页
            </button>
            <span style={{ fontSize: 12, color: "var(--muted)" }}>
              第 {currentPage} / {totalPages} 页
            </span>
            <button
              type="button"
              className="nav-link"
              style={{ fontSize: 12 }}
              disabled={usersOffset + usersLimit >= usersTotal || usersLoading}
              onClick={() => fetchUsers(usersOffset + usersLimit)}
            >
              下一页
            </button>
          </div>
        ) : null}
      </section>
    </div>
  );
}
