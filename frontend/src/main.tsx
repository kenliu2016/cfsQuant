import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import 'antd/dist/reset.css'
import { TenantProvider } from './context/TenantContext'
import { AuthProvider } from './context/AuthContext'
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <TenantProvider>
        <AuthProvider>
          <App/>
        </AuthProvider>
      </TenantProvider>
    </BrowserRouter>
  </React.StrictMode>
)
