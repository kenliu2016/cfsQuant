import { Routes, Route } from 'react-router-dom'
import Reports from '../pages/Reports'
import ReportDetail from '../pages/ReportDetail'

const AppRouter = () => {
  return (
    <Routes>
      <Route path="/reports" element={<Reports />} />
      <Route path="/reports/:runId" element={<ReportDetail />} />
      {/* ...other routes... */}
    </Routes>
  )
}

export default AppRouter
