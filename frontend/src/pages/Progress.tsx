import { useState, useEffect } from 'react'
import { Card, Progress as AntProgress, List, Typography, message, Empty, Button, Row, Col, Statistic, Tag } from 'antd'
import { ReloadOutlined, LeftOutlined, CheckCircleOutlined, CloseCircleOutlined, ClockCircleOutlined } from '@ant-design/icons'
import client from '../api/client'

const { Title, Text } = Typography

interface TaskStatus {
  task_id?: string
  status?: string
  total?: number
  finished?: number
  runs?: Array<{
    params: object
    run_id: string
    trade_count?: number
    win_rate?: number
    final_return?: number
    sharpe?: number
    max_drawdown?: number
    created_at?: string
  }>
  error?: string
  runs_total_count?: number
}

interface TuningTask {
  task_id: string
  strategy: string
  status: string
  total: number
  finished: number
  start_time?: string | null
  created_at: string
  error?: string | null
}

export default function ProgressPage() {
  const [taskId, setTaskId] = useState<string | null>(null)
  const [taskStatus, setTaskStatus] = useState<TaskStatus | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [allTasks, setAllTasks] = useState<TuningTask[]>([])
  const [currentPage, setCurrentPage] = useState<number>(1)
  const [pageSize, setPageSize] = useState<number>(10)

  // 查询任务状态
  const fetchTaskStatus = async (id: string, page = 1, pageSize = 10) => {
    console.log('开始查询任务状态，任务ID:', id)
    try {
      const response = await client.get(`/api/tuning/${id}`, {
        params: {
          page,
          page_size: pageSize
        }
      })
      
      // 打印完整响应信息用于调试
      console.log('任务状态查询响应:', response.data)
      
      // 更健壮的响应处理 - 检查响应是否为空或不完整
      if (!response.data || typeof response.data !== 'object') {
        console.warn('响应数据不完整或格式错误:', response.data)
        setTaskStatus({ task_id: id, error: '获取任务详情数据格式错误' })
        setLoading(false)
        return
      }
      
      // 检查响应中是否包含错误信息 - 只有当响应只有error和detail字段时，才认为是任务不存在
      if (response.data.error === 'not_found' && Object.keys(response.data).length === 2 && 'detail' in response.data) {
        console.error('查询任务状态失败: 任务不存在', id)
        const errorMessage = response.data.detail || '任务不存在或已被删除'
        message.warning(errorMessage)
        setTaskStatus({ task_id: id, error: errorMessage })
        setLoading(false)
      } else {
        console.log('正常处理任务状态数据:', response.data.status, '错误字段存在:', 'error' in response.data, '任务ID:', response.data.task_id || id)
        console.log('完整的任务状态数据:', JSON.stringify(response.data))
        console.log('数据类型检查 - status:', typeof response.data.status, 'total:', typeof response.data.total, 'finished:', typeof response.data.finished)
        // 确保任务ID存在于响应数据中
        if (!response.data.task_id) {
          response.data.task_id = id
        }
        // 创建一个新对象，确保所有字段都是正确的类型
        const formattedData = {
          task_id: response.data.task_id,
          status: response.data.status || 'unknown',
          total: typeof response.data.total === 'number' ? response.data.total : 0,
          finished: typeof response.data.finished === 'number' ? response.data.finished : 0,
          start_time: response.data.start_time || null,
          timeout: response.data.timeout || null,
          error: response.data.error || null,
          runs: Array.isArray(response.data.runs) ? response.data.runs : [],
          runs_total_count: typeof response.data.runs_total_count === 'number' ? response.data.runs_total_count : 0
        }
        console.log('格式化后的数据:', JSON.stringify(formattedData))
        setTaskStatus(formattedData)
        setLoading(false)
      }
    } catch (err) {
      console.error('查询任务状态失败:', err)
      // 尝试从错误对象中提取详细错误信息，添加类型检查
      let errorMessage = '获取任务详情失败'
      
      if (typeof err === 'object' && err !== null && 'response' in err) {
        const axiosError = err as { response?: { status?: number, data?: any } }
        console.error('Axios错误详情:', axiosError.response?.status, axiosError.response?.data)
        
        // 特殊处理404错误
        if (axiosError.response?.status === 404) {
          errorMessage = '任务不存在或已被删除'
          // 不自动导航，让用户决定是否返回
        } else if (axiosError.response?.data?.detail) {
          errorMessage = axiosError.response.data.detail
        } else if (axiosError.response?.data?.error) {
          errorMessage = axiosError.response.data.error
        }
      } else if (err instanceof Error) {
        errorMessage = err.message
      }
      
      // 显示更友好的错误消息
      message.warning(errorMessage)
      // 确保即使taskStatus为null也能正确设置错误状态
      setTaskStatus({ task_id: id, error: errorMessage })
      setLoading(false)
    }
  }

  // 查询所有任务列表
  const fetchAllTasks = async () => {
    try {
      setLoading(true)
      const response = await client.get('/api/tuning')
      setAllTasks(response.data.tasks)
      setLoading(false)
    } catch (err) {
      console.error('查询任务列表失败:', err)
      let errorMessage = '查询任务列表失败，请刷新页面重试'
      // 尝试从错误对象中提取详细错误信息，添加类型检查
      if (typeof err === 'object' && err !== null && 'response' in err) {
        const axiosError = err as { response?: { data?: { detail?: string } } }
        if (axiosError.response?.data?.detail) {
          errorMessage = `查询任务列表失败: ${axiosError.response.data.detail}`
        }
      } else if (err instanceof Error) {
        errorMessage = `查询任务列表失败: ${err.message}`
      }
      message.error(errorMessage)
      setAllTasks([])
      setLoading(false)
    }
  }

  // 初始化时获取任务列表
  useEffect(() => {
    fetchAllTasks()
  }, [])

  // 重新加载任务状态或任务列表
  const handleRefresh = () => {
    if (taskId) {
      setLoading(true)
      fetchTaskStatus(taskId, currentPage, pageSize)
    } else {
      fetchAllTasks()
    }
  }

  // 查看任务详情
  const handleViewTask = (task: TuningTask) => {
    console.log('处理查看任务详情，任务ID:', task.task_id)
    // 确保任务ID有效
    if (!task.task_id) {
      console.error('任务ID无效:', task)
      message.error('无法查看任务详情：任务ID无效')
      return
    }
    // 直接设置taskId并获取任务状态，避免URL导航问题
    setTaskId(task.task_id)
    // 重置分页状态
    setCurrentPage(1)
    setPageSize(10)
    fetchTaskStatus(task.task_id)
  }

  // 返回任务列表
  const handleBack = () => {
    console.log('返回任务列表')
    // 直接设置taskId为null并刷新任务列表，避免URL导航问题
    setTaskId(null)
    fetchAllTasks()
  }

  // 获取状态对应的图标
  const getStatusIcon = (status?: string) => {
    switch (status) {
      case 'finished':
        return <CheckCircleOutlined className="status-icon status-success" />
      case 'error':
        return <CloseCircleOutlined className="status-icon status-error" />
      case 'running':
        return <ClockCircleOutlined className="status-icon status-running" />
      case 'pending':
        return <ClockCircleOutlined className="status-icon status-pending" />
      default:
        return null
    }
  }

  // 获取状态对应的文本
  const getStatusText = (status?: string) => {
    const statusMap: Record<string, string> = {
      'pending': '等待中',
      'running': '运行中',
      'finished': '已完成',
      'error': '出错'
    }
    return statusMap[status || ''] || '未知'
  }

  // 获取状态对应的标签颜色
  const getStatusColor = (status?: string) => {
    const colorMap: Record<string, string> = {
      'pending': 'default',
      'running': 'processing',
      'finished': 'success',
      'error': 'error'
    }
    return colorMap[status || ''] || 'default'
  }

  return (
    <div className="progress-page">
      <Card className="main-card">
        <div className="header-section">
          <Row gutter={[16, 16]} align="middle">
            <Col flex="auto">
              <Title level={4} className="page-title">{taskId ? '任务详情' : '任务列表'}</Title>
            </Col>
            <Col>
              {taskId ? (
                <Button 
                  type="primary" 
                  icon={<LeftOutlined />} 
                  onClick={handleBack}
                  className="back-button"
                >
                  返回任务列表
                </Button>
              ) : null}
              {!taskId && (
                <Button 
                  icon={<ReloadOutlined />} 
                  onClick={handleRefresh}
                  loading={loading}
                  className="refresh-button"
                  style={{ marginLeft: '8px' }}
                >
                  刷新列表
                </Button>
              )}
            </Col>
          </Row>
        </div>

        {!taskId ? (
          <div className="tasks-list-section">
            <Card title="调优任务列表" className="tasks-list-card">
              {loading ? (
                <div className="loading-state">
                  <div className="loading-spinner">加载中...</div>
                </div>
              ) : allTasks.length > 0 ? (
                <div className="tasks-table-container">
                  <div className="tasks-table-header">
                    <div className="table-cell table-cell-strategy">策略名称</div>
                    <div className="table-cell table-cell-id">任务ID</div>
                    <div className="table-cell table-cell-progress">进度</div>
                    <div className="table-cell table-cell-status">状态</div>
                    <div className="table-cell table-cell-time">创建时间</div>
                    <div className="table-cell table-cell-action">操作</div>
                  </div>
                  <div className="tasks-table-body">
                    {allTasks.map((task) => (
                      <div 
                        key={task.task_id} 
                        className="task-row"
                        onClick={() => handleViewTask(task)}
                      >
                        <div className="table-cell table-cell-strategy">
                          <div className="task-strategy">{task.strategy}</div>
                        </div>
                        <div className="table-cell table-cell-id">
                          <div className="task-id truncate">{task.task_id}</div>
                        </div>
                        <div className="table-cell table-cell-progress">
                          <div className="task-progress">
                            <div className="progress-text">
                              {task.finished}/{task.total} ({Math.round((task.finished / task.total) * 100)}%)
                            </div>
                            <AntProgress 
                              percent={Math.round((task.finished / task.total) * 100)}
                              size="small"
                              strokeColor={{
                                '0%': '#108ee9',
                                '100%': '#87d068'
                              }}
                            />
                          </div>
                        </div>
                        <div className="table-cell table-cell-status">
                          <Tag 
                            color={getStatusColor(task.status)} 
                            className="status-tag"
                          >
                            {getStatusText(task.status)}
                          </Tag>
                        </div>
                        <div className="table-cell table-cell-time">
                          <div className="task-time">{task.created_at}</div>
                        </div>
                        <div className="table-cell table-cell-action">
                          <Button 
                            type="link" 
                            onClick={(e) => {
                              e.stopPropagation();
                              handleViewTask(task);
                            }}
                          >
                            查看详情
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="tasks-table-pagination">
                    <List
                      pagination={{
                        pageSize: 10,
                        showSizeChanger: true,
                        showTotal: (total) => `共 ${total} 条记录`
                      }}
                      dataSource={[]}
                      renderItem={() => null}
                    />
                  </div>
                </div>
              ) : (
                <Empty 
                  description="暂无调优任务"
                  className="empty-state"
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                />
              )}
            </Card>
          </div>
        ) : (
          <div className="task-section">
            <Card title="任务信息" className="task-info-card">
              <Row gutter={[16, 16]}>
                <Col xs={24} sm={12} md={8}>
                  <div className="task-info-item">
                    <Text type="secondary">任务ID:</Text>
                    <Text className="task-info-value">{taskId}</Text>
                  </div>
                </Col>
                <Col xs={24} sm={12} md={8}>
                  <div className="task-info-item">
                    <Text type="secondary">当前状态:</Text>
                    <div className="status-display">
                      {getStatusIcon(taskStatus?.status)}
                      <Text className="task-info-value status-text">
                        {getStatusText(taskStatus?.status)}
                      </Text>
                    </div>
                  </div>
                </Col>
                <Col xs={24} sm={12} md={8}>
                  <div className="task-info-item">
                    <Button 
                      icon={<ReloadOutlined />} 
                      onClick={handleRefresh}
                      loading={loading}
                      className="refresh-button"
                    >
                      刷新状态
                    </Button>
                  </div>
                </Col>
              </Row>
            </Card>

            {taskStatus?.error && (
              <Card className="error-card">
                <div className="error-content">
                  <CloseCircleOutlined className="error-icon" />
                  <Text type="danger">任务执行出错: {taskStatus.error}</Text>
                </div>
              </Card>
            )}

            <Card title="进度概览" className="progress-card">
              <Row gutter={[16, 16]}>
                <Col xs={24} md={8}>
                  <Statistic 
                    title="总组合数" 
                    value={taskStatus?.total || 0}
                    className="stat-item"
                  />
                </Col>
                <Col xs={24} md={8}>
                  <Statistic 
                    title="已完成" 
                    value={taskStatus?.finished || 0}
                    className="stat-item"
                  />
                </Col>
                <Col xs={24} md={8}>
                  <Statistic 
                    title="完成率" 
                    value={
                      taskStatus?.total && taskStatus?.finished 
                        ? Math.round((taskStatus.finished / taskStatus.total) * 100)
                        : 0
                    }
                    suffix="%"
                    className="stat-item"
                  />
                </Col>
              </Row>

              <AntProgress 
                percent={
                  taskStatus?.total && taskStatus?.finished 
                    ? Math.round((taskStatus.finished / taskStatus.total) * 100)
                    : 0
                }
                strokeColor={{
                  '0%': '#108ee9',
                  '100%': '#87d068'
                }}
                className="progress-bar"
                status={taskStatus?.status === 'error' ? 'exception' : undefined}
              />
            </Card>

            <Card title="已完成组合" className="results-card">
              {taskStatus?.runs && taskStatus.runs.length > 0 ? (
                <div className="runs-table-container">
                  <div className="runs-table-header">
                    <div className="runs-table-cell runs-table-cell-id">Run ID</div>
                    <div className="runs-table-cell runs-table-cell-params">参数</div>
                    <div className="runs-table-cell runs-table-cell-stats">交易次数</div>
                    <div className="runs-table-cell runs-table-cell-stats">胜率</div>
                    <div className="runs-table-cell runs-table-cell-stats">最终收益</div>
                    <div className="runs-table-cell runs-table-cell-stats">夏普率</div>
                    <div className="runs-table-cell runs-table-cell-stats">最大回撤</div>
                    <div className="runs-table-cell runs-table-cell-time">完成时间</div>
                  </div>
                  <div className="runs-table-body">
                    {taskStatus.runs.map((item) => (
                      <div key={item.run_id} className="runs-table-row">
                        <div className="runs-table-cell runs-table-cell-id">{item.run_id}</div>
                        <div className="runs-table-cell runs-table-cell-params">{JSON.stringify(item.params)}</div>
                        <div className="runs-table-cell runs-table-cell-stats">{item.trade_count || 0}</div>
                        <div className="runs-table-cell runs-table-cell-stats">{item.win_rate ? `${(item.win_rate * 100).toFixed(2)}%` : '-'}</div>
                        <div className="runs-table-cell runs-table-cell-stats">{item.final_return ? `${(item.final_return * 100).toFixed(2)}%` : '-'}</div>
                        <div className="runs-table-cell runs-table-cell-stats">{item.sharpe ? item.sharpe.toFixed(2) : '-'}</div>
                        <div className="runs-table-cell runs-table-cell-stats">{item.max_drawdown ? `${(item.max_drawdown * 100).toFixed(2)}%` : '-'}</div>
                        <div className="runs-table-cell runs-table-cell-time">{item.created_at || '-'}</div>
                      </div>
                    ))}
                  </div>
                  
                  {/* 分页控件 */}
                  {taskStatus?.runs_total_count && taskStatus.runs_total_count > pageSize && (
                    <div className="runs-table-pagination">
                      <List
                        pagination={{
                          current: currentPage,
                          pageSize: pageSize,
                          total: taskStatus.runs_total_count,
                          showSizeChanger: true,
                          showTotal: (total) => `共 ${total} 条记录`,
                          onChange: (page, size) => {
                            setCurrentPage(page);
                            setPageSize(size);
                            fetchTaskStatus(taskId!, page, size);
                          },
                          onShowSizeChange: (_current, size) => {
                            setCurrentPage(1);
                            setPageSize(size);
                            fetchTaskStatus(taskId!, 1, size);
                          }
                        }}
                        dataSource={[]}
                        renderItem={() => null}
                      />
                    </div>
                  )}
                </div>
              ) : (
                <Empty description="暂无已完成的组合" />
              )}
            </Card>
          </div>
        )}
      </Card>

      {/* 内联样式定义 */}
      <style>
      {`
        .tasks-list-section {
          margin-top: 16px;
        }
        
        .tasks-list-card {
          border: 1px solid #d9d9d9;
          border-radius: 8px;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
        }
        
        .loading-state {
          padding: 80px 0;
          text-align: center;
          color: #1890ff;
        }
        
        .loading-spinner {
          font-size: 16px;
          color: #1890ff;
          animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        
        .tasks-table-container {
          border-radius: 4px;
          overflow: hidden;
        }
        
        .tasks-table-header {
          display: flex;
          background-color: #fafafa;
          border-bottom: 1px solid #f0f0f0;
          padding: 0 24px;
          font-weight: 600;
          color: #333;
          position: sticky;
          top: 0;
          z-index: 1;
        }
        
        .table-cell {
          padding: 12px 8px;
          display: flex;
          align-items: center;
          overflow: hidden;
        }
        
        .table-cell-strategy {
          width: 150px;
        }
        
        .table-cell-id {
          flex: 1;
          min-width: 200px;
        }
        
        .table-cell-progress {
          width: 200px;
        }
        
        .table-cell-status {
          width: 100px;
        }
        
        .table-cell-time {
          width: 160px;
        }
        
        .table-cell-action {
          width: 100px;
          justify-content: flex-end;
        }
        
        .tasks-table-body {
          max-height: 600px;
          overflow-y: auto;
        }
        
        .task-row {
          display: flex;
          padding: 0 24px;
          border-bottom: 1px solid #f0f0f0;
          cursor: pointer;
          transition: background-color 0.2s;
        }
        
        .task-row:hover {
          background-color: #f5f5f5;
        }
        
        .task-row:last-child {
          border-bottom: none;
        }
        
        .task-strategy {
          font-weight: 500;
          color: #333;
        }
        
        .task-id {
          color: #666;
          font-size: 13px;
        }
        
        .truncate {
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        
        .task-progress {
          width: 100%;
        }
        
        .progress-text {
          font-size: 12px;
          color: #666;
          margin-bottom: 4px;
        }
        
        .status-tag {
          font-size: 12px;
          padding: 2px 8px;
        }
        
        .task-time {
          font-size: 13px;
          color: #999;
        }
        
        .tasks-table-pagination {
          padding: 16px 24px;
          border-top: 1px solid #f0f0f0;
          background-color: #fff;
        }
        
        .empty-state {
          padding: 80px 0;
          text-align: center;
        }
        
        /* 响应式布局 */
        @media (max-width: 1200px) {
          .table-cell-progress {
            width: 150px;
          }
          
          .table-cell-strategy {
            width: 120px;
          }
        }
        
        @media (max-width: 768px) {
          .tasks-table-container {
            font-size: 12px;
          }
          
          .tasks-table-header {
            padding: 0 12px;
            font-size: 11px;
          }
          
          .task-row {
            padding: 0 12px;
          }
          
          .table-cell {
            padding: 10px 4px;
          }
          
          .table-cell-strategy {
            width: 90px;
          }
          
          .table-cell-id {
            min-width: 150px;
          }
          
          .table-cell-progress {
            width: 120px;
          }
          
          .table-cell-status {
            width: 80px;
          }
          
          .table-cell-time {
            width: 120px;
          }
          
          .table-cell-action {
            width: 80px;
          }
          
          .tasks-table-pagination {
            padding: 12px;
          }
        }
        
        @media (max-width: 480px) {
          .tasks-table-container {
            font-size: 11px;
          }
          
          .table-cell-id {
            min-width: 120px;
          }
          
          .table-cell-progress {
            width: 100px;
          }
          
          .status-tag {
            font-size: 11px;
            padding: 1px 6px;
          }
          
          .task-time {
            font-size: 11px;
          }
          
          .progress-text {
            font-size: 11px;
          }
        }
        .progress-page {
          padding: 20px;
          min-height: 100vh;
          background-color: #f0f2f5;
        }
        
        .main-card {
          border-radius: 8px;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
          overflow: hidden;
        }
        
        .header-section {
          margin-bottom: 16px;
        }
        
        .page-title {
          margin: 0;
          display: flex;
          align-items: center;
        }
        
        .back-button {
          min-width: 100px;
        }
        
        .empty-state {
          padding: 60px 0;
          text-align: center;
        }
        
        .task-section {
          display: flex;
          flex-direction: column;
          gap: 16px;
        }
        
        .task-info-card {
          border: 1px solid #d9d9d9;
          border-radius: 6px;
        }
        
        .task-info-item {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }
        
        .task-info-value {
          font-size: 14px;
          font-weight: 500;
          word-break: break-all;
        }
        
        .status-display {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        
        .status-icon {
          font-size: 16px;
        }
        
        .status-success {
          color: #52c41a;
        }
        
        .status-error {
          color: #ff4d4f;
        }
        
        .status-running {
          color: #1890ff;
        }
        
        .status-pending {
          color: #faad14;
        }
        
        .status-text {
          font-weight: 600;
        }
        
        .refresh-button {
          width: 100%;
        }
        
        .error-card {
          border: 1px solid #ffccc7;
          background-color: #fff2f0;
        }
        
        .error-content {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 16px;
        }
        
        .error-icon {
          font-size: 20px;
          color: #ff4d4f;
        }
        
        .progress-card {
          border: 1px solid #d9d9d9;
          border-radius: 6px;
        }
        
        .stat-item {
          text-align: center;
        }
        
        .progress-bar {
          margin-top: 16px;
        }
        
        .results-card {
          border: 1px solid #d9d9d9;
          border-radius: 6px;
          overflow: hidden;
        }
        
        .runs-table-container {
          width: 100%;
          overflow-x: auto;
        }
        
        .runs-table-header {
          display: flex;
          background-color: #fafafa;
          border-bottom: 1px solid #f0f0f0;
          font-weight: 600;
          color: #333;
          position: sticky;
          top: 0;
          z-index: 1;
        }
        
        .runs-table-body {
          max-height: 500px;
          overflow-y: auto;
        }
        
        .runs-table-row {
          display: flex;
          border-bottom: 1px solid #f0f0f0;
          transition: background-color 0.2s;
        }
        
        .runs-table-row:hover {
          background-color: #f5f5f5;
        }
        
        .runs-table-row:last-child {
          border-bottom: none;
        }
        
        .runs-table-cell {
          padding: 12px 8px;
          display: flex;
          align-items: center;
          overflow: hidden;
          min-width: 0;
        }
        
        .runs-table-cell-id {
          width: 180px;
          font-weight: 500;
        }
        
        .runs-table-cell-params {
          flex: 1;
          min-width: 200px;
          word-break: break-all;
          font-size: 13px;
        }
        
        .runs-table-cell-stats {
          width: 100px;
          text-align: right;
        }
        
        .runs-table-cell-time {
          width: 160px;
          color: #999;
          font-size: 13px;
        }
        
        /* 响应式布局 - 已完成组合表格 */
        @media (max-width: 1200px) {
          .runs-table-cell-stats {
            width: 80px;
          }
          
          .runs-table-cell-id {
            width: 150px;
          }
        }
        
        @media (max-width: 768px) {
          .runs-table-header {
            font-size: 11px;
          }
          
          .runs-table-cell {
            padding: 10px 6px;
            font-size: 12px;
          }
          
          .runs-table-cell-stats {
            width: 70px;
          }
          
          .runs-table-cell-id {
            width: 120px;
          }
          
          .runs-table-cell-time {
            width: 120px;
            font-size: 11px;
          }
        }
        
        @media (max-width: 480px) {
          .runs-table-cell {
            font-size: 11px;
            padding: 8px 4px;
          }
          
          .runs-table-cell-params {
            font-size: 11px;
          }
        }
        
        @media (max-width: 768px) {
          .progress-page {
            padding: 12px;
          }
          
          .back-button {
            width: 100%;
          }
          
          .refresh-button {
            width: 100%;
          }
        }
      `}
      </style>
    </div>
  )
}