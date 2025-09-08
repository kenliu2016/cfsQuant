import { Layout, Menu } from 'antd'
import { Route, Routes, useNavigate } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Market from './pages/Market'
import Strategy from './pages/Strategy'
import Reports from './pages/Reports'
import Tuning from './pages/Tuning'
import Monitor from './pages/Monitor'
import Progress from './pages/Progress'
import Backtest from './pages/Backtest'
const { Header, Sider, Content } = Layout
export default function App(){
  const navigate = useNavigate()
  return (
    <Layout style={{minHeight:'100vh'}}>
      <Sider width={240}>
        <div style={{color:'white',padding:16,fontWeight:700}}>Trading Suite</div>
        <Menu theme='dark' mode='inline' onClick={({key})=>navigate(key)} items={[
          {key:'/dashboard',label:'Dashboard'},
          {key:'/market',label:'Market'},
          {key:'/strategy',label:'Strategy'},
          {key:'/tuning',label:'Tuning'},
          {key:'/monitor',label:'Monitor'},
          {key:'/reports',label:'Reports'},
          {key:'/progress',label:'Progress'}
        ]}/>
      </Sider>
      <Layout>
        <Header style={{background:'#fff',borderBottom:'1px solid #eee'}}/>
        <Content style={{margin:16}}>
          <Routes>
            <Route path='/' element={<Dashboard/>}/>
            <Route path='/dashboard' element={<Dashboard/>}/>
            <Route path='/market' element={<Market/>}/>
            <Route path='/strategy' element={<Strategy/>}/>
            <Route path='/tuning' element={<Tuning/>}/>
            <Route path='/monitor' element={<Monitor/>}/>
            <Route path='/backtest' element={<Backtest/>}/>
            <Route path='/reports' element={<Reports/>}/>
            <Route path='/progress' element={<Progress/>}/>
          </Routes>
        </Content>
      </Layout>
    </Layout>
  )
}
